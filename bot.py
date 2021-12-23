#!/usr/bin/env python3

from discord.ext import commands

import aiohttp
import aiopath
import aiosqlite
import asyncio
import discord
import os
import shutil
import sys
import time


async def startup():
    if sys.version_info.major < 3 and sys.version_info.minor < 9:
        sys.exit('[ERROR] AutoTSS requires Python 3.9 or higher. Exiting.')

    if sys.platform != 'win32':
        tsschecker = True if await asyncio.to_thread(shutil.which, 'tsschecker') is not None else False
    else:
        tsschecker = len([_ async for _ in aiopath.AsyncPath(__file__).parent.glob('tsschecker*.exe') if await _.is_file()]) > 0 # Assume file beginning with 'tsschecker' and ending in '.exe' is a valid tsschecker binary

    if tsschecker == False:
        sys.exit('[ERROR] tsschecker is not installed on your system. Exiting.')

    if 'AUTOTSS_TOKEN' not in os.environ.keys():
        sys.exit("[ERROR] Bot token not set in 'AUTOTSS_TOKEN' environment variable. Exiting.")

    mentions = discord.AllowedMentions(everyone=False, roles=False)    
    (intents := discord.Intents.default()).members = True

    bot = commands.AutoShardedBot(
        help_command=None,
        intents=intents,
        allowed_mentions=mentions
    )

    bot.load_extension('cogs.utils') # Load utils cog first
    cogs = aiopath.AsyncPath('cogs')
    async for cog in cogs.glob('*.py'):
        if cog.stem == 'utils':
            continue

        bot.load_extension(f'cogs.{cog.stem}')

    cpu_count = min(32, (await asyncio.to_thread(os.cpu_count) or 1) + 4)
    bot.get_cog('Utilities').sem = asyncio.Semaphore(cpu_count)

    db_path = aiopath.AsyncPath('Data/autotss.db')
    await db_path.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(db_path) as db, aiohttp.ClientSession() as session:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS autotss(
            user INTEGER,
            devices JSON,
            enabled BOOLEAN
            )
            ''')
        await db.commit()

        await db.execute('''
            CREATE TABLE IF NOT EXISTS whitelist(
            guild INTEGER,
            channel INTEGER,
            enabled BOOLEAN
            )
            ''')
        await db.commit()

        await db.execute('''
            CREATE TABLE IF NOT EXISTS uptime(
            start_time REAL
            )''')
        await db.commit()

        async with db.execute('SELECT start_time FROM uptime') as cursor:
            if await cursor.fetchone() is None:
                sql = 'INSERT INTO uptime(start_time) VALUES(?)'
            else:
                sql = 'UPDATE uptime SET start_time = ?'

        await db.execute(sql, (await asyncio.to_thread(time.time),))
        await db.commit()

        cpu_count = min(32, (await asyncio.to_thread(os.cpu_count) or 1) + 4)
        bot.get_cog('Utilities').sem = asyncio.Semaphore(cpu_count)
        bot.db = db
        bot.session = session

        try:
            await bot.start(os.environ['AUTOTSS_TOKEN'])
        except discord.LoginFailure:
            sys.exit("[ERROR] Token invalid, make sure the 'AUTOTSS_TOKEN' environment variable is set to your bot token. Exiting.")
        except discord.PrivilegedIntentsRequired:
            sys.exit("[ERROR] Server Members Intent not enabled, go to 'https://discord.com/developers/applications' and enable the Server Members Intent. Exiting.")


if __name__ == '__main__':
    try:
        asyncio.run(startup())
    except KeyboardInterrupt:
        pass

