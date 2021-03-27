#!/usr/bin/env python3

from discord.ext import commands
import discord
import glob
import platform
import sqlite3
import subprocess
import sys


def bot_token(token):
	try:
		token_file = open(token, 'r')
		return token_file.read()
	except FileNotFoundError:
		sys.exit("No bot token found in token.txt. Make sure you've created the file and put your token into it, or else this bot will not work.")


def check_tsschecker():
	tsschecker_check = subprocess.run('which tsschecker', stdout=subprocess.DEVNULL, shell=True)
	if tsschecker_check.returncode != 0:
		sys.exit('[ERROR] tsschecker is not installed on your system. Exiting.')


def get_prefix(client, message):
	db = sqlite3.connect('Data/autotss.db')
	cursor = db.cursor()

	if message.channel.type is discord.ChannelType.private:
		return 'p!'

	cursor.execute('SELECT prefix FROM prefix WHERE guild = ?', (message.guild.id,))

	if cursor.fetchone() is None:
		cursor.execute('INSERT INTO prefix(guild, prefix) VALUES(?,?)', (message.guild.id, 'b!'))
		db.commit()

	cursor.execute('SELECT prefix FROM prefix WHERE guild = ?', (message.guild.id,))
	guild_prefix = cursor.fetchone()[0]
	db.close()

	return commands.when_mentioned_or(guild_prefix)(client, message)


if __name__ == '__main__':
	check_tsschecker()

	client = commands.Bot(command_prefix=get_prefix, help_command=None)

	if platform.system() == 'Windows':
		cogs = glob.glob('cogs\*.py')
	else:
		cogs = glob.glob('cogs/*.py')

	for cog in cogs:
		client.load_extension(cog.replace('/', '.').replace('\\', '.')[:-3])

	try:
		client.run(bot_token('token.txt'))
	except discord.LoginFailure:
		sys.exit("[ERROR] Token invalid, make sure your token is the only text in 'token.txt'. Exiting.")
