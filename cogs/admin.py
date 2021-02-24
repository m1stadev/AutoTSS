from discord.ext import commands
import aiohttp
import aiofiles
import asyncio
import discord
import glob


class Admin(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	async def list_cogs(self):
		cogs = str()

		for cog in glob.glob('cogs/*.py'):
			cogs += f"`{cog.split('/')[-1][:-3]}`, "
		return cogs[:-2]

	@commands.group(invoke_without_command=True)
	@commands.is_owner()
	@commands.guild_only()
	async def module(self, ctx):
		embed = discord.Embed(title='Module Commands')
		embed.add_field(name='List', value=f'`{ctx.prefix}module list`', inline=False)
		embed.add_field(name='Load', value=f'`{ctx.prefix}load <module>`', inline=False)
		embed.add_field(name='Reload', value=f'`{ctx.prefix}module reload <all/module>`', inline=False)
		embed.add_field(name='Unload', value=f'`{ctx.prefix}module unload <module>`', inline=False)
		embed.add_field(name='Edit', value=f'`{ctx.prefix}module edit <module>`', inline=False)
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await ctx.send(embed=embed)

	@module.command()
	@commands.is_owner()
	@commands.guild_only()
	async def load(self, ctx, *, module):
		try:
			self.bot.load_extension(f'cogs.{module}')
			embed = discord.Embed(title='Load', description=f'Module `{module}` has been loaded.')

		except discord.ext.commands.ExtensionAlreadyLoaded:
			embed = discord.Embed(title='Load')
			embed.add_field(name='Error', value=f'Module `{module}` is already loaded!', inline=False)

		except discord.ext.commands.ExtensionFailed:
			embed = discord.Embed(title='Load')
			embed.add_field(name='Error', description=f'Module `{module}` has an error, cannot load!', inline=False)

		except discord.ext.commands.ExtensionNotFound:
			embed = discord.Embed(title='Load')
			embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
			embed.add_field(name='Available modules', value=await self.list_cogs(), inline=False)

		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await ctx.send(embed=embed)

	@module.command()
	@commands.is_owner()
	@commands.guild_only()
	async def unload(self, ctx, *, module):
		if module == 'admin':
			embed = discord.Embed(title='Unload')
			embed.add_field(name='Error', value='You cannot unload the `admin` module!', inline=False)
		else:
			try:
				self.bot.unload_extension(f'cogs.{module}')
				embed = discord.Embed(title='Unload', description=f'Module `{module}` has been unloaded.')

			except discord.ext.commands.ExtensionNotLoaded:
				embed = discord.Embed(title='Unload')
				embed.add_field(name='Error', value=f"Module `{module}` is either already unloaded or doesn't exist!", inline=False)

		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await ctx.send(embed=embed)

	@module.command(name='reload')
	@commands.is_owner()
	@commands.guild_only()
	async def _reload(self, ctx, *, module):
		if module == 'all':
			for cog in glob.glob('cogs/*.py'):
				cog = cog.replace('/', '.')[:-3]

				embed = discord.Embed(title='Reload')

				try:
					self.bot.reload_extension(cog)
				except discord.ext.commands.ExtensionNotLoaded:
					embed.add_field(name='Error', value=f"Module `{cog.split('.')[-1]}` is not currently loaded!", inline=False)
					embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
					await ctx.send(embed=embed)

				except discord.ext.commands.ExtensionFailed:
					embed.add_field(name='Error', value=f'Module `{cog}` has an error, cannot reload!', inline=False)
					embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
					await ctx.send(embed=embed)

			embed = discord.Embed(title='Reload', description='All modules have been reloaded.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)

		else:
			try:
				self.bot.reload_extension(f'cogs.{module}')
				embed = discord.Embed(title='Reload', description=f'Module `{module}` has been reloaded.')

			except discord.ext.commands.ExtensionNotLoaded:
				embed = discord.Embed(title='Reload')
				embed.add_field(name='Error', value=f'Module `{module}` is not currently loaded!', inline=False)

			except discord.ext.commands.ExtensionFailed:
				embed = discord.Embed(title='Reload')
				embed.add_field(name='Error', value=f'Module `{module}` has an error, cannot load!', inline=False)

			except discord.ext.commands.ExtensionNotFound:
				embed = discord.Embed(title='Reload')
				embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
				embed.add_field(name='Available modules', value=await self.list_cogs(), inline=False)

			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)

	@module.command()
	@commands.is_owner()
	@commands.guild_only()
	async def edit(self, ctx, *, module):
		timeout_embed = discord.Embed(title='Edit', description='No response given in 1 minute, cancelling.')
		timeout_embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		if module not in await self.list_cogs() or module == 'admin':
			embed = discord.Embed(title='Edit')
			if module not in await self.list_cogs():
				embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
				embed.add_field(name='Available modules', value=await self.list_cogs(), inline=False)
			else:
				embed.add_field(name='Error', value='Module `admin` cannot be edited!', inline=False)

			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await ctx.send(embed=embed)
			return

		embed = discord.Embed(title='Edit', description=f'Send a link to the raw text you wish to update `{module}` to.\nType `cancel` to cancel.')
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		message = await ctx.send(embed=embed)

		async with aiofiles.open(f'cogs/{module}.py', 'r') as f:
			old_module = await f.read()

		try:
			answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)
		except asyncio.exceptions.TimeoutError:
			await message.edit(embed=timeout_embed)
			return

		if answer.content.lower() == 'cancel' or answer.content.lower().startswith(ctx.prefix):
			embed = discord.Embed(title='Edit', description='Cancelled.')
			embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
			await message.edit(embed=embed)

			try:
				await answer.delete()
			except discord.errors.NotFound:
				pass

		new_module = answer.content
		try:
			await answer.delete()
		except discord.errors.NotFound:
			pass

		async with aiohttp.ClientSession() as session:
			async with session.get(new_module) as response:
				new_module = await response.text()

		async with aiofiles.open(f'cogs/{module}.py', 'w') as f:
			await f.write(new_module)

		try:
			self.bot.reload_extension(f'cogs.{module}')
			embed = discord.Embed(title='Edit', description=f'Module `{module}` has been edited & reloaded.')

		except discord.ext.commands.ExtensionNotLoaded:
			try:
				self.bot.load_extension(f'cogs.{module}')

			except discord.ext.commands.ExtensionFailed:
				embed = discord.Embed(title='Edit')
				embed.add_field(name='Error', value=f'Module `{module}` has an error, reverting to backup!', inline=False)

				async with aiofiles.open(f'cogs/{module}.py', 'w') as f:
					await f.write(old_module)

				self.bot.load_extension(f'cogs.{module}')

		except discord.ext.commands.ExtensionFailed:
			embed = discord.Embed(title='Edit')
			embed.add_field(name='Error', value=f'Module `{module}` has an error, reverting to backup!', inline=False)

			async with aiofiles.open(f'cogs/{module}.py', 'w') as f:
				await f.write(old_module)

		except discord.ext.commands.ExtensionNotFound:
			embed = discord.Embed(title='Edit')
			embed.add_field(name='Error', value=f'Module `{module}` does not exist!', inline=False)
			embed.add_field(name='Available modules', value=await self.list_cogs(), inline=False)

		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
		await message.edit(embed=embed)

	@module.command(aliases=['list'])
	@commands.guild_only()
	@commands.is_owner()
	async def _list(self, ctx):
		embed = discord.Embed(title='All Modules', description=await self.list_cogs())
		embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

		await ctx.send(embed=embed)


def setup(bot):
	bot.add_cog(Admin(bot))
