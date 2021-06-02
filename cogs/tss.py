from discord.ext import commands, tasks
import aiohttp
import aiofiles, aiofiles.os
import aiosqlite
import asyncio
import discord
import glob
import os
import shutil


class TSS(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.save_blobs_loop.start()

	async def upload_file(self, file, name):
		async with aiohttp.ClientSession() as session, aiofiles.open(file, 'rb') as f, session.put(f'https://up.psty.io/{name}', data=f) as response:
			resp = await response.text()

		return resp.splitlines()[-1].split(':', 1)[1][1:]

	async def get_signed_buildids(self, device):
		api_url = f'https://api.ipsw.me/v4/device/{device[3]}?type=ipsw'
		async with aiohttp.ClientSession() as session, session.get(api_url) as resp:
			api = await resp.json()

		return [api['firmwares'][x]['buildid'] for x in range(len(api['firmwares'])) if api['firmwares'][x]['signed'] == True]

	async def buildid_to_version(self, device, buildid):
		api_url = f'https://api.ipsw.me/v4/device/{device[3]}?type=ipsw'
		async with aiohttp.ClientSession() as session, session.get(api_url) as resp:
			api = await resp.json()

		return next(x['version'] for x in list(api['firmwares']) if x['buildid'] == buildid)

	async def save_blob(self, device, buildid):
		version = await self.buildid_to_version(device, buildid)

		async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
			args = ['tsschecker', '-d', device[3],  '-e', f'0x{device[4]}', '--buildid', buildid, '-B', device[5], '-s', '--save-path', tmpdir, '--nocache']
			cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
			stdout, stderr = await cmd.communicate()

			if 'Saved shsh blobs!' not in stdout.decode():
				return False

			save_path = '/'.join(('Data/Blobs', device[4], version, 'no-apnonce'))
			os.makedirs(save_path, exist_ok=True)

			for blob in glob.glob('/'.join((tmpdir, '*'))):
				await aiofiles.os.rename(blob, '/'.join((save_path, blob.split('/')[-1])))

			if device[7] is not None:
				args.append('--apnonce')
				args.append(device[7])

				cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
				stdout, stderr = await cmd.communicate()

				if 'Saved shsh blobs!' not in stdout.decode():
					return False

				save_path = '/'.join(('Data/Blobs', device[4], version, device[7]))
				os.makedirs(save_path, exist_ok=True)

				for blob in glob.glob('/'.join((tmpdir, '*'))):
					await aiofiles.os.rename(blob, '/'.join((save_path, blob.split('/')[-1])))

		return True

	@tasks.loop(seconds=1800)  # Change this value to modify the frequency at which blobs will be saved at
	async def save_blobs_loop(self):
		await self.bot.wait_until_ready()
		await asyncio.sleep(1)

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss') as cursor:
			devices = await cursor.fetchall()

		blobs_saved = int()
		devices_saved_for = int()

		for x in range(len(devices)):
			signed_buildids = await self.get_signed_buildids(devices[x])
			saved_buildids = eval(devices[x][6])

			for i in list(signed_buildids):
				if i in saved_buildids:
					signed_buildids.pop(signed_buildids.index(i))
					continue

				saved_blob = await self.save_blob(devices[x], i)

				if saved_blob is True:
					saved_buildids.append(i)
				else:
					signed_buildids.pop(signed_buildids.index(i))
					print(f'Failed to save blobs for `{devices[x][2]} - iOS {await self.buildid_to_version(devices[x], i)} | {i}`.')

			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('UPDATE autotss SET blobs = ? WHERE device_num = ? AND userid = ?', (str(saved_buildids), devices[x][0], devices[x][1]))
				await db.commit()

			blobs_saved += len(signed_buildids)

			if len(signed_buildids) > 0:
				devices_saved_for += 1

		if blobs_saved == 0:
			print('[AUTO] No blobs need to be saved.')
		else:
			print(f"[AUTO] Saved {blobs_saved} blob{'s' if blobs_saved != 1 else ''} for {devices_saved_for} device{'s' if devices_saved_for != 1 else ''}.")

	@commands.group(name='tss', invoke_without_command=True)
	@commands.guild_only()
	async def tss_cmd(self, ctx):
		embed = discord.Embed(title='TSS Commands')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		embed.add_field(name='Save blobs for all of your devices', value=f'`{ctx.prefix}tss save`', inline=False)
		embed.add_field(name='List all blobs saved for your devices', value=f'`{ctx.prefix}tss list`', inline=False)
		embed.add_field(name='Download all blobs saved for your devices', value=f'`{ctx.prefix}tss download`', inline=False)

		if await ctx.bot.is_owner(ctx.author):
			embed.add_field(name='Download blobs saved for all devices', value=f'`{ctx.prefix}tss downloadall`', inline=False)
			embed.add_field(name='Save blobs for all devices', value=f'`{ctx.prefix}tss saveall`', inline=False)

		await ctx.send(embed=embed)

	@tss_cmd.command(name='save')
	@commands.guild_only()
	async def save_blobs(self, ctx):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,)) as cursor:
			devices = await cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Save Blobs', description='Saving blobs for all of your devices...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		blobs_saved = int()
		devices_saved_for = int()

		for x in range(len(devices)):
			signed_buildids = await self.get_signed_buildids(devices[x])
			saved_buildids = eval(devices[x][6])

			for i in list(signed_buildids):
				if i in saved_buildids:
					signed_buildids.pop(signed_buildids.index(i))
					continue

				saved_blob = await self.save_blob(devices[x], i)

				if saved_blob is True:
					saved_buildids.append(i)
				else:
					signed_buildids.pop(signed_buildids.index(i))
					embed.add_field(name='Error', value=f'Failed to save blobs for `{devices[x][2]} - iOS {await self.buildid_to_version(devices[x], i)} | {i}`.', inline=False)
					await message.edit(embed=embed)

			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('UPDATE autotss SET blobs = ? WHERE device_num = ? AND userid = ?', (str(saved_buildids), devices[x][0], ctx.author.id))
				await db.commit()

			blobs_saved += len(signed_buildids)

			if len(signed_buildids) > 0:
				devices_saved_for += 1

		if blobs_saved == 0:
			description = 'No new blobs were saved.'
		else:
			description = f"Saved **{blobs_saved} blob{'s' if blobs_saved != 1 else ''}** for **{devices_saved_for} device{'s' if devices_saved_for != 1 else ''}**."

		embed.add_field(name='Finished!', value=description, inline=False)

		await message.edit(embed=embed)

	@tss_cmd.command(name='list')
	@commands.guild_only()
	async def list_blobs(self, ctx):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,)) as cursor:
			devices = await cursor.fetchall()

		if devices == 0:
			embed = discord.Embed(title='Error', description='You have no devices added.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title=f"{ctx.author.name}'s Saved Blobs")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		total_blobs = int()
		num_devices = len(devices)

		for x in range(num_devices):
			blobs = eval(devices[x][6])
			total_blobs += blobs

			blobs_str = str()

			for i in blobs:
				version = await self.buildid_to_version(devices[x], i)
				blobs_str += f'`iOS {version} | {i}`, '

			embed.add_field(name=devices[x][2], value=blobs_str[:-2], inline=False)

		embed.description = f"**{total_blobs} blob{'s' if total_blobs != 1 else ''}** saved for **{num_devices} device{'s' if num_devices != 1 else ''}**."

		await ctx.send(embed=embed)

	@tss_cmd.command(name='download')
	@commands.guild_only()
	async def download_blobs(self, ctx): #TODO: Make fully async
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,)) as cursor:
			devices = await cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Download Blobs', description='Uploading blobs...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
			await aiofiles.os.mkdir('/'.join((tmpdir, 'Blobs')))

			for ecid in [devices[x][4] for x in range(len(devices))]:
				try:
					shutil.copytree('/'.join(('Data/Blobs', ecid)), '/'.join((tmpdir, 'Blobs', ecid)))
				except FileNotFoundError:
					pass

			shutil.make_archive(f'{tmpdir}_blobs', 'zip', tmpdir)
			url = await self.upload_file(f'{tmpdir}_blobs.zip', 'blobs.zip')

		embed = discord.Embed(title='Download Blobs', description=f'[Click here]({url}).')
		embed.set_footer(text=f'{ctx.author.name} | This message will automatically be deleted in 10 seconds to protect your ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		await asyncio.sleep(10)
		await message.delete()

	@tss_cmd.command(name='downloadall')
	@commands.guild_only()
	@commands.is_owner()
	async def download_all_blobs(self, ctx):
		await ctx.message.delete()

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss', (ctx.author.id,)) as cursor:
			devices = await cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Download Blobs', description='Uploading blobs...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		try:
			message = await ctx.author.send(embed=embed)
		except:
			embed = discord.Embed(title='Error', description="You don't have DMs enabled.")
			await ctx.send(embed=embed)
			return

		async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
			await aiofiles.os.mkdir('/'.join((tmpdir, 'Blobs')))

			for ecid in [devices[x][4] for x in range(len(devices))]:
				try:
					shutil.copytree('/'.join(('Data/Blobs', ecid)), '/'.join((tmpdir, 'Blobs', ecid)))
				except FileNotFoundError:
					pass

			shutil.make_archive(f'{tmpdir}_blobs', 'zip', tmpdir)
			url = await self.upload_file(f'{tmpdir}_blobs.zip', 'blobs.zip')

		embed = discord.Embed(title='Download Blobs', description=f'[Click here]({url}).')
		embed.set_footer(text=f'{ctx.author.name} | This message will automatically be deleted in 10 seconds to protect all ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		await asyncio.sleep(10)
		await message.delete()

	@tss_cmd.command(name='saveall')
	@commands.guild_only()
	@commands.is_owner()
	async def save_all_blobs(self, ctx):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss') as cursor:
			devices = await cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Save All Blobs', description=f"Saving all blobs for {len(devices)} device{'s' if len(devices) != 1 else ''}...")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		blobs_saved = int()
		devices_saved_for = int()

		for x in range(len(devices)):
			signed_buildids = await self.get_signed_buildids(devices[x])
			saved_buildids = eval(devices[x][6])

			for i in list(signed_buildids):
				if i in saved_buildids:
					signed_buildids.pop(signed_buildids.index(i))
					continue

				saved_blob = await self.save_blob(devices[x], i)

				if saved_blob is True:
					saved_buildids.append(i)
				else:
					signed_buildids.pop(signed_buildids.index(i))
					embed.add_field(name='Error', value=f'Failed to save blobs for `{devices[x][2]} - iOS {await self.buildid_to_version(devices[x], i)} | {i}`.', inline=False)
					await message.edit(embed=embed)

			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('UPDATE autotss SET blobs = ? WHERE device_num = ? AND userid = ?', (str(saved_buildids), devices[x][0], devices[x][1]))
				await db.commit()

			blobs_saved += len(signed_buildids)

			if len(signed_buildids) > 0:
				devices_saved_for += 1

		if blobs_saved == 0:
			description = 'No new blobs were saved.'
		else:
			description = f"Saved **{blobs_saved} blob{'s' if blobs_saved != 1 else ''}** for **{devices_saved_for} device{'s' if devices_saved_for != 1 else ''}**."

		embed.add_field(name='Finished!', value=description, inline=False)

		await message.edit(embed=embed)

def setup(bot):
	bot.add_cog(TSS(bot))
