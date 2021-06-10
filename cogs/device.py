from aioify import aioify
from discord.ext import commands
import aiohttp
import aiosqlite
import asyncio
import discord
import json
import os
import shutil


class Device(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.json = aioify(json, name='json')
		self.os = aioify(os, name='os')
		self.shutil = aioify(shutil, name='shutil')
		self.utils = self.bot.get_cog('Utils')

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

	@commands.group(name='device', invoke_without_command=True)
	@commands.guild_only()
	async def device_cmd(self, ctx):
		if ctx.prefix == f'<@!{self.bot.user.id}> ':
			prefix = f'{ctx.prefix}`'
		else:
			prefix = f'`{ctx.prefix}'

		embed = discord.Embed(title='Device Commands')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		embed.add_field(name='Add a device', value=f'{prefix}device add`', inline=False)
		embed.add_field(name='Remove a device', value=f'{prefix}device remove`', inline=False)
		embed.add_field(name='List your devices', value=f'{prefix}device list`', inline=False)

		await ctx.send(embed=embed)


	@device_cmd.command(name='add')
	@commands.guild_only()
	async def add_device(self, ctx):
		timeout_embed = discord.Embed(title='Add Device', description='No response given in 1 minute, cancelling.')
		cancelled_embed = discord.Embed(title='Add Device', description='Cancelled.')

		for embed in (timeout_embed, cancelled_embed):
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		max_devices = 10 #TODO: Export this option to a separate config file

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = await self.json.loads((await cursor.fetchall())[0][0])
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
				response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60)
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
			response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60)
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
				response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60)
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

		device['saved_blobs'] = dict()


		# Add device information into the database

		devices[len(devices)] = device

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (await self.json.dumps(devices), ctx.author.id))
			await db.commit()

		embed = discord.Embed(title='Add Device', description=f"Device `{device['name']}` added successfully!")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		await self.utils.update_device_count()

	@device_cmd.command(name='remove')
	@commands.guild_only()
	async def remove_device(self, ctx):
		invalid_embed = discord.Embed(title='Error', description='Invalid input given.')
		timeout_embed = discord.Embed(title='Remove Device', description='No response given in 1 minute, cancelling.')

		for x in (invalid_embed, timeout_embed):
			x.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = await self.json.loads((await cursor.fetchall())[0][0])
			except IndexError:
				devices = dict()
				await db.execute('INSERT INTO autotss(user, devices, enabled) VALUES(?,?,?)', (ctx.author.id, await self.json.dumps(devices), True))
				await db.commit()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Remove Device', description="Choose the number of the device you'd like to remove.\nType `cancel` to cancel.")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		for x in devices.keys():
			device_info = [
				f"Name: `{devices[x]['name']}`",
				f"Device Identifier: `{devices[x]['identifier']}`",
				f"Boardconfig: `{devices[x]['boardconfig']}`"
			]

			if devices[x]['apnonce'] is not None:
				device_info.append(f"Custom ApNonce: `{devices[x]['apnonce']}`")

			embed.add_field(name=int(x) + 1, value='\n'.join(device_info), inline=False)

		message = await ctx.send(embed=embed)

		try:
			response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60)
			answer = response.content.lower()
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		try:
			await response.delete()
		except:
			pass

		if answer == 'cancel' or answer.startswith(ctx.prefix):
			embed = discord.Embed(title='Remove Device', description='Cancelled.')
			await message.edit(embed=embed)
			return

		try:
			num = str(int(answer) - 1)
		except ValueError:
			await message.edit(embed=invalid_embed)
			return

		if num not in devices.keys():
			await message.edit(embed=invalid_embed)
			return

		embed = discord.Embed(title='Remove Device', description=f"Are you **absolutely sure** you want to delete `{devices[num]['name']}`?")
		embed.add_field(name='Options', value='Type **yes** to delete your device & blobs from AutoTSS, or anything else to cancel.', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await message.edit(embed=embed)

		try:
			response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60)
			answer = response.content.lower()
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		try:
			await response.delete()
		except discord.errors.NotFound:
			pass

		if answer == 'yes':
			await self.os.makedirs(f'Data/Deleted Blobs/{ctx.author.id}', exist_ok=True)

			if await self.os.path.exists(f"Data/Blobs/{devices[num]['ecid']}"): # If for some reason, you've added a device, had blobs save for it, remove it, then do that *again*,
				if not await self.os.path.exists(f"Data/Deleted Blobs/{ctx.author.id}/{devices[num]['ecid']}"): # then don't even bother backing up the new blobs.
					await self.shutil.copytree(
						f"Data/Blobs/{devices[num]['ecid']}",
						f"Data/Deleted Blobs/{ctx.author.id}/{devices[num]['ecid']}",
						dirs_exist_ok=True
					)

				await self.shutil.rmtree(f"Data/Blobs/{devices[num]['ecid']}")

			embed = discord.Embed(title='Remove Device', description=f"Device `{devices[num]['name']}` removed.")
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			del devices[num]
			new_devices = dict()
			for d in list(devices.keys()):
				new_devices[len(new_devices)] = devices[d]

			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (await self.json.dumps(new_devices), ctx.author.id))
				await db.commit()

			await message.edit(embed=embed)
			await self.utils.update_device_count()

		else:
			embed = discord.Embed(title='Remove Device', description='Cancelled.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await message.edit(embed=embed)

	@device_cmd.command(name='list')
	@commands.guild_only()
	async def list_devices(self, ctx):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = await self.json.loads((await cursor.fetchall())[0][0])
			except IndexError:
				devices = dict()
				await db.execute('INSERT INTO autotss(user, devices, enabled) VALUES(?,?,?)', (ctx.author.id, await self.json.dumps(devices), True))
				await db.commit()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title=f"{ctx.author.name}'s Devices")

		for x in devices.keys():
			device_info = [
				f"Device Identifier: `{devices[x]['identifier']}`",
				f"ECID: ||`{devices[x]['ecid']}`||",
				f"Boardconfig: `{devices[x]['boardconfig']}`"
			]

			if devices[x]['apnonce'] is not None:
				device_info.append(f"Custom ApNonce: `{devices[x]['apnonce']}`")

			embed.add_field(name=f"`{devices[x]['name']}`", value='\n'.join(device_info), inline=False)

		embed.set_footer(text=f'{ctx.author.name} | This message will be censored in 10 seconds to protect your ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		await asyncio.sleep(10)

		for x in range(len(embed.fields)):
			field_values = [value for value in embed.fields[x].value.split('\n') if 'ECID' not in value]
			embed.set_field_at(index=x, name=embed.fields[x].name, value='\n'.join(field_values), inline=False)	

		await message.edit(embed=embed)



def setup(bot):
	bot.add_cog(Device(bot))
