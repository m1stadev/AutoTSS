from discord import permissions
from discord.ext import commands

import aiopath
import discord


#TODO: Implement autocomplete for module command arguments, implement modedit command with paginator interface to unload, reload + load modules

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
    async def load_module(self, ctx: discord.ApplicationContext, *cogs: str) -> None:
        modules = sorted([cog.lower() for cog in cogs])

        if len(modules) > 1 or modules[0] == 'all':
            embed = discord.Embed(title='Load Module')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.respond(embed=embed, ephemeral=True)
            successful_loads = int()
            failed_loads = int()

            for module in (await self.get_modules() if modules[0] == 'all' else modules):
                if not any(module == x for x in await self.get_modules()):
                    embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
                    await ctx.edit(embed=embed)
                    failed_loads += 1
                    continue

                try:
                    self.bot.load_extension(f'cogs.{module}')
                    embed.add_field(name='Success', value=f'Module `{module}` successfully unloaded!', inline=False)
                    await ctx.edit(embed=embed)
                    successful_loads += 1
                except discord.ext.commands.ExtensionAlreadyLoaded:
                    embed.add_field(name='Error', value=f'Module `{module}` is already loaded!', inline=False)
                    await ctx.edit(embed=embed)
                    failed_loads += 1
                except discord.ext.commands.ExtensionFailed:
                    embed.add_field(name='Error', value=f'Module `{module}` has an error, cannot load!', inline=False)
                    await ctx.edit(embed=embed)
                    failed_loads += 1

            embed.add_field(name='Finished', value=f"**{successful_loads}** module{'s' if successful_loads != 1 else ''} successfully loaded, **{failed_loads}** module{'s' if failed_loads != 1 else ''} failed to load.")
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
            self.bot.load_extension(f'cogs.{modules[0]}')
            embed = discord.Embed(title='Load Module', description=f'Module `{modules[0]}` has been loaded.')
        except discord.ext.commands.ExtensionAlreadyLoaded:
            embed = discord.Embed(title='Load Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` is already loaded!')
        except discord.ext.commands.ExtensionFailed:
            embed = discord.Embed(title='Load Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` has an error, cannot load!')

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.respond(embed=embed, ephemeral=True)

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
