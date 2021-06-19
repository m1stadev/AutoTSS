from aioify import aioify
from discord.ext import commands, tasks
import aiohttp
import aiosqlite
import asyncio
import discord
import json
import os


class Events(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.os = aioify(os, name='os')
		self.utils = self.bot.get_cog('Utils')
		self.auto_clean_db.start()
		self.auto_invalid_device_check.start()

	@tasks.loop(minutes=5)
	async def auto_clean_db(self):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss') as cursor:
			data = await cursor.fetchall()

		for user_devices in data:
			devices = json.loads(user_devices[0])
			
			if devices == list():
				async with aiosqlite.connect('Data/autotss.db') as db:
					await db.execute('DELETE FROM autotss WHERE devices = ?', (user_devices[0],))
					await db.commit()

	@auto_clean_db.before_loop
	async def before_auto_clean_db(self):
		await self.bot.wait_until_ready()
		await asyncio.sleep(3) # If first run, give on_ready() some time to create the database

	@tasks.loop(hours=72)
	async def auto_invalid_device_check(self, ctx): # If any users are saving SHSH blobs for A12+ devices without using custom apnonces, attempt to DM them saying they need to re-add the device
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * FROM autotss') as cursor:
			data = await cursor.fetchall()

		invalid_devices = dict()

		async with aiohttp.ClientSession() as session:
			for userinfo in data:
				userid = userinfo[0]
				devices = json.loads(userinfo[1])

				for device in devices:
					cpid = await self.utils.get_cpid(session, device['identifier'], device['boardconfig'])

					if (32800 <= cpid < 35072) and (device['apnonce'] is None):
						if userid not in invalid_devices.keys():
							invalid_devices[userid] = list()

						invalid_devices[userid].append(device)

		for userid in invalid_devices.keys():
			user = await self.bot.fetch_user(userid)

			embed = discord.Embed(title='Hey!')
			embed.description = 'One or more of your devices were added incorrectly to AutoTSS, and are saving **non-working SHSH blobs**. \
				To fix this, remove these devices then re-add them with custom apnonces:'

			for device in invalid_devices[userid]:
				device_info = [
					f"Device Identifier: `{device['identifier']}`",
					f"ECID: `{device['ecid']}`",
					f"Boardconfig: `{device['boardconfig']}`"
				]

				if device['generator'] is not None:
					device_info.append(f"Custom generator: `{device['generator']}`")

				embed.add_field(name=f"`{device['name']}`", value='\n'.join(device_info), inline=False)

				try:
					await user.send(embed=embed)
				except: # The device is already saving invalid blobs, so no point in continuing to save blobs for it if we can't contact the user about it.
					await self.shutil.rmtree(f"Data/Blobs/{device['ecid']}")

					async with aiosqlite.connect('Data/autotss.db') as db:
						async with db.execute('SELECT devices FROM autotss WHERE user = ?', (userid,)) as cursor:
							devices = json.loads((await cursor.fetchone())[0])

						devices.pop(next(devices.index(x) for x in devices if x['ecid'] == device['ecid']))

						await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), userid))
						await db.commit()

	@auto_invalid_device_check.before_loop
	async def before_invalid_device_check(self):
		await self.bot.wait_until_ready()
		await asyncio.sleep(3) # If first run, give on_ready() some time to create the database

	@commands.Cog.listener()
	async def on_guild_join(self, guild):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db:
			async with db.execute('SELECT prefix from prefix WHERE guild = ?', (guild.id,)) as cursor:
				if await cursor.fetchone() is not None:
					await db.execute('DELETE from prefix where guild = ?', (guild.id,))
					await db.commit()

			await db.execute('INSERT INTO prefix(guild, prefix) VALUES(?,?)', (guild.id, 'b!'))
			await db.commit()

		embed = discord.Embed(title="Hi, I'm AutoTSS!")
		embed.add_field(name='What do I do?', value='I can automatically save SHSH blobs for all of your iOS devices!', inline=False)
		embed.add_field(name='Prefix', value='My prefix is `b!`. To see what I can do, run `b!help`!', inline=False)
		embed.add_field(name='Creator', value=(await self.bot.fetch_user(728035061781495878)).mention, inline=False)
		embed.add_field(name='Disclaimer', value='This should NOT be your only source for saving blobs. I am not at fault for any issues you may experience with AutoTSS.', inline=False)
		embed.add_field(name='Notes', value='- There is a limit of 10 devices per user.\n- You must be in a server with AutoTSS, or your SHSH blobs will no longer be automatically saved. This **does not** have to be the same server that you added your devices to AutoTSS in.\n- Blobs are automatically saved every 30 minutes.', inline=False)
		embed.add_field(name='Source Code', value="AutoTSS's source code can be found on [GitHub](https://github.com/m1stadev/AutoTSS).", inline=False)
		embed.add_field(name='Support', value='For any questions about AutoTSS, join my [Discord](https://m1sta.xyz/discord).', inline=False)
		embed.set_thumbnail(url=self.bot.user.avatar_url_as(static_format='png'))

		for channel in guild.text_channels:
			try:
				await channel.send(embed=embed)
				break
			except:
				pass

	@commands.Cog.listener()
	async def on_guild_remove(self, guild):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('DELETE from prefix where guild = ?', (guild.id,))
			await db.commit()

	@commands.Cog.listener()
	async def on_member_join(self, member):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE user = ?', (member.id,)) as cursor:
			data = await cursor.fetchone()

		if data is None:
			return

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('UPDATE autotss SET enabled = ? WHERE user = ?', (True, member.id))
			await db.commit()

		await self.utils.update_device_count()

	@commands.Cog.listener()
	async def on_member_remove(self, member):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE user = ?', (member.id,)) as cursor:
			data = await cursor.fetchone()

		if data is None:
			return

		if len(member.mutual_guilds) == 0:
			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('UPDATE autotss SET enabled = ? WHERE user = ?', (False, member.id))
				await db.commit()

			await self.utils.update_device_count()

	@commands.Cog.listener()
	async def on_message(self, message):
		await self.bot.wait_until_ready()

		if message.channel.type == discord.ChannelType.private:
			return

		prefix = await self.utils.get_prefix(message.guild.id)

		if message.content.replace(' ', '').replace('!', '') == self.bot.user.mention:
			embed = discord.Embed(title='AutoTSS', description=f'My prefix is `{prefix}`. To see what I can do, run `{prefix}help`!')
			embed.set_footer(text=message.author.name, icon_url=message.author.avatar_url_as(static_format='png'))
			await message.channel.send(embed=embed)

	@commands.Cog.listener()
	async def on_ready(self):
		await self.os.makedirs('Data', exist_ok=True)

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('''
				CREATE TABLE IF NOT EXISTS autotss(
				user INTEGER,
				devices JSON,
				enabled BOOLEAN
				)
				''')
			await db.commit()

			await db.execute('''
				CREATE TABLE IF NOT EXISTS prefix(
				guild INTEGER,
				prefix TEXT
				)
				''')
			await db.commit()

		await self.utils.update_device_count()
		print('AutoTSS is now online.')

	@commands.Cog.listener()
	async def on_command_error(self, ctx, error):
		await self.bot.wait_until_ready()

		embed = discord.Embed(title='Error')

		if ctx.message.channel.type == discord.ChannelType.private:
			embed.description = 'AutoTSS cannot be used in DMs. Please use AutoTSS in a Discord server.'
			await ctx.send(embed=embed)
			return

		prefix = await self.utils.get_prefix(ctx.guild.id)
		if isinstance(error, commands.CommandNotFound):
			if ctx.prefix.replace('!', '').replace(' ', '') == self.bot.user.mention:
				return

			embed.description = f"That command doesn't exist! Use `{prefix}help` to see all the commands I can run."
			await ctx.send(embed=embed)
		
		elif isinstance(error, commands.MaxConcurrencyReached):
			embed.description = f"You can't run `{prefix + ctx.command.qualified_name}` more than once at the same time!"
			await ctx.send(embed=embed)

		elif isinstance(error, commands.errors.CommandInvokeError):
			if isinstance(error.original, discord.errors.Forbidden):
				embed.description = f"I don't have the proper permissions to run correctly! \
					Please ping an Administrator and tell them to kick & re-invite me using \
					[this]({self.utils.invite}) link to fix this issue."

				message_sent = False
				for channel in ctx.guild.text_channels:
					try:
						await channel.send(embed=embed)
						message_sent = True
						break
					except:
						pass

				if message_sent:
					return

				try:
					embed.description = f"I don't have the proper permissions to run correctly! \
						Please kick me from `{ctx.guild.name}` & re-invite me using \
						[this]({self.utils.invite}) link to fix this issue."

					await ctx.guild.owner.send(embed=embed)
				except: # We can't tell the user to tell an admin to fix our permissions, we can't DM the owner to fix it, we might as well leave.
					await ctx.guild.leave()

			else:
				raise error

		elif isinstance(error, commands.errors.NotOwner):
			return

		else:
			raise error


def setup(bot):
	bot.add_cog(Events(bot))
