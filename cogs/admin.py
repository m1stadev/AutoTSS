from discord.commands import permissions
from discord.ext import commands

import aiopath
import discord


#TODO: Implement autocomplete for module command arguments

class AdminCog(commands.Cog, name='Administrator'):
    def __init__(self, bot):
        self.bot = bot
        self.utils = bot.get_cog('Utilities')

    module = discord.SlashCommandGroup('module', 'Module commands', guild_ids=(729946499102015509,), permissions=[permissions.Permission("owner", 2, True)])

    async def get_modules(self): return sorted([cog.stem async for cog in aiopath.AsyncPath('cogs').glob('*.py')])

    @module.command(name='list', description='List all modules.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
    async def list_modules(self, ctx: discord.ApplicationContext) -> None:
        embed = discord.Embed(title='All Modules', description=f"`{'`, `'.join(await self.get_modules())}`")
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        await ctx.respond(embed=embed, ephemeral=True)

    @module.command(name='load', description='Load a module.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
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

    @module.command(name='reload', description='Reload a module.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
    async def reload_module(self, ctx: discord.ApplicationContext, *cogs: str) -> None:
        modules = sorted([cog.lower() for cog in cogs])

        if len(modules) > 1 or modules[0] == 'all':
            embed = discord.Embed(title='Reload Module')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.respond(embed=embed, ephemeral=True)
            successful_reloads = int()
            failed_reloads = int()

            for module in (await self.get_modules() if modules[0] == 'all' else modules):
                if module not in (await self.get_modules()):
                    embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
                    await ctx.edit(embed=embed)
                    failed_reloads += 1
                    continue

                try:
                    self.bot.reload_extension(f'cogs.{module}')
                    embed.add_field(name='Success', value=f'Module `{module}` successfully reloaded!', inline=False)
                    await ctx.edit(embed=embed)
                    successful_reloads += 1
                except discord.ext.commands.ExtensionNotLoaded:
                    embed.add_field(name='Error', value=f'Module `{module}` is not currently loaded!', inline=False)
                    await ctx.edit(embed=embed)
                    failed_reloads += 1
                except discord.ext.commands.ExtensionFailed:
                    embed.add_field(name='Error', value=f'Module `{module}` failed to reload!', inline=False)
                    await ctx.edit(embed=embed)
                    failed_reloads += 1

            embed.add_field(name='Finished', value=f"**{successful_reloads}** module{'s' if successful_reloads != 1 else ''} successfully reloaded, **{failed_reloads}** module{'s' if failed_reloads != 1 else ''} failed to reload.")
            await ctx.edit(embed=embed)
            return

        if modules[0] not in (await self.get_modules()):
            embed = discord.Embed(title='Reload Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` does not exist!', inline=False)
            embed.add_field(name='Available modules:', value=f"`{'`, `'.join(await self.get_modules())}`", inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.respond(embed=embed, ephemeral=True)
            return

        try:
            self.bot.reload_extension(f'cogs.{modules[0]}')
            embed = discord.Embed(title='Reload Module', description=f'Module `{modules[0]}` has been reloaded.')
        except discord.ext.commands.ExtensionNotLoaded:
            try:
                self.bot.load_extension(f'cogs.{modules[0]}')
            except discord.ext.commands.ExtensionFailed:
                embed = discord.Embed(title='Reload Module')
                embed.add_field(name='Error', value=f'Module `{modules[0]}` has an error, cannot load!')
        except discord.ext.commands.ExtensionFailed:
            embed = discord.Embed(title='Reload Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` has an error, cannot load!')

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.respond(embed=embed, ephemeral=True)

    @module.command(name='unload', description='Unload a module.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
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
