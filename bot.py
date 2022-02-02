#!/usr/bin/env python3

from discord.ext import commands
from dotenv.main import load_dotenv
from utils.logger import Logger

import aiohttp
import aiopath
import aiosqlite
import asyncio
import discord
import ujson
import os
import shutil
import sys
import time


async def startup():
    if sys.version_info.major < 3 and sys.version_info.minor < 9:
        sys.exit('[ERROR] AutoTSS requires Python 3.9 or higher. Exiting.')

    if sys.platform != 'win32':
        tsschecker = await asyncio.to_thread(shutil.which, 'tsschecker')
    else:
        tsschecker = (
            len(
                [
                    _
                    async for _ in aiopath.AsyncPath(__file__).parent.glob(
                        'tsschecker*.exe'
                    )
                    if await _.is_file()
                ]
            )
            > 0
        )  # Assume file beginning with 'tsschecker' and ending in '.exe' is a valid tsschecker binary

    if not tsschecker:
        sys.exit('[ERROR] tsschecker is not installed on your system. Exiting.')

    load_dotenv()

    if 'AUTOTSS_TOKEN' not in os.environ.keys():
        sys.exit(
            "[ERROR] Bot token not set in 'AUTOTSS_TOKEN' environment variable. Exiting."
        )

    try:
        owner_ids = [int(_) for _ in os.environ['OWNER_IDS'].split(', ')]
    except KeyError:
        sys.exit(
            "[ERROR] Owner IDs not set in 'OWNER_IDS' environment variable. Exiting."
        )
    except ValueError:
        sys.exit(
            "[ERROR] Owner IDs specified in 'OWNER_IDS' environment variable are invalid. Exiting."
        )

    mentions = discord.AllowedMentions(everyone=False, roles=False)
    (intents := discord.Intents.default()).members = False
    if len(owner_ids) == 1:
        bot = commands.AutoShardedBot(
            help_command=None,
            intents=intents,
            allowed_mentions=mentions,
            debug_guild=729946499102015509,
            owner_id=owner_ids[0],
        )
    else:
        bot = commands.AutoShardedBot(
            help_command=None,
            intents=intents,
            allowed_mentions=mentions,
            debug_guild=729946499102015509,
            owner_ids=owner_ids,
        )

    bot.load_extension('cogs.utils')  # Load utils cog first
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
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS autotss(
            user INTEGER,
            devices JSON,
            enabled BOOLEAN
            )
            '''
        )
        await db.commit()

        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS whitelist(
            guild INTEGER,
            channel INTEGER,
            enabled BOOLEAN
            )
            '''
        )
        await db.commit()

        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS uptime(
            start_time REAL
            )'''
        )
        await db.commit()

        async with db.execute('SELECT start_time FROM uptime') as cursor:
            if await cursor.fetchone() is None:
                sql = 'INSERT INTO uptime(start_time) VALUES(?)'
            else:
                sql = 'UPDATE uptime SET start_time = ?'

        await db.execute(sql, (await asyncio.to_thread(time.time),))
        await db.commit()

        async with db.execute(
            'SELECT devices from autotss WHERE enabled = ?', (True,)
        ) as cursor:
            num_devices = sum(
                len(ujson.loads(devices[0])) for devices in await cursor.fetchall()
            )

        bot.activity = discord.Game(
            name=f"Saving SHSH blobs for {num_devices} device{'s' if num_devices != 1 else ''}."
        )

        cpu_count = min(32, (await asyncio.to_thread(os.cpu_count) or 1) + 4)
        bot.get_cog('Utilities').sem = asyncio.Semaphore(cpu_count)

        # Setup bot attributes
        bot.db = db
        bot.session = session
        bot.logger = Logger(bot).logger

        try:
            await bot.start(os.environ['AUTOTSS_TOKEN'])
        except discord.LoginFailure:
            sys.exit(
                "[ERROR] Token invalid, make sure the 'AUTOTSS_TOKEN' environment variable is set to your bot token. Exiting."
            )
        except discord.PrivilegedIntentsRequired:
            sys.exit(
                "[ERROR] Server Members Intent not enabled, go to 'https://discord.com/developers/applications' and enable the Server Members Intent. Exiting."
            )


if __name__ == '__main__':
    try:
        asyncio.run(startup())
    except KeyboardInterrupt:
        pass
