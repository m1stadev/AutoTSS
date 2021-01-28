from discord.ext import commands
import asyncio
import discord


class TSS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='tss', invoke_without_command=True)
    async def tss_cmd(self, ctx):
        embed = discord.Embed(title='TSS Commands')
        embed.add_field(name='Save blobs for all of your devices',
                        value=f'`{ctx.prefix}tss saveall`', inline=False)
        embed.add_field(name='Save blobs for one of your devices',
                        value=f'`{ctx.prefix}tss save <device>`', inline=False)
        embed.add_field(name='List all of the blobs saved for your devices',
                        value=f'`{ctx.prefix}tss listall`', inline=False)
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @tss_cmd.command(name='save')
    async def save_single_device_blobs(self, ctx, device):
        await ctx.send("stfu i haven't implemented this yet")

    @tss_cmd.command(name='saveall')
    async def save_all_device_blobs(self, ctx):
        await ctx.send("stfu i haven't implemented this yet")

    @tss_cmd.command(name='listall')
    async def list_all_blobs(self, ctx):
        await ctx.send("stfu i haven't implemented this yet")

    # ignore this, was using it to test async subprocesses lol
    @tss_cmd.command(name='test')
    async def cock(self, ctx):
        cmd = await asyncio.create_subprocess_exec('tsschecker', stdout=asyncio.subprocess.PIPE)

        await ctx.send('started process')

        stdout, stderr = await cmd.communicate()

        await ctx.send('process ended')
        await ctx.send(f'pid: {cmd.pid}, output: {stdout.decode()}')


def setup(bot):
    bot.add_cog(TSS(bot))
