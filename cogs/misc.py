from discord.ext import commands
import discord
import sqlite3


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    async def prefix(self, ctx, *, prefix):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        if len(prefix) > 4:
            embed = discord.Embed(title='Error', description='Prefixes are limited to 4 characters or less.')
            embed.set_footer(text=ctx.message.author.name, icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await ctx.send(embed=embed)
            return

        if ctx.message.author.guild_permissions.administrator:
            cursor.execute('UPDATE prefix SET prefix = ? WHERE guild = ?', (prefix, ctx.guild.id))
            db.commit()

            embed = discord.Embed(title='Prefix', description=f'Prefix changed to `{prefix}`.')

        else:
            embed = discord.Embed(title='Error', description='You do not have permission to run this command!')

        embed.set_footer(text=ctx.message.author.name, icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

        db.close()


def setup(bot):
    bot.add_cog(Misc(bot))
