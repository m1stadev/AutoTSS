from discord.ext import commands, tasks
from aioify import aioify
import aiofiles
import aiosqlite
import asyncio
import discord
import json
import os

class Events(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.check_users_loop.start()
		self.os = aioify(os, name='os')

	async def update_device_count(self):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE enabled = ?', (True,)) as cursor:
			devices = (await cursor.fetchall())

		device_count = int()
		for user_devices in devices:
			device_count += len(json.loads(user_devices[0]))

		await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving blobs for {device_count} device{'s' if device_count != 1 else ''}"))

	@tasks.loop(seconds=300)
	async def check_users_loop(self):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss') as cursor:
			data = await cursor.fetchall()

		for user_info in data:
			user = await self.bot.fetch_user(user_info[0])

			if (len(user.mutual_guilds) > 0) and (bool(user_info[2]) == False): # If the user shares at least one guild with the bot, but blob saving is still disabled for some reason
				db_args = (True, user.id)
			elif (len(user.mutual_guilds) == 0) and (bool(user_info[2]) == True): # Vice-versa
				db_args = (False, user.id)
			else:
				continue

			async with aiosqlite.connect('Data/autotss.db') as db:
				await db.execute('UPDATE autotss SET enabled = ? WHERE user = ?', db_args)
				await db.commit()
			
		await self.update_device_count()

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
		embed.add_field(name='Notes', value='- There is a limit of 10 devices per user.\n- You must be in a server with AutoTSS, or your devices & blobs will be deleted. This **does not** have to be the same server that you added your devices to AutoTSS in.\n- Blobs are automatically saved every 30 minutes.', inline=False)
		embed.add_field(name='Source Code', value="AutoTSS's source code can be found on [GitHub](https://github.com/m1stadev/AutoTSS).", inline=False)
		embed.add_field(name='Support', value='For any questions about AutoTSS, join my [Discord](https://m1sta.xyz/discord).', inline=False)
		embed.set_thumbnail(url=self.bot.user.avatar_url_as(static_format='png'))

		for ch in guild.text_channels:
			channel = self.bot.get_channel(ch.id)

			try:
				await channel.send(embed=embed)
				break
			except:
				continue

	@commands.Cog.listener()
	async def on_guild_remove(self, guild):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('DELETE from prefix where guild = ?', (guild.id,))
			await db.commit()

	@commands.Cog.listener()
	async def on_member_join(self, member):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (member.id,)) as cursor:
			devices = await cursor.fetchall()

		if devices is None:
			return

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('UPDATE autotss SET enabled = ? WHERE user = ?', (True, member.id))
			await db.commit()

		await self.update_device_count()

	@commands.Cog.listener()
	async def on_member_remove(self, member):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (member.id,)) as cursor:
			devices = await cursor.fetchall()

		if devices is None:
			return

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('UPDATE autotss SET enabled = ? WHERE user = ?', (False, member.id))
			await db.commit()

		await self.update_device_count()

	@commands.Cog.listener()
	async def on_message(self, message):
		await self.bot.wait_until_ready()

		if message.channel.type is discord.ChannelType.private:
			return

		async with aiosqlite.connect('Data/autotss.db') as db:
			async with db.execute('SELECT prefix from prefix WHERE guild = ?', (message.guild.id,)) as cursor:
				prefix = await cursor.fetchone()
				if prefix is None:
					await db.execute('INSERT INTO prefix(guild, prefix) VALUES(?,?)', (message.guild.id, 'b!'))
					await db.commit()
					
					prefix = 'b!'
				else:
					prefix = prefix[0]

		if message.content.replace(' ', '').replace('!', '') == self.bot.user.mention:
			embed = discord.Embed(title='AutoTSS', description=f'My prefix is `{prefix}`. To see what I can do, run `{prefix}help`!')
			embed.set_footer(text=message.author.name, icon_url=message.author.avatar_url_as(static_format='png'))
			await message.channel.send(embed=embed)

	@commands.Cog.listener()
	async def on_ready(self):
		try:
			await self.os.mkdir('Data')
		except FileExistsError:
			pass

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

		await self.update_device_count()
		print('AutoTSS is now online.')

	@commands.Cog.listener()
	async def on_command_error(self, ctx, error):
		await self.bot.wait_until_ready()
		if isinstance(error, commands.CommandNotFound):
			if ctx.prefix.replace('!', '').replace(' ', '') == self.bot.user.mention:
				return

			embed = discord.Embed(title='Error', description=f"That command doesn't exist! Use `{ctx.prefix}help` to see all the commands I can run.")
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
		else:
			raise error


def setup(bot):
	bot.add_cog(Events(bot))
