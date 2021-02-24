from discord.ext import commands
import aiohttp
import asyncio
import discord
import os
import re
import shutil
import sqlite3


class Device(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	async def check_identifier(self, identifier):
		try:
			identifier = f"{identifier.split('p')[0]}P{identifier.split('p')[1]}"
		except IndexError:
			return False

		async with aiohttp.ClientSession() as session:
			async with session.get('https://api.ipsw.me/v2.1/firmwares.json/condensed') as resp:
				json = await resp.json()

		if identifier not in json['devices']:
			return False

		return identifier

	async def check_boardconfig(self, identifier, boardconfig):
		if boardconfig[-2:] != 'ap':
			return False

		async with aiohttp.ClientSession() as session:
			async with session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
				json = await resp.json()

		if identifier.startswith('iPhone8,') or identifier.startswith('iPad6,') or identifier.startswith('iPad7,') or identifier.startswith('iPad11,'):
			if not json['boardconfig'].startswith(boardconfig[:3]):
				return False

		else:
			if json['boardconfig'].lower() != boardconfig:
				return False

		return True

	async def check_name(self, name):
		name_check = re.findall('^[a-zA-Z0-9 ]*$', name)
		if len(name_check) == 0:
			return False

		if not 5 <= len(name) <= 20:
			return False
		
		return True

	async def check_ecid(self, ecid):
		if not 9 < len(ecid) < 17:
			return False

		try:
			int(ecid, 16)
		except ValueError or TypeError:
			return False

		return True

	async def check_apnonce(self, nonce):
		try:
			int(nonce, 16)
		except ValueError or TypeError:
			return False

		if len(nonce) not in (40, 64):
			return False

		return True

	@commands.group(name='device', invoke_without_command=True)
	@commands.guild_only()
	async def device_cmd(self, ctx):
		embed = discord.Embed(title='Device Commands')
		embed.add_field(name=f'`{ctx.prefix}device add`', value='Add a device', inline=False)
		embed.add_field(name=f'`{ctx.prefix}device remove`', value='Remove a device', inline=False)
		embed.add_field(name=f'`{ctx.prefix}device list`', value='List your devices', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await ctx.send(embed=embed)

	@device_cmd.command(name='add')
	@commands.guild_only()
	async def add_device(self, ctx):
		timeout_embed = discord.Embed(title='Add Device', description='No response given in 1 minute, cancelling.')
		timeout_embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		max_devices = 10  # Change this to change the maximum allowed devices for each user

		cursor.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,))
		devices = cursor.fetchall()

		if len(devices) > max_devices and ctx.author != commands.is_owner:
			embed = discord.Embed(title='Add Device')
			embed.add_field(name='Error', value=f'You cannot add over {max_devices} devices to AutoTSS.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await ctx.send(embed=embed)
			return

		device = {'num': len(devices) + 1, 'userid': ctx.author.id}

		for x in range(4):
			if x == 0:
				description = 'Enter a name for your device'
			elif x == 1:
				description = "Enter your device's identifier (e.g. `iPhone8,4`)"
			elif x == 2:
				description = "Enter your device's ECID (hex only)"
			else:
				description = "Enter your device's Board Config (e.g. `n51ap`). This value ends in `ap`, and can be found with [System Info](https://arx8x.github.io/depictions/systeminfo.html) under the `Platform` section, or by running `gssc | grep HWModelStr` in a terminal on your iOS device."

			embed = discord.Embed(title='Add Device', description=f'{description}\nType `cancel` to cancel.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			if x == 0:
				message = await ctx.send(embed=embed)
			else:
				await message.edit(embed=embed)

			try:
				answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
			except asyncio.exceptions.TimeoutError:
				await message.edit(embed=timeout_embed)
				return

			if answer.content == 'cancel':
				embed = discord.Embed(title='Add Device', description='Cancelled.')
				await message.edit(embed=embed)

				try:
					await answer.delete()
				except discord.errors.NotFound:
					pass

				return

			if x == 0:
				device['name'] = answer.content
			elif x == 1:
				device['identifier'] = answer.content.lower()
			elif x == 2:
				if answer.content.lower().startswith('0x'):
					device['ecid'] = answer.content.lower()[2:]
				else:
					device['ecid'] = answer.content.lower()
			else:
				device['boardconfig'] = answer.content.lower()

			try:
				await answer.delete()
			except discord.errors.NotFound:
				pass

		embed = discord.Embed(title='Add Device', description='Would you like to save blobs with a custom apnonce?\n*This is required on A12+ devices due to nonce entanglement, more info [here](https://www.reddit.com/r/jailbreak/comments/f5wm6l/tutorial_repost_easiest_way_to_save_a12_blobs/).*')
		embed.add_field(name='Options', value='Type **Yes** to add a custom apnonce, **cancel** to cancel adding this device, or anything else to skip.', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		try:
			answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		if answer.content.lower() == 'yes':
			embed = discord.Embed(title='Add Device', description='Please enter the custom apnonce you wish to save blobs with.\nType `cancel` to cancel.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)

			try:
				apnonce = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
			except asyncio.exceptions.TimeoutError:
				await message.edit(embed=timeout_embed)
				return

			if apnonce.content.lower() == 'cancel' or apnonce.content.lower().startswith(ctx.prefix):
				embed = discord.Embed(title='Add Device', description='Cancelled.')
				await message.edit(embed=embed)

				try:
					await apnonce.delete()
					await answer.delete()
				except discord.errors.NotFound:
					pass
					
				return

			device['apnonce'] = apnonce.content.lower()

			try:
				await apnonce.delete()
			except discord.errors.NotFound:
				pass

		elif answer.content.lower() == 'cancel' or answer.content.lower().startswith(ctx.prefix):
			embed = discord.Embed(title='Add Device', description='Cancelled.')

			await message.edit(embed=embed)
			return
		else:
			device['apnonce'] = None

		try:
			await answer.delete()
		except discord.errors.NotFound:
			pass

		embed = discord.Embed(title='Add Device', description='Verifying input...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		name_check = await self.check_name(device['name'])

		if name_check is False:
			embed = discord.Embed(title='Add Device')
			embed.add_field(name='Error', value=f"Device name `{device['name']}` is not valid. A device's name must only contain letters, numbers, and spaces, and must be between 5 and 20 characters.", inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		identifier = await self.check_identifier(device['identifier'])

		if identifier is False:
			embed = discord.Embed(title='Add Device')
			embed.add_field(name='Error', value=f"Device Identifier `{device['identifier']}` does not exist.", inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		device['identifier'] = identifier
		boardconfig = await self.check_boardconfig(device['identifier'], device['boardconfig'])

		if boardconfig is False:
			embed = discord.Embed(title='Add Device')
			embed.add_field(name='Error', value=f"Device `{device['name']}`'s board config `{device['boardconfig']}` does not exist.", inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		ecid = await self.check_ecid(device['ecid'])

		if ecid is False:
			embed = discord.Embed(title='Add Device')
			embed.add_field(name='Error', value=f"Device `{device['name']}`'s ECID `{device['ecid']}` is not valid.", inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		if device['apnonce'] is not None:
			apnonce = await self.check_apnonce(device['apnonce'])

			if apnonce is False:
				embed = discord.Embed(title='Add Device')
				embed.add_field(name='Error', value=f"Device `{device['name']}`'s apnonce `{device['apnonce']}` is not valid.", inline=False)
				embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
				await message.edit(embed=embed)
				return

		cursor.execute('SELECT ecid from autotss')
		ecids = cursor.fetchall()
		if any(x[0] == device['ecid'] for x in ecids):
			embed = discord.Embed(title='Add Device')
			embed.add_field(name='Error', value="This device's ECID is already in my database.", inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		cursor.execute('SELECT name from autotss WHERE userid = ?', (ctx.author.id,))
		names = cursor.fetchall()

		if any(x[0].lower() == device['name'].lower() for x in names):
			embed = discord.Embed(title='Add Device')
			embed.add_field(name='Error', value="You've already added a device with this name.", inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		val = (device['num'], device['userid'], device['name'], device['identifier'], device['ecid'], device['boardconfig'], str(list()), device['apnonce'])
		cursor.execute('INSERT INTO autotss(device_num, userid, name, identifier, ecid, boardconfig, blobs, apnonce) VALUES(?,?,?,?,?,?,?,?)', val)
		db.commit()

		embed = discord.Embed(title='Add Device', description=f"Device `{device['name']}` added successfully!")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		cursor.execute('SELECT ecid from autotss')
		devices = len(cursor.fetchall())
		db.close()

		await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving blobs for {devices} device{'s' if devices != 1 else ''}"))

	@device_cmd.command(name='remove')
	@commands.guild_only()
	async def remove_device(self, ctx):
		timeout_embed = discord.Embed(title='Remove Device', description='No response given in 1 minute, cancelling.')
		timeout_embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		try:
			await ctx.message.delete()
		except discord.errors.NotFound:
			pass

		cursor.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,))
		devices = cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Remove Device')
			embed.add_field(name='Error', value='You have no devices added.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Remove Device', description="Choose the number of the device you'd like to remove.\nType `cancel` to cancel.")

		for x in range(len(devices)):
			device_info = f'Name: `{devices[x][2]}`\nDevice Identifier: `{devices[x][3]}`\nBoard Config: `{devices[x][5]}`'
			if devices[x][7] is not None:
				device_info += f'\nCustom apnonce: `{devices[x][7]}`'

			embed.add_field(name=devices[x][0], value=device_info, inline=False)

		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		try:
			answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		if answer.content == 'cancel' or answer.content.lower().startswith(ctx.prefix):
			embed = discord.Embed(title='Remove Device', description='Cancelled.')
			await message.edit(embed=embed)

			try:
				await answer.delete()
			except discord.errors.NotFound:
				pass

			return

		embed = discord.Embed(title='Remove Device')
		embed.add_field(name='Error', value='Invalid input given.', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		try:
			num = int(answer.content)
		except ValueError:
			await message.edit(embed=embed)
			return

		if num not in range(len(devices) + 1):
			await message.edit(embed=embed)
			return

		cursor.execute('SELECT * from autotss WHERE device_num = ? AND userid = ?', (num, ctx.author.id))
		device = cursor.fetchall()[0]

		embed = discord.Embed(title='Remove Device', description=f'Are you **absolutely sure** you want to delete `{device[2]}`?')
		embed.add_field(name='Options', value='Type **Yes** to delete your device & blobs from AutoTSS, or anything else to cancel.', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await message.edit(embed=embed)

		try:
			answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		if answer.content.lower() == 'yes':
			os.makedirs('Data/Deleted Blobs', exist_ok=True)
			shutil.copytree(f'Data/Blobs/{device[4]}', f'Data/Deleted Blobs/{device[4]}', dirs_exist_ok=True)  # Just in case someone deletes their device accidentally...
			shutil.rmtree(f'Data/Blobs/{device[4]}')

			cursor.execute('DELETE from autotss WHERE device_num = ? AND userid = ?', (num, ctx.author.id))
			db.commit()

			cursor.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,))
			devices = cursor.fetchall()

			for x in range(len(devices)):
				cursor.execute('UPDATE autotss SET device_num = ? WHERE device_num = ? AND userid = ?', (x + 1, devices[x][0], ctx.author.id))
				db.commit()

			embed = discord.Embed(title='Remove Device', description=f'Device `{device[2]}` removed.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await message.edit(embed=embed)

		else:
			embed = discord.Embed(title='Remove Device', description='Cancelled.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await message.edit(embed=embed)

		try:
			await answer.delete()
		except discord.errors.NotFound:
			pass


		cursor.execute('SELECT ecid from autotss')
		devices = len(cursor.fetchall())
		db.close()

		await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving blobs for {devices} device{'s' if devices != 1 else ''}"))

	@device_cmd.command(name='list')
	@commands.guild_only()
	async def list_devices(self, ctx):
		db = sqlite3.connect('Data/autotss.db')
		cursor = db.cursor()

		try:
			await ctx.message.delete()
		except discord.errors.NotFound:
			pass

		cursor.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,))
		devices = cursor.fetchall()

		embed = discord.Embed(title=f"{ctx.author.name}'s Devices")

		if len(devices) == 0:
			embed.add_field(name='Error', value='You have no devices added.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await ctx.send(embed=embed)
			return

		for x in range(len(devices)):
			device_info = f'Device Identifier: `{devices[x][3]}`\nECID: ||`{devices[x][4]}`||\nBoard Config: `{devices[x][5]}`'
			if devices[x][7] is not None:
				device_info += f'\nCustom apnonce: `{devices[x][7]}`'

			embed.add_field(name=f'Name: {devices[x][2]}', value=device_info, inline=False)

		embed.set_footer(text=f'{ctx.author.name} | This message will automatically be deleted in 10 seconds to protect your ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		await asyncio.sleep(10)
		try:
			await message.delete()
		except discord.errors.NotFound:
			pass


def setup(bot):
	bot.add_cog(Device(bot))
