from discord.ext import commands
import discord


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='help', invoke_without_command=True)
    @commands.guild_only()
    async def help_cmd(self, ctx):
        embed = discord.Embed(title='Commands')
        embed.add_field(name='Device Commands',
                        value=f'`{ctx.prefix}help device`', inline=False)
        embed.add_field(name='TSS Commands',
                        value=f'`{ctx.prefix}help tss`', inline=False)
        embed.add_field(name='Miscellaneous Commands',
                        value=f'`{ctx.prefix}help misc`', inline=False)
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @help_cmd.command(name='device')
    @commands.guild_only()
    async def device_commands(self, ctx):
        embed = discord.Embed(title='Device Commands')
        embed.add_field(name='Add a device',
                        value=f'`{ctx.prefix}device add`', inline=False)
        embed.add_field(name='Remove a device',
                        value=f'`{ctx.prefix}device remove`', inline=False)
        embed.add_field(name='List your devices',
                        value=f'`{ctx.prefix}device list`', inline=False)
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @help_cmd.command(name='tss')
    @commands.guild_only()
    async def tss_commands(self, ctx):
        embed = discord.Embed(title='TSS Commands')
        embed.add_field(name='Manually save blobs for all of your devices',
                        value=f'`{ctx.prefix}tss saveall`', inline=False)
        embed.add_field(name='Manually save blobs for one of your devices',
                        value=f'`{ctx.prefix}tss save`', inline=False)
        embed.add_field(name='List all of the blobs saved for your devices',
                        value=f'`{ctx.prefix}tss list`', inline=False)
        embed.add_field(name='Download all of the blobs saved for your devices',
                        value=f'`{ctx.prefix}tss download`', inline=False)
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @help_cmd.command(name='misc')
    @commands.guild_only()
    async def misc_commands(self, ctx):
        embed = discord.Embed(title='Miscellaneous Commands')
        embed.add_field(name='Change the command prefix for AutoTSS',
                        value=f'`{ctx.prefix}prefix <prefix>`', inline=False)
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))
