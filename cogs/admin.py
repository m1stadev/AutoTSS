from discord import permissions, Option
from discord.commands.context import AutocompleteContext
from discord.errors import ExtensionAlreadyLoaded, ExtensionFailed, ExtensionNotLoaded
from discord.ext import commands
from views.buttons import SelectView

import aiofiles
import aiopath
import aiosqlite
import asyncio
import discord
import json
import time


async def mod_autocomplete(ctx: AutocompleteContext) -> list:
    modules = sorted([cog.stem async for cog in aiopath.AsyncPath('cogs').glob('*.py')])

    return [_ for _ in modules if _.startswith(ctx.value.lower())]

class AdminCog(commands.Cog, name='Administrator'):
    def __init__(self, bot):
        self.bot = bot
        self.utils = bot.get_cog('Utilities')

    admin = discord.SlashCommandGroup('admin', 'Administrator commands', guild_ids=(729946499102015509,), permissions=[permissions.Permission('owner', 2, True)])

    async def get_modules(self): return sorted([cog.stem async for cog in aiopath.AsyncPath('cogs').glob('*.py')])

    @admin.command(name='modlist', description='List all modules.')
    async def list_modules(self, ctx: discord.ApplicationContext) -> None:
        embed = discord.Embed(title='All Modules', description=f"`{'`, `'.join(await self.get_modules())}`")
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        await ctx.respond(embed=embed, ephemeral=True)

    @admin.command(name='modload', description='Load a module.')
    async def load_module(self, ctx: discord.ApplicationContext, module: Option(str, description='Module to load', autocomplete=mod_autocomplete)) -> None:
        await ctx.defer(ephemeral=True)

        if not any(module == x for x in await self.get_modules()):
            embed = discord.Embed(title='Unload Module')
            embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
            embed.add_field(name='Available modules:', value=f"`{'`, `'.join(await self.get_modules())}`", inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.respond(embed=embed)
            return

        try:
            self.bot.load_extension(f'cogs.{module}')
            embed = discord.Embed(title='Load Module', description=f'Module `{module}` has been loaded.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        except ExtensionAlreadyLoaded:
            embed = discord.Embed(title='Error', description=f'Module `{module}` is already loaded.')
        except ExtensionFailed:
            embed = discord.Embed(title='Error', description=f'Module `{module}` has an error, cannot load.')

        await ctx.respond(embed=embed)

    @admin.command(name='modunload', description='Unload a module.')
    async def unload_module(self, ctx: discord.ApplicationContext, module: Option(str, description='Module to unload', autocomplete=mod_autocomplete)) -> None:
        await ctx.defer(ephemeral=True)

        if module not in (await self.get_modules()):
            embed = discord.Embed(title='Unload Module')
            embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
            embed.add_field(name='Available modules:', value=f"`{'`, `'.join(await self.get_modules())}`", inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.respond(embed=embed)
            return

        try:
            self.bot.unload_extension(f'cogs.{module}')
            embed = discord.Embed(title='Unload Module', description=f'Module `{module}` has been unloaded.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        except ExtensionNotLoaded:
            embed = discord.Embed(title='Error', description=f'Module `{module}` is not loaded.')

        await ctx.respond(embed=embed)

    @admin.command(name='modreload', description='Reload a module.')
    async def reload_module(self, ctx: discord.ApplicationContext, module: Option(str, description='Module to reload', autocomplete=mod_autocomplete)) -> None:
        await ctx.defer(ephemeral=True)

        if module not in (await self.get_modules()):
            embed = discord.Embed(title='Reload Module')
            embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
            embed.add_field(name='Available modules:', value=f"`{'`, `'.join(await self.get_modules())}`", inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.respond(embed=embed)
            return

        try:
            self.bot.reload_extension(f'cogs.{module}')
            embed = discord.Embed(title='Reload Module', description=f'Module `{module}` has been reloaded.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        except ExtensionNotLoaded:
            try:
                self.bot.load_extension(f'cogs.{module}')
            except ExtensionFailed:
                embed = discord.Embed(title='Error', description=f'Module `{module}` has an error, cannot reload.')

        except ExtensionFailed:
            embed = discord.Embed(title='Error', description=f'Module `{module}` has an error, cannot reload.')

        await ctx.respond(embed=embed)


    @admin.command(name='modunload', description='Unload a module.')
    async def unload_module(self, ctx: discord.ApplicationContext, *cogs: str) -> None:
        modules = sorted([cog.lower() for cog in cogs])

        if len(modules) > 1 or modules[0] == 'all':
            embed = discord.Embed(title='Unload Module')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.respond(embed=embed, ephemeral=True)
            successful_unloads = int()
            failed_unloads = int()

            for module in (await self.get_modules() if modules[0] == 'all' else modules):
                if not any(module == x for x in await self.get_modules()):
                    embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
                    await ctx.edit(embed=embed)
                    failed_unloads += 1
                    continue

                if module == 'admin':
                    embed.add_field(name='Error', value=f'Module `{module}` cannot be unloaded!', inline=False)
                    await ctx.edit(embed=embed)
                    failed_unloads += 1
                    continue

                try:
                    self.bot.unload_extension(f'cogs.{module}')
                    embed.add_field(name='Success', value=f'Module `{module}` successfully unloaded!', inline=False)
                    await ctx.edit(embed=embed)
                    successful_unloads += 1
                except discord.ext.commands.ExtensionNotLoaded:
                    embed.add_field(name='Error', value=f'Module `{module}` is already unloaded!', inline=False)
                    await ctx.edit(embed=embed)
                    failed_unloads += 1

            embed.add_field(name='Finished', value=f"**{successful_unloads}** module{'s' if successful_unloads != 1 else ''} successfully unloaded, **{failed_unloads}** module{'s' if failed_unloads != 1 else ''} failed to unload.")
            await ctx.edit(embed=embed)
            return

        if not any(modules[0] == x for x in await self.get_modules()):
            embed = discord.Embed(title='Unload Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` does not exist!', inline=False)
            embed.add_field(name='Available modules:', value=f"`{'`, `'.join(await self.get_modules())}`", inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.respond(embed=embed, ephemeral=True)
            return

        try:
            self.bot.unload_extension(f'cogs.{modules[0]}')
            embed = discord.Embed(title='Unload Module', description=f'Module `{modules[0]}` has been unloaded.')
        except discord.ext.commands.ExtensionNotLoaded:
            embed = discord.Embed(title='Unload Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` is already unloaded!')

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(AdminCog(bot))
