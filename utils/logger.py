# imports
from datetime import datetime
from discord.ext import commands
from dotenv.main import load_dotenv

import asyncio
import discord
import logging
import os
import sys

load_dotenv()


class WebhookLogger(logging.Handler):
    def __init__(self, bot: commands.Bot):
        super().__init__()

        self.bot = bot
        self.webhook = discord.Webhook.from_url(
            os.environ['LOGGING_WEBHOOK_URL'], session=self.bot.session
        )

    def emit(self, record: logging.LogRecord):
        if self.webhook is None:
            return

        embed = discord.Embed(
            title=record.levelname.capitalize(),
            description=record.message,
            timestamp=datetime.fromtimestamp(record.created),
        )

        message = {'embed': embed}

        if record.levelno in (logging.ERROR, logging.CRITICAL):
            message['content'] = self.bot.get_user(self.bot.owner_id).mention

        asyncio.ensure_future(self.post_content(**message))

    async def post_content(self, **message):
        try:
            await self.webhook.send(**message)
        except Exception:
            pass


class Logger:
    def __init__(self, bot: commands.Bot):
        stdout_log = logging.StreamHandler(sys.stdout)
        stdout_log.setFormatter(logging.Formatter(fmt='log - {message}', style='{'))

        webhook_log = WebhookLogger(bot)
        webhook_log.setFormatter(
            logging.Formatter(fmt='{asctime}s - {levelname}s - {message}s', style='{')
        )

        for logger in (logging.getLogger('discord'), logging.getLogger(__name__)):
            logger.setLevel(logging.WARN)
            logger.addHandler(stdout_log)
            logger.addHandler(webhook_log)

        self.logger = logging.getLogger(__name__)
