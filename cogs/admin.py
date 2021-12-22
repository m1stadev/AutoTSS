from discord.errors import ExtensionAlreadyLoaded, ExtensionFailed, ExtensionNotLoaded
from discord.ext import commands
from discord import permissions, Option
from views.buttons import SelectView

import aiofiles
import aiopath
import asyncio
import discord
import json
import time


async def mod_autocomplete(ctx: discord.AutocompleteContext) -> list:
    modules = sorted([cog.stem async for cog in aiopath.AsyncPath('cogs').glob('*.py')])

    return [_ for _ in modules if _.startswith(ctx.value.lower())]

class AdminCog(commands.Cog, name='Administrator'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.utils = bot.get_cog('Utilities')

    admin = discord.SlashCommandGroup('admin', 'Administrator commands', permissions=[permissions.Permission('owner', 2, True)])

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

    @admin.command(name='downloadall', description='Download SHSH blobs for all devices in AutoTSS.')
    async def download_all_blobs(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)

        async with self.bot.db.execute('SELECT devices from autotss') as cursor:
            num_devices = sum(len(json.loads(devices[0])) for devices in await cursor.fetchall())

        if num_devices == 0:
            embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
            await ctx.respond(embed=embed)
            return

        ecids = [ecid.stem async for ecid in aiopath.AsyncPath('Data/Blobs').glob('*') if ecid.is_dir()]
        async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
            url = await self.utils.backup_blobs(aiopath.AsyncPath(tmpdir), *ecids)

        if url is None:
            embed = discord.Embed(title='Error', description='There are no SHSH blobs saved in AutoTSS.')
            await ctx.respond(embed=embed)

        else:
            buttons = [{
                'label': 'Download',
                'style': discord.ButtonStyle.link,
                'url': url
            }]

            view = SelectView(buttons, ctx, timeout=None)
            embed = discord.Embed(title='Download Blobs', description='Download all SHSH Blobs:')
            await ctx.respond(embed=embed, view=view)

    @admin.command(name='saveall', description='Manually save SHSH blobs for all devices in AutoTSS.')
    async def save_all_blobs(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer()

        async with self.bot.db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
            data = await cursor.fetchall()

        num_devices = sum(len(json.loads(devices[1])) for devices in data)
        if num_devices == 0:
            embed = discord.Embed(title='Error', description='There are no devices added to AutoTSS.')
            await ctx.respond(embed=embed)
            return

        if self.utils.saving_blobs:
            embed = discord.Embed(title='Hey!', description="I'm automatically saving SHSH blobs right now, please wait until I'm finished to manually save SHSH blobs.")
            await ctx.respond(embed=embed)
            return

        self.utils.saving_blobs = True
        await self.bot.change_presence(activity=discord.Game(name='Ping me for help! | Currently saving SHSH blobs!'))

        embed = discord.Embed(title='Save Blobs', description='Saving SHSH blobs for all of your devices...')
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.respond(embed=embed)

        start_time = await asyncio.to_thread(time.time)
        data = await asyncio.gather(*[self.utils.sem_call(self.utils.save_user_blobs, user_data[0], json.loads(user_data[1])) for user_data in data])
        finish_time = round(await asyncio.to_thread(time.time) - start_time)
        self.utils.saving_blobs = False

        blobs_saved = sum(user['blobs_saved'] for user in data)
        devices_saved = sum(user['devices_saved'] for user in data)

        if blobs_saved > 0:
            embed.description = ' '.join((
                f"Saved **{blobs_saved} SHSH blob{'s' if blobs_saved > 1 else ''}**",
                f"for **{devices_saved} device{'s' if devices_saved > 1 else ''}**",
                f"in **{finish_time} second{'s' if finish_time != 1 else ''}**."
            ))

        else:
            embed.description = 'All SHSH blobs have already been saved.\n\n*Tip: AutoTSS will automatically save SHSH blobs for you, no command necessary!*'

        await self.utils.update_device_count()
        await ctx.edit(embed=embed)

    @admin.command(name='dtransfer', description="Transfer a user's devices to another user.")
    @permissions.is_owner()
    async def transfer_devices(self, ctx: discord.ApplicationContext, old: Option(discord.User, description='User to transfer devices from'), new: Option(discord.User, description='User to transfer devices to')) -> None:
        cancelled_embed = discord.Embed(title='Transfer Devices', description='Cancelled.')
        invalid_embed = discord.Embed(title='Error')
        timeout_embed = discord.Embed(title='Transfer Devices', description='No response given in 1 minute, cancelling.')

        for x in (cancelled_embed, invalid_embed, timeout_embed):
            x.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        await ctx.defer()

        if self.utils.saving_blobs == True: # Avoid any potential conflict with transferring devices while blobs are being saved
            invalid_embed.description = "I'm currently automatically saving SHSH blobs, please wait until I'm finished to transfer devices."
            await ctx.respond(embed=invalid_embed)
            return

        if old == new:
            invalid_embed.description = "Silly goose, you can't transfer devices between the same user!"
            await ctx.respond(embed=invalid_embed)
            return

        if new.bot == True:
            invalid_embed.description = 'You cannot transfer devices to a bot account.'
            await ctx.respond(embed=invalid_embed)
            return
   
        async with self.bot.db.execute('SELECT devices from autotss WHERE user = ?', (old.id,)) as cursor:
            try:
                old_devices = json.loads((await cursor.fetchone())[0])
            except TypeError:
                old_devices = list()

        async with self.bot.db.execute('SELECT devices from autotss WHERE user = ?', (new.id,)) as cursor:
            try:
                new_devices = json.loads((await cursor.fetchone())[0])
            except TypeError:
                new_devices = list()

        if len(old_devices) == 0:
            invalid_embed.description = f'{old.mention} has no devices added to AutoTSS.'
            await ctx.respond(embed=invalid_embed)
            return

        if len(new_devices) > 0:
            invalid_embed.description = f'{new.mention} has devices added to AutoTSS already.'
            await ctx.respond(embed=invalid_embed)
            return

        embed = discord.Embed(title='Transfer Devices')
        embed.description = f"Are you sure you'd like to transfer {old.mention}'s **{len(old_devices)} device{'s' if len(old_devices) != 1 else ''}** to {new.mention}?"
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        buttons = [{
                'label': 'Yes',
                'style': discord.ButtonStyle.success
            }, {
                'label': 'Cancel',
                'style': discord.ButtonStyle.danger
            }]

        view = SelectView(buttons, ctx)
        await ctx.respond(embed=embed, view=view)
        await view.wait()
        if view.answer is None:
            await ctx.edit(embed=timeout_embed)
            return

        if view.answer == 'Cancel':
            await ctx.edit(embed=cancelled_embed)
            return

        await self.bot.db.execute('UPDATE autotss SET user = ? WHERE user = ?', (new.id, old.id))
        await self.bot.db.commit()

        embed.description = f"Successfully transferred {old.mention}'s **{len(old_devices)} device{'s' if len(old_devices) != 1 else ''}** to {new.mention}."
        await ctx.edit(embed=embed)


def setup(bot):
    bot.add_cog(AdminCog(bot))
