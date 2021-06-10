from aioify import aioify
from discord.ext import commands, tasks
import aiofiles
import aiohttp
import aiosqlite
import asyncio
import discord
import glob
import json
import time
import os
import remotezip
import requests
import shutil


class TSS(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.os = aioify(os, name='os')
		self.shutil = aioify(shutil, name='shutil')
		self.time = aioify(time, name='time')
		self.save_blobs_loop.start()

	def get_manifest(self, identifier, buildid, dir):
		api_url = f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw'
		api = requests.get(api_url).json()

		firm = next(x['url'] for x in api['firmwares'] if x['buildid'] == buildid)
		with remotezip.RemoteZip(firm) as ipsw:
			manifest = ipsw.read(next(f for f in ipsw.namelist() if 'BuildManifest' in f))

		with open(f'{dir}/BuildManifest.plist', 'wb') as f:
			f.write(manifest)

		return f'{dir}/BuildManifest.plist'

	async def upload_file(self, file, name):
		async with aiohttp.ClientSession() as session, aiofiles.open(file, 'rb') as f, session.put(f'https://up.psty.io/{name}', data=f) as response:
			resp = await response.text()

		return resp.splitlines()[-1].split(':', 1)[1][1:]

	async def get_signed_buildids(self, identifier):
		api_url = f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw'
		async with aiohttp.ClientSession() as session, session.get(api_url) as resp:
			api = await resp.json()

		return [x['buildid'] for x in api['firmwares'] if x['signed'] == True]

	async def buildid_to_version(self, identifier, buildid):
		api_url = f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw'
		async with aiohttp.ClientSession() as session, session.get(api_url) as resp:
			api = await resp.json()

		return next(x['version'] for x in api['firmwares'] if x['buildid'] == buildid)

	async def save_blob(self, device, version, manifest):
		async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
			args = ['tsschecker', '-d', device['identifier'], '-B', device['boardconfig'], '-e', '0x' + device['ecid'], '-m', manifest, '-s', '--save-path', tmpdir]

			save_path = ('Data', 'Blobs', device['ecid'], version, 'no-apnonce')
			if await self.os.path.exists('/'.join(save_path)):
				if len(glob.glob(f"{'/'.join(save_path)}/*")) > 0:
					blob_saved = True
				else:
					blob_saved = False
			else:
				blob_saved = False
				await self.os.makedirs('/'.join(save_path))

			if blob_saved == False:
				cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
				stdout = (await cmd.communicate())[0]

				if 'Saved shsh blobs!' not in stdout.decode():
					return False

				for blob in glob.glob(f"{tmpdir}/*"):
					blob_path = '/'.join((*save_path, blob.split('/')[-1]))
					await self.os.rename(blob, blob_path)

			if device['apnonce'] is not None:
				args.append('--apnonce')
				args.append(device['apnonce'])

				save_path = ('Data', 'Blobs', device['ecid'], version, device['apnonce'])
				if await self.os.path.exists('/'.join(save_path)):
					if len(glob.glob(f"{'/'.join(save_path)}/*")) > 0:
						blob_saved = True
					else:
						blob_saved = False
				else:
					blob_saved = False
					await self.os.makedirs('/'.join(save_path))

				if blob_saved == False:
					cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
					stdout = (await cmd.communicate())[0]

					if 'Saved shsh blobs!' not in stdout.decode():
						return False

					for blob in glob.glob(f"{tmpdir}/*"):
						blob_path = (*save_path, blob.split('/')[-1])
						await self.os.rename(blob, '/'.join(blob_path))

		return True

	@tasks.loop(seconds=1800)  # Change this value to modify the frequency at which blobs will be saved at
	async def save_blobs_loop(self):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
			all_devices = await cursor.fetchall()

		num_devices = int()
		for user_devices in all_devices:
			user_devices = json.loads(user_devices[1])

			num_devices += len(user_devices)

		if num_devices == 0:
			print('[AUTO] No blobs need to be saved.')
			return

		blobs_saved = int()
		devices_saved_for = int()

		for user_devices in all_devices:
			user = user_devices[0]
			devices = json.loads(user_devices[1])

			for x in devices.keys():
				current_blobs_saved = blobs_saved

				signed_buildids = await self.get_signed_buildids(devices[x]['identifier'])
				saved_versions = devices[x]['saved_blobs']

				for buildid in signed_buildids:
					if any(buildid == saved_versions[firm]['buildid'] for firm in saved_versions):
						continue

					version = await self.buildid_to_version(devices[x]['identifier'], buildid)

					async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
						manifest = await asyncio.to_thread(self.get_manifest, devices[x]['identifier'], buildid, tmpdir)
						saved_blob = await self.save_blob(devices[x], version, manifest)

					if saved_blob is True:
						saved_versions[len(saved_versions)] = {
							'version': version,
							'buildid': buildid, 
							'type': 'Release'
						}

						blobs_saved += 1
					else:
						failed_info = f"{devices[x]['name']} - iOS {version} | {buildid}"
						print(f'Failed to save blobs for `{failed_info}`.')

				devices[x]['saved_blobs'] = saved_versions

				if blobs_saved > current_blobs_saved:
					devices_saved_for += 1

				async with aiosqlite.connect('Data/autotss.db') as db:
					await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), user))
					await db.commit()

		if blobs_saved == 0:
			print('[AUTO] No new blobs were saved.')
		else:
			print(f"[AUTO] Saved {blobs_saved} blob{'s' if blobs_saved != 1 else ''} for {devices_saved_for} device{'s' if devices_saved_for != 1 else ''}.")

	@commands.group(name='tss', invoke_without_command=True)
	@commands.guild_only()
	async def tss_cmd(self, ctx):
		if ctx.prefix == f'<@!{self.bot.user.id}> ':
			prefix = f'{ctx.prefix}`'
		else:
			prefix = f'`{ctx.prefix}'

		embed = discord.Embed(title='TSS Commands')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		embed.add_field(name='Download all blobs saved for your devices', value=f'{prefix}tss download`', inline=False)
		embed.add_field(name='List all blobs saved for your devices', value=f'{prefix}tss list`', inline=False)
		embed.add_field(name='Save blobs for all of your devices', value=f'{prefix}tss save`', inline=False)

		if await ctx.bot.is_owner(ctx.author):
			embed.add_field(name='Download blobs saved for all devices', value=f'{prefix}tss downloadall`', inline=False)
			embed.add_field(name='Save blobs for all devices', value=f'{prefix}tss saveall`', inline=False)

		await ctx.send(embed=embed)

	@tss_cmd.command(name='download')
	@commands.guild_only()
	async def download_blobs(self, ctx):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = json.loads((await cursor.fetchall())[0][0])
			except IndexError:
				devices = dict()
				await db.execute('INSERT INTO autotss(user, devices, enabled) VALUES(?,?,?)', (ctx.author.id, json.dumps(devices), True))
				await db.commit()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Download Blobs', description='Uploading blobs...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		try:
			message = await ctx.author.send(embed=embed)
		except:
			message = await ctx.send(embed=embed)
		

		async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
			await self.os.mkdir(f'{tmpdir}/Blobs')

			for ecid in [devices[x]['ecid'] for x in devices.keys()]:
				try:
					await self.shutil.copytree(f'Data/Blobs/{ecid}', f'{tmpdir}/Blobs/{ecid}')
				except FileNotFoundError:
					pass

			await self.shutil.make_archive(f'{tmpdir}_blobs', 'zip', tmpdir)
			url = await self.upload_file(f'{tmpdir}_blobs.zip', 'blobs.zip')

		embed = discord.Embed(title='Download Blobs', description=f'[Click here]({url}).')

		if message.channel.type == discord.ChannelType.private:
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
		else:
			embed.set_footer(text=f'{ctx.author.name} | This message will automatically be deleted in 10 seconds to protect your ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)

			await asyncio.sleep(10)
			await message.delete()

	@tss_cmd.command(name='list')
	@commands.guild_only()
	async def list_blobs(self, ctx):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = json.loads((await cursor.fetchall())[0][0])
			except IndexError:
				devices = dict()
				await db.execute('INSERT INTO autotss(user, devices, enabled) VALUES(?,?,?)', (ctx.author.id, json.dumps(devices), True))
				await db.commit()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title=f"{ctx.author.name}'s Saved Blobs")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		blobs_saved = int()
		for x in devices.keys():
			blobs = devices[x]['saved_blobs']
			blobs_saved += len(blobs)

			blobs_list = list()

			for i in blobs.keys():
				blobs_list.append(f"`iOS {blobs[i]['version']} | {blobs[i]['buildid']}`")

			embed.add_field(name=devices[x]['name'], value=', '.join(blobs_list), inline=False)

		num_devices = len(devices)
		embed.description = f"**{blobs_saved} blob{'s' if blobs_saved != 1 else ''}** saved for **{num_devices} device{'s' if num_devices != 1 else ''}**."

		await ctx.send(embed=embed)

	@tss_cmd.command(name='save')
	@commands.guild_only()
	async def save_blobs(self, ctx):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ? AND enabled = ?', (ctx.author.id, True)) as cursor:
			try:
				devices = json.loads((await cursor.fetchall())[0][0])
			except IndexError:
				devices = dict()
				await db.execute('INSERT INTO autotss(user, devices, enabled) VALUES(?,?,?)', (ctx.author.id, json.dumps(devices), True))
				await db.commit()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Save Blobs', description='Saving blobs for all of your devices...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		blobs_saved = int()
		devices_saved_for = int()

		for x in devices.keys():
			current_blobs_saved = blobs_saved

			signed_buildids = await self.get_signed_buildids(devices[x]['identifier'])
			saved_versions = devices[x]['saved_blobs']

			for buildid in signed_buildids:
				if any(buildid == saved_versions[firm]['buildid'] for firm in saved_versions):
					continue

				version = await self.buildid_to_version(devices[x]['identifier'], buildid)

				async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
					manifest = await asyncio.to_thread(self.get_manifest, devices[x]['identifier'], buildid, tmpdir)
					saved_blob = await self.save_blob(devices[x], version, manifest)

				if saved_blob is True:
					saved_versions[len(saved_versions)] = {
						'version': version,
						'buildid': buildid, 
						'type': 'Release'
					}

					blobs_saved += 1
				else:
					failed_info = f"{devices[x]['name']} - iOS {version} | {buildid}"
					embed.add_field(name='Error', value=f'Failed to save blobs for `{failed_info}`.', inline=False)
					await message.edit(embed=embed)

			devices[x]['saved_blobs'] = saved_versions

			if blobs_saved > current_blobs_saved:
				devices_saved_for += 1

			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), ctx.author.id))
				await db.commit()

		if blobs_saved == 0:
			description = 'No new blobs were saved.'
		else:
			description = f"Saved **{blobs_saved} blob{'s' if blobs_saved != 1 else ''}** for **{devices_saved_for} device{'s' if devices_saved_for != 1 else ''}**."

		embed.add_field(name='Finished!', value=description, inline=False)
		await message.edit(embed=embed)

	@tss_cmd.command(name='downloadall')
	@commands.guild_only()
	@commands.is_owner()
	async def download_all_blobs(self, ctx):
		await ctx.message.delete()

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss') as cursor:
			all_devices = await cursor.fetchall()

		num_devices = int()
		for user_devices in all_devices:
			user_devices = json.loads(user_devices[0])

			num_devices += len(user_devices)

		if num_devices == 0:
			embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Download All Blobs', description='Uploading blobs...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		try:
			message = await ctx.author.send(embed=embed)
		except:
			embed = discord.Embed(title='Error', description="You don't have DMs enabled.")
			await ctx.send(embed=embed)
			return

		async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
			await self.os.mkdir(f'{tmpdir}/Blobs')

			for folder in glob.glob('Data/Blobs/*'):
				try:
					await self.shutil.copytree(folder, f"{tmpdir}/Blobs/{folder.split('/')[-1]}")
				except FileNotFoundError:
					pass

			shutil.make_archive(f'{tmpdir}_blobs', 'zip', tmpdir)
			url = await self.upload_file(f'{tmpdir}_blobs.zip', 'blobs.zip')

		embed = discord.Embed(title='Download All Blobs', description=f'[Click here]({url}).')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

	@tss_cmd.command(name='saveall')
	@commands.guild_only()
	@commands.is_owner()
	async def save_all_blobs(self, ctx):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
			all_devices = await cursor.fetchall()

		num_devices = int()
		for user_devices in all_devices:
			user_devices = json.loads(user_devices[1])

			num_devices += len(user_devices)

		if num_devices == 0:
			embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Save Blobs', description='Saving blobs for all devices...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		blobs_saved = int()
		devices_saved_for = int()

		for user_devices in all_devices:
			user = user_devices[0]
			devices = json.loads(user_devices[1])

			for x in devices.keys():
				current_blobs_saved = blobs_saved

				signed_buildids = await self.get_signed_buildids(devices[x]['identifier'])
				saved_versions = devices[x]['saved_blobs']

				for buildid in signed_buildids:
					if any(buildid == saved_versions[firm]['buildid'] for firm in saved_versions):
						continue

					version = await self.buildid_to_version(devices[x]['identifier'], buildid)

					async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
						manifest = await asyncio.to_thread(self.get_manifest, devices[x]['identifier'], buildid, tmpdir)
						saved_blob = await self.save_blob(devices[x], version, manifest)

					if saved_blob is True:
						saved_versions[len(saved_versions)] = {
							'version': version,
							'buildid': buildid, 
							'type': 'Release'
						}

						blobs_saved += 1
					else:
						failed_info = f"{devices[x]['name']} - iOS {version} | {buildid}"
						embed.add_field(name='Error', value=f'Failed to save blobs for `{failed_info}`.', inline=False)
						await message.edit(embed=embed)

				devices[x]['saved_blobs'] = saved_versions

				if blobs_saved > current_blobs_saved:
					devices_saved_for += 1

				async with aiosqlite.connect('Data/autotss.db') as db:
					await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), user))
					await db.commit()

		if blobs_saved == 0:
			description = 'No new blobs were saved.'
		else:
			description = f"Saved **{blobs_saved} blob{'s' if blobs_saved != 1 else ''}** for **{devices_saved_for} device{'s' if devices_saved_for != 1 else ''}**."

		embed.add_field(name='Finished!', value=description, inline=False)
		await message.edit(embed=embed)

def setup(bot):
	bot.add_cog(TSS(bot))
