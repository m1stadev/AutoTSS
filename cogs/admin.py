from .utils import UtilsCog
from discord.errors import ExtensionAlreadyLoaded, ExtensionFailed, ExtensionNotLoaded
from discord.ext import commands
from discord.commands import permissions, Option
from utils.views.buttons import PaginatorView

import aiopath
import discord


async def mod_autocomplete(ctx: discord.AutocompleteContext) -> list:
    modules = sorted([cog.stem async for cog in aiopath.AsyncPath('cogs').glob('*.py')])

    return [m for m in modules if m.startswith(ctx.value.lower())]


class AdminCog(commands.Cog, name='Administrator'):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.utils: UtilsCog = self.bot.get_cog('Utilities')

    admin = discord.SlashCommandGroup('admin', 'Administrator commands')

    async def get_modules(self):
        return sorted(
            [cog.stem async for cog in aiopath.AsyncPath('cogs').glob('*.py')]
        )

    @permissions.is_owner()
    @admin.command(name='help', description='View all administrator commands.')
    async def _help(self, ctx: discord.ApplicationContext) -> None:
        cmd_embeds = [
            self.utils.cmd_help_embed(ctx, sc) for sc in self.admin.subcommands
        ]

        paginator = PaginatorView(cmd_embeds, ctx, timeout=180)
        await ctx.respond(
            embed=cmd_embeds[paginator.embed_num], view=paginator, ephemeral=True
        )

    @permissions.is_owner()
    @admin.command(name='modlist', description='List all modules.')
    async def list_modules(self, ctx: discord.ApplicationContext) -> None:
        embed = discord.Embed(
            title='All Modules',
            description=f"`{'`, `'.join(await self.get_modules())}`",
        )
        embed.set_footer(
            text=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.with_static_format('png').url,
        )

        await ctx.respond(embed=embed, ephemeral=True)

    @permissions.is_owner()
    @admin.command(name='modload', description='Load a module.')
    async def load_module(
        self,
        ctx: discord.ApplicationContext,
        module: Option(
            str, description='Module to load', autocomplete=mod_autocomplete
        ),
    ) -> None:
        await ctx.defer(ephemeral=True)

        if not any(module == x for x in await self.get_modules()):
            embed = discord.Embed(title='Unload Module')
            embed.add_field(
                name='Error', value=f'Module `{module}` does not exist!', inline=False
            )
            embed.add_field(
                name='Available modules:',
                value=f"`{'`, `'.join(await self.get_modules())}`",
                inline=False,
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )
            await ctx.respond(embed=embed)
            return

        try:
            self.bot.load_extension(f'cogs.{module}')
            embed = discord.Embed(
                title='Load Module', description=f'Module `{module}` has been loaded.'
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )
        except ExtensionAlreadyLoaded:
            embed = discord.Embed(
                title='Error', description=f'Module `{module}` is already loaded.'
            )
        except ExtensionFailed:
            embed = discord.Embed(
                title='Error',
                description=f'Module `{module}` has an error, cannot load.',
            )

        await ctx.respond(embed=embed)

        self.bot.logger.info(f'Loaded `{module}` module.')

    @permissions.is_owner()
    @admin.command(name='modunload', description='Unload a module.')
    async def unload_module(
        self,
        ctx: discord.ApplicationContext,
        module: Option(
            str, description='Module to unload', autocomplete=mod_autocomplete
        ),
    ) -> None:
        await ctx.defer(ephemeral=True)

        if module not in (await self.get_modules()):
            embed = discord.Embed(title='Unload Module')
            embed.add_field(
                name='Error', value=f'Module `{module}` does not exist!', inline=False
            )
            embed.add_field(
                name='Available modules:',
                value=f"`{'`, `'.join(await self.get_modules())}`",
                inline=False,
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )
            await ctx.respond(embed=embed)
            return

        try:
            self.bot.unload_extension(f'cogs.{module}')
            embed = discord.Embed(
                title='Unload Module',
                description=f'Module `{module}` has been unloaded.',
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )
        except ExtensionNotLoaded:
            embed = discord.Embed(
                title='Error', description=f'Module `{module}` is not loaded.'
            )

        await ctx.respond(embed=embed)

        self.bot.logger.info(f'Unloaded `{module}` module.')

    @permissions.is_owner()
    @admin.command(name='modreload', description='Reload a module.')
    async def reload_module(
        self,
        ctx: discord.ApplicationContext,
        module: Option(
            str, description='Module to reload', autocomplete=mod_autocomplete
        ),
    ) -> None:
        await ctx.defer(ephemeral=True)

        if module not in (await self.get_modules()):
            embed = discord.Embed(title='Reload Module')
            embed.add_field(
                name='Error', value=f'Module `{module}` does not exist!', inline=False
            )
            embed.add_field(
                name='Available modules:',
                value=f"`{'`, `'.join(await self.get_modules())}`",
                inline=False,
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )
            await ctx.respond(embed=embed)
            return

        try:
            self.bot.reload_extension(f'cogs.{module}')
            embed = discord.Embed(
                title='Reload Module',
                description=f'Module `{module}` has been reloaded.',
            )
            embed.set_footer(
                text=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.with_static_format('png').url,
            )

        except ExtensionNotLoaded:
            try:
                self.bot.load_extension(f'cogs.{module}')
            except ExtensionFailed:
                embed = discord.Embed(
                    title='Error',
                    description=f'Module `{module}` has an error, cannot reload.',
                )

        except ExtensionFailed:
            embed = discord.Embed(
                title='Error',
                description=f'Module `{module}` has an error, cannot reload.',
            )

        await ctx.respond(embed=embed)
        self.bot.logger.info(f'Reloaded `{module}` module.')


def setup(bot: discord.Bot):
    bot.add_cog(AdminCog(bot))
