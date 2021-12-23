from datetime import datetime
from discord.commands import slash_command
from discord.ext import commands
from views.buttons import SelectView

import asyncio
import discord
import sys
import textwrap


class MiscCog(commands.Cog, name='Miscellaneous'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.utils = self.bot.get_cog('Utilities')

    @slash_command(description='Get the invite for AutoTSS.')
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

    @slash_command(description="See AutoTSS's latency.")
    async def ping(self, ctx: discord.ApplicationContext) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        embed = discord.Embed(title='Pong!', description='Testing ping...')
        embed.set_thumbnail(url=self.bot.user.display_avatar.with_static_format('png').url)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        current_time = await asyncio.to_thread(datetime.utcnow)
        await ctx.respond(embed=embed)

        embed.description = f'API ping: {self.bot.latencies}\nMessage Ping: `{round((await asyncio.to_thread(datetime.utcnow) - current_time).total_seconds() * 1000)}ms`'
        await ctx.edit(embed=embed)

    @slash_command(description='General info on AutoTSS.')
    async def info(self, ctx: discord.ApplicationContext) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        embed = await self.utils.info_embed(ctx.author)
        await ctx.respond(embed=embed)

    @slash_command(description="See AutoTSS's statistics.")
    async def stats(self, ctx: discord.ApplicationContext) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        async with self.bot.db.execute('SELECT start_time from uptime') as cursor:
            start_time = (await cursor.fetchone())[0]

        embed = {
            'title': 'AutoTSS Statistics',
            'fields': [{
                'name': 'Bot Started',
                'value': await self.utils.get_uptime(start_time),
                'inline': True
            },
            {
                'name': 'Python Version',
                'value': '.'.join(str(_) for _ in (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)),
                'inline': True
            },
            {
                'name': 'TSSChecker Version',
                'value': await self.utils.get_tsschecker_version(),
                'inline': False
            },
            {
                'name': 'SHSH Blobs Saved',
                'value': f"**{','.join(textwrap.wrap(str(await self.utils.shsh_count())[::-1], 3))[::-1]}**",
                'inline': False
            }],
            'footer': {
                'text': ctx.author.display_name,
                'icon_url': str(ctx.author.display_avatar.with_static_format('png').url)
            }
        }

        await ctx.respond(embed=discord.Embed.from_dict(embed))

def setup(bot):
    bot.add_cog(MiscCog(bot))
