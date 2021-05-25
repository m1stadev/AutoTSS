from discord.ext import commands
import aiofiles
import aiosqlite
import discord
import os
import shutil


class Events(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

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

		if guild.system_channel:
			channel = guild.system_channel
		else:
			channel = self.bot.get_channel(guild.text_channels[0].id)

		user = await self.bot.fetch_user(728035061781495878)

		embed = discord.Embed(title="Hi, I'm AutoTSS!")
		embed.add_field(name='What do I do?', value='I can automatically save SHSH blobs for all of your iOS devices!', inline=False)
		embed.add_field(name='Prefix', value='My prefix is `b!`. To see what I can do, run `b!help`!', inline=False)
		embed.add_field(name='Creator', value=user.mention, inline=False)
		embed.add_field(name='Disclaimer', value='This should NOT be your only source for saving blobs. I am not at fault for any issues you may experience with AutoTSS.', inline=False)
		embed.add_field(name='Notes', value='- There is a limit of 10 devices per user.\n- You must be in a server with AutoTSS, or your devices & blobs will be deleted. This **does not** have to be the same server that you added your devices to AutoTSS in.\n- Blobs are automatically saved every 30 minutes.', inline=False)
		embed.add_field(name='Source Code', value="AutoTSS's source code can be found on [GitHub](https://github.com/m1stadev/AutoTS).", inline=False)
		embed.add_field(name='Support', value='For any questions about AutoTSS, join my [Discord](https://m1sta.xyz/discord).', inline=False)
		embed.set_thumbnail(url=self.bot.user.avatar_url_as(static_format='png'))

		await channel.send(embed=embed)

	@commands.Cog.listener()
	async def on_guild_remove(self, guild):
		await self.bot.wait_until_ready()

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('DELETE from prefix where guild = ?', (guild.id,))
			await db.commit()

	@commands.Cog.listener()
	async def on_member_remove(self, member):  # Don't bother saving blobs for a user if the user doesn't share any servers with the bot.
		await self.bot.wait_until_ready()

		if self.bot.get_user(member.id) is not None:
			pass

		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE userid = ?', (member.id,)) as cursor:
			devices = await cursor.fetchall()

		if len(devices) == 0:
			return

		try:
			await aiofiles.os.mkdir('Data/Deleted Blobs')
		except:
			pass

		for x in range(len(devices)):
			if not os.path.isdir(f'Data/Blobs/{devices[x][4]}'):
				continue

			shutil.copytree(f'Data/Blobs/{devices[x][4]}', f'Data/Deleted Blobs/{devices[x][4]}', dirs_exist_ok=True)  # Just in case someone deletes their device accidentally...
			shutil.rmtree(f'Data/Blobs/{devices[x][4]}')


		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('DELETE * from autotss WHERE userid = ?', (member.id,))
			await db.commit()

			async with db.execute('SELECT ecid from autotss') as cursor:
				devices = len(await cursor.fetchall())

		await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving blobs for {devices} device{'s' if devices != 1 else ''}"))

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
		os.makedirs('Data', exist_ok=True)

		async with aiosqlite.connect('Data/autotss.db') as db:
			await db.execute('''
				CREATE TABLE IF NOT EXISTS autotss(
				device_num INTEGER,
				userid INTEGER,
				name TEXT,
				identifier TEXT,
				ecid TEXT,
				boardconfig TEXT,
				blobs TEXT,
				apnonce TEXT
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

			async with db.execute('SELECT ecid from autotss') as cursor:
				devices = len(await cursor.fetchall())

		await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving blobs for {devices} device{'s' if devices != 1 else ''}"))
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
