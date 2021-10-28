from aioify import aioify
from discord.ext import commands, tasks
from typing import Union
from views.buttons import SelectView, PaginatorView
from views.selects import DropdownView

import aiofiles
import aiohttp
import aiosqlite
import asyncio
import discord
import glob
import json
import os
import shutil
import time


class TSS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.os = aioify(os, name='os')
        self.shutil = aioify(shutil, name='shutil')
        self.time = aioify(time, name='time')
        self.utils = self.bot.get_cog('Utils')
        self.blobs_loop = None
        self.auto_blob_saver.start()


    @tasks.loop()
    async def auto_blob_saver(self) -> None:
        async with aiosqlite.connect('Data/autotss.db') as db:
            async with db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
                all_devices = await cursor.fetchall()

            async with db.execute('SELECT time FROM auto_frequency') as cursor:
                sleep = (await cursor.fetchone())[0]

        if self.blobs_loop == True:
            print('[AUTO] Manual blob saving currently running, not saving SHSH blobs.')
            await asyncio.sleep(sleep)
            return

        num_devices = int()
        for user_devices in all_devices:
            num_devices += len(json.loads(user_devices[1]))

        if num_devices == 0:
            print('[AUTO] No SHSH blobs need to be saved.')
            await asyncio.sleep(sleep)
            return

        await self.bot.change_presence(activity=discord.Game(name='Ping me for help! | Currently saving SHSH blobs!'))
        self.blobs_loop = True
        start_time = await self.time.time()

        blobs_saved = int()
        devices_saved_for = int()
        cached_firms = dict()

        async with aiohttp.ClientSession() as session, aiosqlite.connect('Data/autotss.db') as db:
            for user_devices in all_devices:
                user = user_devices[0]
                devices = json.loads(user_devices[1])

                for device in devices:
                    current_blobs_saved = blobs_saved

                    if device['identifier'] not in cached_firms.keys():
                        cached_firms[device['identifier']] = await self.utils.get_firms(session, device['identifier'])

                    signed_firms = [f for f in cached_firms[device['identifier']] if f['signed'] == True]
                    for firm in signed_firms:
                        if any(firm['buildid'] == saved_firm['buildid'] for saved_firm in device['saved_blobs']): # If we've already saved blobs for this version, skip
                            continue

                        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
                            manifest = await self.bot.loop.run_in_executor(None, self.utils.get_manifest, firm['url'], tmpdir)
                            if manifest == False:
                                saved_blob = False
                            else:
                                saved_blob = await self.utils.save_blob(device, firm['version'], firm['buildid'], manifest, tmpdir)

                        if saved_blob is True:
                            device['saved_blobs'].append({x:y for x,y in firm.items() if x != 'url'})

                            await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), user))
                            await db.commit()

                            blobs_saved += 1
                        else:
                            failed_info = f"{device['name']}, iOS {firm['version']} | {firm['buildid']}"
                            print(f"[AUTO] Failed to save SHSH blobs for: {failed_info}.")

                    if blobs_saved > current_blobs_saved:
                        devices_saved_for += 1

        self.blobs_loop = False

        if blobs_saved == 0:
            print('[AUTO] No new SHSH blobs were saved.')
        else:
            total_time = round(await self.time.time() - start_time)
            output = (
                f"[AUTO] Saved {blobs_saved} SHSH blob{'s' if blobs_saved != 1 else ''}",
                f"for {devices_saved_for} device{'s' if devices_saved_for != 1 else ''}",
                f"in {total_time} second{'s' if total_time != 1 else ''}."
            )
            print(' '.join(output))

        await self.utils.update_device_count()
        await asyncio.sleep(sleep)

    @auto_blob_saver.before_loop
    async def before_auto_blob_saver(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(3) # If first run, give on_ready() some time to create the database

    @commands.group(name='tss', aliases=('t',), help='SHSH Blob commands.', invoke_without_command=True)
    @commands.guild_only()
    async def tss_cmd(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='TSS Commands')
        embed.add_field(name='Download all SHSH blobs saved for your devices', value=f'`{prefix}tss download`', inline=False)
        embed.add_field(name='List all SHSH blobs saved for your devices', value=f'`{prefix}tss list`', inline=False)
        embed.add_field(name='Save SHSH blobs for all of your devices', value=f'`{prefix}tss save`', inline=False)
        if await ctx.bot.is_owner(ctx.author):
            embed.add_field(name='Download SHSH blobs saved for all devices', value=f'`{prefix}tss downloadall`', inline=False)
            embed.add_field(name='Save SHSH blobs for all devices', value=f'`{prefix}tss saveall`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)

    @tss_cmd.command(name='download', help='Download your saved SHSH blobs.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def download_blobs(self, ctx: commands.Context) -> None:
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

        total_blobs = sum([len(device['saved_blobs']) for device in devices])
        if total_blobs == 0:
            embed = discord.Embed(title='Error', description='Currently, you do not have any saved SHSH blobs in AutoTSS. Please save SHSH blobs with AutoTSS before attempting to download them.')
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
        message = await message.edit(embed=embed) if message is not None else ctx.reply(embed=embed)

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

    @tss_cmd.command(name='list', help='List your saved SHSH blobs.')
    @commands.guild_only()
    async def list_blobs(self, ctx: commands.Context, user: Union[discord.User, int, str]=None) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        if type(user) == int:
            user = ctx.author if user == 0 else self.bot.get_user(user)

        if type(user) in (None, str):
            embed = discord.Embed(title='Error', description="This user doesn't exist!")
            await ctx.reply(embed=embed)
            return

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

    @tss_cmd.command(name='save', help='Manually save SHSH blobs for your devices.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def save_blobs(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        start_time = await self.time.time()
        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
            try:
                devices = json.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if len(devices) == 0:
            embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
            await ctx.reply(embed=embed)
            return

        if self.blobs_loop:
            embed = discord.Embed(title='Hey!', description="I'm automatically saving SHSH blobs right now, please wait until I'm finished to manually save SHSH blobs.")
            await ctx.reply(embed=embed)
            return

        embed = discord.Embed(title='Save Blobs', description='Saving SHSH blobs for all of your devices...')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        message = await ctx.reply(embed=embed)

        blobs_saved = int()
        devices_saved_for = int()
        cached_firms = dict()

        async with aiohttp.ClientSession() as session, aiosqlite.connect('Data/autotss.db') as db:
            for device in devices:
                current_blobs_saved = blobs_saved

                if device['identifier'] not in cached_firms.keys():
                    cached_firms[device['identifier']] = await self.utils.get_firms(session, device['identifier'])

                signed_firms = [firm for firm in cached_firms[device['identifier']] if firm['signed'] == True]
                for firm in signed_firms:
                    if any(firm['buildid'] == saved_firm['buildid'] for saved_firm in device['saved_blobs']): # If we've already saved blobs for this version, skip
                        continue

                    async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
                        manifest = await self.bot.loop.run_in_executor(None, self.utils.get_manifest, firm['url'], tmpdir)
                        if manifest == False:
                            saved_blob = False
                        else:
                            saved_blob = await self.utils.save_blob(device, firm['version'], firm['buildid'], manifest, tmpdir)

                    if saved_blob is True:
                        device['saved_blobs'].append({x:y for x,y in firm.items() if x != 'url'})

                        await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), ctx.author.id))
                        await db.commit()

                        blobs_saved += 1
                    else:
                        failed_info = f"{device['name']} - iOS {firm['version']} | {firm['buildid']}"
                        embed.add_field(name='Error', value=f'Failed to save SHSH blobs for `{failed_info}`.', inline=False)
                        message = await message.edit(embed=embed)

                if blobs_saved > current_blobs_saved:
                    devices_saved_for += 1

        if blobs_saved == 0:
            description = 'No new SHSH blobs were saved.'
        else:
            total_time = round(await self.time.time() - start_time)
            output = (
                f"Saved **{blobs_saved} SHSH blob{'s' if blobs_saved != 1 else ''}**",
                f"for **{devices_saved_for} device{'s' if devices_saved_for != 1 else ''}**",
                f"in **{total_time} second{'s' if total_time != 1 else ''}**."
            )
            description = ' '.join(output)

        embed.add_field(name='Finished!', value=description, inline=False)
        await message.edit(embed=embed)

    @tss_cmd.command(name='downloadall', help='Download SHSH blobs for all devices in AutoTSS.')
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    async def download_all_blobs(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        await ctx.message.delete()

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss') as cursor:
            all_devices = await cursor.fetchall()

        num_devices = int()
        for user_devices in all_devices:
            devices = json.loads(user_devices[0])

            num_devices += len(devices)

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
            embed = discord.Embed(title='Download All Blobs', description=f'[Click here]({url}).')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        await message.edit(embed=embed)

    @tss_cmd.command(name='saveall', help='Manually save SHSH blobs for all devices in AutoTSS.')
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    async def save_all_blobs(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        if self.blobs_loop:
            embed = discord.Embed(title='Hey!', description="I'm automatically saving SHSH blobs right now, please wait until I'm finished to manually save SHSH blobs.")
            await ctx.reply(embed=embed)
            return

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
            all_devices = await cursor.fetchall()

        num_devices = int()
        for user_devices in all_devices:
            num_devices += len(json.loads(user_devices[1]))

        if num_devices == 0:
            embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
            await ctx.reply(embed=embed)
            return

        embed = discord.Embed(title='Save Blobs', description='Saving SHSH blobs for all devices...')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        message = await ctx.reply(embed=embed)

        await self.bot.change_presence(activity=discord.Game(name='Ping me for help! | Currently saving SHSH blobs!'))
        self.blobs_loop = True
        start_time = await self.time.time()

        blobs_saved = int()
        devices_saved_for = int()
        cached_firms = dict()

        async with aiohttp.ClientSession() as session, aiosqlite.connect('Data/autotss.db') as db:
            for user_devices in all_devices:
                user = user_devices[0]
                devices = json.loads(user_devices[1])

                for device in devices:
                    current_blobs_saved = blobs_saved

                    if device['identifier'] not in cached_firms.keys():
                        cached_firms[device['identifier']] = await self.utils.get_firms(session, device['identifier'])

                    signed_firms = [f for f in cached_firms[device['identifier']] if f['signed'] == True]
                    for firm in signed_firms:
                        if any(firm['buildid'] == saved_firm['buildid'] for saved_firm in device['saved_blobs']): # If we've already saved blobs for this version, skip
                            continue

                        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
                            manifest = await self.bot.loop.run_in_executor(None, self.utils.get_manifest, firm['url'], tmpdir)
                            if manifest == False:
                                saved_blob = False
                            else:
                                saved_blob = await self.utils.save_blob(device, firm['version'], firm['buildid'], manifest, tmpdir)

                        if saved_blob is True:
                            device['saved_blobs'].append({x:y for x,y in firm.items() if x != 'url'})

                            await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), user))
                            await db.commit()

                            blobs_saved += 1
                        else:
                            failed_info = f"{device['name']} - iOS {firm['version']} | {firm['buildid']}"
                            embed.add_field(name='Error', value=f'Failed to save SHSH blobs for `{failed_info}`.', inline=False)
                            message = await message.edit(embed=embed)

                    if blobs_saved > current_blobs_saved:
                        devices_saved_for += 1

        self.blobs_loop = False

        if blobs_saved == 0:
            description = 'No new SHSH blobs were saved.'
        else:
            total_time = round(await self.time.time() - start_time)
            output = (
                f"Saved **{blobs_saved} SHSH blob{'s' if blobs_saved != 1 else ''}**",
                f"for **{devices_saved_for} device{'s' if devices_saved_for != 1 else ''}**",
                f"in **{total_time} second{'s' if total_time != 1 else ''}**."
            )
            description = ' '.join(output)

        await self.utils.update_device_count()

        embed.add_field(name='Finished!', value=description, inline=False)
        await message.edit(embed=embed)

def setup(bot):
    bot.add_cog(TSS(bot))
