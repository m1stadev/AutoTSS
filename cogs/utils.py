from discord.ext import commands
import aiosqlite
import discord
import json


class Utils(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	async def update_device_count(self):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE enabled = ?', (True,)) as cursor:
			all_devices = (await cursor.fetchall())

		num_devices = int()
		for user_devices in all_devices:
			devices = json.loads(user_devices[0])
			num_devices += len(devices)

		await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving blobs for {num_devices} device{'s' if num_devices != 1 else ''}"))

def setup(bot):
	bot.add_cog(Utils(bot))
