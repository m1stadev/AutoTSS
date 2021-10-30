from discord.ext import commands

import aiosqlite
import discord


class WhitelistCog(commands.Cog, name='Whitelist'):
    def __init__(self, bot):
        self.bot = bot
        self.utils = self.bot.get_cog('Utilities')

    @commands.group(name='whitelist', aliases=('w',), help='Whitelist management commands.', invoke_without_command=True)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.has_permissions(administrator=True)
    async def whitelist_group(self, ctx: commands.Context) -> None:
        help_aliases = (self.bot.help_command.command_attrs['name'], *self.bot.help_command.command_attrs['aliases'])
        if (ctx.subcommand_passed is None) or (ctx.subcommand_passed.lower() in help_aliases):
            await ctx.send_help(ctx.command)
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)
        invoked_cmd = f'{prefix + ctx.invoked_with} {ctx.subcommand_passed}'
        embed = discord.Embed(title='Error', description=f'`{invoked_cmd}` does not exist! Use `{prefix}help` to see all the commands I can run.')
        await ctx.reply(embed=embed)

    @whitelist_group.command(name='set', help='Set the whitelist channel for AutoTSS commands.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.has_permissions(administrator=True)
    async def set_whitelist_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        if channel.guild != ctx.guild:
            embed = discord.Embed(title='Error', description=f'{channel.mention} is not a valid channel.')
            await ctx.reply(embed=embed)
            return

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * FROM whitelist WHERE guild = ?', (ctx.guild.id,)) as cursor:
            if await cursor.fetchone() is None:
                sql = 'INSERT INTO whitelist(channel, enabled, guild) VALUES(?,?,?)'
            else:
                sql = 'UPDATE whitelist SET channel = ?, enabled = ? WHERE guild = ?'
                
            await db.execute(sql, (channel.id, True, ctx.guild.id))
            await db.commit()

        embed = discord.Embed(title='Whitelist', description=f'Enabled AutoTSS whitelisting and set to {channel.mention}.')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)

    @whitelist_group.command(name='toggle', help='Toggle the whitelist for AutoTSS commands on/off.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.has_permissions(administrator=True)
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
                    embed.description = f"No{'w' if not data[2] == True else ' longer'} restricting commands for AutoTSS to {channel.mention}."
                    embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            else:
                embed = discord.Embed(title='Error', description='No whitelist channel is set.')

        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(WhitelistCog(bot))
