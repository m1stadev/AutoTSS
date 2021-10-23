from aioify import aioify
from datetime import datetime
from discord.ext import commands
import aiosqlite
import discord

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.datetime = aioify(datetime, name='datetime')
        self.utils = self.bot.get_cog('Utils')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx: commands.Context, *, prefix: str = None) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        if prefix is None:
            prefix = await self.utils.get_prefix(ctx.guild.id)
            embed = discord.Embed(title='Prefix', description=f'My prefix is `{prefix}`.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.reply(embed=embed)
            return

        if len(prefix) > 4:
            embed = discord.Embed(title='Error', description='Prefixes are limited to 4 characters or less.')
            await ctx.reply(embed=embed)
            return

        async with aiosqlite.connect('Data/autotss.db') as db:
            await db.execute('UPDATE prefix SET prefix = ? WHERE guild = ?', (prefix, ctx.guild.id))
            await db.commit()

        embed = discord.Embed(title='Prefix', description=f'Prefix changed to `{prefix}`.')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        await ctx.reply(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def invite(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        embed = discord.Embed(title='Invite', description=f'[Click here]({self.utils.invite}).')
        embed.set_thumbnail(url=self.bot.user.display_avatar.with_static_format('png').url)
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        await ctx.reply(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def ping(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        embed = discord.Embed(title='Pong!', description='Testing ping...')
        embed.set_thumbnail(url=self.bot.user.display_avatar.with_static_format('png').url)
        embed.set_footer(text=ctx.message.author.name, icon_url=ctx.message.author.display_avatar.with_static_format('png').url)

        time = await self.datetime.utcnow()
        message = await ctx.reply(embed=embed)

        embed.description = f'Ping: `{round((await self.datetime.utcnow() - time).total_seconds() * 1000)}ms`'
        await message.edit(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def info(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)
        embed = await self.utils.info_embed(prefix, ctx.author)
        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(Misc(bot))
