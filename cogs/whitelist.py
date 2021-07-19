from discord.ext import commands
import aiosqlite
import discord


class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='whitelist', invoke_without_command=True)
    @commands.guild_only()
    async def whitelist_cmd(self, ctx: commands.Context) -> None:
        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='Whitelist Commands')
        embed.add_field(name='Set an allowed channel to use AutoTSS in', value=f'`{prefix}whitelist set <channel>`', inline=False)
        embed.add_field(name='Toggle channel whitelist', value=f'`{prefix}whitelist toggle`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @whitelist_cmd.command(name='set')
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def set_whitelist_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        embed = discord.Embed(title='Whitelist')
        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * FROM whitelist WHERE guild = ?', (ctx.guild.id,)) as cursor:
            if await cursor.fetchone() is None:
                await db.execute('INSERT INTO whitelist(guild, channel, enabled) VALUES(?,?,?)', (ctx.guild.id, channel.id, True))
                embed.description = f'Enabled AutoTSS whitelisting and set to {channel.mention}.'
            else:
                await db.execute('UPDATE whitelist SET channel = ?, enabled = ? WHERE guild = ?', (channel.id, ctx.guild.id))
                embed.description = f'Set AutoTSS whitelist to {channel.mention}.'

            await db.commit()

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @whitelist_cmd.command(name='toggle')
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def toggle_whitelist(self, ctx: commands.Context) -> None:
        async with aiosqlite.connect('Data/autotss.db') as db:
            async with db.execute('SELECT * FROM whitelist WHERE guild = ?', (ctx.guild.id,)) as cursor:
                data = await cursor.fetchone()

            if type(data) == tuple:
                channel = ctx.guild.get_channel(data[1])
                if channel is None:
                    embed = discord.Embed(title='Error', description=f'Channel `{data[1]}` no longer exists, please set a new whitelist channel.')
                else:
                    await db.execute('UPDATE whitelist SET enabled = ? WHERE guild = ?', (not data[2], ctx.guild.id))
                    await db.commit()

                    embed = discord.Embed(title='Whitelist')
                    embed.description = f"No{'w' if not data[2] == True else ' longer'} restricting commands for {self.bot.user.mention} to {channel.mention}."
            else:
                embed = discord.Embed(title='Error', description='No whitelist channel is set.')

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Whitelist(bot))