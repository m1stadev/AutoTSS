from discord.ext import commands
import aiofiles
import aiohttp
import aiosqlite
import asyncio
import discord
import re
import shutil


class Device(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	async def amakedirs(directory, exist_ok=False):
		folder_str = str()
		if len(directory.split('/')) == 0:
			return

		for folder in directory.split('/'):
			folder_str += folder

			try:
				await aiofiles.mkdir(folder)
			except Exception as error:
				if exist_ok:
					pass
				else:
					raise error


	async def check_identifier(self, identifier):
		identifier = 'P'.join(identifier.split('p'))

		async with aiohttp.ClientSession() as session:
			async with session.get('https://api.ipsw.me/v2.1/firmwares.json') as resp:
				api = await resp.json()

		if identifier not in api['devices']:
			return False

		return identifier

	async def check_boardconfig(self, identifier, boardconfig):
		if boardconfig[-2:] != 'ap':
			return False

		async with aiohttp.ClientSession() as session:
			async with session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
				api = await resp.json()

		if len(api['boards']) > 1:
			if not any(api['boards'][x]['boardconfig'].lower() == boardconfig for x in range(len(api['boards']))):
				return False

		else:
			if api['boards'][0]['boardconfig'].lower() != boardconfig:
				return False

		return True

	async def check_name(self, name):
		if not 4 <= len(name) <= 20: # Length check
			return False

		name_regex = re.findall(r'^[a-zA-Z0-9 ]*$', name) # Regex expression to make sure only allowed characters are in name
		if len(name_regex) == 0:
			return False
		
		return True

	async def check_ecid(self, ecid):
		if not 9 <= len(ecid) <= 16: # All ECIDs are between 9-16 characters
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

		if len(nonce) not in (40, 64): # 32-bit devices' apnonce lengths are 40 characters, 64-bit devices' apnonce lengths are 64 characters
			return False

		return True

	async def update_device_count(self):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT ecid from autotss') as cursor:
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
		timeout_embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		max_devices = 10  #TODO: Export this option to a separate config file

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,)) as cursor:
			devices = await cursor.fetchall()

		if len(devices) > max_devices and await ctx.bot.is_owner(ctx.author) == False: # Error out if you attempt to add over 'max_devices' devices, and if you're not the owner of the bot
			embed = discord.Embed(title='Add Device')
			embed.add_field(name='Error', value=f'You cannot add over {max_devices} devices to AutoTSS.', inline=False)
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

			await ctx.send(embed=embed)
			return

		device = {
			'num': len(devices) + 1,
			'userid': ctx.author.id
			}

		for x in range(4): # Loop that gets all of the required information to save blobs with from the user
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


			# Wait for a response from the user, and error out if the user takes over 1 minute to respond
			try:
				answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
			except asyncio.exceptions.TimeoutError:
				await message.edit(embed=timeout_embed)
				return

			if answer.content == 'cancel':
				# Delete the message, unless it has already been deleted
				try:
					await answer.delete()
				except discord.errors.NotFound:
					pass

				embed = discord.Embed(title='Add Device', description='Cancelled.')
				await message.edit(embed=embed)
				return


			# Parse information into dict
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

		embed = discord.Embed(title='Add Device', description='Would you like to save blobs with a custom apnonce?\n*This is required on A12+ devices due to nonce entanglement, more info [here](https://www.reddit.com/r/jailbreak/comments/f5wm6l/tutorial_repost_easiest_way_to_save_a12_blobs/).*\nNOTE: This is **NOT** the same as your **generator**, which begins with `0x` and is 16 characters long.')
		embed.add_field(name='Options', value='Type **Yes** to add a custom apnonce, **cancel** to cancel adding this device, or anything else to skip.', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		try:
			answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		if answer.content.lower() == 'yes':
			try:
				await answer.delete()
			except discord.errors.NotFound:
				pass

			embed = discord.Embed(title='Add Device', description='Please enter the custom apnonce you wish to save blobs with.\nType `cancel` to cancel.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)

			try:
				apnonce = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
			except asyncio.exceptions.TimeoutError:
				await message.edit(embed=timeout_embed)
				return

			if apnonce.content.lower() == 'cancel' or apnonce.content.lower().startswith(ctx.prefix):
				try:
					await apnonce.delete()
				except discord.errors.NotFound:
					pass

				embed = discord.Embed(title='Add Device', description='Cancelled.')
				await message.edit(embed=embed)
					
				return

			else:
				try:
					await apnonce.delete()
				except discord.errors.NotFound:
					pass

				device['apnonce'] = apnonce.content.lower()

		elif answer.content.lower() == 'cancel' or answer.content.lower().startswith(ctx.prefix):
			try:
				await answer.delete()
			except discord.errors.NotFound:
				pass

			embed = discord.Embed(title='Add Device', description='Cancelled.')
			await message.edit(embed=embed)
			return
		else:
			try:
				await answer.delete()
			except discord.errors.NotFound:
				pass

			device['apnonce'] = None

		embed = discord.Embed(title='Add Device', description='Verifying input...')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		# Check user-provided input and make sure it's valid

		embed = discord.Embed(title='Add Device')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		name_check = await self.check_name(device['name'])
		if name_check is False:
			embed.add_field(name='Error', value=f"Device name `{device['name']}` is not valid. A device's name must only contain letters, numbers, and spaces, and must be between 4 and 20 characters.", inline=False)

		identifier = await self.check_identifier(device['identifier'])
		if identifier is False:
			embed.add_field(name='Error', value=f"Device Identifier `{device['identifier']}` does not exist.", inline=False)

		device['identifier'] = identifier

		boardconfig = await self.check_boardconfig(device['identifier'], device['boardconfig'])
		if boardconfig is False:
			embed.add_field(name='Error', value=f"Device `{device['name']}`'s board config `{device['boardconfig']}` does not exist.", inline=False)
			return

		ecid = await self.check_ecid(device['ecid'])

		if ecid is False:
			embed.add_field(name='Error', value=f"Device `{device['name']}`'s ECID `{device['ecid']}` is not valid.", inline=False)
			return

		if device['apnonce'] is not None:
			apnonce = await self.check_apnonce(device['apnonce'])
			if apnonce is False:
				embed.add_field(name='Error', value=f"Device `{device['name']}`'s apnonce `{device['apnonce']}` is not valid.", inline=False)
				return

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT ecid from autotss') as cursor:
			ecids = await cursor.fetchall()

		if any(x[0] == device['ecid'] for x in ecids):
			embed.add_field(name='Error', value="This device's ECID is already in my database.", inline=False)

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT name from autotss WHERE userid = ?', (ctx.author.id,)) as cursor:
			names = await cursor.fetchall()

		if any(x[0].lower() == device['name'].lower() for x in names):
			embed.add_field(name='Error', value="You've already added a device with this name.", inline=False)
			return

		if len(embed.fields) > 0:
			await message.edit(embed=embed)
			return

		# Add device information into the database

		device_info = (device['num'], device['userid'], device['name'], device['identifier'], device['ecid'], device['boardconfig'], str(list()), device['apnonce'])

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('INSERT INTO autotss(device_num, userid, name, identifier, ecid, boardconfig, blobs, apnonce) VALUES(?,?,?,?,?,?,?,?)', device_info)
			await db.commit()

		embed = discord.Embed(title='Add Device', description=f"Device `{device['name']}` added successfully!")
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		await self.update_device_count()

	@device_cmd.command(name='remove')
	@commands.guild_only()
	async def remove_device(self, ctx):
		timeout_embed = discord.Embed(title='Remove Device', description='No response given in 1 minute, cancelling.')
		timeout_embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		try:
			await ctx.message.delete()
		except discord.errors.NotFound:
			pass

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE userid = ?', (ctx.author.id,)) as cursor:
			devices = await cursor.fetchall()

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
			try:
				await answer.delete()
			except discord.errors.NotFound:
				pass

			embed = discord.Embed(title='Remove Device', description='Cancelled.')
			await message.edit(embed=embed)
			return

		invalid_embed = discord.Embed(title='Remove Device')
		invalid_embed.add_field(name='Error', value='Invalid input given.', inline=False)
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
			await self.amakedirs('Data/Deleted Blobs', exist_ok=True)
			shutil.copytree(f'Data/Blobs/{device[4]}', f'Data/Deleted Blobs/{device[4]}', dirs_exist_ok=True)  # Just in case someone deletes their device accidentally...
			shutil.rmtree(f'Data/Blobs/{device[4]}')

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
