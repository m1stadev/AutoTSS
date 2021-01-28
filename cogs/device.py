from discord.ext import commands
import aiohttp
import asyncio
import discord
import sqlite3


class Device(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_identifier(self, identifier):  # this is a stupid check
        try:
            identifier = f"{identifier.split('p')[0]}P{identifier.split('p')[1]}"
        except IndexError:
            return False

        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.ipsw.me/v2.1/firmwares.json/condensed') as resp:
                json = await resp.json()
                if identifier not in json['devices']:
                    return False

        return identifier

    async def check_boardconfig(self, identifier, boardconfig):
        if boardconfig[-2:] != 'ap':
            return False

        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
                json = await resp.json()

        if not json['boardconfig'].startswith(boardconfig[:3]):
            return False

        return True

    async def check_ecid(self, ecid):
        try:
            int(ecid, 16)
        except:
            return False

        return True

    @commands.group(name='device', invoke_without_command=True)
    async def device_cmd(self, ctx):
        embed = discord.Embed(title='Device Commands')
        embed.add_field(name=f'`{ctx.prefix}device add`',
                        value='Add a device', inline=False)
        embed.add_field(name=f'`{ctx.prefix}device remove`',
                        value='Remove a device', inline=False)
        embed.add_field(name=f'`{ctx.prefix}device list`',
                        value='List your devices', inline=False)
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @device_cmd.command(name='add')
    async def add_device(self, ctx):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        cursor.execute(
            'SELECT device_num from autotss WHERE userid = ?', (ctx.message.author.id,))
        result = cursor.fetchall()

        device = {'num': len(result) + 1, 'userid': ctx.message.author.id}

        embed = discord.Embed(title='Add Device')
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        message = await ctx.send(embed=embed)

        for x in range(4):
            if x == 0:
                title = 'Name'
                description = 'Enter a name for your device'
            elif x == 1:
                title = 'Device Identifier'
                description = "Enter your device's identifier (e.g. iPhone8,4)"
            elif x == 2:
                title = 'ECID'
                description = "Enter your device's ECID (hex only)"
            else:
                title = 'Hardware Model'
                description = "Enter your device's Hardware Model (e.g. n51ap)"

            embed = discord.Embed(
                title=title, description=f'{description}\nType `cancel` to cancel.')
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)

            answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author)

            if answer.content == 'cancel':
                embed = discord.Embed(title='Add Device',
                                      description='Cancelled.')
                await message.edit(embed=embed)
                await answer.delete()
                return

            if x == 0:
                device['name'] = answer.content
            elif x == 1:
                device['identifier'] = answer.content.lower()
            elif x == 2:
                device['ecid'] = answer.content.lower()
            else:
                device['boardconfig'] = answer.content.lower()

            await answer.delete()

        embed = discord.Embed(title='Add Device',
                              description='Verifying input...')
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await message.edit(embed=embed)

        identifier = await self.check_identifier(device['identifier'])

        if identifier is False:
            embed = discord.Embed(
                title='Error', description=f"Device `{device['identifier']}` does not exist.")
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        device['identifier'] = identifier

        boardconfig = await self.check_boardconfig(device['identifier'], device['boardconfig'])

        if boardconfig is False:
            embed = discord.Embed(
                title='Error', description=f"Device `{device['identifier']}`'s boardconfig `{device['boardconfig']}` does not exist.")
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        ecid = await self.check_ecid(device['ecid'])

        if ecid is False:
            embed = discord.Embed(
                title='Error', description=f"Device `{device['identifier']}`'s ECID `{device['ecid']}` is not valid.")
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        cursor.execute('SELECT ecid from autotss')
        result = cursor.fetchall()
        if any(x[0] == device['ecid'] for x in result):
            embed = discord.Embed(
                title='Error', description="This device's ECID is already in my database.")
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        cursor.execute('SELECT name from autotss WHERE userid = ?',
                       (ctx.message.author.id,))
        result = cursor.fetchall()

        if any(x[0] == device['name'] for x in result):
            embed = discord.Embed(
                title='Error', description="You've already added a device with this name. Please run this command again, and choose another name for this device.")
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        result.append(device)
        insert_device = (
            "INSERT INTO autotss(device_num, userid, name, identifier, ecid, boardconfig, blobs) VALUES(?,?,?,?,?,?,?)")
        val = (device['num'], device['userid'], device['name'],
               device['identifier'], device['ecid'], device['boardconfig'], str(list()))
        cursor.execute(insert_device, val)

        db.commit()
        db.close()

        embed = discord.Embed(
            title='Add Device', description=f"Device `{device['name']}` added successfully!")
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await message.edit(embed=embed)

    @device_cmd.command(name='remove')
    async def remove_device(self, ctx):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        await ctx.message.delete()

        cursor.execute('SELECT * from autotss WHERE userid = ?',
                       (ctx.message.author.id,))
        result = cursor.fetchall()

        if len(result) == 0:
            embed = discord.Embed(
                name='Error', value='You have no devices added.', inline=False)
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title='Remove Device', description="Choose the number of the device you'd like to remove.\nType `cancel` to cancel.")

        for x in result:
            embed.add_field(
                name=x[0], value=f"Name: `{x[2]}`\nDevice Identifier: `{x[3]}`\nHardware Model: `{x[5]}`", inline=False)

        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        message = await ctx.send(embed=embed)
        answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author)

        if answer.content == 'cancel':
            await answer.delete()
            await message.delete()
            return

        try:
            num = int(answer.content)
        except ValueError:
            embed = discord.Embed(
                title='Error', description='Invalid input given.')
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        cursor.execute(
            'SELECT * from autotss WHERE device_num = ? AND userid = ?', (num, ctx.message.author.id))
        result = cursor.fetchall()

        embed = discord.Embed(
            title='Remove Device', description=f"Device `{result[0][2]}` removed successfully!")
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await message.edit(embed=embed)
        await answer.delete()

        cursor.execute(
            'DELETE from autotss WHERE device_num = ? AND userid = ?', (num, ctx.message.author.id))

        db.commit()
        db.close()

    @device_cmd.command(name='list')
    async def list_devices(self, ctx):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        await ctx.message.delete()

        cursor.execute('SELECT * from autotss WHERE userid = ?',
                       (ctx.message.author.id,))
        result = cursor.fetchall()

        embed = discord.Embed(title='Devices')

        if len(result) == 0:
            embed.add_field(
                name='Error', value='You have no devices added.', inline=False)
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await ctx.send(embed=embed)
            return
        else:
            for x in result:
                embed.add_field(
                    name=f'Name: {x[2]}', value=f"Device Identifier: `{x[3]}`\nECID: `{x[4]}`\nHardware Model: `{x[5]}`", inline=False)
        embed.set_footer(text=f'{ctx.message.author.name} | This message will automatically be deleted in 15 seconds.',
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        message = await ctx.send(embed=embed)

        await asyncio.sleep(15)
        await message.delete()


def setup(bot):
    bot.add_cog(Device(bot))
