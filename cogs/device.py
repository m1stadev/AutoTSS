from aioify import aioify
from discord.ext import commands
import aiofiles
import aiohttp
import aiosqlite
import asyncio
import discord
import json
import shutil


class Device(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.shutil = aioify(shutil, name='shutil')
		self.utils = self.bot.get_cog('Utils')

	@commands.group(name='device', invoke_without_command=True)
	@commands.guild_only()
	async def device_cmd(self, ctx: commands.Context) -> None:
		prefix = await self.utils.get_prefix(ctx.guild.id)

		embed = discord.Embed(title='Device Commands')
		embed.add_field(name='Add a device', value=f'`{prefix}device add`', inline=False)
		embed.add_field(name='Remove a device', value=f'`{prefix}device remove`', inline=False)
		embed.add_field(name='List your devices', value=f'`{prefix}device list`', inline=False)
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await ctx.send(embed=embed)


	@device_cmd.command(name='add')
	@commands.guild_only()
	@commands.max_concurrency(1, per=commands.BucketType.user)
	async def add_device(self, ctx: commands.Context) -> None:
		prefix = await self.utils.get_prefix(ctx.guild.id)

		timeout_embed = discord.Embed(title='Add Device', description='No response given in 1 minute, cancelling.')
		cancelled_embed = discord.Embed(title='Add Device', description='Cancelled.')

		for embed in (timeout_embed, cancelled_embed):
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		max_devices = 10 #TODO: Export this option to a separate config file

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = json.loads((await cursor.fetchone())[0])
			except TypeError:
				devices = list()
				await db.execute('INSERT INTO autotss(user, devices, enabled) VALUES(?,?,?)', (ctx.author.id, json.dumps(devices), True))
				await db.commit()

		if len(devices) > max_devices and await ctx.bot.is_owner(ctx.author) == False: # Error out if you attempt to add over 'max_devices' devices, and if you're not the owner of the bot
			embed = discord.Embed(title='Error', description=f'You cannot add over {max_devices} devices to AutoTSS.')
			await ctx.send(embed=embed)
			return

		device = dict()
		async with aiohttp.ClientSession() as session:
			for x in range(4): # Loop that gets all of the required information to save blobs with from the user
				descriptions = (
					'Enter a name for your device',
					"Enter your device's identifier (e.g. `iPhone6,1`)",
					"Enter your device's ECID (hex)",
					"Enter your device's Board Config (e.g. `n51ap`). \
					This value ends in `ap`, and can be found with [System Info](https://arx8x.github.io/depictions/systeminfo.html) \
					under the `Platform` section, or by running `gssc | grep HWModelStr` in a terminal on your iOS device."
				)

				embed = discord.Embed(title='Add Device', description='\n'.join((descriptions[x], 'Type `cancel` to cancel.')))
				embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

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

				if 'cancel' in answer.lower() or answer.startswith(prefix):
					await message.edit(embed=cancelled_embed)
					return

				# Make sure given information is valid
				if x == 0:
					device['name'] = answer
					name_check = await self.utils.check_name(device['name'], ctx.author.id)
					if name_check != True:
						embed = discord.Embed(title='Error', description = f"Device name `{device['name']}` is not valid.")

						if name_check == 0:
							embed.description += " A device's name must be between 4 and 20 characters."
						elif name_check == -1:
							embed.description += " You cannot use a device's name more than once."

						embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
						await message.edit(embed=embed)
						return

				elif x == 1:
					device['identifier'] = 'P'.join(answer.lower().split('p'))
					if await self.utils.check_identifier(session, device['identifier']) is False:
						embed = discord.Embed(title='Error', description=f"Device Identifier `{device['identifier']}` is not valid.")
						embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
						await message.edit(embed=embed)
						return

				elif x == 2:
					if answer.startswith('0x'):
						device['ecid'] = answer[2:]
					else:
						device['ecid'] = answer

					ecid_check = await self.utils.check_ecid(device['ecid'])
					if ecid_check != True:
						embed = discord.Embed(title='Error', description=f"Device ECID `{device['ecid']}` is not valid.")
						embed.set_footer(text=f'{ctx.author.display_name} | This message will be censored in 5 seconds to protect your ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
						if ecid_check == -1:
							embed.description += ' This ECID has already been added to AutoTSS.'

						await message.edit(embed=embed)
						embed.description = embed.description.replace(f"`{device['ecid']}` ", '')
						embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
						await asyncio.sleep(5)
						await message.edit(embed=embed)
						return

				else:
					device['boardconfig'] = answer
					if await self.utils.check_boardconfig(session, device['identifier'], device['boardconfig']) is False:
						embed = discord.Embed(title='Error', description=f"Device boardconfig `{device['boardconfig']}` is not valid.")
						embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
						await message.edit(embed=embed)
						return

					cpid = await self.utils.get_cpid(session, device['identifier'], device['boardconfig'])

			generator_description = [
				'Would you like to save blobs with a custom generator?',
				'*If being ran on A12+ devices, you **will** need to provide a matching apnonce for SHSH blobs to be saved correctly.*',
				'Guide for jailbroken A12+ devices: [Click here](https://ios.cfw.guide/tss-web#getting-generator-and-apnonce-jailbroken-a12-only)',
				'Guide for nonjailbroken A12+ devices: [Click here](https://ios.cfw.guide/tss-computer#get-your-device-specific-apnonce-and-generator)',
				'This value is hexadecimal, 16 characters long, and begins with `0x`.'
			]

			embed = discord.Embed(title='Add Device', description='\n'.join(generator_description)) # Ask the user if they'd like to save blobs with a custom generator
			embed.add_field(name='Options', value='Type **yes** to add a custom generator, **cancel** to cancel adding this device, or anything else to skip.', inline=False)
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
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
				embed = discord.Embed(title='Add Device', description='Please enter the custom generator you wish to save blobs with.\nType `cancel` to cancel.')
				embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
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

				if 'cancel' in answer or answer.startswith(prefix):
					await message.edit(embed=cancelled_embed)
					return

				else:
					device['generator'] = answer
					if await self.utils.check_generator(device['generator']) is False:
						embed = discord.Embed(title='Error', description=f"Device Generator `{device['generator']}` is not valid.")
						embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
						await message.edit(embed=embed)
						return

			elif 'cancel' in answer or answer.startswith(prefix):
				await message.edit(embed=cancelled_embed)
				return
			else:
				device['generator'] = None

			apnonce_description = [
				'Would you like to save blobs with a custom apnonce?',
			]

			if device['generator'] is not None:
				apnonce_description.append(f"This custom apnonce MUST match with your custom generator `{device['generator']}`, or else your SHSH blobs **will be invalid**.")

			if cpid >= 32800:
				if len(apnonce_description) == 2:
					a12_apnonce_desc = 'This also MUST be done for your device, or else your SHSH blobs **will be invalid**. More info \
						[here](https://www.reddit.com/r/jailbreak/comments/f5wm6l/tutorial_repost_easiest_way_to_save_a12_blobs/).'

				else:
					a12_apnonce_desc = 'This MUST be done for your device, or else your SHSH blobs **will be invalid**. More info \
						[here](https://www.reddit.com/r/jailbreak/comments/f5wm6l/tutorial_repost_easiest_way_to_save_a12_blobs/).'

				apnonce_description.append(a12_apnonce_desc)

			apnonce_description.append('NOTE: This is **NOT** the same as your **generator**, which is hex, begins with `0x`, and is 16 characters long.')

			embed = discord.Embed(title='Add Device', description='\n'.join(apnonce_description)) # Ask the user if they'd like to save blobs with a custom ApNonce
			embed.add_field(name='Options', value='Type **yes** to add a custom apnonce, **cancel** to cancel adding this device, or anything else to skip.', inline=False)
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
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
				embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
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

				if 'cancel' in answer or answer.startswith(prefix):
					await message.edit(embed=cancelled_embed)
					return

				else:
					device['apnonce'] = answer
					if await self.utils.check_apnonce(cpid, device['apnonce']) is False:
						embed = discord.Embed(title='Error', description=f"Device ApNonce `{device['apnonce']}` is not valid.")
						embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
						await message.edit(embed=embed)
						return

			elif 'cancel' in answer or answer.startswith(prefix):
				await message.edit(embed=cancelled_embed)
				return
			else:
				device['apnonce'] = None

			if 32800 <= cpid < 35072 and device['apnonce'] is None: # If A12+ and no apnonce was specified
				embed = discord.Embed(title='Add Device')
				apnonce_warning = (
					'You are attempting to add an A12+ device while choosing to not specify a custom apnonce.',
					'This will save **non-working SHSH blobs**.',
					'Are you sure you want to do this?'
				)

				embed.add_field(name='Warning', value='\n'.join(apnonce_warning), inline=False)
				embed.add_field(name='Options', value='Type **yes** to go back and add a custom apnonce, **cancel** to cancel adding this device, or anything else to skip.', inline=False)
				embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
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
					embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
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

					if 'cancel' in answer or answer.startswith(prefix):
						await message.edit(embed=cancelled_embed)
						return

					else:
						device['apnonce'] = answer
						if await self.utils.check_apnonce(device['apnonce']) is False:
							embed = discord.Embed(title='Error', description=f"Device ApNonce `{device['apnonce']}` is not valid.")
							embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
							await message.edit(embed=embed)
							return

				elif 'cancel' in answer or answer.startswith(prefix):
					await message.edit(embed=cancelled_embed)
					return
				else:
					device['apnonce'] = None

		device['saved_blobs'] = list()

		# Add device information into the database
		devices.append(device)

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), ctx.author.id))
			await db.commit()

		embed = discord.Embed(title='Add Device', description=f"Device `{device['name']}` added successfully!")
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

		await self.utils.update_device_count()

	@device_cmd.command(name='remove')
	@commands.guild_only()
	@commands.max_concurrency(1, per=commands.BucketType.user)
	async def remove_device(self, ctx: commands.Context) -> None:
		prefix = await self.utils.get_prefix(ctx.guild.id)

		cancelled_embed = discord.Embed(title='Remove Device', description='Cancelled.')
		invalid_embed = discord.Embed(title='Error', description='Invalid input given.')
		timeout_embed = discord.Embed(title='Remove Device', description='No response given in 1 minute, cancelling.')

		for x in (cancelled_embed, invalid_embed, timeout_embed):
			x.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = json.loads((await cursor.fetchone())[0])
			except TypeError:
				devices = list()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Remove Device', description="Choose the number of the device you'd like to remove.\nType `cancel` to cancel.")
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		for x in range(len(devices)):
			device_info = [
				f"Name: `{devices[x]['name']}`",
				f"Device Identifier: `{devices[x]['identifier']}`",
				f"Boardconfig: `{devices[x]['boardconfig']}`"
			]

			if devices[x]['apnonce'] is not None:
				device_info.append(f"Custom ApNonce: `{devices[x]['apnonce']}`")

			embed.add_field(name=x + 1, value='\n'.join(device_info), inline=False)

		message = await ctx.send(embed=embed)

		try:
			response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
			answer = response.content.lower()
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		try:
			await response.delete()
		except:
			pass

		if 'cancel' in answer or answer.startswith(prefix):
			await message.edit(embed=cancelled_embed)
			return

		try:
			num = int(answer) - 1
		except:
			await message.edit(embed=invalid_embed)
			return

		if num not in range(len(devices)):
			await message.edit(embed=invalid_embed)
			return

		embed = discord.Embed(title='Remove Device', description=f"Are you **absolutely sure** you want to delete `{devices[num]['name']}`?")
		embed.add_field(name='Options', value='Type **yes** to delete your device & blobs from AutoTSS, or anything else to cancel.', inline=False)
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

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
			embed = discord.Embed(title='Remove Device', description='Removing device...')
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)

			async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
				url = await self.utils.backup_blobs(tmpdir, devices[num]['ecid'])

			if url is None:
				embed = discord.Embed(title='Remove Device', description=f"Device `{devices[num]['name']}` removed.")
				embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
				await message.edit(embed=embed)

			else:
				await self.shutil.rmtree(f"Data/Blobs/{devices[num]['ecid']}")

				embed = discord.Embed(title='Remove Device')
				embed.description = f"Blobs from `{devices[num]['name']}`: [Click here]({url})"
				embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

				try:
					await ctx.author.send(embed=embed)
					embed.description = f"Device `{devices[num]['name']}` removed."
					await message.edit(embed=embed)
				except:
					embed.description = f"Device `{devices[num]['name']}` removed.\nBlobs from `{devices[num]['name']}`: [Click here]({url})"
					embed.set_footer(
						text=f'{ctx.author.display_name} | This message will automatically be deleted in 15 seconds to protect your ECID(s).',
						icon_url=ctx.author.avatar_url_as(static_format='png')
						)

					await message.edit(embed=embed)

					await asyncio.sleep(15)
					await ctx.message.delete()
					await message.delete()

			devices.pop(num)

			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), ctx.author.id))
				await db.commit()

			await message.edit(embed=embed)
			await self.utils.update_device_count()

		else:
			await message.edit(embed=cancelled_embed)

	@device_cmd.command(name='list')
	@commands.guild_only()
	async def list_devices(self, ctx: commands.Context) -> None:
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
			try:
				devices = json.loads((await cursor.fetchone())[0])
			except TypeError:
				devices = list()

		if len(devices) == 0:
			embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title=f"{ctx.author.display_name}'s Devices")

		for device in devices:
			device_info = [
				f"Device Identifier: `{device['identifier']}`",
				f"ECID: ||`{device['ecid']}`||",
				f"Boardconfig: `{device['boardconfig']}`"
			]

			if device['generator'] is not None:
				device_info.append(f"Custom generator: `{device['generator']}`")

			if device['apnonce'] is not None:
				device_info.append(f"Custom ApNonce: `{device['apnonce']}`")

			embed.add_field(name=f"`{device['name']}`", value='\n'.join(device_info), inline=False)

		embed.set_footer(text=f'{ctx.author.display_name} | This message will be censored in 10 seconds to protect your ECID(s).', icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		await asyncio.sleep(10)

		for x in range(len(embed.fields)):
			field_values = [value for value in embed.fields[x].value.splitlines() if 'ECID' not in value]
			embed.set_field_at(index=x, name=embed.fields[x].name, value='\n'.join(field_values), inline=False)
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await message.edit(embed=embed)



def setup(bot):
	bot.add_cog(Device(bot))
