from discord.ext import commands
import discord


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='help', invoke_without_command=True)
    @commands.guild_only()
    async def help_command(self, ctx):
        embed = discord.Embed(title='Commands')
        if await ctx.bot.is_owner(ctx.author):
            embed.add_field(name='Admin Commands', value=f'`{ctx.prefix}help admin`', inline=False)

        embed.add_field(name='Device Commands', value=f'`{ctx.prefix}help device`', inline=False)
        embed.add_field(name='TSS Commands', value=f'`{ctx.prefix}help tss`', inline=False)
        embed.add_field(name='Miscellaneous Commands', value=f'`{ctx.prefix}help misc`', inline=False)
        embed.add_field(name='Want information about AutoTSS?', value=f'`{ctx.prefix}info`', inline=False)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @help_command.command(name='device')
    @commands.guild_only()
    async def device_commands(self, ctx):
        embed = discord.Embed(title='Device Commands')
        embed.add_field(name='Add a device', value=f'`{ctx.prefix}device add`', inline=False)
        embed.add_field(name='Remove a device', value=f'`{ctx.prefix}device remove`', inline=False)
        embed.add_field(name='List your devices', value=f'`{ctx.prefix}device list`', inline=False)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @help_command.command(name='tss')
    @commands.guild_only()
    async def tss_commands(self, ctx):
        embed = discord.Embed(title='TSS Commands')
        embed.add_field(name='Manually save blobs for all of your devices', value=f'`{ctx.prefix}tss saveall`', inline=False)
        embed.add_field(name='Manually save blobs for one of your devices', value=f'`{ctx.prefix}tss save`', inline=False)
        embed.add_field(name='List all of the blobs saved for your devices', value=f'`{ctx.prefix}tss list`', inline=False)
        embed.add_field(name='Download all of the blobs saved for your devices', value=f'`{ctx.prefix}tss download`', inline=False)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @help_command.command(name='misc')
    @commands.guild_only()
    async def misc_commands(self, ctx):
        embed = discord.Embed(title='Miscellaneous Commands')
        embed.add_field(name='Change the command prefix for AutoTSS', value=f'`{ctx.prefix}prefix <prefix>`', inline=False)
        embed.add_field(name='Get the invite for this bot', value=f'`{ctx.prefix}invite`', inline=False)
        embed.add_field(name='Information about AutoTSS', value=f'`{ctx.prefix}info`', inline=False)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @help_command.command(name='admin')
    @commands.guild_only()
    @commands.is_owner()
    async def admin_commands(self, ctx):
        embed = discord.Embed(title='Admin Commands')
        embed.add_field(name='See module subcommands', value=f'`{ctx.prefix}module`', inline=False)
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))
