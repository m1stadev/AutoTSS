from discord.ext import commands
import aiofiles
import aiohttp
import aiosqlite
import asyncio
import discord
import glob
import math
import time
import platform


class Admin(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	def get_modules(self):
		if platform.system() == 'Windows':
			modules = glob.glob('cogs\*.py')
		else:
			modules = glob.glob('cogs/*.py')

		return sorted([module.replace('/', '.').replace('\\', '.')[:-3].split('.')[-1] for module in modules])

	@commands.group(invoke_without_command=True)
	@commands.is_owner()
	async def module(self, ctx):
		if ctx.prefix == f'<@!{self.bot.user.id}> ':
			prefix = f'{ctx.prefix}`'
		else:
			prefix = f'`{ctx.prefix}'

		embed = discord.Embed(title='Module Commands')
		embed.add_field(name='Edit', value=f'{prefix}module edit <module>`', inline=False)
		embed.add_field(name='List', value=f'{prefix}module list`', inline=False)
		embed.add_field(name='Load', value=f'{prefix}module load <module>`', inline=False)
		embed.add_field(name='Reload', value=f'{prefix}module reload <all/module>`', inline=False)
		embed.add_field(name='Unload', value=f'{prefix}module unload <module>`', inline=False)
		embed.add_field(name='Note:', value='Use commas to separate multiple modules.', inline=False)
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await ctx.send(embed=embed)

	@module.command()
	@commands.is_owner()
	@commands.guild_only()
	async def edit(self, ctx, *modules):
		local_modules = self.get_modules()
		modules = [module.lower() for module in modules]

		if len(modules) > 1:
			embed = discord.Embed(title='Edit Module')
			embed.add_field(name='Error', description='You can only edit one module at a time!')
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		if modules[0] not in local_modules:
			embed = discord.Embed(title='Edit Module')
			embed.add_field(name='Error', description=f'Module `{modules[0]}` does not exist!')
			embed.add_field(name='Available modules:', value=f"`{'`, `'.join(local_modules)}`")
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Edit Module', description=f'Send a link to the raw code you wish to update the `{modules[0]}` module to.')
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		message = await ctx.send(embed=embed)

		try:
			answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
		except asyncio.exceptions.TimeoutError:
			embed = discord.Embed(title='Edit Module')
			embed.add_field(name='Error', value='No response given in 1 minute, cancelling.')
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		await answer.delete()

		async with aiofiles.open(f'cogs/{modules[0]}.py', 'r') as f:
			old_module = await f.read()

		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(answer.content) as response:
					new_module = await response.text().replace('    ', '	') # fuck space indents, shifts FTW

		except aiohttp.client_exceptions.InvalidURL:
			embed = discord.Embed(title='Edit Module')
			embed.add_field(name='Error', value='Response is not a valid URL.')
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		if old_module == new_module:
			embed = discord.Embed(title='Edit Module')
			embed.add_field(name='Error', value=f'URL content is the same as current module `{modules[0]}` content.')
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)
			return

		async with aiofiles.open(f'cogs/{modules[0]}.py', 'w') as f:
			await f.write(new_module)

		try:
			self.bot.reload_extension(f'cogs.{modules[0]}')
			embed = discord.Embed(title='Edit Module', description=f'Module `{modules[0]}` has been reloaded.')
		except discord.ext.commands.ExtensionNotLoaded: # Attempt to load module
			try:
				self.bot.load_extension(f'cogs.{modules[0]}')
			except discord.ext.commands.ExtensionFailed:
				embed = discord.Embed(title='Edit Module')
				embed.add_field(name='Error', value=f'Module `{modules[0]}` has an error, reverting to backup!')

				async with aiofiles.open(f'cogs/{modules[0]}.py', 'w') as f:
					await f.write(old_module)

		except discord.ext.commands.ExtensionFailed:
			embed = discord.Embed(title='Edit Module')
			embed.add_field(name='Error', value=f'Module `{modules[0]}` has an error, reverting to backup!')

			async with aiofiles.open(f'cogs/{modules[0]}.py', 'w') as f:
				await f.write(old_module)

		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

	@module.command(name='list')
	@commands.guild_only()
	@commands.is_owner()
	async def _list(self, ctx):
		local_modules = self.get_modules()

		embed = discord.Embed(title='All Modules', description=f"`{'`, `'.join(local_modules)}`")
		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png')) 
		await ctx.send(embed=embed)

	@module.command()
	@commands.is_owner()
	@commands.guild_only()
	async def load(self, ctx, *modules):
		local_modules = self.get_modules()
		modules = sorted([module.lower() for module in modules])
		
		if len(modules) > 1 or modules[0] == 'all':
			embed = discord.Embed(title='Load Module')
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			message = await ctx.send(embed=embed)
			successful_loads = int()
			failed_loads = int()

			for module in (local_modules if modules[0] == 'all' else modules):
				if not any(module == x for x in local_modules):
					embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
					await message.edit(embed=embed)
					failed_loads += 1
					continue

				try:
					self.bot.load_extension(f'cogs.{module}')
					embed.add_field(name='Success', value=f'Module `{module}` successfully unloaded!', inline=False)
					await message.edit(embed=embed)
					successful_loads += 1
				except discord.ext.commands.ExtensionAlreadyLoaded:
					embed.add_field(name='Error', value=f'Module `{module}` is already loaded!', inline=False)
					await message.edit(embed=embed)
					failed_loads += 1
				except discord.ext.commands.ExtensionFailed:
					embed.add_field(name='Error', value=f'Module `{module}` has an error, cannot load!', inline=False)
					await message.edit(embed=embed)
					failed_loads += 1

			embed.add_field(name='Finished', value=f"**{successful_loads}** module{'s' if successful_loads != 1 else ''} successfully loaded, **{failed_loads}** module{'s' if failed_loads != 1 else ''} failed to load.")
			await message.edit(embed=embed)
			return

		if not any(modules[0] == x for x in local_modules):
			embed = discord.Embed(title='Unload Module')
			embed.add_field(name='Error', value=f'Module `{modules[0]}` does not exist!', inline=False)
			embed.add_field(name='Available modules:', value=f"`{'`, `'.join(local_modules)}`", inline=False)
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
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

		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await ctx.send(embed=embed)

	@module.command(name='reload')
	@commands.is_owner()
	@commands.guild_only()
	async def _reload(self, ctx, *modules):
		local_modules = self.get_modules()
		modules = sorted([module.lower() for module in modules])
		
		if len(modules) > 1 or modules[0] == 'all':
			embed = discord.Embed(title='Reload Module')
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			message = await ctx.send(embed=embed)
			successful_reloads = int()
			failed_reloads = int()

			for module in (local_modules if modules[0] == 'all' else modules):
				if module not in local_modules:
					embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
					await message.edit(embed=embed)
					failed_reloads += 1
					continue

				try:
					self.bot.reload_extension(f'cogs.{module}')
					embed.add_field(name='Success', value=f'Module `{module}` successfully reloaded!', inline=False)
					await message.edit(embed=embed)
					successful_reloads += 1
				except discord.ext.commands.ExtensionNotLoaded:
					embed.add_field(name='Error', value=f'Module `{module}` is not currently loaded!', inline=False)
					await message.edit(embed=embed)
					failed_reloads += 1
				except discord.ext.commands.ExtensionFailed:
					embed.add_field(name='Error', value=f'Module `{module}` failed to reload!', inline=False)
					await message.edit(embed=embed)
					failed_reloads += 1

			embed.add_field(name='Finished', value=f"**{successful_reloads}** module{'s' if successful_reloads != 1 else ''} successfully reloaded, **{failed_reloads}** module{'s' if failed_reloads != 1 else ''} failed to reload.")
			await message.edit(embed=embed)
			return
		

		if modules[0] not in local_modules:
			embed = discord.Embed(title='Reload Module')
			embed.add_field(name='Error', value=f'Module `{modules[0]}` does not exist!', inline=False)
			embed.add_field(name='Available modules:', value=f"`{'`, `'.join(local_modules)}`", inline=False)
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
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

		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await ctx.send(embed=embed)

	@module.command()
	@commands.is_owner()
	@commands.guild_only()
	async def unload(self, ctx, *modules):
		local_modules = self.get_modules()
		modules = sorted([module.lower() for module in modules])
		
		if len(modules) > 1 or modules[0] == 'all':
			embed = discord.Embed(title='Unload Module')
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			message = await ctx.send(embed=embed)
			successful_unloads = int()
			failed_unloads = int()

			for module in (local_modules if modules[0] == 'all' else modules):
				if not any(module == x for x in local_modules):
					embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
					await message.edit(embed=embed)
					failed_unloads += 1
					continue

				if module == 'admin':
					embed.add_field(name='Error', value=f'Module `{module}` cannot be unloaded!', inline=False)
					await message.edit(embed=embed)
					failed_unloads += 1
					continue

				try:
					self.bot.unload_extension(f'cogs.{module}')
					embed.add_field(name='Success', value=f'Module `{module}` successfully unloaded!', inline=False)
					await message.edit(embed=embed)
					successful_unloads += 1
				except discord.ext.commands.ExtensionNotLoaded:
					embed.add_field(name='Error', value=f'Module `{module}` is already unloaded!', inline=False)
					await message.edit(embed=embed)
					failed_unloads += 1

			embed.add_field(name='Finished', value=f"**{successful_unloads}** module{'s' if successful_unloads != 1 else ''} successfully unloaded, **{failed_unloads}** module{'s' if failed_unloads != 1 else ''} failed to unload.")
			await message.edit(embed=embed)
			return

		if not any(modules[0] == x for x in local_modules):
			embed = discord.Embed(title='Unload Module')
			embed.add_field(name='Error', value=f'Module `{modules[0]}` does not exist!', inline=False)
			embed.add_field(name='Available modules:', value=f"`{'`, `'.join(local_modules)}`", inline=False)
			embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		try:
			self.bot.unload_extension(f'cogs.{modules[0]}')
			embed = discord.Embed(title='Unload Module', description=f'Module `{modules[0]}` has been unloaded.')
		except discord.ext.commands.ExtensionNotLoaded:
			embed = discord.Embed(title='Unload Module')
			embed.add_field(name='Error', value=f'Module `{modules[0]}` is already unloaded!')

		embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await ctx.send(embed=embed)

def setup(bot):
	bot.add_cog(Admin(bot))
