from .botutils import UtilsCog
from collections import namedtuple
from discord.ext import commands
from discord import Option
from views.buttons import PaginatorView

import discord


WhitelistData = namedtuple('WhitelistData', ['guild', 'channel', 'enabled'])


class WhitelistCog(commands.Cog, name='Whitelist'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.utils: UtilsCog = self.bot.get_cog('Utilities')

    whitelist = discord.SlashCommandGroup('whitelist', 'Whitelist commands')

    @whitelist.command(name='help', description='View all whitelist commands.')
    async def _help(self, ctx: discord.ApplicationContext) -> None:
        cmd_embeds = [
            self.utils.cmd_help_embed(ctx, sc) for sc in self.whitelist.subcommands
        ]

        paginator = PaginatorView(cmd_embeds, ctx, timeout=180)
        await ctx.respond(
            embed=cmd_embeds[paginator.embed_num], view=paginator, ephemeral=True
        )

    @whitelist.command(
        name='set', description='Set the whitelist channel for AutoTSS commands.'
    )
    async def set_whitelist_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: Option(
            discord.TextChannel, description='Channel to allow AutoTSS commands in.'
        ),
    ) -> None:
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingPermissions(['administrator'])

        async with self.bot.db.execute(
            'SELECT * FROM whitelist WHERE guild = ?', (ctx.guild.id,)
        ) as cursor:
            if await cursor.fetchone() is None:
                sql = 'INSERT INTO whitelist(channel, enabled, guild) VALUES(?,?,?)'
            else:
                sql = 'UPDATE whitelist SET channel = ?, enabled = ? WHERE guild = ?'

            await self.bot.db.execute(sql, (channel.id, True, ctx.guild.id))
            await self.bot.db.commit()

        embed = discord.Embed(
            title='Whitelist',
            description=f'Enabled AutoTSS whitelisting and set whitelist channel to {channel.mention}.',
        )
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )
        await ctx.respond(embed=embed)

    @whitelist.command(
        name='toggle', description='Toggle the whitelist for AutoTSS commands on/off.'
    )
    async def toggle_whitelist(self, ctx: discord.ApplicationContext) -> None:
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingPermissions(['administrator'])

        await ctx.defer()

        async with self.bot.db.execute(
            'SELECT * FROM whitelist WHERE guild = ?', (ctx.guild.id,)
        ) as cursor:
            data = await cursor.fetchone()

        if data is None:
            raise commands.BadArgument('No whitelist channel is set.')

        whitelist = WhitelistData(*data)
        channel = ctx.guild.get_channel(whitelist.channel)

        if channel is None:
            raise commands.ChannelNotFound(whitelist.channel)
        else:
            await self.bot.db.execute(
                'UPDATE whitelist SET enabled = ? WHERE guild = ?',
                (not whitelist.enabled, ctx.guild.id),
            )
            await self.bot.db.commit()

            embed = discord.Embed(title='Whitelist')
            embed.description = f"No{'w' if whitelist.enabled == False else ' longer'} restricting commands for AutoTSS to {channel.mention}."
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )

        await ctx.respond(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(WhitelistCog(bot))
