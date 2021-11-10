from discord.ext import commands
from views.buttons import SelectView, PaginatorView
from views.selects import DropdownView

import aiofiles
import aiosqlite
import asyncio
import discord
import glob
import json
import time


class TSSCog(commands.Cog, name='TSS'):
    def __init__(self, bot):
        self.bot = bot
        self.utils = self.bot.get_cog('Utilities')

    @commands.group(name='tss', aliases=('t',), help='SHSH Blob commands.', invoke_without_command=True)
    @commands.guild_only()
    async def tss_group(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        help_aliases = (self.bot.help_command.command_attrs['name'], *self.bot.help_command.command_attrs['aliases'])
        if (ctx.subcommand_passed is None) or (ctx.subcommand_passed.lower() in help_aliases):
            await ctx.send_help(ctx.command)
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)
        invoked_cmd = f'{prefix + ctx.invoked_with} {ctx.subcommand_passed}'
        embed = discord.Embed(title='Error', description=f'`{invoked_cmd}` does not exist! Use `{prefix}help` to see all the commands I can run.')
        await ctx.reply(embed=embed)

    @tss_group.command(name='download', help='Download your saved SHSH blobs.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def download_blobs(self, ctx: commands.Context, user: commands.UserConverter=None) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        if user is None:
            user = ctx.author
        else:
            if await ctx.bot.is_owner(ctx.author) == False:
                return

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (user.id,)) as cursor:
            try:
                devices = json.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if len(devices) == 0:
            embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
            await ctx.reply(embed=embed)
            return

        total_blobs = sum([len(device['saved_blobs']) for device in devices])
        if total_blobs == 0:
            embed = discord.Embed(title='Error', description=f"Currently, {'you do' if user.id == ctx.author.id else f'{user.mention} does'} not have any saved SHSH blobs in AutoTSS. Please save SHSH blobs with AutoTSS before attempting to download them.")
            await ctx.reply(embed=embed)
            return

        if len(devices) > 1:
            device_options = [discord.SelectOption(
                label='All',
                description=f"Devices: {len(devices)} | Total SHSH blob{'s' if total_blobs != 1 else ''} saved: {total_blobs}",
                emoji='📱'
            )]

            for device in devices:
                device_options.append(discord.SelectOption(
                    label=device['name'],
                    description=f"ECID: {await self.utils.censor_ecid(device['ecid'])} | SHSH blob{'s' if len(device['saved_blobs']) != 1 else ''} saved: {len(device['saved_blobs'])}",
                    emoji='📱'
                ))

            embed = discord.Embed(title='Download Blobs', description="Choose which device you'd like to download SHSH blobs for")
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

            dropdown = DropdownView(device_options, 'Device')
            dropdown.message = await ctx.reply(embed=embed, view=dropdown)
            await dropdown.wait()
            if dropdown.answer is None:
                embed.description = 'No response given in 1 minute, cancelling.'
                await dropdown.message.edit(embed=embed)
                return

            if dropdown.answer == 'All':
                ecids = [device['ecid'] for device in devices]
            else:
                device = next(d for d in devices if d['name'] == dropdown.answer)
                ecids = [device['ecid']]

            message = dropdown.message
        else:
            ecids = [devices[0]['ecid']]
            message = None

        embed = discord.Embed(title='Download Blobs', description='Uploading SHSH blobs...')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        message = await message.edit(embed=embed) if message is not None else await ctx.reply(embed=embed)

        async with message.channel.typing(), aiofiles.tempfile.TemporaryDirectory() as tmpdir:
            url = await self.utils.backup_blobs(tmpdir, *ecids)

        buttons = [{
            'label': 'Download',
            'style': discord.ButtonStyle.link,
            'url': url
        }]

        view = SelectView(buttons, timeout=None)
        embed = discord.Embed(title='Download Blobs')

        try:
            await ctx.author.send(embed=embed, view=view)
            embed.description = "I've DMed the download link to you."
            await message.edit(embed=embed)

        except:
            embed.set_footer(text='This message will automatically be deleted in 5 seconds to protect your ECID(s).')
            message = await message.edit(embed=embed, view=view)

            await message.delete(delay=5)
            await ctx.message.delete()

    @tss_group.command(name='list', help='List your saved SHSH blobs.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def list_blobs(self, ctx: commands.Context, user: commands.UserConverter=None) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        if user is None:
            user = ctx.author

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (user.id,)) as cursor:
            try:
                devices = json.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if len(devices) == 0:
            embed = discord.Embed(title='Error', description=f"{'You have' if user == ctx.author else f'{user.mention} has'} no devices added to AutoTSS.")
            await ctx.reply(embed=embed)
            return

        device_embeds = list()
        for device in devices:
            blobs = sorted(device['saved_blobs'], key=lambda firm: firm['buildid'])

            device_embed = {
                'title': f"*{device['name']}*'s Saved SHSH Blobs ({devices.index(device) + 1}/{len(devices)})",
                'fields': list(),
                'footer': {
                    'text': ctx.author.display_name,
                    'icon_url': str(ctx.author.display_avatar.with_static_format('png').url)
                }
            }

            blobs_list = dict()
            for firm in blobs:
                major_ver = int(firm['version'].split('.')[0])
                if major_ver not in blobs_list:
                    blobs_list[major_ver] = str()

                blobs_list[major_ver] += f"iOS {firm['version']}, "

            for ver in sorted(blobs_list, reverse=True):
                device_embed['fields'].append({
                    'name': f'iOS {ver}',
                    'value': blobs_list[ver][:-2]
                })

            if len(device_embed['fields']) == 0:
                del device_embed['fields']
                device_embed['description'] = 'No SHSH blobs saved.'

            device_embeds.append(discord.Embed.from_dict(device_embed))

        if len(device_embeds) == 1:
            await ctx.reply(embed=device_embeds[0])
            return

        paginator = PaginatorView(device_embeds)
        paginator.message = await ctx.reply(embed=device_embeds[paginator.embed_num], view=paginator)

    @tss_group.command(name='save', help='Manually save SHSH blobs for your devices.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def save_blobs(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
            try:
                devices = json.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if len(devices) == 0:
            embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
            await ctx.reply(embed=embed)
            return

        if self.utils.saving_blobs:
            embed = discord.Embed(title='Hey!', description="I'm automatically saving SHSH blobs right now, please wait until I'm finished to manually save SHSH blobs.")
            await ctx.reply(embed=embed)
            return

        embed = discord.Embed(title='Save Blobs', description='Saving SHSH blobs for all of your devices...')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        message = await ctx.reply(embed=embed)

        start_time = await asyncio.to_thread(time.time)
        user = await self.utils.save_user_blobs(ctx.author.id, devices)
        finish_time = round(await asyncio.to_thread(time.time) - start_time)

        if user['blobs_saved'] > 0:
            embed.description = ' '.join((
                f"Saved **{user['blobs_saved']} SHSH blob{'s' if user['blobs_saved'] != 1 else ''}**",
                f"for **{user['devices_saved']} device{'s' if user['devices_saved'] != 1 else ''}**",
                f"in **{finish_time} second{'s' if finish_time != 1 else ''}**."
            ))
        else:
            embed.description = 'All SHSH blobs have already been saved for your devices.\n\n*Tip: AutoTSS will automatically save SHSH blobs for you, no command necessary!*'

        await message.edit(embed=embed)

    @tss_group.command(name='downloadall', help='Download SHSH blobs for all devices in AutoTSS.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
    async def download_all_blobs(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        await ctx.message.delete()

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss') as cursor:
            num_devices = sum(len(json.loads(devices[0])) for devices in await cursor.fetchall())

        if num_devices == 0:
            embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
            await ctx.reply(embed=embed)
            return

        embed = discord.Embed(title='Download All Blobs', description='Uploading SHSH blobs...')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        try:
            message = await ctx.author.send(embed=embed)
        except:
            embed = discord.Embed(title='Error', description="You don't have DMs enabled.")
            await ctx.reply(embed=embed)
            return

        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
            ecids = [ecid.split('/')[-1] for ecid in glob.glob('Data/Blobs/*')]
            url = await self.utils.backup_blobs(tmpdir, *ecids)

        if url is None:
            embed = discord.Embed(title='Error', description='There are no SHSH blobs saved in AutoTSS.')
        else:
            embed.description = f'[Click here]({url}).'

        await message.edit(embed=embed)

    @tss_group.command(name='saveall', help='Manually save SHSH blobs for all devices in AutoTSS.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
    async def save_all_blobs(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
            data = await cursor.fetchall()

        num_devices = sum(len(json.loads(devices[1])) for devices in data)
        if num_devices == 0:
            embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
            await ctx.reply(embed=embed)
            return

        if self.utils.saving_blobs:
            embed = discord.Embed(title='Hey!', description="I'm automatically saving SHSH blobs right now, please wait until I'm finished to manually save SHSH blobs.")
            await ctx.reply(embed=embed)
            return

        self.utils.saving_blobs = True
        await self.bot.change_presence(activity=discord.Game(name='Ping me for help! | Currently saving SHSH blobs!'))

        embed = discord.Embed(title='Save Blobs', description='Saving SHSH blobs for all of your devices...')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        message = await ctx.reply(embed=embed)

        start_time = await asyncio.to_thread(time.time)
        data = await asyncio.gather(*[self.utils.sem_call(self.utils.save_user_blobs, user_data[0], json.loads(user_data[1])) for user_data in data])
        finish_time = round(await asyncio.to_thread(time.time) - start_time)
        self.utils.saving_blobs = False

        blobs_saved = sum(user['blobs_saved'] for user in data)
        devices_saved = sum(user['devices_saved'] for user in data)

        if blobs_saved > 0:
            embed.description = ' '.join((
                f"Saved **{blobs_saved} SHSH blob{'s' if blobs_saved > 1 else ''}**",
                f"for **{devices_saved} device{'s' if devices_saved > 1 else ''}**",
                f"in **{finish_time} second{'s' if finish_time != 1 else ''}**."
            ))

        else:
            embed.description = 'All SHSH blobs have already been saved.\n\n*Tip: AutoTSS will automatically save SHSH blobs for you, no command necessary!*'

        await self.utils.update_device_count()
        await message.edit(embed=embed)


def setup(bot):
    bot.add_cog(TSSCog(bot))
