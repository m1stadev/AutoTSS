from aioify import aioify
from discord.ext import commands
from typing import Union
from views.buttons import SelectView, PaginatorView
from views.selects import DropdownView

import aiofiles
import aiohttp
import aiosqlite
import asyncio
import discord
import json
import shutil


class Device(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shutil = aioify(shutil, name='shutil')
        self.utils = self.bot.get_cog('Utils')

    @commands.group(name='devices', aliases=('device',), invoke_without_command=True)
    @commands.guild_only()
    async def device_cmd(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='Device Commands')
        embed.add_field(name='Add a device', value=f'`{prefix}devices add`', inline=False)
        embed.add_field(name='Remove a device', value=f'`{prefix}devices remove`', inline=False)
        embed.add_field(name='List your devices', value=f'`{prefix}devices list`', inline=False)
        if await ctx.bot.is_owner(ctx.author):
            embed.add_field(name='Transfer devices to new user', value=f'`{prefix}devices transfer <old user> <new user>`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)

    @device_cmd.command(name='add')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def add_device(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        timeout_embed = discord.Embed(title='Add Device', description='No response given in 5 minutes, cancelling.')
        cancelled_embed = discord.Embed(title='Add Device', description='Cancelled.')
        invalid_embed = discord.Embed(title='Error')

        for embed in (timeout_embed, cancelled_embed):
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        max_devices = 10 #TODO: Export this option to a separate config file

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
            try:
                devices = json.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()
                await db.execute('INSERT INTO autotss(user, devices, enabled) VALUES(?,?,?)', (ctx.author.id, json.dumps(devices), True))
                await db.commit()

        if (len(devices) >= max_devices) and (await ctx.bot.is_owner(ctx.author) == False): # Error out if you attempt to add over 'max_devices' devices, and if you're not the owner of the bot
            invalid_embed.description = f'You cannot add over {max_devices} devices to AutoTSS.'
            await ctx.reply(embed=invalid_embed)
            return

        device = dict()
        async with aiohttp.ClientSession() as session:
            for x in range(4): # Loop that gets all of the required information to save blobs with from the user
                descriptions = (
                    'Enter a name for your device.',
                    "Enter your device's identifier. This can be found with [AIDA64](https://apps.apple.com/app/apple-store/id979579523) under the `Device` section (as `Device String`).",
                    f"Enter your device's ECID (hex).\n*If you'd like to keep your ECID private, you can DM your ECID to {self.bot.user.mention}.*",
                    "Enter your device's Board Config. This value ends in `ap`, and can be found with [AIDA64](https://apps.apple.com/app/apple-store/id979579523) under the `Device` section (as `Device Id`), [System Info](https://arx8x.github.io/depictions/systeminfo.html) under the `Platform` section, or by running `gssc | grep HWModelStr` in a terminal on your iOS device."
                )

                embed = discord.Embed(title='Add Device', description='\n'.join((descriptions[x], 'Type `cancel` to cancel.')))
                embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

                if (x == 3) and ('boardconfig' in device.keys()): # If we got boardconfig from API, no need to get it from user
                    continue

                if x == 0:
                    message = await ctx.reply(embed=embed)
                else:
                    message = await message.edit(embed=embed)

                # Wait for a response from the user, and error out if the user takes over 5 minutes to respond
                try:
                    response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=300)
                    if x == 0:
                        answer = response.content # Don't make the device's name lowercase
                    else:
                        answer = response.content.lower()

                except asyncio.exceptions.TimeoutError:
                    await message.edit(embed=timeout_embed)
                    return

                # Delete the message
                try:
                    await response.delete()
                except discord.errors.NotFound:
                    pass
                except discord.errors.Forbidden as error:
                    if x != 2:
                        raise error

                answer = discord.utils.remove_markdown(answer)
                if 'cancel' in answer.lower() or answer.startswith(prefix):
                    await message.edit(embed=cancelled_embed)
                    return

                # Make sure given information is valid
                if x == 0:
                    device['name'] = answer
                    name_check = await self.utils.check_name(device['name'], ctx.author.id)
                    if name_check != True:
                        if name_check == 0:
                            invalid_embed.description = f"Device name `{device['name']}` is not valid. A device's name cannot be over 20 characters long."
                        elif name_check == -1:
                            invalid_embed.description = f"Device name `{device['name']}` is not valid. You cannot use a device's name more than once."

                        invalid_embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                        await message.edit(embed=invalid_embed)
                        return

                elif x == 1:
                    device['identifier'] = 'P'.join(answer.lower().replace(' ', '').replace('devicestring:', '').split('p'))
                    if await self.utils.check_identifier(session, device['identifier']) is False:
                        invalid_embed.description = f"Device Identifier `{answer}` is not valid."
                        invalid_embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                        await message.edit(embed=invalid_embed)
                        return

                    # If there's only one board for the device, grab the boardconfig now
                    api = await self.utils.fetch_ipswme_api(session, device['identifier'])
                    if len([board for board in api['boards'] if board['boardconfig'].lower().endswith('ap')]) == 1: # Exclude development boards that may pop up
                        device['boardconfig'] = api['boards'][0]['boardconfig'].lower()

                elif x == 2:
                    if answer.startswith('0x'):
                        device['ecid'] = answer[2:]
                    else:
                        device['ecid'] = answer

                    ecid_check = await self.utils.check_ecid(device['ecid'])
                    if ecid_check != True:
                        invalid_embed.description = f"Device ECID `{answer}` is not valid."
                        invalid_embed.set_footer(text=f'{ctx.author.display_name} | This message will be censored in 5 seconds to protect your ECID(s).', icon_url=ctx.author.display_avatar.with_static_format('png').url)
                        if ecid_check == -1:
                            invalid_embed.description += ' This ECID has already been added to AutoTSS.'

                        message = await message.edit(embed=invalid_embed)
                        invalid_embed.description = invalid_embed.description.replace(f'`{answer}`', f'`{await self.utils.censor_ecid(answer)}`')
                        invalid_embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                        await asyncio.sleep(5)
                        await message.edit(embed=invalid_embed)
                        return

                else:
                    device['boardconfig'] = answer.lower().replace(' ', '').replace('deviceid:', '')
                    if await self.utils.check_boardconfig(session, device['identifier'], device['boardconfig']) is False:
                        invalid_embed.description = f"Device boardconfig `{answer}` is not valid."
                        invalid_embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                        await message.edit(embed=invalid_embed)
                        return

            generator_description = [
                'Would you like to save SHSH blobs with a custom generator?',
                'This value is hexadecimal, 18 characters long, and begins with `0x`.'
            ]

            cpid = await self.utils.get_cpid(session, device['identifier'], device['boardconfig'])
            if 32800 <= cpid < 35072:
                generator_description.append('\n*If you choose to, you **will** need to provide a matching ApNonce for SHSH blobs to be saved correctly.*')
                generator_description.append('*Guide for jailbroken A12+ devices: [Click here](https://ios.cfw.guide/tss-web#getting-generator-and-apnonce-jailbroken-a12-only)*')
                generator_description.append('*Guide for nonjailbroken A12+ devices: [Click here](https://ios.cfw.guide/tss-computer#get-your-device-specific-apnonce-and-generator)*')

            embed = discord.Embed(title='Add Device', description='\n'.join(generator_description)) # Ask the user if they'd like to save blobs with a custom generator
            embed.add_field(name='Options', value='Type `yes` to add a custom generator, `cancel` to cancel adding this device, or anything else to skip.', inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            message = await message.edit(embed=embed)

            try:
                response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=300)
                answer = discord.utils.remove_markdown(response.content.lower())
            except asyncio.exceptions.TimeoutError:
                await message.edit(embed=timeout_embed)
                return

            try:
                await response.delete()
            except discord.errors.NotFound:
                pass

            if answer == 'yes':
                embed = discord.Embed(title='Add Device', description='Please enter the custom generator you wish to save SHSH blobs with.\nType `cancel` to cancel.')
                embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                message = await message.edit(embed=embed)

                try:
                    response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=300)
                    answer = discord.utils.remove_markdown(response.content.lower())
                except asyncio.exceptions.TimeoutError:
                    await message.edit(embed=timeout_embed)
                    return

                try:
                    await response.delete()
                except discord.errors.NotFound:
                    pass

                if 'cancel' in answer or answer.startswith(prefix):
                    await message.edit(embed=cancelled_embed)
                    return

                else:
                    device['generator'] = answer
                    if await self.utils.check_generator(device['generator']) is False:
                        invalid_embed.description = f"Generator `{device['generator']}` is not valid."
                        invalid_embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                        await message.edit(embed=invalid_embed)
                        return

            elif 'cancel' in answer or answer.startswith(prefix):
                await message.edit(embed=cancelled_embed)
                return
            else:
                device['generator'] = None

            apnonce_description = [
                'Would you like to save SHSH blobs with a custom ApNonce?',
                'This is **NOT** the same as your **generator**, which is hexadecimal, begins with `0x`, and is 16 characters long.'
            ]

            if 32800 <= cpid < 35072:
                apnonce_description.append('\n*You must save blobs with an ApNonce, or else your SHSH blobs **will not work**. More info [here](https://www.reddit.com/r/jailbreak/comments/f5wm6l/tutorial_repost_easiest_way_to_save_a12_blobs/).*')

            embed = discord.Embed(title='Add Device', description='\n'.join(apnonce_description)) # Ask the user if they'd like to save blobs with a custom ApNonce
            embed.add_field(name='Options', value='Type **yes** to add a custom ApNonce, **cancel** to cancel adding this device, or anything else to skip.', inline=False)
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            message = await message.edit(embed=embed)

            try:
                response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=300)
                answer = discord.utils.remove_markdown(response.content.lower())
            except asyncio.exceptions.TimeoutError:
                await message.edit(embed=timeout_embed)
                return

            try:
                await response.delete()
            except discord.errors.NotFound:
                pass

            if answer == 'yes':
                embed = discord.Embed(title='Add Device', description='Please enter the custom ApNonce you wish to save SHSH blobs with.\nType `cancel` to cancel.')
                embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                message = await message.edit(embed=embed)

                try:
                    response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=300)
                    answer = discord.utils.remove_markdown(response.content.lower())
                except asyncio.exceptions.TimeoutError:
                    await message.edit(embed=timeout_embed)
                    return

                try:
                    await response.delete()
                except discord.errors.NotFound:
                    pass

                if 'cancel' in answer or answer.startswith(prefix):
                    await message.edit(embed=cancelled_embed)
                    return

                else:
                    device['apnonce'] = answer
                    if await self.utils.check_apnonce(cpid, device['apnonce']) is False:
                        invalid_embed.description = f"Device ApNonce `{device['apnonce']}` is not valid."
                        invalid_embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                        await message.edit(embed=invalid_embed)
                        return

            elif 'cancel' in answer or answer.startswith(prefix):
                await message.edit(embed=cancelled_embed)
                return
            else:
                if 32800 <= cpid < 35072: # If A12+ and no apnonce was specified
                    embed = discord.Embed(title='Add Device')
                    embed.add_field(name='Error', value='You cannot add a device with an A12+ SoC without specifying an ApNonce.', inline=False)
                    embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                    await message.edit(embed=embed)
                    return

                device['apnonce'] = None

        device['saved_blobs'] = list()

        # Add device information into the database
        devices.append(device)

        async with aiosqlite.connect('Data/autotss.db') as db:
            async with db.execute('SELECT devices FROM autotss WHERE user = ?', (ctx.author.id,)) as cursor:
                if await cursor.fetchone() is None:
                    sql = 'INSERT INTO autotss(devices, enabled, user) VALUES(?,?,?)'
                else:
                    sql = 'UPDATE autotss SET devices = ?, enabled = ? WHERE user = ?'

            await db.execute(sql, (json.dumps(devices), True,  ctx.author.id))
            await db.commit()

        embed = discord.Embed(title='Add Device', description=f"Device `{device['name']}` added successfully!")
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await message.edit(embed=embed)

        await self.utils.update_device_count()

    @device_cmd.command(name='remove')
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def remove_device(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        cancelled_embed = discord.Embed(title='Remove Device', description='Cancelled.')
        invalid_embed = discord.Embed(title='Error', description='Invalid input given.')
        timeout_embed = discord.Embed(title='Remove Device', description='No response given in 1 minute, cancelling.')

        for x in (cancelled_embed, invalid_embed, timeout_embed):
            x.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (ctx.author.id,)) as cursor:
            try:
                devices = json.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if len(devices) == 0:
            embed = discord.Embed(title='Error', description='You have no devices added to AutoTSS.')
            await ctx.reply(embed=embed)
            return

        if len(devices) > 1:
            device_options = list()
            for device in devices:
                device_options.append(discord.SelectOption(
                    label=device['name'],
                    description=f"ECID: {await self.utils.censor_ecid(device['ecid'])} | SHSH blob{'s' if len(device['saved_blobs']) != 1 else ''} saved: {len(device['saved_blobs'])}",
                    emoji='📱'
                ))

            embed = discord.Embed(title='Remove Device', description="Please select the device you'd like to remove.")
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

            dropdown = DropdownView(device_options, 'Device to remove...')
            dropdown.message = await ctx.reply(embed=embed, view=dropdown)
            await dropdown.wait()
            if dropdown.answer is None:
                await dropdown.message.edit(embed=timeout_embed)
                return

            num = next(devices.index(x) for x in devices if x['name'] == dropdown.answer)
            message = dropdown.message

        else:
            num = 0
            message = None

        embed = discord.Embed(title='Remove Device', description=f"Are you **absolutely sure** you want to delete `{devices[num]['name']}`?")
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        buttons = [{
            'label': 'Confirm',
            'style': discord.ButtonStyle.danger,
            'disabled': False
        }, {
            'label': 'Cancel',
            'style': discord.ButtonStyle.secondary,
            'disabled': False
        }]

        view = SelectView(buttons)
        view.message = await message.edit(embed=embed, view=view) if message is not None else await ctx.reply(embed=embed, view=view)
        await view.wait()
        if view.answer is None:
            await view.message.edit(embed=timeout_embed)
            return

        if view.answer == 'confirm':
            embed = discord.Embed(title='Remove Device', description='Removing device...')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            message = await view.message.edit(embed=embed)

            async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
                url = await self.utils.backup_blobs(tmpdir, devices[num]['ecid'])

            if url is None:
                embed = discord.Embed(title='Remove Device', description=f"Device `{devices[num]['name']}` removed.")
                embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
                message = await message.edit(embed=embed)

            else:
                await self.shutil.rmtree(f"Data/Blobs/{devices[num]['ecid']}")

                embed = discord.Embed(title='Remove Device')
                embed.description = f"SHSH Blobs from `{devices[num]['name']}`: [Click here]({url})"
                embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

                try:
                    await ctx.author.send(embed=embed)
                    embed.description = f"Device `{devices[num]['name']}` removed."
                    message = await message.edit(embed=embed)
                except:
                    embed.description = f"Device `{devices[num]['name']}` removed.\nSHSH Blobs from `{devices[num]['name']}`: [Click here]({url})"
                    embed.set_footer(
                        text=f'{ctx.author.display_name} | This message will automatically be deleted in 5 seconds to protect your ECID(s).',
                        icon_url=ctx.author.display_avatar.with_static_format('png').url
                        )

                    message = await message.edit(embed=embed)

                    await asyncio.sleep(5)
                    await ctx.message.delete()
                    await message.delete()

            devices.pop(num)

            async with aiosqlite.connect('Data/autotss.db') as db:
                await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), ctx.author.id))
                await db.commit()

            await message.edit(embed=embed)
            await self.utils.update_device_count()

        elif view.answer == 'cancel':
            await view.message.edit(embed=cancelled_embed)

    @device_cmd.command(name='list')
    @commands.guild_only()
    async def list_devices(self, ctx: commands.Context, user: Union[discord.User, int, str]=0) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        if type(user) == int:
            user = ctx.author if user == 0 else self.bot.get_user(user)

        if type(user) in (None, str):
            embed = discord.Embed(title='Error', description="This user doesn't exist!")
            await ctx.reply(embed=embed)
            return

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE user = ?', (user.id,)) as cursor:
            try:
                devices = json.loads((await cursor.fetchone())[0])
            except TypeError:
                devices = list()

        if len(devices) == 0:
            embed = discord.Embed(title='Error', description=f"{'You have' if user == ctx.author else f'{user.mention} has'} no devices added to AutoTSS.")
            await ctx.reply(embed=embed)
            return

        device_embeds = list()
        for device in devices:
            device_embed = {
                'title': f"*{device['name']}*  ({devices.index(device) + 1}/{len(devices)})",
                'fields': [{
                    'name': 'Device Identifier',
                    'value': f"`{device['identifier']}`",
                    'inline': False
                },
                {
                    'name': 'ECID',
                    'value': f"`{await self.utils.censor_ecid(device['ecid'])}`",
                    'inline': False
                },
                {
                    'name': 'Board Config',
                    'value': f"`{device['boardconfig']}`",
                    'inline': False
                }],
                'footer': {
                    'text': ctx.author.display_name,
                    'icon_url': str(ctx.author.display_avatar.with_static_format('png').url)
                }
            }

            if device['generator'] is not None:
                device_embed['fields'].append({
                    'name': 'Custom Generator',
                    'value': f"`{device['generator']}`",
                    'inline': False
                })

            if device['apnonce'] is not None:
                device_embed['fields'].append({
                    'name': 'Custom ApNonce',
                    'value': f"`{device['apnonce']}`",
                    'inline': False
                })

            num_blobs = len(device['saved_blobs'])
            device_embed['fields'].append({
                'name': 'SHSH Blobs',
                'value': f"**{num_blobs}** SHSH blob{'s' if num_blobs != 1 else ''} saved",
                'inline': False
            })

            device_embeds.append(device_embed)

        if len(device_embeds) == 1:
            await ctx.reply(embed=discord.Embed.from_dict(device_embeds[0]))
            return

        paginator = PaginatorView(device_embeds)
        paginator.message = await ctx.reply(embed=discord.Embed.from_dict(device_embeds[paginator.embed_num]), view=paginator)

    @device_cmd.command(name='transfer')
    @commands.guild_only()
    @commands.is_owner()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def transfer_devices(self, ctx: commands.Context, old_member: Union[discord.User, int], new_member: Union[discord.User, int]) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        cancelled_embed = discord.Embed(title='Transfer Devices', description='Cancelled.')
        invalid_embed = discord.Embed(title='Error')
        timeout_embed = discord.Embed(title='Transfer Devices', description='No response given in 5 minutes, cancelling.')

        for x in (cancelled_embed, invalid_embed, timeout_embed):
            x.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)

        if self.bot.get_cog('TSS').blobs_loop == True: # Avoid any potential conflict with transferring devices while blobs are being saved
            invalid_embed.description = "I'm currently automatically saving SHSH blobs, please wait until I'm finished to transfer devices."
            await ctx.reply(embed=invalid_embed)
            return

        if type(old_member) == int:
            old_member = await self.bot.fetch_user(old_member)
            if old_member is None:
                invalid_embed.description = "The member specified to transfer devices from doesn't exist!"
                await ctx.reply(embed=invalid_embed)
                return

        if type(new_member) == int:
            new_member = await self.bot.fetch_user(new_member)
            if new_member is None:
                invalid_embed.description = "The member specified to transfer devices to doesn't exist!"
                await ctx.reply(embed=invalid_embed)
                return

        if old_member.id == new_member.id:
            invalid_embed.description = "Silly goose, you can't transfer devices between the same user!"
            await ctx.reply(embed=invalid_embed)
            return

        if new_member.bot == True:
            invalid_embed.description = 'You cannot transfer devices to a bot account.'
            await ctx.reply(embed=invalid_embed)
            return
   
        async with aiosqlite.connect('Data/autotss.db') as db:
            async with db.execute('SELECT devices from autotss WHERE user = ?', (old_member.id,)) as cursor:
                try:
                    old_devices = json.loads((await cursor.fetchone())[0])
                except TypeError:
                    old_devices = list()

            async with db.execute('SELECT devices from autotss WHERE user = ?', (new_member.id,)) as cursor:
                try:
                    new_devices = json.loads((await cursor.fetchone())[0])
                except TypeError:
                    new_devices = list()

        if len(old_devices) == 0:
            invalid_embed.description = f'{old_member.mention} has no devices added to AutoTSS!'
            await ctx.reply(embed=invalid_embed)
            return

        if len(new_devices) > 0:
            invalid_embed.description = f'{new_member.mention} has devices added to AutoTSS already.'
            await ctx.reply(embed=invalid_embed)
            return

        embed = discord.Embed(title='Transfer Devices')
        msg = (
            f"Are you sure you'd like to transfer {old_member.mention}'s **{len(old_devices)} device{'s' if len(old_devices) != 1 else ''}** to {new_member.mention}?",
            'Type `yes` to transfer the devices, or anything else to cancel.'
        )
        embed.description = '\n'.join(msg)
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        message = await ctx.reply(embed=embed)

        try:
            response = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=300)
            answer = discord.utils.remove_markdown(response.content.lower())
        except asyncio.exceptions.TimeoutError:
            await message.edit(embed=timeout_embed)
            return

        try:
            await response.delete()
        except:
            pass

        if answer != 'yes' or answer.startswith(prefix):
            await message.edit(embed=cancelled_embed)
            return

        async with aiosqlite.connect('Data/autotss.db') as db:
            await db.execute('UPDATE autotss SET user = ? WHERE user = ?', (new_member.id, old_member.id))
            await db.commit()

        embed.description = f"Successfully transferred {old_member.mention}'s {len(old_devices)} device{'s' if len(old_devices) != 1 else ''} to {new_member.mention}."
        await message.edit(embed=embed)

def setup(bot):
    bot.add_cog(Device(bot))
