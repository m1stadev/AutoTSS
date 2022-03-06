from .botutils import UtilsCog
from discord.commands import permissions, Option
from discord.ext import commands
from utils.errors import *
from views.buttons import SelectView, PaginatorView
from views.selects import DropdownView

import aiofiles
import aiopath
import asyncio
import discord
import ujson
import time


class TSSCog(commands.Cog, name='TSS'):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.utils: UtilsCog = self.bot.get_cog('Utilities')

    tss = discord.SlashCommandGroup('tss', 'TSS commands')

    @tss.command(name='help', description='View all TSS commands.')
    async def _help(self, ctx: discord.ApplicationContext) -> None:
        cmd_embeds = [self.utils.cmd_help_embed(ctx, sc) for sc in self.tss.subcommands]

        paginator = PaginatorView(cmd_embeds, ctx, timeout=180)
        await ctx.respond(
            embed=cmd_embeds[paginator.embed_num], view=paginator, ephemeral=True
        )

    @tss.command(name='download', description='Download your saved SHSH blobs.')
    async def download_blobs(
        self,
        ctx: discord.ApplicationContext,
        user: Option(
            commands.UserConverter,
            description='User to download SHSH blobs for',
            required=False,
        ),
    ) -> None:
        if user is None:
            user = ctx.author
        elif (user != ctx.author) and (await ctx.bot.is_owner(ctx.author) == False):
            raise commands.NotOwner()

        async with self.bot.db.execute(
            'SELECT devices from autotss WHERE user = ?', (user.id,)
        ) as cursor:
            try:
                devices = ujson.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if len(devices) == 0:
            raise NoDevicesFound(user)

        total_blobs = sum([len(device['saved_blobs']) for device in devices])
        if total_blobs == 0:
            raise NoSHSHFound(user)

        upload_embed = discord.Embed(
            title='Download Blobs', description='Uploading SHSH blobs...'
        )
        upload_embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )

        if len(devices) > 1:
            device_options = [
                discord.SelectOption(
                    label='All',
                    description=f"Devices: {len(devices)} | Total SHSH blob{'s' if total_blobs != 1 else ''} saved: {total_blobs}",
                    emoji='📱',
                )
            ]

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
                title='Download Blobs',
                description="Choose which device you'd like to download SHSH blobs for",
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )

            dropdown = DropdownView(device_options, ctx, 'Device')
            await ctx.respond(embed=embed, view=dropdown, ephemeral=True)

            await dropdown.wait()
            if dropdown.answer is None:
                raise ViewTimeoutException(dropdown.timeout)
            elif dropdown.answer == 'Cancel':
                raise StopCommand
            elif dropdown.answer == 'All':
                ecids = [device['ecid'] for device in devices]
            else:
                device = next(d for d in devices if d['name'] == dropdown.answer)
                ecids = [device['ecid']]

            await ctx.edit(embed=upload_embed)

        else:
            ecids = [devices[0]['ecid']]
            await ctx.respond(embed=upload_embed, ephemeral=True)

        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
            url = await self.utils.backup_blobs(aiopath.AsyncPath(tmpdir), *ecids)

        buttons = [{'label': 'Download', 'style': discord.ButtonStyle.link, 'url': url}]

        view = SelectView(buttons, ctx, timeout=None)
        embed = discord.Embed(
            title='Download Blobs', description='Download your SHSH Blobs:'
        )
        await ctx.edit(embed=embed, view=view)
        self.bot.logger.info(f"User: `@{ctx.author}` has downloaded SHSH blobs.")

    @tss.command(name='list', description='List your saved SHSH blobs.')
    async def list_blobs(
        self,
        ctx: discord.ApplicationContext,
        user: Option(
            commands.UserConverter,
            description='User to list SHSH blobs for',
            required=False,
        ),
    ) -> None:
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
            blobs = sorted(device['saved_blobs'], key=lambda firm: firm['buildid'])

            device_embed = {
                'title': f"*{device['name']}*'s Saved SHSH Blobs ({devices.index(device) + 1}/{len(devices)})",
                'fields': list(),
                'footer': {
                    'text': ctx.author.display_name,
                    'icon_url': str(
                        ctx.author.display_avatar.with_static_format('png').url
                    ),
                },
            }

            blobs_list = dict()
            for firm in blobs:
                major_ver = int(firm['version'].split('.')[0])
                if major_ver not in blobs_list:
                    blobs_list[major_ver] = str()

                blobs_list[major_ver] += f"iOS {firm['version']}, "

            for ver in sorted(blobs_list, reverse=True):
                device_embed['fields'].append(
                    {'name': f'iOS {ver}', 'value': blobs_list[ver][:-2]}
                )

            if len(device_embed['fields']) == 0:
                del device_embed['fields']
                device_embed['description'] = 'No SHSH blobs saved.'

            device_embeds.append(discord.Embed.from_dict(device_embed))

        if len(device_embeds) == 1:
            await ctx.respond(embed=device_embeds[0], ephemeral=True)
        else:
            paginator = PaginatorView(device_embeds, ctx)
            await ctx.respond(
                embed=device_embeds[paginator.embed_num], view=paginator, ephemeral=True
            )

    @tss.command(name='save', description='Manually save SHSH blobs for your devices.')
    async def save_blobs(self, ctx: discord.ApplicationContext) -> None:
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

        if self.utils.saving_blobs:
            raise SavingSHSHError

        start_time = await asyncio.to_thread(time.time)
        user = await self.utils.save_user_blobs(ctx.author.id, devices)
        finish_time = round(await asyncio.to_thread(time.time) - start_time)

        embed = discord.Embed(
            title='Save Blobs',
            description='Saving SHSH blobs for all of your devices...',
        )
        if user['blobs_saved'] > 0:
            embed.description = ' '.join(
                (
                    f"Saved **{user['blobs_saved']} SHSH blob{'s' if user['blobs_saved'] != 1 else ''}**",
                    f"for **{user['devices_saved']} device{'s' if user['devices_saved'] != 1 else ''}**",
                    f"in **{finish_time} second{'s' if finish_time != 1 else ''}**.",
                )
            )
            self.bot.logger.info(
                f"User: `@{ctx.author}` has saved {user['blobs_saved']} SHSH blob{'s' if user['blobs_saved'] != 1 else ''} SHSH blobs."
            )
        else:
            embed.description = 'All SHSH blobs have already been saved for your devices.\n\n*Tip: AutoTSS will automatically save SHSH blobs for you, no command necessary!*'

        await ctx.respond(embed=embed)

    @permissions.is_owner()
    @tss.command(
        name='downloadall',
        description='Download SHSH blobs for all devices in AutoTSS.',
    )
    async def download_all_blobs(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)

        async with self.bot.db.execute('SELECT devices from autotss') as cursor:
            num_devices = sum(
                len(ujson.loads(devices[0])) for devices in await cursor.fetchall()
            )

        if num_devices == 0:
            embed = discord.Embed(
                title='Error', description='There are no devices added to AutoTSS.'
            )
            await ctx.respond(embed=embed)
            return

        ecids = [
            ecid.stem
            async for ecid in aiopath.AsyncPath('Data/Blobs').glob('*')
            if ecid.is_dir()
        ]
        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
            url = await self.utils.backup_blobs(aiopath.AsyncPath(tmpdir), *ecids)

        if url is None:
            embed = discord.Embed(
                title='Error', description='There are no SHSH blobs saved in AutoTSS.'
            )
            await ctx.respond(embed=embed)

        else:
            buttons = [
                {'label': 'Download', 'style': discord.ButtonStyle.link, 'url': url}
            ]

            view = SelectView(buttons, ctx, timeout=None)
            embed = discord.Embed(
                title='Download Blobs', description='Download all SHSH Blobs:'
            )
            await ctx.respond(embed=embed, view=view)

        self.bot.logger.info(f"Owner: `@{ctx.author}` has downloaded all SHSH blobs.")

    @permissions.is_owner()
    @tss.command(
        name='saveall',
        description='Manually save SHSH blobs for all devices in AutoTSS.',
    )
    async def save_all_blobs(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)

        async with self.bot.db.execute(
            'SELECT * from autotss WHERE enabled = ?', (True,)
        ) as cursor:
            data = await cursor.fetchall()

        num_devices = sum(len(ujson.loads(devices[1])) for devices in data)
        if num_devices == 0:
            embed = discord.Embed(
                title='Error', description='There are no devices added to AutoTSS.'
            )
            await ctx.respond(embed=embed)
            return

        if self.utils.saving_blobs:
            embed = discord.Embed(
                title='Hey!',
                description="I'm automatically saving SHSH blobs right now, please wait until I'm finished to manually save SHSH blobs.",
            )
            await ctx.respond(embed=embed)
            return

        self.utils.saving_blobs = True
        await self.bot.change_presence(
            activity=discord.Game(name='Currently saving SHSH blobs!')
        )

        embed = discord.Embed(
            title='Save Blobs',
            description='Saving SHSH blobs for all of your devices...',
        )
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )
        await ctx.respond(embed=embed)

        start_time = await asyncio.to_thread(time.time)
        data = await asyncio.gather(
            *[
                self.utils.sem_call(
                    self.utils.save_user_blobs, user_data[0], ujson.loads(user_data[1])
                )
                for user_data in data
            ]
        )
        finish_time = round(await asyncio.to_thread(time.time) - start_time)
        self.utils.saving_blobs = False

        blobs_saved = sum(user['blobs_saved'] for user in data)
        devices_saved = sum(user['devices_saved'] for user in data)

        if blobs_saved > 0:
            embed.description = ' '.join(
                (
                    f"Saved **{blobs_saved} SHSH blob{'s' if blobs_saved > 1 else ''}**",
                    f"for **{devices_saved} device{'s' if devices_saved > 1 else ''}**",
                    f"in **{finish_time} second{'s' if finish_time != 1 else ''}**.",
                )
            )

            self.bot.logger.info(
                f"Owner: `@{ctx.author}` has saved {blobs_saved} SHSH blob{'s' if blobs_saved > 1 else ''} for all devices."
            )

        else:
            embed.description = 'All SHSH blobs have already been saved.\n\n*Tip: AutoTSS will automatically save SHSH blobs for you, no command necessary!*'

        await self.utils.update_device_count()
        await ctx.edit(embed=embed)


def setup(bot: discord.Bot):
    bot.add_cog(TSSCog(bot))
