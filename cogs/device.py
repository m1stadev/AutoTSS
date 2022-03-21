from .utils import UtilsCog
from discord.commands import permissions, Option
from discord.ext import commands
from discord.ui import InputText
from utils.device import Device
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
            InputText(label='Device Identifier', placeholder='ex. iPhone10,6'),
            InputText(
                label='ECID (hex)',
                placeholder='ex. abcdef0123456',
            ),
            InputText(
                label='Board config (Optional, required on A9)',
                placeholder='ex. d221ap',
                required=False,
            ),
            InputText(
                label='Nonce generator (Optional, required on A12+)',
                placeholder='ex. 0xabcdef0123456789',
                required=False,
            ),
            InputText(
                label='ApNonce (Optional, required on A12+)',
                placeholder='ex. abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
                required=False,
            ),
        )

        await ctx.interaction.response.send_modal(modal)
        await modal.wait()

        device = await Device().init(
            name=name,
            identifier=modal.answers[0]
            .lower()
            .replace(' ', '')
            .replace('devicestring:', ''),
            ecid=modal.answers[1],
            boardconfig=modal.answers[2]
            .lower()
            .replace(' ', '')
            .replace('deviceid:', '')
            if modal.answers[2] is not None
            else None,
            generator=modal.answers[3],
            apnonce=modal.answers[4],
        )

        if 0x8020 <= device.cpid < 0x8900:
            if device.generator is None:
                raise commands.BadArgument(
                    'A nonce generator is required for saving SHSH blobs on A12+ devices. An explanation on why can be found [here](https://gist.github.com/5464ea557c2b999cb9324639c777cd09#whats-nonce-entanglement).'
                )

            if device.apnonce is None:
                raise commands.BadArgument(
                    'An ApNonce is required for saving SHSH blobs on A12+ devices. An explanation on why can be found [here](https://gist.github.com/5464ea557c2b999cb9324639c777cd09#whats-nonce-entanglement).'
                )

        if device.apnonce and device.generator:
            buttons = [
                {'label': 'Yes', 'style': discord.ButtonStyle.primary},
                {'label': 'No', 'style': discord.ButtonStyle.secondary},
                {'label': 'Cancel', 'style': discord.ButtonStyle.danger},
            ]
            embed.description = f"Nonce generator: `{device.generator}`\nApNonce: `{device.apnonce}`\n\nAre you **absolutely sure** this is a valid generator-ApNonce pair for your device?"

            view = SelectView(buttons, ctx)
            await ctx.edit(embed=embed, view=view)
            await view.wait()

            if view.answer is None:
                raise ViewTimeoutException(view.timeout)
            elif view.answer == 'Cancel':
                raise StopCommand()

            if 0x8020 <= device.cpid < 0x8900:
                if view.answer == 'No':
                    raise commands.BadArgument(
                        'Invalid generator-ApNonce pair provided. Guides for a getting a valid generator-ApNonce pair on A12+ devices can be found below:\n\n[Getting a generator-Apnonce pair (jailbroken)[https://gist.github.com/5464ea557c2b999cb9324639c777cd09#getting-a-generator-apnonce-pair-jailbroken]\n\n[Getting a generator-Apnonce pair (no jailbreak)[https://gist.github.com/5464ea557c2b999cb9324639c777cd09#getting-a-generator-apnonce-pair-non-jailbroken]'
                    )
            else:
                await device.verify_apnonce_pair()

        # Add device to the database
        await device.add(ctx.author)

        embed = discord.Embed(
            title='Add Device',
            description=f'Device `{device.name}` added successfully!',
        )
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )
        await ctx.edit(embed=embed)

        self.bot.logger.info(
            f'User: {ctx.author.mention} (`@{ctx.author}`) has added device: `{device.name}`'
        )

        await self.utils.update_device_count()

    @device.command(name='remove', description='Remove a device from AutoTSS.')
    async def remove_device(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)

        async with self.bot.db.execute(
            'SELECT devices FROM autotss WHERE user = ?', (ctx.author.id,)
        ) as cursor:
            try:
                devices = [
                    await Device().init(**d)
                    for d in ujson.loads((await cursor.fetchone())[0])
                ]
            except TypeError:
                devices = list()

        if len(devices) == 0:
            raise NoDevicesFound(ctx.author)

        buttons = [
            {'label': 'Confirm', 'style': discord.ButtonStyle.danger},
            {'label': 'Cancel', 'style': discord.ButtonStyle.secondary},
        ]

        view = SelectView(buttons, ctx)
        if len(devices) > 1:
            device_options = [
                discord.SelectOption(
                    label=device.name,
                    description=f"ECID: {device.ecid} | SHSH blob{'s' if len(device.blobs) != 1 else ''} saved: {len(device.blobs)}",
                    emoji='📱',
                )
                for device in devices
            ]

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
                raise StopCommand()

            device = next(
                device for device in devices if device.name == dropdown.answer
            )
            embed.description = (
                f'Are you **absolutely sure** you want to remove `{device.name}`?'
            )
            await ctx.edit(embed=embed, view=view)

        else:
            device = devices[0]
            embed.description = (
                f'Are you **absolutely sure** you want to remove `{device.name}`?'
            )
            await ctx.respond(embed=embed, view=view)

        await view.wait()

        if view.answer is None:
            raise ViewTimeoutException(view.timeout)

        elif view.answer == 'Cancel':
            raise StopCommand()

        embed.description = 'Removing device...'
        await ctx.edit(embed=embed)

        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
            url = await self.utils.backup_blobs(aiopath.AsyncPath(tmpdir), device.ecid)

        if url is not None:
            await asyncio.to_thread(
                shutil.rmtree,
                aiopath.AsyncPath(f"Data/Blobs/{device.ecid}"),
            )

            buttons = [
                {'label': 'Download', 'style': discord.ButtonStyle.link, 'url': url}
            ]

            view = SelectView(buttons, ctx, timeout=None)
            embed.description = f"Device `{device.name}` removed.\nSHSH Blobs:"
            await ctx.edit(embed=embed, view=view)

        else:
            embed.description = f"Device `{device.name}` removed."
            await ctx.edit(embed=embed)

        self.bot.logger.info(
            f"User: {ctx.author.mention} (`@{ctx.author}`) has removed device: `{device.name}`"
        )

        await device.remove()
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
            'SELECT devices FROM autotss WHERE user = ?', (user.id,)
        ) as cursor:
            try:
                devices = [
                    await Device().init(**d)
                    for d in ujson.loads((await cursor.fetchone())[0])
                ]
            except TypeError:
                devices = list()

        if len(devices) == 0:
            raise NoDevicesFound(user)

        device_embeds = list()
        for device in devices:
            num_blobs = ','.join(
                textwrap.wrap(
                    str(await asyncio.to_thread(self.utils.shsh_count, device.ecid))[
                        ::-1
                    ],
                    3,
                )
            )[::-1]
            device_embed = {
                'title': f"*{device.name}*{f'  ({devices.index(device) + 1}/{len(devices)})' if len(devices) > 1 else ''}",
                'description': f"**{num_blobs}** SHSH blob{'s' if num_blobs != 1 else ''} saved",
                'fields': [
                    {
                        'name': 'Device Identifier',
                        'value': f'`{device.identifier}`',
                        'inline': False,
                    },
                    {
                        'name': 'ECID',
                        'value': f'`{device.ecid if user == ctx.author else device.censored_ecid}`',
                        'inline': False,
                    },
                    {
                        'name': 'Board Config',
                        'value': f'`{device.board}`',
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

            if device.generator is not None:
                device_embed['fields'].append(
                    {
                        'name': 'Nonce Generator',
                        'value': f'`{device.generator}`',
                        'inline': False,
                    }
                )

            if device.apnonce is not None:
                device_embed['fields'].append(
                    {
                        'name': 'ApNonce',
                        'value': f'`{device.apnonce}`',
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
        await ctx.defer()

        if (
            self.utils.saving_blobs == True
        ):  # Avoid any potential conflict with transferring devices while blobs are being saved
            raise SavingSHSHError()

        if old == new:
            raise commands.BadArgument(
                'You cannot transfer devices between the same user.'
            )

        if new.bot == True:
            raise commands.BadArgument('You cannot transfer devices to a bot account.')

        async with self.bot.db.execute(
            'SELECT devices FROM autotss WHERE user = ?', (old.id,)
        ) as cursor:
            try:
                old_devices = ujson.loads((await cursor.fetchone())[0])
            except TypeError:
                old_devices = list()

        async with self.bot.db.execute(
            'SELECT devices FROM autotss WHERE user = ?', (new.id,)
        ) as cursor:
            try:
                new_devices = ujson.loads((await cursor.fetchone())[0])
            except TypeError:
                new_devices = list()

        if len(old_devices) == 0:
            raise NoDevicesFound(old)

        if len(new_devices) > 0:
            raise commands.BadArgument(
                f'{new.mention} currently has devices added to AutoTSS.'  # TODO: Combine devices
            )

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
            raise ViewTimeoutException(view.timeout)

        if view.answer == 'Cancel':
            raise StopCommand()

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
