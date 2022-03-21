#!/usr/bin/env python3

from datetime import datetime
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


DB_PATH = aiopath.AsyncPath('Data/autotss.db')

load_dotenv()

try:
    MAX_USER_DEVICES = int(os.environ.get('AUTOTSS_MAX_DEVICES'))
except TypeError:
    MAX_USER_DEVICES = 10

try:
    OWNER_ID = int(os.environ['AUTOTSS_OWNER'])
except TypeError:
    OWNER_ID = None


async def main():
    if sys.version_info[:2] < (3, 9):
        sys.exit('[ERROR] AutoTSS requires Python 3.9 or higher. Exiting.')

    if sys.platform != 'win32':
        tsschecker = await asyncio.to_thread(shutil.which, 'tsschecker')
    else:
        tsschecker = (
            len(
                [
                    b
                    async for b in aiopath.AsyncPath(__file__).parent.glob(
                        'tsschecker*.exe'
                    )
                    if await b.is_file()
                ]
            )
            > 0
        )  # Assume file beginning with 'tsschecker' and ending in '.exe' is a valid tsschecker binary

    if not tsschecker:
        sys.exit('[ERROR] tsschecker is not installed on your system. Exiting.')

    if MAX_USER_DEVICES <= 0:
        sys.exit(
            "[ERROR] Invalid maximum device count set in 'AUTOTSS_MAX_DEVICES' environment variable. Exiting."
        )

    if 'AUTOTSS_TOKEN' not in os.environ.keys():
        sys.exit(
            "[ERROR] Bot token not set in 'AUTOTSS_TOKEN' environment variable. Exiting."
        )

    if 'AUTOTSS_TEST_GUILD' in os.environ.keys():
        try:
            debug_guild = int(os.environ['AUTOTSS_TEST_GUILD'])
        except TypeError:
            sys.exit(
                "[ERROR] Invalid test guild ID set in 'AUTOTSS_TEST_GUILD' environment variable. Exiting."
            )
    else:
        debug_guild = None

    if OWNER_ID is None or not 17 <= len(str(OWNER_ID)) <= 18:
        sys.exit(
            "[ERROR] Invalid owner ID set in 'AUTOTSS_OWNER' environment variable. Exiting."
        )

    if 'AUTOTSS_OWNER' not in os.environ.keys():
        sys.exit(
            "[ERROR] Owner ID not set in 'AUTOTSS_OWNER' environment variable. Exiting."
        )

    mentions = discord.AllowedMentions(everyone=False, roles=False)
    (intents := discord.Intents.default()).members = True

    bot = discord.AutoShardedBot(
        help_command=None, intents=intents, allowed_mentions=mentions, owner_id=OWNER_ID
    )

    if debug_guild is not None:
        bot.debug_guilds = [debug_guild]

    bot.load_extension('cogs.utils')  # Load utils cog first
    cogs = aiopath.AsyncPath('cogs')
    async for cog in cogs.glob('*.py'):
        if cog.stem == 'utils':
            continue

        bot.load_extension(f'cogs.{cog.stem}')

    cpu_count = min(32, (await asyncio.to_thread(os.cpu_count) or 1) + 4)
    bot.get_cog('Utilities').sem = asyncio.Semaphore(cpu_count)

    await DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db, aiohttp.ClientSession() as session:
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

        async with db.execute(
            'SELECT devices FROM autotss WHERE enabled = ?', (True,)
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
        bot.start_time = await asyncio.to_thread(datetime.now)

        if 'AUTOTSS_WEBHOOK' in os.environ.keys():
            bot.logger = Logger(bot, os.environ['AUTOTSS_WEBHOOK']).logger
        else:
            bot.logger = Logger().logger

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
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
