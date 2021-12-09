from discord.ext import commands

import aiofiles
import aiohttp
import asyncio
import discord
import glob


class AdminCog(commands.Cog, name='Administrator'):
    def __init__(self, bot):
        self.bot = bot
        self.utils = bot.get_cog('Utilities')

    @property
    def modules(self): return sorted([cog.split('/')[-1][:-3] for cog in glob.glob('cogs/*.py')])

    @commands.group(name='module', aliases=('m',), help='Module management commands.', invoke_without_command=True)
    @commands.guild_only()
    @commands.is_owner()
    async def module_group(self, ctx: commands.Context) -> None:
        help_aliases = (self.bot.help_command.command_attrs['name'], *self.bot.help_command.command_attrs['aliases'])
        if (ctx.subcommand_passed is None) or (ctx.subcommand_passed.lower() in help_aliases):
            await ctx.send_help(ctx.command)
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)
        invoked_cmd = f'{prefix + ctx.invoked_with} {ctx.subcommand_passed}'
        embed = discord.Embed(title='Error', description=f'`{invoked_cmd}` does not exist! Use `{prefix}help` to see all the commands I can run.')
        await ctx.reply(embed=embed)

    @module_group.command(name='list', help='List all modules.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
    async def list_modules(self, ctx: commands.Context) -> None:
        embed = discord.Embed(title='All Modules', description=f"`{'`, `'.join(self.modules)}`")
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        await ctx.reply(embed=embed)

    @module_group.command(name='load', help='Load a module.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
    async def load_module(self, ctx: commands.Context, *cogs: str) -> None:
        modules = sorted([cog.lower() for cog in cogs])

        if len(modules) > 1 or modules[0] == 'all':
            embed = discord.Embed(title='Load Module')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            message = await ctx.reply(embed=embed)
            successful_loads = int()
            failed_loads = int()

            for module in (self.modules if modules[0] == 'all' else modules):
                if not any(module == x for x in self.modules):
                    embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
                    message = await message.edit(embed=embed)
                    failed_loads += 1
                    continue

                try:
                    self.bot.load_extension(f'cogs.{module}')
                    embed.add_field(name='Success', value=f'Module `{module}` successfully unloaded!', inline=False)
                    message = await message.edit(embed=embed)
                    successful_loads += 1
                except discord.ext.commands.ExtensionAlreadyLoaded:
                    embed.add_field(name='Error', value=f'Module `{module}` is already loaded!', inline=False)
                    message = await message.edit(embed=embed)
                    failed_loads += 1
                except discord.ext.commands.ExtensionFailed:
                    embed.add_field(name='Error', value=f'Module `{module}` has an error, cannot load!', inline=False)
                    message = await message.edit(embed=embed)
                    failed_loads += 1

            embed.add_field(name='Finished', value=f"**{successful_loads}** module{'s' if successful_loads != 1 else ''} successfully loaded, **{failed_loads}** module{'s' if failed_loads != 1 else ''} failed to load.")
            await message.edit(embed=embed)
            return

        if not any(modules[0] == x for x in self.modules):
            embed = discord.Embed(title='Unload Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` does not exist!', inline=False)
            embed.add_field(name='Available modules:', value=f"`{'`, `'.join(self.modules)}`", inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.reply(embed=embed)
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
        await ctx.reply(embed=embed)

    @module_group.command(name='reload', help='Reload a module.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
    async def reload_module(self, ctx: commands.Context, *cogs: str) -> None:
        modules = sorted([cog.lower() for cog in cogs])

        if len(modules) > 1 or modules[0] == 'all':
            embed = discord.Embed(title='Reload Module')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            message = await ctx.reply(embed=embed)
            successful_reloads = int()
            failed_reloads = int()

            for module in (self.modules if modules[0] == 'all' else modules):
                if module not in self.modules:
                    embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
                    message = await message.edit(embed=embed)
                    failed_reloads += 1
                    continue

                try:
                    self.bot.reload_extension(f'cogs.{module}')
                    embed.add_field(name='Success', value=f'Module `{module}` successfully reloaded!', inline=False)
                    message = await message.edit(embed=embed)
                    successful_reloads += 1
                except discord.ext.commands.ExtensionNotLoaded:
                    embed.add_field(name='Error', value=f'Module `{module}` is not currently loaded!', inline=False)
                    message = await message.edit(embed=embed)
                    failed_reloads += 1
                except discord.ext.commands.ExtensionFailed:
                    embed.add_field(name='Error', value=f'Module `{module}` failed to reload!', inline=False)
                    message = await message.edit(embed=embed)
                    failed_reloads += 1

            embed.add_field(name='Finished', value=f"**{successful_reloads}** module{'s' if successful_reloads != 1 else ''} successfully reloaded, **{failed_reloads}** module{'s' if failed_reloads != 1 else ''} failed to reload.")
            await message.edit(embed=embed)
            return

        if modules[0] not in self.modules:
            embed = discord.Embed(title='Reload Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` does not exist!', inline=False)
            embed.add_field(name='Available modules:', value=f"`{'`, `'.join(self.modules)}`", inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.reply(embed=embed)
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
        await ctx.reply(embed=embed)

    @module_group.command(name='unload', help='Unload a module.')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.default)
    @commands.is_owner()
    async def unload_module(self, ctx: commands.Context, *cogs: str) -> None:
        modules = sorted([cog.lower() for cog in cogs])

        if len(modules) > 1 or modules[0] == 'all':
            embed = discord.Embed(title='Unload Module')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            message = await ctx.reply(embed=embed)
            successful_unloads = int()
            failed_unloads = int()

            for module in (self.modules if modules[0] == 'all' else modules):
                if not any(module == x for x in self.modules):
                    embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
                    message = await message.edit(embed=embed)
                    failed_unloads += 1
                    continue

                if module == 'admin':
                    embed.add_field(name='Error', value=f'Module `{module}` cannot be unloaded!', inline=False)
                    message = await message.edit(embed=embed)
                    failed_unloads += 1
                    continue

                try:
                    self.bot.unload_extension(f'cogs.{module}')
                    embed.add_field(name='Success', value=f'Module `{module}` successfully unloaded!', inline=False)
                    message = await message.edit(embed=embed)
                    successful_unloads += 1
                except discord.ext.commands.ExtensionNotLoaded:
                    embed.add_field(name='Error', value=f'Module `{module}` is already unloaded!', inline=False)
                    message = await message.edit(embed=embed)
                    failed_unloads += 1

            embed.add_field(name='Finished', value=f"**{successful_unloads}** module{'s' if successful_unloads != 1 else ''} successfully unloaded, **{failed_unloads}** module{'s' if failed_unloads != 1 else ''} failed to unload.")
            await message.edit(embed=embed)
            return

        if not any(modules[0] == x for x in self.modules):
            embed = discord.Embed(title='Unload Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` does not exist!', inline=False)
            embed.add_field(name='Available modules:', value=f"`{'`, `'.join(self.modules)}`", inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.reply(embed=embed)
            return

        try:
            self.bot.unload_extension(f'cogs.{modules[0]}')
            embed = discord.Embed(title='Unload Module', description=f'Module `{modules[0]}` has been unloaded.')
        except discord.ext.commands.ExtensionNotLoaded:
            embed = discord.Embed(title='Unload Module')
            embed.add_field(name='Error', value=f'Module `{modules[0]}` is already unloaded!')

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(AdminCog(bot))
