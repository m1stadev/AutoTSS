from .botutils import UtilsCog
from discord.commands import permissions, Option
from discord.ext import commands
from discord.ui import InputText
from utils.errors import *
from utils.views.buttons import SelectView, PaginatorView
from utils.views.modals import QuestionModal
from utils.views.selects import DropdownView

import aiofiles
import aiopath
import asyncio
import discord
import ujson
import shutil
import textwrap


class DeviceCog(commands.Cog, name='Device'):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.utils: UtilsCog = self.bot.get_cog('Utilities')

    device = discord.SlashCommandGroup('devices', 'Device commands')

    @device.command(name='help', description='View all device commands.')
    async def _help(self, ctx: discord.ApplicationContext) -> None:
        cmd_embeds = [
            self.utils.cmd_help_embed(ctx, sc) for sc in self.device.subcommands
        ]

        paginator = PaginatorView(cmd_embeds, ctx, timeout=180)
        await ctx.respond(
            embed=cmd_embeds[paginator.embed_num], view=paginator, ephemeral=True
        )

    @device.command(name='add', description='Add a device to AutoTSS.')
    async def add_device(
        self,
        ctx: discord.ApplicationContext,
        name: Option(str, description='Name for device'),
    ) -> None:
        async with self.bot.db.execute(
            'SELECT devices from autotss WHERE user = ?', (ctx.author.id,)
        ) as cursor:
            try:
                devices = ujson.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if (len(devices) >= self.bot.max_devices) and (
            await self.bot.is_owner(ctx.author) == False
        ):  # Error out if you attempt to add more devices than allowed and if you're not the owner of the bot
            raise TooManyDevices(self.bot.max_devices)

        embed = discord.Embed(
            title='Add Device', description='Verifying device information...'
        )
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )

        modal = QuestionModal(
            ctx,
            'Add Device',
            embed,
            InputText(
                label="Device board config (Optional, required on A9)", placeholder='ex. d221ap', required=False
            ),
            InputText(
                label="Device ECID (hex)",
                placeholder='ex. abcdef0123456789',
            ),
            InputText(label="Device Board Config", placeholder='ex. d221ap'),
            InputText(
                label="Nonce Generator (Optional, required on A12+)",
                placeholder='ex. 0x1111111111111111',
                required=False,
            ),
            InputText(
                label="ApNonce (Optional, required on A12+)",
                placeholder='ex. abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
                required=False,
            ),
        )

        await ctx.interaction.response.send_modal(modal)
        await modal.wait()

        device = dict()

        name_check = await self.utils.check_name(name, ctx.author.id)
        if name_check == -1:
            raise commands.BadArgument(
                "A device's name cannot be over 20 characters long."
            )
        elif name_check == -2:
            raise commands.BadArgument(
                "You cannot use the same name for multiple devices."
            )
        device['name'] = name

        identifier = (
            modal.answers[0].replace(' ', '').lower().replace('devicestring:', '')
        )
        if 'appletv' in identifier:
            identifier = 'TV'.join(identifier.capitalize().split('tv'))
        else:
            identifier = 'P'.join(identifier.split('p'))

        if await self.utils.check_identifier(identifier) is False:
            raise commands.BadArgument('Invalid device identifier provided.')
        device['identifier'] = identifier

        ecid = modal.answers[1].lower().removeprefix('0x')
        ecid_check = await self.utils.check_ecid(ecid)
        if ecid_check < 0:
            error = 'Invalid device ECID provided.'
            if ecid_check == -2:
                error += ' This ECID has already been added to AutoTSS.'

            raise commands.BadArgument(error)
        device['ecid'] = ecid

        boardconfig = modal.answers[2].replace(' ', '').lower().replace('deviceid:', '')
        if (
            await self.utils.check_boardconfig(device['identifier'], boardconfig)
            is False
        ):
            raise commands.BadArgument('Invalid device boardconfig provided.')
        device['boardconfig'] = boardconfig

        if len(modal.answers[3]) > 0:
            generator = modal.answers[3].lower()
            if self.utils.check_generator(generator) is False:
                raise commands.BadArgument('Invalid nonce generator provided.')
            device['generator'] = generator
        else:
            device['generator'] = None

        cpid = await self.utils.get_cpid(device['identifier'], device['boardconfig'])
        if len(modal.answers[4]) > 0:
            apnonce = modal.answers[4].lower()
            if self.utils.check_apnonce(cpid, apnonce) is False:
                raise commands.BadArgument('Invalid ApNonce provided.')
            device['apnonce'] = apnonce
        else:
            device['apnonce'] = None

        if 0x8020 <= cpid < 0x8900:
            if device['generator'] is None:
                raise commands.BadArgument(
                    'A nonce generator is required for saving SHSH blobs on A12+ devices. An explanation on why can be found [here](https://gist.github.com/5464ea557c2b999cb9324639c777cd09#whats-nonce-entanglement).'
                )

            if device['apnonce'] is None:
                raise commands.BadArgument(
                    'An ApNonce is required for saving SHSH blobs on A12+ devices. An explanation on why can be found [here](https://gist.github.com/5464ea557c2b999cb9324639c777cd09#whats-nonce-entanglement).'
                )

        if device['apnonce'] and device['generator']:
            buttons = [
                {'label': 'Yes', 'style': discord.ButtonStyle.primary},
                {'label': 'No', 'style': discord.ButtonStyle.secondary},
                {'label': 'Cancel', 'style': discord.ButtonStyle.danger},
            ]
            embed.description = f"Nonce generator: `{device['generator']}`\nApNonce: `{device['apnonce']}`\n\nAre you **absolutely sure** this is a valid generator-ApNonce pair for your device?"

            view = SelectView(buttons, ctx)
            await ctx.edit(embed=embed, view=view)
            await view.wait()

            if view.answer is None:
                raise ViewTimeoutException(view.timeout)
            elif view.answer == 'Cancel':
                raise StopCommand

            if (
                not 0x8020
                <= cpid
                < 0x8900  # Verify generator-apnonce pair on A11 and below
                and await asyncio.to_thread(
                    self.utils.check_apnonce_pair,
                    device['generator'],
                    device['apnonce'],
                )
                == False
            ) or view.answer == 'No':
                error = 'Invalid generator-ApNonce pair provided.'
                if 0x8020 <= cpid < 0x8900:
                    error += ' Guides for a getting a valid generator-ApNonce pair on A12+ devices can be found below:\n\n[Getting a generator-Apnonce pair (jailbroken)[https://gist.github.com/5464ea557c2b999cb9324639c777cd09#getting-a-generator-apnonce-pair-jailbroken]\n\n[Getting a generator-Apnonce pair (no jailbreak)[https://gist.github.com/5464ea557c2b999cb9324639c777cd09#getting-a-generator-apnonce-pair-non-jailbroken]'

                raise commands.BadArgument(error)

        device['saved_blobs'] = list()

        # Add device information into the database
        devices.append(device)

        async with self.bot.db.execute(
            'SELECT devices FROM autotss WHERE user = ?', (ctx.author.id,)
        ) as cursor:
            if await cursor.fetchone() is None:
                sql = 'INSERT INTO autotss(devices, enabled, user) VALUES(?,?,?)'
            else:
                sql = 'UPDATE autotss SET devices = ?, enabled = ? WHERE user = ?'

        await self.bot.db.execute(sql, (ujson.dumps(devices), True, ctx.author.id))
        await self.bot.db.commit()

        embed = discord.Embed(
            title='Add Device',
            description=f"Device `{device['name']}` added successfully!",
        )
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )
        await ctx.edit(embed=embed)

        self.bot.logger.info(
            f"User: {ctx.author.mention} (`@{ctx.author}`) has added device: `{device['name']}`"
        )

        await self.utils.update_device_count()

    @device.command(name='remove', description='Remove a device from AutoTSS.')
    async def remove_device(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)

        async with self.bot.db.execute(
            'SELECT devices from autotss WHERE user = ?', (ctx.author.id,)
        ) as cursor:
            try:
                devices = ujson.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if len(devices) == 0:
            raise NoDevicesFound(ctx.author)

        confirm_embed = discord.Embed(title='Remove Device')
        confirm_embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )

        buttons = [
            {'label': 'Confirm', 'style': discord.ButtonStyle.danger},
            {'label': 'Cancel', 'style': discord.ButtonStyle.secondary},
        ]

        view = SelectView(buttons, ctx)
        if len(devices) > 1:
            device_options = list()
            for device in devices:
                device_options.append(
                    discord.SelectOption(
                        label=device['name'],
                        description=f"ECID: {device['ecid']} | SHSH blob{'s' if len(device['saved_blobs']) != 1 else ''} saved: {len(device['saved_blobs'])}",
                        emoji='📱',
                    )
                )

            device_options.append(discord.SelectOption(label='Cancel', emoji='❌'))

            embed = discord.Embed(
                title='Remove Device',
                description="Please select the device you'd like to remove.",
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )

            dropdown = DropdownView(device_options, ctx, 'Device to remove...')
            await ctx.respond(embed=embed, view=dropdown)
            await dropdown.wait()
            if dropdown.answer is None:
                raise ViewTimeoutException(dropdown.timeout)

            if dropdown.answer == 'Cancel':
                raise StopCommand

            num = next(
                devices.index(x) for x in devices if x['name'] == dropdown.answer
            )
            confirm_embed.description = f"Are you **absolutely sure** you want to delete `{devices[num]['name']}`?"
            await ctx.edit(embed=confirm_embed, view=view)

        else:
            num = 0
            confirm_embed.description = f"Are you **absolutely sure** you want to delete `{devices[num]['name']}`?"
            await ctx.respond(embed=confirm_embed, view=view)

        await view.wait()
        if view.answer is None:
            raise ViewTimeoutException(view.timeout)
        elif view.answer == 'Cancel':
            raise StopCommand

        embed = discord.Embed(title='Remove Device', description='Removing device...')
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )
        await ctx.edit(embed=embed)

        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
            url = await self.utils.backup_blobs(
                aiopath.AsyncPath(tmpdir), devices[num]['ecid']
            )

        if url is not None:
            await asyncio.to_thread(
                shutil.rmtree,
                aiopath.AsyncPath(f"Data/Blobs/{devices[num]['ecid']}"),
            )

            buttons = [
                {'label': 'Download', 'style': discord.ButtonStyle.link, 'url': url}
            ]

            view = SelectView(buttons, ctx, timeout=None)
            embed = discord.Embed(
                title='Remove Device',
                description=f"Device `{devices[num]['name']}` removed.\nSHSH Blobs:",
            )
            await ctx.edit(embed=embed, view=view)

        else:
            embed = discord.Embed(
                title='Remove Device',
                description=f"Device `{devices[num]['name']}` removed.",
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )
            await ctx.edit(embed=embed)

        self.bot.logger.info(
            f"User: {ctx.author.mention} (`@{ctx.author}`) has removed device: `{devices[num]['name']}`"
        )

        devices.pop(num)

        if len(devices) == 0:
            await self.bot.db.execute(
                'DELETE FROM autotss WHERE user = ?', (ctx.author.id,)
            )
        else:
            await self.bot.db.execute(
                'UPDATE autotss SET devices = ? WHERE user = ?',
                (ujson.dumps(devices), ctx.author.id),
            )

        await self.bot.db.commit()

        await self.utils.update_device_count()

    @device.command(name='list', description='List your added devices.')
    async def list_devices(
        self,
        ctx: discord.ApplicationContext,
        user: Option(
            commands.UserConverter,
            description='User to list SHSH blobs for',
            required=False,
        ),
    ) -> None:
        await ctx.defer(ephemeral=True)

        if user is None:
            user = ctx.author

        async with self.bot.db.execute(
            'SELECT devices from autotss WHERE user = ?', (user.id,)
        ) as cursor:
            try:
                devices = ujson.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if len(devices) == 0:
            raise NoDevicesFound(user)

        device_embeds = list()
        for device in devices:
            num_blobs = ','.join(
                textwrap.wrap(
                    str(await asyncio.to_thread(self.utils.shsh_count, device['ecid']))[
                        ::-1
                    ],
                    3,
                )
            )[::-1]
            device_embed = {
                'title': f"*{device['name']}*{f'  ({devices.index(device) + 1}/{len(devices)})' if len(devices) > 1 else ''}",
                'description': f"**{num_blobs}** SHSH blob{'s' if num_blobs != 1 else ''} saved",
                'fields': [
                    {
                        'name': 'Device Identifier',
                        'value': f"`{device['identifier']}`",
                        'inline': False,
                    },
                    {
                        'name': 'ECID',
                        'value': f"`{device['ecid'] if user == ctx.author else self.utils.censor_ecid(device['ecid'])}`",
                        'inline': False,
                    },
                    {
                        'name': 'Board Config',
                        'value': f"`{device['boardconfig']}`",
                        'inline': False,
                    },
                ],
                'footer': {
                    'text': ctx.author.display_name,
                    'icon_url': str(
                        ctx.author.display_avatar.with_static_format('png').url
                    ),
                },
            }

            if device['generator'] is not None:
                device_embed['fields'].append(
                    {
                        'name': 'Nonce Generator',
                        'value': f"`{device['generator']}`",
                        'inline': False,
                    }
                )

            if device['apnonce'] is not None:
                device_embed['fields'].append(
                    {
                        'name': 'ApNonce',
                        'value': f"`{device['apnonce']}`",
                        'inline': False,
                    }
                )

            device_embeds.append(discord.Embed.from_dict(device_embed))

        if len(device_embeds) == 1:
            await ctx.respond(embed=device_embeds[0], ephemeral=True)
            return

        paginator = PaginatorView(device_embeds, ctx)
        await ctx.respond(
            embed=device_embeds[paginator.embed_num], view=paginator, ephemeral=True
        )

    @permissions.is_owner()
    @device.command(
        name='transfer', description="Transfer a user's devices to another user."
    )
    async def transfer_devices(
        self,
        ctx: discord.ApplicationContext,
        old: Option(int, description='ID of user to transfer devices from'),
        new: Option(commands.UserConverter, description='User to transfer devices to'),
    ) -> None:
        cancelled_embed = discord.Embed(
            title='Transfer Devices', description='Cancelled.'
        )
        invalid_embed = discord.Embed(title='Error')
        timeout_embed = discord.Embed(
            title='Transfer Devices',
            description='No response given in 1 minute, cancelling.',
        )

        for x in (cancelled_embed, invalid_embed, timeout_embed):
            x.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )

        await ctx.defer()

        if (
            self.utils.saving_blobs == True
        ):  # Avoid any potential conflict with transferring devices while blobs are being saved
            invalid_embed.description = "I'm currently automatically saving SHSH blobs, please wait until I'm finished to transfer devices."
            await ctx.respond(embed=invalid_embed)
            return

        if old == new:
            invalid_embed.description = (
                "Silly goose, you can't transfer devices between the same user!"
            )
            await ctx.respond(embed=invalid_embed)
            return

        if new.bot == True:
            invalid_embed.description = 'You cannot transfer devices to a bot account.'
            await ctx.respond(embed=invalid_embed)
            return

        async with self.bot.db.execute(
            'SELECT devices from autotss WHERE user = ?', (old.id,)
        ) as cursor:
            try:
                old_devices = ujson.loads((await cursor.fetchone())[0])
            except TypeError:
                old_devices = list()

        async with self.bot.db.execute(
            'SELECT devices from autotss WHERE user = ?', (new.id,)
        ) as cursor:
            try:
                new_devices = ujson.loads((await cursor.fetchone())[0])
            except TypeError:
                new_devices = list()

        if len(old_devices) == 0:
            invalid_embed.description = (
                f'{old.mention} has no devices added to AutoTSS.'
            )
            await ctx.respond(embed=invalid_embed)
            return

        if len(new_devices) > 0:
            invalid_embed.description = (
                f'{new.mention} has devices added to AutoTSS already.'
            )
            await ctx.respond(embed=invalid_embed)
            return

        embed = discord.Embed(title='Transfer Devices')
        embed.description = f"Are you sure you'd like to transfer {old.mention}'s **{len(old_devices)} device{'s' if len(old_devices) != 1 else ''}** to {new.mention}?"
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )

        buttons = [
            {'label': 'Yes', 'style': discord.ButtonStyle.success},
            {'label': 'Cancel', 'style': discord.ButtonStyle.danger},
        ]

        view = SelectView(buttons, ctx)
        await ctx.respond(embed=embed, view=view)
        await view.wait()
        if view.answer is None:
            await ctx.edit(embed=timeout_embed)
            return

        if view.answer == 'Cancel':
            await ctx.edit(embed=cancelled_embed)
            return

        await self.bot.db.execute(
            'UPDATE autotss SET user = ? WHERE user = ?', (new.id, old.id)
        )
        await self.bot.db.commit()

        embed.description = f"Successfully transferred {old.mention}'s **{len(old_devices)} device{'s' if len(old_devices) != 1 else ''}** to {new.mention}."
        await ctx.edit(embed=embed)

        self.bot.logger.info(
            f"{old.mention}'s devices have been transferred to {new.mention}."
        )


def setup(bot: discord.Bot):
    bot.add_cog(DeviceCog(bot))
