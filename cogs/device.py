from discord.ext import commands
import discord
import sqlite3


class Device(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='device', invoke_without_command=True)
    async def device_cmd(self, ctx):
        embed = discord.Embed(title='Device Commands')
        embed.add_field(name=f'`{ctx.prefix}device add`', value='Add a device', inline=False)
        embed.add_field(name=f'`{ctx.prefix}device remove`', value='Remove a device', inline=False)
        embed.add_field(name=f'`{ctx.prefix}device list`', value='List your devices', inline=False)
        embed.set_footer(text=ctx.message.author.name, icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @device_cmd.command(name='add')
    async def add_device(self, ctx):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        cursor.execute('SELECT devices from autotss WHERE userid = ?', (ctx.message.author.id,))
        result = cursor.fetchone()
        if result is None:
            insert_user = ('INSERT INTO autotss(userid, devices) VALUES(?,?)')
            val = (ctx.message.author.id, list())
            cursor.execute(insert_user, val)

        device = {}

        embed = discord.Embed(title='Add Device')
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

            embed = discord.Embed(title=title, description=description)
            await message.edit(embed=embed)

            answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author)
         
            if x == 0:
                device['name'] = answer.content
            elif x == 1:
                device['identifier'] = answer.content
            elif x == 2:
                device['ecid'] = answer.content
            else:
                device['boardconfig'] = answer.content

            await answer.delete()

        await message.delete()

        cursor.execute('SELECT devices from autotss')
        result = cursor.fetchone()[0].strip('][').split(', ')
        for x in result:
            if any(i['ecid'] == device['ecid'] for i in x):
                await ctx.send("hey dipshit, this device has either been added by you or someone else already. that's tuff, bro.")
                return

        cursor.execute('SELECT devices from autotss WHERE userid = ?', (ctx.message.author.id,))
        result = cursor.fetchone()[0].strip('][').split(', ')

        await ctx.send(result)

        if result[0] == '':
            result.pop(0)

        if any(x['name'] == device['name'] for x in result):
            await message.edit('hey dipshit, you already added this device. what the hell??')
            return

        result.append(device)
        cursor.execute('UPDATE autotss SET devices = ? WHERE userid = ?', (str(result), ctx.message.author.id))

        db.commit()
        db.close()

    @device_cmd.command(name='remove')
    async def remove_device(self, ctx):
        await ctx.send("stfu i haven't implemented this yet")

    @device_cmd.command(name='list')
    async def list_devices(self, ctx):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        cursor.execute('SELECT devices from autotss WHERE userid = ?', (ctx.message.author.id,))
        result = cursor.fetchone()
        if result is None:
            insert_user = ("INSERT INTO autotss(userid, devices) VALUES(?,?)")
            val = (ctx.message.author.id, list())
            cursor.execute(insert_user, val)
            db.commit()

        cursor.execute('SELECT devices from autotss WHERE userid = ?', (ctx.message.author.id,))
        result = cursor.fetchone()[0].strip('][').split(', ')

        db.close()

        embed = discord.Embed(title='Devices')

        if result[0] == '':
            result.pop(0)

        await ctx.send(str(result))

        if len(result) == 1:
            embed.add_field(name='Note:', value='You have no devices added', inline=False)
        else:
            for x in result:
                await ctx.send(str(x))
                embed.add_field(name=x['name'], value=f"Device Identifier: {x['identifier']}\nHardware Model: {x['boardconfig']}", inline=False)
        embed.set_footer(text=ctx.message.author.name, icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Device(bot))
