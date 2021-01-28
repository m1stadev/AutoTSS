from discord.ext import commands
import discord


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='help', invoke_without_command=True)
    async def help_cmd(self, ctx):
        embed = discord.Embed(title='Commands')
        embed.add_field(name='Device Commands', value=f'`{ctx.prefix}help device`', inline=False)
        embed.add_field(name='TSS Commands', value=f'`{ctx.prefix}help tss`', inline=False)
        embed.set_footer(text=ctx.message.author.name, icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @help_cmd.command(name='device')
    async def device_commands(self, ctx):
        embed = discord.Embed(title='Device Commands')
        embed.add_field(name='Add a device', value=f'`{ctx.prefix}device add`', inline=False)
        embed.add_field(name='Remove a device', value=f'`{ctx.prefix}device remove`', inline=False)
        embed.add_field(name='List your devices', value=f'`{ctx.prefix}device list`', inline=False)
        embed.set_footer(text=ctx.message.author.name, icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @help_cmd.command(name='tss')
    async def tss_commands(self, ctx):
        embed = discord.Embed(title='TSS Commands')
        embed.add_field(name='Save blobs for all of your devices', value=f'`{ctx.prefix}tss saveall`', inline=False)
        embed.add_field(name='Save blobs for one of your devices', value=f'`{ctx.prefix}tss save <device>`', inline=False)
        embed.add_field(name='List all of the blobs saved for your devices', value=f'`{ctx.prefix}tss listall`', inline=False)
        embed.set_footer(text=ctx.message.author.name, icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))
