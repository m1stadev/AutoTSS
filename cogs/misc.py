from discord.ext import commands
import discord
import sqlite3


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx, *, prefix):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        if len(prefix) > 4:
            embed = discord.Embed(
                title='Error', description='Prefixes are limited to 4 characters or less.')
            embed.set_footer(text=ctx.author.name,
                             icon_url=ctx.author.avatar_url_as(static_format='png'))
            await ctx.send(embed=embed)
            return

        cursor.execute(
            'UPDATE prefix SET prefix = ? WHERE guild = ?', (prefix, ctx.guild.id))
        db.commit()

        embed = discord.Embed(
            title='Prefix', description=f'Prefix changed to `{prefix}`.')

        embed.set_footer(text=ctx.author.name,
                         icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

        db.close()

    @commands.command()
    @commands.guild_only()
    async def invite(self, ctx):
        embed = discord.Embed(title='Invite',
                              description='[Click here](https://discord.com/oauth2/authorize?client_id=804072225723383818&scope=bot&permissions=93184).')
        embed.set_thumbnail(
            url=self.bot.user.avatar_url_as(static_format='png'))
        embed.set_footer(text=ctx.author.name,
                         icon_url=ctx.author.avatar_url_as(static_format='png'))

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Misc(bot))
