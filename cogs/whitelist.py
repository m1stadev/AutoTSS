
from discord.ext import commands
from discord import Option
from views.buttons import PaginatorView

import discord


class WhitelistCog(commands.Cog, name='Whitelist'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.utils = self.bot.get_cog('Utilities')

    whitelist = discord.SlashCommandGroup('whitelist', 'Whitelist commands')

    @whitelist.command(name='help', description='View all whitelist commands.')
    async def _help(self, ctx: discord.ApplicationContext) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        cmd_embeds = [await self.utils.cmd_help_embed(ctx, _) for _ in self.whitelist.subcommands]

        paginator = PaginatorView(cmd_embeds, ctx, timeout=180)
        await ctx.respond(embed=cmd_embeds[paginator.embed_num], view=paginator)

    @whitelist.command(name='set', description='Set the whitelist channel for AutoTSS commands.')
    async def set_whitelist_channel(self, ctx: discord.ApplicationContext, channel: Option(discord.TextChannel, description='Channel to allow AutoTSS commands in.')) -> None:
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(title='Error', description='You do not have permission to run this command.')
            await ctx.respond(embed=embed, ephemeral=True)

        if channel.guild != ctx.guild:
            embed = discord.Embed(title='Error', description=f'{channel.mention} is not a valid channel.')
            await ctx.respond(embed=embed)
            return

        async with self.bot.db.execute('SELECT * FROM whitelist WHERE guild = ?', (ctx.guild.id,)) as cursor:
            if await cursor.fetchone() is None:
                sql = 'INSERT INTO whitelist(channel, enabled, guild) VALUES(?,?,?)'
            else:
                sql = 'UPDATE whitelist SET channel = ?, enabled = ? WHERE guild = ?'
                
            await self.bot.db.execute(sql, (channel.id, True, ctx.guild.id))
            await self.bot.db.commit()

        embed = discord.Embed(title='Whitelist', description=f'Enabled AutoTSS whitelisting and set whitelist channel to {channel.mention}.')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.respond(embed=embed)

    @whitelist.command(name='toggle', description='Toggle the whitelist for AutoTSS commands on/off.')
    async def toggle_whitelist(self, ctx: discord.ApplicationContext) -> None:
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(title='Error', description='You do not have permission to run this command.')
            await ctx.respond(embed=embed, ephemeral=True)

        await ctx.defer()

        async with self.bot.db.execute('SELECT * FROM whitelist WHERE guild = ?', (ctx.guild.id,)) as cursor:
            data = await cursor.fetchone()

        if type(data) == tuple:
            channel = ctx.guild.get_channel(data[1])
            if channel is None:
                embed = discord.Embed(title='Error', description=f'Channel `{data[1]}` no longer exists, please set a new whitelist channel.')
            else:
                await self.bot.db.execute('UPDATE whitelist SET enabled = ? WHERE guild = ?', (not data[2], ctx.guild.id))
                await self.bot.db.commit()

                embed = discord.Embed(title='Whitelist')
                embed.description = f"No{'w' if not data[2] == True else ' longer'} restricting commands for AutoTSS to {channel.mention}."
                embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        else:
            embed = discord.Embed(title='Error', description='No whitelist channel is set.')

        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(WhitelistCog(bot))
