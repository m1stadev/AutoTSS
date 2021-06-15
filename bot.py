#!/usr/bin/env python3

from discord.ext import commands
import aiosqlite
import discord
import glob
import os
import platform
import subprocess
import sys


def bot_token(): 
	if os.getenv('AUTOTSS_TOKEN') is not None:
		return os.getenv('AUTOTSS_TOKEN')
	else:
		sys.exit("[ERROR] Bot token not set in 'AUTOTSS_TOKEN' environment variable. Exiting.")


def check_tsschecker():
	tsschecker_check = subprocess.run('which tsschecker', stdout=subprocess.DEVNULL, shell=True)
	if tsschecker_check.returncode != 0:
		sys.exit('[ERROR] tsschecker is not installed on your system. Exiting.')


async def get_prefix(client, message):
	if message.channel.type is discord.ChannelType.private:
		return 'b!'

	async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT prefix FROM prefix WHERE guild = ?', (message.guild.id,)) as cursor:
		try:
			guild_prefix = (await cursor.fetchone())[0]
		except TypeError:
			await db.execute('INSERT INTO prefix(guild, prefix) VALUES(?,?)', (message.guild.id, 'b!'))
			await db.commit()
			guild_prefix = 'b!'

	return commands.when_mentioned_or(guild_prefix)(client, message)

def main():
	if platform.system() == 'Windows':
		sys.exit('[ERROR] AutoTSS is not supported on Windows. Exiting.')

	check_tsschecker()

	client = commands.AutoShardedBot(command_prefix=get_prefix, help_command=None)

	client.load_extension('cogs.utils') # Load utils cog first

	for cog in glob.glob('cogs/*.py'):
		if 'utils.py' in cog:
			continue

		client.load_extension(cog.replace('/', '.')[:-3])

	try:
		client.run(bot_token())
	except discord.LoginFailure:
		sys.exit("[ERROR] Token invalid, make sure the 'AUTOTSS_TOKEN' environment variable is set to your bot token. Exiting.")

if __name__ == '__main__':
	main()
