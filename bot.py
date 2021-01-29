#!/usr/bin/env python3

from discord.ext import commands
import discord
import os
import sqlite3
import sys

client = commands.Bot(command_prefix='b!', help_command=None)


def list_cogs():
    cogs = str()

    for cog in os.listdir('cogs'):
        if cog.endswith('.py'):
            cog = cog[:-3]
            cogs += f'`{cog}` '

    return cogs


def bot_token(token):
    try:
        token_file = open(token, 'r')
        return token_file.read()
    except FileNotFoundError:
        sys.exit("No bot token found in token.txt. Make sure you've created the file and put your token into it, or else this bot will not work.")


@client.event
async def on_ready():
    os.makedirs('Data', exist_ok=True)

    db = sqlite3.connect('Data/autotss.db')
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS autotss(
        device_num INTEGER,
        userid INTEGER,
        name TEXT,
        identifier TEXT,
        ecid TEXT,
        boardconfig TEXT,
        blobs TEXT
        )
        ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uptime(
        start_time TEXT,
        filler TEXT
        )
        ''')
    db.commit()
    db.close()

    await client.change_presence(activity=discord.Game(name=f'Ping me for help! | Prefix: {client.command_prefix}'))
    print('AutoTSS is now online.')


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(title='Error',
                              description=f"That command doesn't exist! Use `{ctx.prefix}help` to see all the commands you can use.")
        embed.set_footer(text=ctx.message.author.nick,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)
    else:
        raise error


for cog in os.listdir('cogs'):
    if cog.endswith('.py'):
        cog = cog[:-3]
        client.load_extension(f'cogs.{cog}')

try:
    client.run(bot_token('token.txt'))
except discord.LoginFailure:
    sys.exit("Token invalid, make sure your token is the only text in 'token.txt'.")
