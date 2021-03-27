from discord.ext import commands, tasks
import aiohttp
import aiofiles
import ast
import asyncio
import discord
import os
import shutil
import sqlite3
import tempfile


class TSS(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.save_all_blobs.start()

	async def upload_zip(self, file, name):
		async with aiofiles.open(file, 'rb') as f:
			async with aiohttp.ClientSession() as session:
				async with session.put(f'https://up.psty.io/{name}', data=f) as response:
					resp = await response.text()

		return resp.splitlines()[-1].split(':', 1)[1][1:]

	async def get_signed_buildids(self, device):
		signed_buildids = list()
		async with aiohttp.ClientSession() as session:
			async with session.get(f'https://api.ipsw.me/v4/device/{device[3]}?type=ipsw') as resp:
				api = await resp.json()

		for x in [x for x in range(len(api['firmwares'])) if api['firmwares'][x]['signed'] == True]:
				signed_buildids.append(api['firmwares'][x]['buildid'])

		return signed_buildids

	async def buildid_to_version(self, device, buildid):
		async with aiohttp.ClientSession() as session:
			async with session.get(f'https://api.ipsw.me/v4/device/{device[3]}?type=ipsw') as resp:
				api = await resp.json()

		return next(x['version'] for x in list(api['firmwares']) if x['buildid'] == buildid)

	async def save_blob(self, device, buildid):
		version = await self.buildid_to_version(device, buildid)
		save_path = f'Data/Blobs/{device[4]}/{version}/{buildid}/no-apnonce'
		os.makedirs(save_path, exist_ok=True)

		cmd = await asyncio.create_subprocess_exec('tsschecker', '-d', device[3],  '-e', f'0x{device[4]}', '--buildid', buildid, '-B', device[5], '-s', '--save-path', save_path, stdout=asyncio.subprocess.PIPE)
		stdout, stderr = await cmd.communicate()

		if 'Saved shsh blobs!' not in stdout.decode():
			return False

		if device[7] is not None:
			save_path = f'Data/Blobs/{device[4]}/{version}/{buildid}/{device[7]}'
			os.makedirs(save_path, exist_ok=True)
			cmd = await asyncio.create_subprocess_exec('tsschecker', '-d', device[3],  '-e', f'0x{device[4]}', '--buildid', buildid, '-B', device[5], '-s', '--save-path', save_path, '--apnonce', device[7], stdout=asyncio.subprocess.PIPE)
			stdout, stderr = await cmd.communicate()

			if 'Saved shsh blobs!' not in stdout.decode():
				return False

		return True

	@tasks.loop(seconds=1800)  # Change this value to modify the frequency at which blobs will be saved at
	async def save_all_blobs(self):
		await self.bot.wait_until_ready()
		await asyncio.sleep(1)

		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		cursor.execute('SELECT * from autotss')
		devices = cursor.fetchall()

		saved_blobs = int()
		for x in range(len(devices)):

			signed_buildids = await self.get_signed_buildids(devices[x])
			saved_buildids = ast.literal_eval(devices[x][6])
			for i in list(signed_buildids):
				if i in saved_buildids:
					signed_buildids.pop(signed_buildids.index(i))

			signed_versions = list()
			for i in signed_buildids:
				signed_versions.append(await self.buildid_to_version(devices[x], i))

			for i in list(signed_buildids):
				blob = await self.save_blob(devices[x], i)

				if blob is False:
					signed_versions.pop(signed_buildids.index(i))
					signed_buildids.pop(signed_buildids.index(i))
				else:
					saved_buildids.append(i)

			cursor.execute('UPDATE autotss SET blobs = ? WHERE device_num = ? AND userid = ?', (str(saved_buildids), devices[x][0], devices[x][1]))
			db.commit()

			saved_blobs += len(signed_buildids)

		if saved_blobs == 0:
			print('[AUTO] No blobs need to be saved.')
		else:
			print(f'[AUTO] Saved {saved_blobs} blobs.')

		db.close()

	@commands.group(name='tss', invoke_without_command=True)
	@commands.guild_only()
	async def tss_cmd(self, ctx):
		embed = discord.Embed(title='TSS Commands')
		embed.add_field(name='Manually save blobs for all of your devices', value=f'`{ctx.prefix}tss saveall`', inline=False)
		embed.add_field(name='Manually save blobs for one of your devices', value=f'`{ctx.prefix}tss save`', inline=False)
		embed.add_field(name='List all of the blobs saved for your devices', value=f'`{ctx.prefix}tss list`', inline=False)
		embed.add_field(name='Download all of the blobs saved for your devices', value=f'`{ctx.prefix}tss download`', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		if await ctx.bot.is_owner(ctx.author):
			embed.add_field(name='Download all blobs saved for all devices', value=f'`{ctx.prefix}tss downloadall`', inline=False)
			embed.add_field(name='Save blobs for all devices', value=f'`{ctx.prefix}tss saveitall`', inline=False)

		await ctx.send(embed=embed)

	@tss_cmd.command(name='save')
	@commands.guild_only()
	async def save_single_blob(self, ctx):
		timeout_embed = discord.Embed(title='Save Blobs', description='No response given in 1 minute, cancelling.')
		timeout_embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		cursor.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,))
		devices = cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Save Blobs')
			embed.add_field(name='Error', value='You have no devices added.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Save Blobs', description="Choose the number of the device you'd like to save blobs for.\nType `cancel` to cancel.")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		for x in range(len(devices)):
			device_info = f'Name: `{devices[x][2]}`\nDevice Identifier: `{devices[x][3]}`\nBoard Config: `{devices[x][5]}`'
			if devices[x][7] is not None:
				device_info += f'\nCustom apnonce: `{devices[x][7]}`'

			embed.add_field(name=devices[x][0], value=device_info, inline=False)

		message = await ctx.send(embed=embed)

		try:
			answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		if answer.content == 'cancel' or answer.content.lower().startswith(ctx.prefix):
			try:
				await answer.delete()
				await message.delete()
			except discord.errors.NotFound:
				pass

			return

		try:
			int(answer.content)
		except ValueError:
			embed = discord.Embed(title='Save Blobs')
			embed.add_field(name='Error', value='Invalid input given.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await message.edit(embed=embed)
			return

		num = int(answer.content)
		try:
			await answer.delete()
		except discord.errors.NotFound:
			pass

		if not 0 < num <= len(devices):
			embed = discord.Embed(title='Save Blobs')
			embed.add_field(name='Error', value=f'Device `{num}` does not exist.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await message.edit(embed=embed)
			return

		cursor.execute('SELECT * from autotss WHERE device_num = ? AND userid = ?', (num, ctx.author.id))
		device = cursor.fetchall()[0]

		embed = discord.Embed(title='Save Blobs', description=f'Saving blobs for `{device[2]}`...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await message.edit(embed=embed)

		signed_buildids = await self.get_signed_buildids(device)
		saved_buildids = ast.literal_eval(device[6])
		for x in list(signed_buildids):
			if x in saved_buildids:
				signed_buildids.pop(signed_buildids.index(x))

		signed_versions = list()
		for x in signed_buildids:
			signed_versions.append(await self.buildid_to_version(device, x))

		for x in list(signed_buildids):
			blob = await self.save_blob(device, x)

			if blob is False:
				embed.add_field(name='Error', value=f'Failed to save blobs for `iOS {signed_versions[signed_buildids.index(x)]} | {x}`.')
				embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
				await message.edit(embed=embed)

				signed_versions.pop(signed_buildids.index(x))
				signed_buildids.pop(signed_buildids.index(x))
			else:
				saved_buildids.append(x)

		cursor.execute('UPDATE autotss SET blobs = ? WHERE device_num = ? AND userid = ?', (str(saved_buildids), device[0], ctx.author.id))
		db.commit()

		saved_versions = str()
		for x in range(len(signed_buildids)):
			saved_versions += f'`iOS {signed_versions[x]} | {signed_buildids[x]}`, '

		if saved_versions == '':
			description = 'No blobs were saved.'
		else:
			description = f'Saved blobs for {saved_versions[:-2]}.'

		embed = discord.Embed(title='Save Blobs', description=description)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await message.edit(embed=embed)
		db.close()

	@tss_cmd.command(name='saveall')
	@commands.guild_only()
	async def save_all_device_blobs(self, ctx):
		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		cursor.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,))
		devices = cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Save All Blobs')
			embed.add_field(name='Error', value='You have no devices added.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Save Blobs', description='Saving blobs for all of your devices...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		saved_blobs = int()
		for x in range(len(devices)):
			signed_buildids = await self.get_signed_buildids(devices[x])
			saved_buildids = ast.literal_eval(devices[x][6])
			for i in list(signed_buildids):
				if i in saved_buildids:
					signed_buildids.pop(signed_buildids.index(i))

			signed_versions = list()
			for i in signed_buildids:
				signed_versions.append(await self.buildid_to_version(devices[x], i))

			for i in list(signed_buildids):
				blob = await self.save_blob(devices[x], i)

				if blob is False:
					embed.add_field(name='Error', value=f'Failed to save blobs for `{devices[x][2]} - iOS {signed_versions[signed_buildids.index(i)]} | {i}`.', inline=False)
					await message.edit(embed=embed)

					signed_versions.pop(signed_buildids.index(i))
					signed_buildids.pop(signed_buildids.index(i))
				else:
					saved_buildids.append(i)

			cursor.execute('UPDATE autotss SET blobs = ? WHERE device_num = ? AND userid = ?', (str(saved_buildids), devices[x][0], ctx.author.id))
			db.commit()

			saved_blobs += len(signed_buildids)

		if saved_blobs == 0:
			description = 'No blobs were saved.'
		else:
			description = f"Saved **{saved_blobs} blob{'s' if saved_blobs != 1 else ''}** for **{len(devices)} device{'s' if len(devices) != 1 else ''}**."

		embed.add_field(name='Finished!', value=description, inline=False)
		await message.edit(embed=embed)
		db.close()

	@tss_cmd.command(name='list')
	@commands.guild_only()
	async def list_all_blobs(self, ctx):
		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		cursor.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,))
		devices = cursor.fetchall()

		saved_blobs = int()
		saved_devices = len(devices)

		for x in range(saved_devices):
			saved_blobs += len(ast.literal_eval(devices[x][6]))

		embed = discord.Embed(title=f"{ctx.author.name}'s Saved Blobs", description=f"**{saved_blobs} blob{'s' if saved_blobs != 1 else ''}** saved for **{saved_devices} device{'s' if saved_devices != 1 else ''}**.")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		for x in range(saved_devices):
			blobs = ast.literal_eval(devices[x][6])

			saved_blobs = str()

			for i in blobs:
				version = await self.buildid_to_version(devices[x], i)
				saved_blobs += f'`iOS {version} | {i}`, '

			embed.add_field(name=devices[x][2], value=saved_blobs[:-2], inline=False)

		await ctx.send(embed=embed)
		db.close()

	@tss_cmd.command(name='download')
	@commands.guild_only()
	async def download_all_blobs(self, ctx):
		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		embed = discord.Embed(title='Download Blobs', description='Uploading blobs...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		message = await ctx.send(embed=embed)

		cursor.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,))
		devices = cursor.fetchall()
		db.close()
		ecids = list()

		if len(devices) == 0:
			embed = discord.Embed( title='Download Blobs', inline=False)
			embed.add_field(name='Error', value='You have no devices added.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await message.edit(embed=embed)
			return

		for x in range(len(devices)):
			ecids.append(devices[x][4])

		with tempfile.TemporaryDirectory() as tmpdir:
			os.makedirs(f'{tmpdir}/Blobs')
			for x in ecids:
				try:
					shutil.copytree(f'Data/Blobs/{x}', f'{tmpdir}/Blobs/{x}')
				except FileNotFoundError:
					pass

			shutil.make_archive(f'{tmpdir}_blobs', 'zip', tmpdir)

			url = await self.upload_zip(f'{tmpdir}_blobs.zip', 'blobs.zip')

		embed = discord.Embed(title='Download Blobs', description=f'[Click here]({url}).')
		embed.set_footer(text=f'{ctx.author.name} | This message will automatically be deleted in 10 seconds to protect your ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		await asyncio.sleep(10)
		await message.delete()

	@tss_cmd.command(name='downloadall')
	@commands.guild_only()
	@commands.is_owner()
	async def download_everything(self, ctx):
		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		await ctx.message.delete()

		embed = discord.Embed(title='Download All Blobs', description='Uploading all blobs...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		message = await ctx.author.send(embed=embed)
		cursor.execute('SELECT * from autotss')
		devices = cursor.fetchall()
		db.close()
		ecids = list()

		if len(devices) == 0:
			embed = discord.Embed(title='Download All Blobs', inline=False)
			embed.add_field(name='Error', value='There are no devices added to AutoTSS.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		for x in range(len(devices)):
			ecids.append(devices[x][4])

		with tempfile.TemporaryDirectory() as tmpdir:
			for x in ecids:
				try:
					shutil.copytree(f'Data/Blobs/{x}', f'{tmpdir}/{x}')
				except FileNotFoundError:
					pass

			shutil.make_archive(f'{tmpdir}_blobs', 'zip', tmpdir)
			url = await self.upload_zip(f'{tmpdir}_blobs.zip', 'blobs.zip')

		embed = discord.Embed(title='Download All Blobs', description=f'[Click here]({url}).')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		await asyncio.sleep(10)
		await message.delete()

	@tss_cmd.command(name='saveitall')
	@commands.guild_only()
	@commands.is_owner()
	async def save_everything(self, ctx):
		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		cursor.execute('SELECT * from autotss')
		devices = cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Save Everything')
			embed.add_field(name='Error', value='There are no devices in the database.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Save Everything', description=f"Saving blobs for {len(devices)} device{'s' if len(devices) != 1 else ''}...")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		saved_blobs = int()
		for x in range(len(devices)):
			signed_buildids = await self.get_signed_buildids(devices[x])
			saved_buildids = ast.literal_eval(devices[x][6])
			for i in list(signed_buildids):
				if i in saved_buildids:
					signed_buildids.pop(signed_buildids.index(i))

			signed_versions = list()
			for i in signed_buildids:
				signed_versions.append(await self.buildid_to_version(devices[x], i))

			for i in list(signed_buildids):
				blob = await self.save_blob(devices[x], i)

				if blob is False:
					embed.add_field(name='Error', value=f'Failed to save blobs for `{devices[x][2]} - iOS {signed_versions[signed_buildids.index(i)]} | {i}`.', inline=False)
					await message.edit(embed=embed)

					signed_versions.pop(signed_buildids.index(i))
					signed_buildids.pop(signed_buildids.index(i))
				else:
					saved_buildids.append(i)

			cursor.execute('UPDATE autotss SET blobs = ? WHERE device_num = ? AND userid = ?', (str(saved_buildids), devices[x][0], devices[x][1]))
			db.commit()

			saved_blobs += len(signed_buildids)

		if saved_blobs == 0:
			description = 'No blobs were saved.'
		else:
			description = f"Saved **{saved_blobs} blob{'s' if saved_blobs != 1 else ''}** for **{len(devices)} device{'s' if len(devices) != 1 else ''}**."

		embed.add_field(name='Finished!', value=description, inline=False)
		await message.edit(embed=embed)
		db.close()

def setup(bot):
	bot.add_cog(TSS(bot))
