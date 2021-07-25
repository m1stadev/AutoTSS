from aioify import aioify
from discord.ext import commands, tasks
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

    async def save_blob(self, device: dict, version: str, buildid: str, manifest: str, tmpdir: str) -> bool:
        generators = list()
        save_path = [
            'Data',
            'Blobs',
            device['ecid'],
            version,
            buildid
        ]

        args = [
            'tsschecker',
            '-d',
            device['identifier'],
            '-B',
            device['boardconfig'],
            '-e',
            f"0x{device['ecid']}",
            '-m',
            manifest,
            '-s',
            '--save-path',
            tmpdir
        ]

        if device['apnonce'] is not None:
            args.append('--apnonce')
            args.append(device['apnonce'])
            save_path.append(device['apnonce'])
        else:
            generators.append('0x1111111111111111')
            generators.append('0xbd34a880be0b53f3')
            save_path.append('no-apnonce')

        if device['generator'] is not None and device['generator'] not in generators:
            generators.append(device['generator'])

        path = '/'.join(save_path)
        if not await self.os.path.isdir(path):
            await self.os.makedirs(path)

        if len(glob.glob(f'{path}/*.shsh*')) > 0:
            return True

        if len(generators) == 0:
            cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
            stdout = (await cmd.communicate())[0]

            if 'Saved shsh blobs!' not in stdout.decode():
                return False

        else:
            args.append('-g')
            for gen in generators:
                args.append(gen)
                cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
                stdout = (await cmd.communicate())[0]

                if 'Saved shsh blobs!' not in stdout.decode():
                    return False

                args.pop(-1)

        for blob in glob.glob(f'{tmpdir}/*.shsh*'):
            await self.os.rename(blob, f"{path}/{blob.split('/')[-1]}")

        return True

    @tasks.loop()
    async def auto_blob_saver(self) -> None:
        if self.blobs_loop == True:
            print('[AUTO] Manual blob saving currently running, not saving SHSH blobs.')
            return

        async with aiosqlite.connect('Data/autotss.db') as db:
            async with db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
                all_devices = await cursor.fetchall()

            async with db.execute('SELECT time FROM auto_frequency') as cursor:
                sleep = (await cursor.fetchone())[0]

        num_devices = int()
        for user_devices in all_devices:
            num_devices += len(json.loads(user_devices[1]))

        if num_devices == 0:
            print('[AUTO] No SHSH blobs need to be saved.')
            self.blobs_loop = False
            await asyncio.sleep(sleep)
            return

        await self.bot.change_presence(activity=discord.Game(name='Ping me for help! | Currently saving SHSH blobs!'))
        self.blobs_loop = True
        start_time = await self.time.time()

        blobs_saved = int()
        devices_saved_for = int()
        cached_signed_buildids = dict()

        async with aiohttp.ClientSession() as session:
            for user_devices in all_devices:
                user = user_devices[0]
                devices = json.loads(user_devices[1])

                for device in devices:
                    current_blobs_saved = blobs_saved
                    saved_versions = device['saved_blobs']

                    if device['identifier'] not in cached_signed_buildids.keys():
                        cached_signed_buildids[device['identifier']] = await self.utils.get_signed_buildids(session, device['identifier'])

                    signed_firms = cached_signed_buildids[device['identifier']]
                    for firm in signed_firms:
                        if any(firm['buildid'] == saved_firm['buildid'] for saved_firm in saved_versions): # If we've already saved blobs for this version, skip
                            continue

                        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
                            manifest = await asyncio.to_thread(self.utils.get_manifest, firm['url'], tmpdir)
                            if manifest == False:
                                saved_blob = False
                            else:
                                saved_blob = await self.save_blob(device, firm['version'], firm['buildid'], manifest, tmpdir)

                        if saved_blob is True:
                            saved_versions.append({
                                'version': firm['version'],
                                'buildid': firm['buildid'],
                                'type': firm['type']
                            })

                            blobs_saved += 1
                        else:
                            failed_info = f"{device['name']} - iOS {firm['version']} | {firm['buildid']}"
                            print(f"Failed to save SHSH blobs for '{failed_info}'.")

                    if blobs_saved > current_blobs_saved:
                        devices_saved_for += 1

                    device['saved_blobs'] = saved_versions

                    async with aiosqlite.connect('Data/autotss.db') as db:
                        await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), user))
                        await db.commit()

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

    @commands.group(name='tss', invoke_without_command=True)
    @commands.guild_only()
    async def tss_cmd(self, ctx: commands.Context) -> None:
        whitelist = await self.utils.get_whitelist(ctx.guild.id)
        if (whitelist is not None) and (whitelist.id != ctx.channel.id):
            embed = discord.Embed(title='Hey!', description=f'AutoTSS can only be used in {whitelist.mention}.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await ctx.reply(embed=embed)
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='TSS Commands')
        embed.add_field(name='Download all SHSH blobs saved for your devices', value=f'`{prefix}tss download`', inline=False)
        embed.add_field(name='List all SHSH blobs saved for your devices', value=f'`{prefix}tss list`', inline=False)
        embed.add_field(name='Save SHSH blobs for all of your devices', value=f'`{prefix}tss save`', inline=False)
        if await ctx.bot.is_owner(ctx.author):
            embed.add_field(name='Download SHSH blobs saved for all devices', value=f'`{prefix}tss downloadall`', inline=False)
            embed.add_field(name='Save SHSH blobs for all devices', value=f'`{prefix}tss saveall`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.reply(embed=embed)

    @tss_cmd.command(name='download')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def download_blobs(self, ctx: commands.Context) -> None:
        whitelist = await self.utils.get_whitelist(ctx.guild.id)
        if (whitelist is not None) and (whitelist.id != ctx.channel.id):
            embed = discord.Embed(title='Hey!', description=f'AutoTSS can only be used in {whitelist.mention}.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await ctx.reply(embed=embed)
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

        embed = discord.Embed(title='Download Blobs', description='Uploading SHSH blobs...')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        try:
            message = await ctx.author.send(embed=embed)
            await ctx.message.delete()
        except:
            message = await ctx.reply(embed=embed)

        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
            ecids = [device['ecid'] for device in devices]
            url = await self.utils.backup_blobs(tmpdir, *ecids)

        if url is None:
            embed = discord.Embed(title='Error', description='Currently, you do not have any saved SHSH blobs in AutoTSS. Please save SHSH blobs with AutoTSS before attempting to download them.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        embed = discord.Embed(title='Download Blobs', description=f'[Click here]({url}).')

        if message.channel.type == discord.ChannelType.private:
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
        else:
            embed.set_footer(text=f'{ctx.author.display_name} | This message will automatically be deleted in 5 seconds to protect your ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)

            await asyncio.sleep(5)
            await ctx.message.delete()
            await message.delete()

    @tss_cmd.command(name='list')
    @commands.guild_only()
    async def list_blobs(self, ctx: commands.Context) -> None:
        whitelist = await self.utils.get_whitelist(ctx.guild.id)
        if (whitelist is not None) and (whitelist.id != ctx.channel.id):
            embed = discord.Embed(title='Hey!', description=f'AutoTSS can only be used in {whitelist.mention}.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await ctx.reply(embed=embed)
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

        embed = discord.Embed(title=f"{ctx.author.display_name}'s Saved SHSH Blobs")
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

        blobs_saved = int()
        for device in devices:
            blobs = sorted(device['saved_blobs'], key=lambda firm: firm['buildid'])
            blobs_saved += len(blobs)

            blobs_list = list()
            for firm in blobs:
                blobs_list.append(f"`iOS {firm['version']} | {firm['buildid']}`")

            if len(blobs_list) == 0:
                embed.add_field(name=device['name'], value='No SHSH blobs saved.', inline=False)
            else:
                embed.add_field(name=device['name'], value=', '.join(blobs_list), inline=False)

        num_devices = len(devices)
        embed.description = f"**{blobs_saved} SHSH blob{'s' if blobs_saved != 1 else ''}** saved for **{num_devices} device{'s' if num_devices != 1 else ''}**."

        await ctx.reply(embed=embed)

    @tss_cmd.command(name='save')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def save_blobs(self, ctx: commands.Context) -> None:
        whitelist = await self.utils.get_whitelist(ctx.guild.id)
        if (whitelist is not None) and (whitelist.id != ctx.channel.id):
            embed = discord.Embed(title='Hey!', description=f'AutoTSS can only be used in {whitelist.mention}.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await ctx.reply(embed=embed)
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
            embed = discord.Embed(title='Error', description="I'm automatically saving SHSH blobs right now, please wait until I'm finished to manually save SHSH blobs.")
            await ctx.reply(embed=embed)
            return

        embed = discord.Embed(title='Save Blobs', description='Saving SHSH blobs for all of your devices...')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        message = await ctx.reply(embed=embed)

        blobs_saved = int()
        devices_saved_for = int()
        cached_signed_buildids = dict()

        async with aiohttp.ClientSession() as session:
            for device in devices:
                current_blobs_saved = blobs_saved
                saved_versions = device['saved_blobs']

                if device['identifier'] not in cached_signed_buildids.keys():
                    cached_signed_buildids[device['identifier']] = await self.utils.get_signed_buildids(session, device['identifier'])

                signed_firms = cached_signed_buildids[device['identifier']]
                for firm in signed_firms:
                    if any(firm['buildid'] == saved_firm['buildid'] for saved_firm in saved_versions): # If we've already saved blobs for this version, skip
                        continue

                    async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
                        manifest = await asyncio.to_thread(self.utils.get_manifest, firm['url'], tmpdir)
                        if manifest == False:
                            saved_blob = False
                        else:
                            saved_blob = await self.save_blob(device, firm['version'], firm['buildid'], manifest, tmpdir)

                    if saved_blob is True:
                        saved_versions.append({
                            'version': firm['version'],
                            'buildid': firm['buildid'],
                            'type': firm['type']
                        })

                        blobs_saved += 1
                    else:
                        failed_info = f"{device['name']} - iOS {firm['version']} | {firm['buildid']}"
                        embed.add_field(name='Error', value=f'Failed to save SHSH blobs for `{failed_info}`.', inline=False)
                        await message.edit(embed=embed)

                if blobs_saved > current_blobs_saved:
                    devices_saved_for += 1

                device['saved_blobs'] = saved_versions

            async with aiosqlite.connect('Data/autotss.db') as db:
                await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), ctx.author.id))
                await db.commit()

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

    @tss_cmd.command(name='downloadall')
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def download_all_blobs(self, ctx: commands.Context) -> None:
        whitelist = await self.utils.get_whitelist(ctx.guild.id)
        if (whitelist is not None) and (whitelist.id != ctx.channel.id):
            embed = discord.Embed(title='Hey!', description=f'AutoTSS can only be used in {whitelist.mention}.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await ctx.reply(embed=embed)
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
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

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
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

        await message.edit(embed=embed)

    @tss_cmd.command(name='saveall')
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def save_all_blobs(self, ctx: commands.Context) -> None:
        whitelist = await self.utils.get_whitelist(ctx.guild.id)
        if (whitelist is not None) and (whitelist.id != ctx.channel.id):
            embed = discord.Embed(title='Hey!', description=f'AutoTSS can only be used in {whitelist.mention}.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await ctx.reply(embed=embed)
            return

        if self.blobs_loop:
            embed = discord.Embed(title='Error', description="I'm automatically saving SHSH blobs right now, please wait until I'm finished to manually save SHSH blobs.")
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
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        message = await ctx.reply(embed=embed)

        await self.bot.change_presence(activity=discord.Game(name='Ping me for help! | Currently saving SHSH blobs!'))
        self.blobs_loop = True
        start_time = await self.time.time()

        blobs_saved = int()
        devices_saved_for = int()
        cached_signed_buildids = dict()

        async with aiohttp.ClientSession() as session:
            for user_devices in all_devices:
                user = user_devices[0]
                devices = json.loads(user_devices[1])

                for device in devices:
                    current_blobs_saved = blobs_saved
                    saved_versions = device['saved_blobs']

                    if device['identifier'] not in cached_signed_buildids.keys():
                        cached_signed_buildids[device['identifier']] = await self.utils.get_signed_buildids(session, device['identifier'])

                    signed_firms = cached_signed_buildids[device['identifier']]
                    for firm in signed_firms:
                        if any(firm['buildid'] == saved_firm['buildid'] for saved_firm in saved_versions): # If we've already saved blobs for this version, skip
                            continue

                        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
                            manifest = await asyncio.to_thread(self.utils.get_manifest, firm['url'], tmpdir)
                            if manifest == False:
                                saved_blob = False
                            else:
                                saved_blob = await self.save_blob(device, firm['version'], firm['buildid'], manifest, tmpdir)

                        if saved_blob is True:
                            saved_versions.append({
                                'version': firm['version'],
                                'buildid': firm['buildid'],
                                'type': firm['type']
                            })

                            blobs_saved += 1
                        else:
                            failed_info = f"{device['name']} - iOS {firm['version']} | {firm['buildid']}"
                            embed.add_field(name='Error', value=f'Failed to save SHSH blobs for `{failed_info}`.', inline=False)
                            await message.edit(embed=embed)

                    if blobs_saved > current_blobs_saved:
                        devices_saved_for += 1

                    device['saved_blobs'] = saved_versions

                async with aiosqlite.connect('Data/autotss.db') as db:
                    await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), user))
                    await db.commit()

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
