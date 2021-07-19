from discord.ext import commands
import aiosqlite
import discord


class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = self.bot.get_cog('Utils')

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
        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * FROM whitelist WHERE guild = ?', (ctx.guild.id,)) as cursor:
            if await cursor.fetchone() is None:
                sql = 'INSERT INTO whitelist(channel, enabled, guild) VALUES(?,?,?)'
            else:
                sql = 'UPDATE whitelist SET channel = ?, enabled = ? WHERE guild = ?'
                
            await db.execute(sql, (channel.id, True, ctx.guild.id))
            await db.commit()

        embed = discord.Embed(title='Whitelist', description=f'Enabled AutoTSS whitelisting and set to {channel.mention}.')
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
                    embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            else:
                embed = discord.Embed(title='Error', description='No whitelist channel is set.')

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Whitelist(bot))
