from datetime import datetime

import asyncio
import discord
import logging
import sys


class WebhookLogger(logging.Handler):
    def __init__(self, bot: discord.Bot, url: str):
        super().__init__()

        self.bot = bot
        self.webhook = discord.Webhook.from_url(url, session=self.bot.session)

    def emit(self, record: logging.LogRecord):
        if self.webhook is None:
            return

        embed = discord.Embed(
            title=record.levelname.capitalize(),
            description=record.msg,
            timestamp=datetime.fromtimestamp(record.created),
        )

        if record.name == 'discord':
            module = f'discord.{record.module}'
        else:
            module = record.module

        embed.add_field(name='Module', value=f'`{module}`')
        embed.set_author(name=record.funcName)

        message = {'embed': embed}

        if record.levelno in (logging.ERROR, logging.CRITICAL):
            message['content'] = self.bot.get_user(self.bot.owner_id).mention

        asyncio.create_task(self.post_content(**message))

    async def post_content(self, **message):
        try:
            await self.webhook.send(**message)
        except:
            pass


class Logger:
    def __init__(self, bot: discord.Bot = None, url: str = None):
        discord_log = logging.getLogger('discord')
        discord_log.setLevel(logging.WARN)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        if bot and url:
            webhook_log = WebhookLogger(bot, url)
            for logger in (self.logger, discord_log):
                logger.addHandler(webhook_log)
