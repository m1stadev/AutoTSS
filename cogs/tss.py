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

	async def save_blob(self, device: dict, version: str, buildid: str, manifest: str) -> bool:
		async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
			base_args = ('tsschecker', '-d', device['identifier'], '-B', device['boardconfig'], '-e', '0x' + device['ecid'], '-m', manifest, '-s', '--save-path', tmpdir)
			generators = ['0x1111111111111111', '0xbd34a880be0b53f3']

			apnonce_save_path = ('Data', 'Blobs', device['ecid'], version, buildid, device['apnonce'])
			normal_save_path = ('Data', 'Blobs', device['ecid'], version, buildid, 'no-apnonce')

			if device['generator'] is None: #TODO: Make this less shit
				if device['apnonce'] is not None: # If only ApNonce specified, only save specified apnonce blobs
					if await self.os.path.exists('/'.join(apnonce_save_path)):
						if len(glob.glob(f"{'/'.join(apnonce_save_path)}/*")) > 0:
							blob_saved = True
						else:
							blob_saved = False

					else:
						blob_saved = False
						await self.os.makedirs('/'.join(apnonce_save_path))

					if blob_saved == False:
						args = (*base_args, '--apnonce', device['apnonce'])
						cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
						stdout = (await cmd.communicate())[0]

						if 'Saved shsh blobs!' not in stdout.decode():
							return False

						for blob in glob.glob(f"{tmpdir}/*"):
							blob_path = (*apnonce_save_path, blob.split('/')[-1])
							await self.os.rename(blob, '/'.join(blob_path))

				else: # If no generator/ApNonce specified, save for default generators
					if await self.os.path.exists('/'.join(normal_save_path)):
						if len(glob.glob(f"{'/'.join(normal_save_path)}/*")) > 0:
							blob_saved = True
						else:
							blob_saved = False

					else:
						blob_saved = False
						await self.os.makedirs('/'.join(normal_save_path))

					if blob_saved == False:
						for generator in generators:
							args = (*base_args, '-g', generator)
							cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
							stdout = (await cmd.communicate())[0]

							if 'Saved shsh blobs!' not in stdout.decode():
								return False

							for blob in glob.glob(f"{tmpdir}/*"):
								blob_path = '/'.join((*normal_save_path, blob.split('/')[-1]))
								await self.os.rename(blob, blob_path)

			else:
				if device['apnonce'] is not None: # If generator + ApNonce specified, only save for that combo
					if await self.os.path.exists('/'.join(apnonce_save_path)):
						if len(glob.glob(f"{'/'.join(apnonce_save_path)}/*")) > 0:
							blob_saved = True
						else:
							blob_saved = False

					else:
						blob_saved = False
						await self.os.makedirs('/'.join(apnonce_save_path))

					if blob_saved == False:
						args = (*base_args, '-g', device['generator'], '--apnonce', device['apnonce'])
						cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
						stdout = (await cmd.communicate())[0]

						if 'Saved shsh blobs!' not in stdout.decode():
							return False

						for blob in glob.glob(f"{tmpdir}/*"):
							blob_path = (*apnonce_save_path, blob.split('/')[-1])
							await self.os.rename(blob, '/'.join(blob_path))

				else: # If only generator specified, save for default generators + custom generator
					if device['generator'] not in generators:
						generators.append(device['generator'])

					if await self.os.path.exists('/'.join(normal_save_path)):
						if len(glob.glob(f"{'/'.join(normal_save_path)}/*")) > 0:
							blob_saved = True
						else:
							blob_saved = False

					else:
						blob_saved = False
						await self.os.makedirs('/'.join(normal_save_path))

					if blob_saved == False:
						for generator in generators:
							gen_args = (*base_args, '-g', generator)
							cmd = await asyncio.create_subprocess_exec(*gen_args, stdout=asyncio.subprocess.PIPE)
							stdout = (await cmd.communicate())[0]

							if 'Saved shsh blobs!' not in stdout.decode():
								return False

							for blob in glob.glob(f"{tmpdir}/*"):
								blob_path = '/'.join((*normal_save_path, blob.split('/')[-1]))
								await self.os.rename(blob, blob_path)

		return True

	@tasks.loop(minutes=30)
	async def auto_blob_saver(self) -> None:
		if self.blobs_loop == True:
			print('[AUTO] Manual blob saving currently running, not saving blobs.')
			return

		self.blobs_loop = True
		start_time = await self.time.time()
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
			all_devices = await cursor.fetchall()

		num_devices = int()
		for user_devices in all_devices:
			devices = json.loads(user_devices[1])

			num_devices += len(devices)

		if num_devices == 0:
			print('[AUTO] No blobs need to be saved.')
			self.blobs_loop = False
			return

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
								saved_blob = await self.save_blob(device, firm['version'], firm['buildid'], manifest)

						if saved_blob is True:
							saved_versions.append({
								'version': firm['version'],
								'buildid': firm['buildid'],
								'type': firm['type']
							})

							blobs_saved += 1
						else:
							failed_info = f"{device['name']} - iOS {firm['version']} | {firm['buildid']}"
							print(f"Failed to save blobs for '{failed_info}'.")

					if blobs_saved > current_blobs_saved:
						devices_saved_for += 1

					device['saved_blobs'] = saved_versions

					async with aiosqlite.connect('Data/autotss.db') as db:
						await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), user))
						await db.commit()

		if blobs_saved == 0:
			print('[AUTO] No new blobs were saved.')
		else:
			total_time = round(await self.time.time() - start_time)
			print(f"[AUTO] Saved {blobs_saved} blob{'s' if blobs_saved != 1 else ''} for {devices_saved_for} device{'s' if devices_saved_for != 1 else ''} in {total_time} second{'s' if total_time != 1 else ''}.")

		self.blobs_loop = False

	@auto_blob_saver.before_loop
	async def before_auto_blob_saver(self) -> None:
		await self.bot.wait_until_ready()
		await asyncio.sleep(3) # If first run, give on_ready() some time to create the database

	@commands.group(name='tss', invoke_without_command=True)
	@commands.guild_only()
	async def tss_cmd(self, ctx: commands.Context) -> None:
		prefix = await self.utils.get_prefix(ctx.guild.id)

		embed = discord.Embed(title='TSS Commands')
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		embed.add_field(name='Download all blobs saved for your devices', value=f'`{prefix}tss download`', inline=False)
		embed.add_field(name='List all blobs saved for your devices', value=f'`{prefix}tss list`', inline=False)
		embed.add_field(name='Save blobs for all of your devices', value=f'`{prefix}tss save`', inline=False)

		if await ctx.bot.is_owner(ctx.author):
			embed.add_field(name='Download blobs saved for all devices', value=f'`{prefix}tss downloadall`', inline=False)
			embed.add_field(name='Save blobs for all devices', value=f'`{prefix}tss saveall`', inline=False)

		await ctx.send(embed=embed)

	@tss_cmd.command(name='download')
	@commands.guild_only()
	@commands.max_concurrency(1, per=commands.BucketType.user)
	async def download_blobs(self, ctx: commands.Context) -> None:
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = json.loads((await cursor.fetchone())[0])
			except TypeError:
				devices = list()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Download Blobs', description='Uploading blobs...')
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		try:
			message = await ctx.author.send(embed=embed)
			await ctx.message.delete()
		except:
			message = await ctx.send(embed=embed)

		async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
			ecids = [device['ecid'] for device in devices]
			url = await self.utils.backup_blobs(tmpdir, *ecids)

		embed = discord.Embed(title='Download Blobs', description=f'[Click here]({url}).')


		if message.channel.type == discord.ChannelType.private:
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
		else:
			embed.set_footer(text=f'{ctx.author.display_name} | This message will automatically be deleted in 10 seconds to protect your ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)

			await asyncio.sleep(10)
			await ctx.message.delete()
			await message.delete()

	@tss_cmd.command(name='list')
	@commands.guild_only()
	async def list_blobs(self, ctx: commands.Context) -> None:
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = json.loads((await cursor.fetchone())[0])
			except TypeError:
				devices = list()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title=f"{ctx.author.display_name}'s Saved Blobs")
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		blobs_saved = int()
		for device in devices:
			blobs = sorted(device['saved_blobs'], key=lambda firm: firm['buildid'])
			blobs_saved += len(blobs)

			blobs_list = list()
			for firm in blobs:
				blobs_list.append(f"`iOS {firm['version']} | {firm['buildid']}`")

			if len(blobs_list) == 0:
				embed.add_field(name=device['name'], value='No blobs saved.', inline=False)
			else:
				embed.add_field(name=device['name'], value=', '.join(blobs_list), inline=False)

		num_devices = len(devices)
		embed.description = f"**{blobs_saved} blob{'s' if blobs_saved != 1 else ''}** saved for **{num_devices} device{'s' if num_devices != 1 else ''}**."

		await ctx.send(embed=embed)

	@tss_cmd.command(name='save')
	@commands.guild_only()
	@commands.max_concurrency(1, per=commands.BucketType.user)
	async def save_blobs(self, ctx: commands.Context) -> None:
		start_time = await self.time.time()
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = json.loads((await cursor.fetchone())[0])
			except TypeError:
				devices = list()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		if self.blobs_loop:
			embed = discord.Embed(title='Error', description="I'm already saving blobs right now!")
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Save Blobs', description='Saving blobs for all of your devices...')
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

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
							saved_blob = await self.save_blob(device, firm['version'], firm['buildid'], manifest)

					if saved_blob is True:
						saved_versions.append({
							'version': firm['version'],
							'buildid': firm['buildid'],
							'type': firm['type']
						})

						blobs_saved += 1
					else:
						failed_info = f"{device['name']} - iOS {firm['version']} | {firm['buildid']}"
						embed.add_field(name='Error', value=f'Failed to save blobs for `{failed_info}`.', inline=False)
						await message.edit(embed=embed)

				if blobs_saved > current_blobs_saved:
					devices_saved_for += 1

				device['saved_blobs'] = saved_versions

			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), ctx.author.id))
				await db.commit()

		if blobs_saved == 0:
			description = 'No new blobs were saved.'
		else:
			total_time = round(await self.time.time() - start_time)
			description = f"Saved **{blobs_saved} blob{'s' if blobs_saved != 1 else ''}** for **{devices_saved_for} device{'s' if devices_saved_for != 1 else ''}** in **{total_time} second{'s' if total_time != 1 else ''}**."

		embed.add_field(name='Finished!', value=description, inline=False)
		await message.edit(embed=embed)

	@tss_cmd.command(name='downloadall')
	@commands.guild_only()
	@commands.is_owner()
	@commands.max_concurrency(1, per=commands.BucketType.user)
	async def download_all_blobs(self, ctx: commands.Context) -> None:
		await ctx.message.delete()

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss') as cursor:
			all_devices = await cursor.fetchall()

		num_devices = int()
		for user_devices in all_devices:
			devices = json.loads(user_devices[0])

			num_devices += len(devices)

		if num_devices == 0:
			embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Download All Blobs', description='Uploading blobs...')
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		try:
			message = await ctx.author.send(embed=embed)
		except:
			embed = discord.Embed(title='Error', description="You don't have DMs enabled.")
			await ctx.send(embed=embed)
			return

		async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
			ecids = [ecid.split('/')[-1] for ecid in glob.glob('Data/Blobs/*')]
			url = await self.utils.backup_blobs(tmpdir, *ecids)

		if url is None:
			embed = discord.Embed(title='Error', description='There are no blobs saved in AutoTSS.')
		else:
			embed = discord.Embed(title='Download All Blobs', description=f'[Click here]({url}).')
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await message.edit(embed=embed)

	@tss_cmd.command(name='saveall')
	@commands.guild_only()
	@commands.is_owner()
	@commands.max_concurrency(1, per=commands.BucketType.user)
	async def save_all_blobs(self, ctx: commands.Context) -> None:
		start_time = await self.time.time()
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
			all_devices = await cursor.fetchall()

		num_devices = int()
		for user_devices in all_devices:
			num_devices += len(json.loads(user_devices[1]))

		if num_devices == 0:
			embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			self.blobs_loop = False
			return

		if self.blobs_loop:
			embed = discord.Embed(title='Error', description="I'm already saving blobs right now!")
			await ctx.send(embed=embed)
			return

		self.blobs_loop = True

		embed = discord.Embed(title='Save Blobs', description='Saving blobs for all devices...')
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

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
								saved_blob = await self.save_blob(device, firm['version'], firm['buildid'], manifest)

						if saved_blob is True:
							saved_versions.append({
								'version': firm['version'],
								'buildid': firm['buildid'],
								'type': firm['type']
							})

							blobs_saved += 1
						else:
							failed_info = f"{device['name']} - iOS {firm['version']} | {firm['buildid']}"
							embed.add_field(name='Error', value=f'Failed to save blobs for `{failed_info}`.', inline=False)
							await message.edit(embed=embed)

					if blobs_saved > current_blobs_saved:
						devices_saved_for += 1

					device['saved_blobs'] = saved_versions

				async with aiosqlite.connect('Data/autotss.db') as db:
					await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), user))
					await db.commit()

		if blobs_saved == 0:
			description = 'No new blobs were saved.'
		else:
			total_time = round(await self.time.time() - start_time)
			description = f"Saved **{blobs_saved} blob{'s' if blobs_saved != 1 else ''}** for **{devices_saved_for} device{'s' if devices_saved_for != 1 else ''}** in **{total_time} second{'s' if total_time != 1 else ''}**."

		embed.add_field(name='Finished!', value=description, inline=False)
		await message.edit(embed=embed)

		self.blobs_loop = False

def setup(bot):
	bot.add_cog(TSS(bot))
