#!/usr/bin/env python3

from discord.ext import commands
import aiosqlite
import discord
import glob
import os
import platform
import shutil
import sys


def bot_token():
    if os.getenv('AUTOTSS_TOKEN') is not None:
        return os.getenv('AUTOTSS_TOKEN')
    else:
        sys.exit("[ERROR] Bot token not set in 'AUTOTSS_TOKEN' environment variable. Exiting.")


def check_tsschecker():
    if shutil.which('tsschecker') is None:
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

    mentions = discord.AllowedMentions(
        **dict.fromkeys([
            "roles",
            "everyone",
            "replied_user"
        ], False)
    )

    # Neato trick for intents in one line
    (intents := discord.Intents.default()).members = True
    
    client = commands.AutoShardedBot(
        help_command=None,
        command_prefix=get_prefix,
        intents=intents,
        allowed_mentions=mentions
    )

    client.load_extension('cogs.utils') # Load utils cog first

    for cog in glob.glob('cogs/*.py'):
        if 'utils.py' in cog:
            continue

        client.load_extension(cog.replace('/', '.')[:-3])

    try:
        client.run(bot_token())
    except discord.LoginFailure:
        sys.exit("[ERROR] Token invalid, make sure the 'AUTOTSS_TOKEN' environment variable is set to your bot token. Exiting.")
    except discord.errors.PrivilegedIntentsRequired:
        sys.exit("[ERROR] Server Members Intent not enabled, go to 'https://discord.com/developers/applications/' and enable the Server Members Intent. Exiting.")

if __name__ == '__main__':
    main()
