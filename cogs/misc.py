from datetime import datetime
from discord.commands import slash_command
from discord.ext import commands
from views.buttons import SelectView

import aiosqlite
import asyncio
import discord
import math
import time


class MiscCog(commands.Cog, name='Miscellaneous'):
    def __init__(self, bot):
        self.bot = bot

        self.utils = self.bot.get_cog('Utilities')

    @slash_command(description='Get the invite for AutoTSS', guild_ids=(729946499102015509,))
    async def invite(self, ctx: discord.ApplicationContext) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        buttons = [{
            'label': 'Invite',
            'style': discord.ButtonStyle.link,
            'url': self.utils.invite
        }]

        embed = discord.Embed(title='Invite', description='AutoTSS invite:')
        embed.set_thumbnail(url=self.bot.user.display_avatar.with_static_format('png').url)
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        view = SelectView(buttons, ctx, timeout=None)
        await ctx.respond(embed=embed, view=view)

    @slash_command(description="See AutoTSS's latency", guild_ids=(729946499102015509,))
    async def ping(self, ctx: discord.ApplicationContext) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        embed = discord.Embed(title='Pong!', description='Testing ping...')
        embed.set_thumbnail(url=self.bot.user.display_avatar.with_static_format('png').url)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        current_time = await asyncio.to_thread(datetime.utcnow)
        await ctx.respond(embed=embed)

        embed.description = f'Ping: `{round((await asyncio.to_thread(datetime.utcnow) - current_time).total_seconds() * 1000)}ms`'
        await ctx.edit(embed=embed)

    @slash_command(description='General info on AutoTSS', guild_ids=(729946499102015509,))
    async def info(self, ctx: discord.ApplicationContext) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        embed = await self.utils.info_embed(ctx.author)
        await ctx.respond(embed=embed)

    @slash_command(description="See AutoTSS's uptime", guild_ids=(729946499102015509,))
    async def uptime(self, ctx: discord.ApplicationContext) -> None:
        async with aiosqlite.connect(self.utils.db_path) as db, db.execute('SELECT start_time from uptime') as cursor:
            start_time = (await cursor.fetchone())[0]

        uptime = await asyncio.to_thread(math.floor, await asyncio.to_thread(time.time) - float(start_time))
        uptime = await asyncio.to_thread(time.strftime, '%H:%M:%S', await asyncio.to_thread(time.gmtime, uptime))
        hours, minutes, seconds = [int(i) for i in uptime.split(':')]

        formatted_uptime = list()
        if hours > 0:
            formatted_uptime.append(f"**{hours}** hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            formatted_uptime.append(f"**{minutes}** minute{'s' if minutes != 1 else ''}")
        if seconds > 0:
            formatted_uptime.append(f"**{seconds}** second{'s' if seconds != 1 else ''}")

        embed = discord.Embed(title='Uptime', description=', '.join(formatted_uptime))
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(MiscCog(bot))
