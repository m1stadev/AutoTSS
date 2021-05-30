from aioify import aioify
from discord.ext import commands
import aiofiles
import aiohttp
import aiosqlite
import asyncio
import discord
import json
import os
import re
import shutil


class Device(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.json = aioify(json, name='json')
		self.os = aioify(os, name='os')
		self.shutil = aioify(shutil, name='shutil')

	async def check_identifier(self, identifier):
		async with aiohttp.ClientSession() as session, session.get('https://api.ipsw.me/v2.1/firmwares.json') as resp:
			if identifier not in (await resp.json())['devices']:
				return False
			else:
				return True

	async def check_boardconfig(self, identifier, boardconfig):
		if boardconfig[-2:] != 'ap':
			return False

		async with aiohttp.ClientSession() as session, session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
			api = await resp.json()

		if not any(x['boardconfig'].lower() == boardconfig for x in api['boards']): # If no boardconfigs for the given device identifier match the boardconfig, then return False
			return False
		else:
			return True

	async def check_name(self, name, user): # This function will return different values based on where it errors out at
		if not 4 <= len(name) <= 20: # Length check
			return 0

		async with aiosqlite.connect('Data/autotss.db') as db: # Make sure the user doesn't have any other devices with the same name added
			async with db.execute('SELECT devices from autotss WHERE user = ?', (user,)) as cursor:
				devices = await self.json.loads((await cursor.fetchall())[0][0])

		if any(devices[x]['name'] == name.lower() for x in devices.keys()):
			return -1

		return True

	async def check_ecid(self, ecid, user):
		if not 9 <= len(ecid) <= 16: # All ECIDs are between 9-16 characters
			return 0

		try:
			int(ecid, 16) # Make sure the ECID provided is hexadecimal, not decimal
		except ValueError or TypeError:
			return 0

		async with aiosqlite.connect('Data/autotss.db') as db: # Make sure the ECID the user provided isn't already a device added to AutoTSS.
			async with db.execute('SELECT devices from autotss WHERE user = ?', (user,)) as cursor:
				devices = (await cursor.fetchall())[0][0]

		if ecid in devices: # There's no need to convert the json string to a dict here
			return -1

		return True

	async def check_apnonce(self, nonce):
		try:
			int(nonce, 16)
		except ValueError or TypeError:
			return False

		if len(nonce) not in (40, 64): # All ApNonce lengths are either 40 characters long, or 64 characters long
			return False

		return True

	async def update_device_count(self):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE enabled = ?', (True,)) as cursor:
			devices = len(await cursor.fetchall())

		await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving blobs for {devices} device{'s' if devices != 1 else ''}"))

	@commands.group(name='device', invoke_without_command=True)
	@commands.guild_only()
	async def device_cmd(self, ctx):
		if ctx.prefix == f'<@!{self.bot.user.id}> ':
			prefix = f'{ctx.prefix}`'
		else:
			prefix = f'`{ctx.prefix}'

		embed = discord.Embed(title='Device Commands')
		embed.add_field(name=f'{prefix}device add`', value='Add a device', inline=False)
		embed.add_field(name=f'{prefix}device remove`', value='Remove a device', inline=False)
		embed.add_field(name=f'{prefix}device list`', value='List your devices', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await ctx.send(embed=embed)

	@device_cmd.command(name='add')
	@commands.guild_only()
	async def add_device(self, ctx):
		timeout_embed = discord.Embed(title='Add Device', description='No response given in 1 minute, cancelling.')
		cancelled_embed = discord.Embed(title='Add Device', description='Cancelled.')

		for embed in (timeout_embed, cancelled_embed):
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		max_devices = 10 #TODO: Export this option to a separate config file

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = await self.json.loads((await cursor.fetchall())[0][1])
			except IndexError:
				devices = dict()
				await db.execute('INSERT INTO autotss(user, devices, enabled) VALUES(?,?,?)', (ctx.author.id, await self.json.dumps(devices), True))
				await db.commit()

		if len(devices) > max_devices and await ctx.bot.is_owner(ctx.author) == False: # Error out if you attempt to add over 'max_devices' devices, and if you're not the owner of the bot
			embed = discord.Embed(title='Error', description=f'You cannot add over {max_devices} devices to AutoTSS.')
			await ctx.send(embed=embed)
			return

		device = dict()

		for x in range(4): # Loop that gets all of the required information to save blobs with from the user
			descriptions = [
				'Enter a name for your device',
				"Enter your device's identifier (e.g. `iPhone6,1`)",
				"Enter your device's ECID (hex)",
				"Enter your device's Board Config (e.g. `n51ap`). \
				This value ends in `ap`, and can be found with [System Info](https://arx8x.github.io/depictions/systeminfo.html) \
				under the `Platform` section, or by running `gssc | grep HWModelStr` in a terminal on your iOS device."
			]

			embed = discord.Embed(title='Add Device', description='\n'.join((descriptions[x], 'Type `cancel` to cancel.')))
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			if x == 0:
				message = await ctx.send(embed=embed)
			else:
				await message.edit(embed=embed)


			# Wait for a response from the user, and error out if the user takes over 1 minute to respond
			try:
				response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
				if x == 0:
					answer = response.content # Don't make the device's name lowercase
				else:
					answer = response.content.lower()

			except asyncio.exceptions.TimeoutError:
				await message.edit(embed=timeout_embed)
				return

			# Delete the message
			try:
				await response.delete()
			except discord.errors.NotFound:
				pass

			if answer.lower() == 'cancel' or answer.lower().startswith(ctx.prefix):
				await message.edit(embed=cancelled_embed)
				return

			# Make sure given information is valid
			if x == 0:
				device['name'] = answer

				name_check = await self.check_name(device['name'], ctx.author.id)
				if name_check != True:
					embed = discord.Embed(title='Error', description = f"Device name `{device['name']}` is not valid.")

					if name_check == 0:
						embed.description += " A device's name must be between 4 and 20 characters."
					elif name_check == -1:
						embed.description += " You cannot use a device's name more than once."

					embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
					await message.edit(embed=embed)
					return

			elif x == 1:
				device['identifier'] = 'P'.join(answer.split('p'))

				identifier_check = await self.check_identifier(device['identifier'])
				if identifier_check is False:
					embed = discord.Embed(title='Error', description=f"Device Identifier `{device['identifier']}` is not valid.")
					embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
					await message.edit(embed=embed)
					return


			elif x == 2:
				if answer.startswith('0x'):
					device['ecid'] = answer[2:]
				else:
					device['ecid'] = answer

				ecid_check = await self.check_ecid(device['ecid'], ctx.author.id)
				if ecid_check != True:
					embed = discord.Embed(title='Error', description=f"Device ECID `{device['ecid']}` is not valid.")
					embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
					if ecid_check == -1:
						embed.description += ' This ECID has already been added to AutoTSS.'

					await message.edit(embed=embed)
					return
			else:
				device['boardconfig'] = answer

				boardconfig_check = await self.check_boardconfig(device['identifier'], device['boardconfig'])
				if boardconfig_check is False:
					embed = discord.Embed(title='Error', description=f"Device boardconfig `{device['boardconfig']}` is not valid.")
					embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
					await message.edit(embed=embed)
					return

		apnonce_description = [
			'Would you like to save blobs with a custom apnonce?',
			'*This is required on A12+ devices due to nonce entanglement, more info [here](https://www.reddit.com/r/jailbreak/comments/f5wm6l/tutorial_repost_easiest_way_to_save_a12_blobs/).*',
			'NOTE: This is **NOT** the same as your **generator**, which begins with `0x` and is 16 characters long.'
		]

		embed = discord.Embed(title='Add Device', description='\n'.join(apnonce_description)) # Ask the user if they'd like to save blobs with a custom ApNonce
		embed.add_field(name='Options', value='Type **Yes** to add a custom apnonce, **cancel** to cancel adding this device, or anything else to skip.', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		try:
			response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
			answer = response.content.lower()
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		try:
			await response.delete()
		except discord.errors.NotFound:
			pass

		if answer == 'yes':
			embed = discord.Embed(title='Add Device', description='Please enter the custom apnonce you wish to save blobs with.\nType `cancel` to cancel.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)

			try:
				response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
				answer = response.content.lower()
			except asyncio.exceptions.TimeoutError:
				await message.edit(embed=timeout_embed)
				return

			try:
				await response.delete()
			except discord.errors.NotFound:
				pass

			if answer == 'cancel' or answer.startswith(ctx.prefix):
				await message.edit(embed=cancelled_embed)
				return

			else:
				device['apnonce'] = answer

				apnonce_check = await self.check_apnonce(device['apnonce'])
				if apnonce_check is False:
					embed = discord.Embed(title='Error', description=f"Device ApNonce `{device['apnonce']}` is not valid.")
					embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
					await message.edit(embed=embed)
					return

		elif answer == 'cancel' or answer.startswith(ctx.prefix):
			await message.edit(embed=cancelled_embed)
			return
		else:
			device['apnonce'] = None


		# Add device information into the database

		devices[len(devices)] = device

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (await self.json.dumps(devices), ctx.author.id))
			await db.commit()

		embed = discord.Embed(title='Add Device', description=f"Device `{device['name']}` added successfully!")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		await self.update_device_count()

	@device_cmd.command(name='remove')
	@commands.guild_only()
	async def remove_device(self, ctx):
		try:
			await ctx.message.delete()
		except discord.errors.NotFound:
			pass

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,)) as cursor:
			devices = await cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Remove Device', description="Choose the number of the device you'd like to remove.\nType `cancel` to cancel.")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		for x in range(len(devices)):
			device_info = f'Name: `{devices[x][2]}`\nDevice Identifier: `{devices[x][3]}`\nBoard Config: `{devices[x][5]}`'
			if devices[x][7] is not None:
				device_info += f'\nCustom apnonce: `{devices[x][7]}`'

			embed.add_field(name=devices[x][0], value=device_info, inline=False)

		message = await ctx.send(embed=embed)

		timeout_embed = discord.Embed(title='Remove Device', description='No response given in 1 minute, cancelling.')
		timeout_embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		try:
			answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		if answer.content == 'cancel' or answer.content.lower().startswith(ctx.prefix):
			try:
				await answer.delete()
			except discord.errors.NotFound:
				pass

			embed = discord.Embed(title='Remove Device', description='Cancelled.')
			await message.edit(embed=embed)
			return

		invalid_embed = discord.Embed(title='Error', description='Invalid input given.')
		invalid_embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		try:
			num = int(answer.content)
		except ValueError:
			await message.edit(embed=invalid_embed)
			return

		try:
			await answer.delete()
		except discord.errors.NotFound:
			pass

		if num not in range(len(devices) + 1):
			await message.edit(embed=invalid_embed)
			return

		async with aiosqlite.connect('Data/autotss.db'), db.execute('SELECT * from autotss WHERE device_num = ? AND userid = ?', (num, ctx.author.id)) as cursor:
			device = (await cursor.fetchall())[0]

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
			await self.os.makedirs('Data/Deleted Blobs', exist_ok=True)
			await self.shutil.copytree(f'Data/Blobs/{device[4]}', f'Data/Deleted Blobs/{device[4]}', dirs_exist_ok=True)  # Just in case someone deletes their device accidentally...
			await self.shutil.rmtree(f'Data/Blobs/{device[4]}')

			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('DELETE from autotss WHERE device_num = ? AND userid = ?', (num, ctx.author.id))
				await db.commit()

				async with db.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,)) as cursor:
					devices = await cursor.fetchall()

					for x in range(len(devices)):
						await db.execute('UPDATE autotss SET device_num = ? WHERE device_num = ? AND userid = ?', (x + 1, devices[x][0], ctx.author.id))
						await db.commit()

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

		await self.update_device_count()

	@device_cmd.command(name='list')
	@commands.guild_only()
	async def list_devices(self, ctx):
		try:
			await ctx.message.delete()
		except discord.errors.NotFound:
			pass

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,)) as cursor:
			devices = await cursor.fetchall()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title=f"{ctx.author.name}'s Devices")

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
