from .errors import (
    StopCommand,
    NoDevicesFound,
    TooManyDevices,
    ViewTimeoutException,
)
from discord.errors import NotFound, Forbidden
from discord.ext import commands
from discord import Option
from views.buttons import SelectView, PaginatorView
from views.selects import DropdownView

import aiofiles
import aiopath
import asyncio
import discord
import ujson
import shutil

MAX_DEVICES = 10  # TODO: Export this option to a separate config file


class DeviceCog(commands.Cog, name='Device'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.utils = self.bot.get_cog('Utilities')

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
    async def add_device(self, ctx: discord.ApplicationContext) -> None:
        async with self.bot.db.execute(
            'SELECT devices from autotss WHERE user = ?', (ctx.author.id,)
        ) as cursor:
            try:
                devices = ujson.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if (len(devices) >= MAX_DEVICES) and (
            await self.bot.is_owner(ctx.author) == False
        ):  # Error out if you attempt to add over 'max_devices' devices, and if you're not the owner of the bot
            raise TooManyDevices(MAX_DEVICES)

        device = dict()
        embed = discord.Embed(title='Add Device')
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )
        for x in range(
            4
        ):  # Loop that gets all of the required information to save blobs with from the user
            descriptions = (
                'Enter a name for your device.',
                "Enter your device's identifier. This can be found with [AIDA64](https://apps.apple.com/app/apple-store/id979579523) under the `Device` section (as `Device String`).",
                f"Enter your device's ECID (hex).\n\n*If you'd like to keep your ECID private, you can DM your ECID to {self.bot.user.mention}.*",
                "Enter your device's Board Config. This value ends in `ap`, and can be found with [AIDA64](https://apps.apple.com/app/apple-store/id979579523) under the `Device` section (as `Device Id`), [System Info](https://arx8x.github.io/depictions/systeminfo.html) under the `Platform` section, or by running `gssc | grep HWModelStr` in a terminal on your iOS device.",
            )

            embed.description = '\n'.join((descriptions[x], 'Type `cancel` to cancel.'))

            if (x == 3) and (
                'boardconfig' in device.keys()
            ):  # If we got boardconfig from API, no need to get it from user
                continue

            # TODO: Figure out how I'll have a cancel button through this loop
            if x == 0:
                await ctx.respond(embed=embed, ephemeral=True)
            else:
                await ctx.edit(embed=embed)

            # Wait for a response from the user, and error out if the user takes over 5 minutes to respond
            try:
                response = await self.bot.wait_for(
                    'message',
                    check=lambda message: message.author == ctx.author
                    and (
                        message.channel == ctx.channel
                        or message.channel.type == discord.ChannelType.private
                    ),
                    timeout=300,
                )
                if x == 0:
                    answer = response.content  # Don't make the device's name lowercase
                else:
                    answer = response.content.lower()

            except asyncio.exceptions.TimeoutError as e:
                raise ViewTimeoutException(300) from e

            # Delete the message
            try:
                await response.delete()
            except NotFound:
                pass
            except Forbidden as e:
                if x != 2:
                    raise e

            answer = discord.utils.remove_markdown(answer)
            if answer.lower().startswith('cancel'):
                raise StopCommand()

            # Make sure given information is valid
            if x == 0:
                device['name'] = answer
                name_check = await self.utils.check_name(device['name'], ctx.author.id)
                if name_check != True:
                    if name_check == 0:
                        raise commands.BadArgument(
                            "A device's name cannot be over 20 characters long."
                        )
                    elif name_check == -1:
                        raise commands.BadArgument(
                            "You cannot use a device's name more than once."
                        )

            elif x == 1:
                device['identifier'] = answer.replace(' ', '').replace(
                    'devicestring:', ''
                )
                if 'appletv' in device['identifier']:
                    device['identifier'] = 'TV'.join(
                        device['identifier'].capitalize().split('tv')
                    )
                else:
                    device['identifier'] = 'P'.join(device['identifier'].split('p'))

                if await self.utils.check_identifier(device['identifier']) is False:
                    raise commands.BadArgument('Invalid device identifier provided.')

                # If there's only one board for the device, grab the boardconfig now
                api = await self.utils.fetch_ipswme_api(device['identifier'])
                valid_boards = [
                    board
                    for board in api['boards']
                    if board['boardconfig'].lower().endswith('ap')
                ]
                if len(valid_boards) == 1:  # Exclude development boards that may pop up
                    device['boardconfig'] = valid_boards[0]['boardconfig'].lower()

            elif x == 2:
                device['ecid'] = answer[2:] if answer.startswith('0x') else answer
                ecid_check = await self.utils.check_ecid(device['ecid'])
                if ecid_check != True:
                    error = 'Invalid device ECID provided.'
                    if ecid_check == -1:
                        error += ' This ECID has already been added to AutoTSS.'
                    raise commands.BadArgument(error)

            elif x == 3:
                device['boardconfig'] = answer.replace(' ', '').replace('deviceid:', '')
                if (
                    await self.utils.check_boardconfig(
                        device['identifier'], device['boardconfig']
                    )
                    is False
                ):
                    raise commands.BadArgument('Invalid device boardconfig provided.')

        generator_description = [
            'Would you like to save SHSH blobs with a custom generator?',
            'This value begins with `0x` and is followed by 16 hexadecimal characters.',
        ]

        cpid = await self.utils.get_cpid(device['identifier'], device['boardconfig'])
        if 0x8020 <= cpid < 0x8900:
            generator_description.append(
                '\n*If you choose to, you **will** need to provide a matching ApNonce for SHSH blobs to be saved correctly.*'
            )
            generator_description.append(
                '*Guide for jailbroken A12+ devices: [Click here](https://gist.github.com/m1stadev/5464ea557c2b999cb9324639c777cd09#getting-a-generator-apnonce-pair-jailbroken)*'
            )
            generator_description.append(
                '*Guide for non-jailbroken A12+ devices: [Click here](https://gist.github.com/m1stadev/5464ea557c2b999cb9324639c777cd09#getting-a-generator-apnonce-pair-non-jailbroken)*'
            )

        embed = discord.Embed(
            title='Add Device', description='\n'.join(generator_description)
        )  # Ask the user if they'd like to save blobs with a custom generator
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )

        buttons = [
            {'label': 'Yes', 'style': discord.ButtonStyle.primary},
            {'label': 'No', 'style': discord.ButtonStyle.secondary},
            {'label': 'Cancel', 'style': discord.ButtonStyle.danger},
        ]

        view = SelectView(buttons, ctx)
        await ctx.edit(embed=embed, view=view)
        await view.wait()
        if view.answer is None:
            raise ViewTimeoutException(view.timeout)

        if view.answer == 'Yes':
            embed = discord.Embed(
                title='Add Device',
                description='Please enter the custom generator you wish to save SHSH blobs with.\nType `cancel` to cancel.',
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )
            await ctx.edit(embed=embed)

            try:
                response = await self.bot.wait_for(
                    'message',
                    check=lambda message: message.author == ctx.author,
                    timeout=300,
                )
                answer = discord.utils.remove_markdown(response.content).lower()
            except asyncio.exceptions.TimeoutError:
                raise ViewTimeoutException(300)

            try:
                await response.delete()
            except discord.errors.NotFound:
                pass

            if answer.startswith('cancel'):
                raise StopCommand()
            else:
                device['generator'] = answer
                if self.utils.check_generator(device['generator']) is False:
                    raise commands.BadArgument('Invalid nonce generator provided.')

        elif view.answer == 'No':
            device['generator'] = None

        elif view.answer == 'Cancel':
            raise StopCommand()

        apnonce_description = [
            'Would you like to save SHSH blobs with a custom ApNonce?',
            f'This value is hexadecimal and {40 if 0x8010 <= cpid < 0x8900 else 64} characters long.',
            'This is **NOT** the same as your **generator**, which begins with `0x` and is followed by 16 hexadecimal characters.',
        ]

        if 0x8020 <= cpid < 0x8900:
            apnonce_description.append(
                '\n*You must save blobs with an ApNonce, or else your SHSH blobs **will not work**. More info [here](https://www.reddit.com/r/jailbreak/comments/f5wm6l/tutorial_repost_easiest_way_to_save_a12_blobs/).*'
            )

        embed = discord.Embed(
            title='Add Device', description='\n'.join(apnonce_description)
        )  # Ask the user if they'd like to save blobs with a custom ApNonce
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )

        buttons = [
            {'label': 'Yes', 'style': discord.ButtonStyle.primary},
            {
                'label': 'No',
                'style': discord.ButtonStyle.secondary,
                'disabled': 0x8020
                <= cpid
                < 0x8900,  # Don't allow A12+ users to save blobs without an ApNonce
            },
            {'label': 'Cancel', 'style': discord.ButtonStyle.danger},
        ]

        view = SelectView(buttons, ctx)
        await ctx.edit(embed=embed, view=view)
        await view.wait()
        if view.answer is None:
            raise ViewTimeoutException(view.timeout)

        if view.answer == 'Yes':
            embed = discord.Embed(
                title='Add Device',
                description='Please enter the custom ApNonce you wish to save SHSH blobs with.\nType `cancel` to cancel.',
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )
            await ctx.edit(embed=embed)

            try:
                response = await self.bot.wait_for(
                    'message',
                    check=lambda message: message.author == ctx.author,
                    timeout=300,
                )
                answer = discord.utils.remove_markdown(response.content.lower())
            except asyncio.exceptions.TimeoutError:
                raise ViewTimeoutException(300)

            try:
                await response.delete()
            except discord.errors.NotFound:
                pass

            if answer.startswith('cancel'):
                raise StopCommand()
            else:
                device['apnonce'] = answer
                if self.utils.check_apnonce(cpid, device['apnonce']) is False:
                    raise commands.BadArgument('Invalid device ApNonce provided.')

        elif view.answer == 'No':
            device['apnonce'] = None

        elif view.answer == 'Cancel':
            raise StopCommand()

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
            raise NoDevicesFound()

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
                raise StopCommand()

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

        if view.answer == 'Confirm':
            embed = discord.Embed(
                title='Remove Device', description='Removing device...'
            )
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

            await ctx.edit(embed=embed)
            await self.utils.update_device_count()

        elif view.answer == 'Cancel':
            raise StopCommand()

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
            num_blobs = len(device['saved_blobs'])
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
                        'name': 'Custom Generator',
                        'value': f"`{device['generator']}`",
                        'inline': False,
                    }
                )

            if device['apnonce'] is not None:
                device_embed['fields'].append(
                    {
                        'name': 'Custom ApNonce',
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


def setup(bot: commands.Bot):
    bot.add_cog(DeviceCog(bot))
