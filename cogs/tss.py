from discord.ext import commands
import aiohttp
import aiofiles
import ast
import asyncio
import discord
import glob
import os
import shutil
import sqlite3


class TSS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def upload_zip(self, file):
        async with aiofiles.open(file, 'rb') as f:
            async with aiohttp.ClientSession() as session:
                async with session.put('https://up.psty.io/blobs.zip', data=f) as response:
                    resp = await response.text()

        return resp.splitlines()[-1].split(':', 1)[1][1:]

    async def get_signed_buildids(self, device):
        signed_buildids = []
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.ipsw.me/v4/device/{device[3]}?type=ipsw') as resp:
                api = await resp.json()

        for x in list(api['firmwares']):
            if x['signed'] is True:
                signed_buildids.append(x['buildid'])

        return signed_buildids

    async def buildid_to_version(self, device, buildid):
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.ipsw.me/v4/device/{device[3]}?type=ipsw') as resp:
                api = await resp.json()

        return next(x['version'] for x in list(api['firmwares']) if x['buildid'] == buildid)

    async def save_blob(self, device, buildid):
        version = await self.buildid_to_version(device, buildid)
        save_path = f'Data/Blobs/{device[4]}/{version}/{buildid}'
        os.makedirs(save_path, exist_ok=True)

        cmd = await asyncio.create_subprocess_exec('tsschecker', '-d', device[3],  '-e', device[4], '--buildid', buildid, '-B', device[5], '-s', '--save-path', save_path, stdout=asyncio.subprocess.PIPE)

        stdout, stderr = await cmd.communicate()

        if 'Saved shsh blobs!' not in stdout.decode():
            return False

        return True

    @commands.group(name='tss', invoke_without_command=True)
    async def tss_cmd(self, ctx):
        embed = discord.Embed(title='TSS Commands')
        embed.add_field(name='Save blobs for all of your devices',
                        value=f'`{ctx.prefix}tss saveall`', inline=False)
        embed.add_field(name='Save blobs for one of your devices',
                        value=f'`{ctx.prefix}tss save`', inline=False)
        embed.add_field(name='List all of the blobs saved for your devices',
                        value=f'`{ctx.prefix}tss list`', inline=False)
        embed.add_field(name='Download all of the blobs saved for your devices',
                        value=f'`{ctx.prefix}tss download`', inline=False)
        embed.set_footer(text=ctx.message.author.nick,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @tss_cmd.command(name='save')
    async def save_single_device_blobs(self, ctx):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        cursor.execute('SELECT * from autotss WHERE userid = ?',
                       (ctx.message.author.id,))
        devices = cursor.fetchall()

        if len(devices) == 0:
            embed = discord.Embed(
                title='Error', description='You have no devices added.', inline=False)
            embed.set_footer(text=ctx.message.author.nick,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title='Save Blobs', description="Choose the number of the device you'd like to save blobs for.\nType `cancel` to cancel.")
        embed.set_footer(text=ctx.message.author.nick,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))

        for x in range(len(devices)):
            embed.add_field(
                name=devices[x][0], value=f'Name: `{devices[x][2]}`\nDevice Identifier: `{devices[x][3]}`\nHardware Model: `{devices[x][5]}`', inline=False)

        message = await ctx.send(embed=embed)
        answer = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author)

        if answer.content == 'cancel':
            try:
                await answer.delete()
                await message.delete()
            except discord.errors.NotFound:
                pass

            return

        try:
            int(answer.content)
        except ValueError:
            embed = discord.Embed(
                title='Error', description='Invalid input given.')
            embed.set_footer(text=ctx.message.author.nick,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        num = int(answer.content)
        try:
            await answer.delete()
        except discord.errors.NotFound:
            pass

        if not 0 < num <= len(devices):
            embed = discord.Embed(
                title='Error', description=f'Device `{num}` does not exist.')
            embed.set_footer(text=ctx.message.author.nick,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        cursor.execute(
            'SELECT * from autotss WHERE device_num = ? AND userid = ?', (num, ctx.message.author.id))
        device = cursor.fetchall()[0]

        embed = discord.Embed(
            title='Save Blobs', description=f'Saving blobs for `{device[2]}`...')
        embed.set_footer(text=ctx.message.author.nick,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await message.edit(embed=embed)

        signed_buildids = await self.get_signed_buildids(device)
        saved_buildids = ast.literal_eval(device[6])
        for x in list(signed_buildids):
            if x in saved_buildids:
                signed_buildids.pop(signed_buildids.index(x))

        signed_versions = list()
        for x in signed_buildids:
            signed_versions.append(await self.buildid_to_version(device, x))

        for x in list(signed_buildids):
            blob = await self.save_blob(device, x)

            if blob is False:
                embed.add_field(
                    name='Error', value=f'Failed to save blobs for `iOS {signed_versions[signed_buildids.index(x)]} | {x}`.')
                embed.set_footer(text=ctx.message.author.nick,
                                 icon_url=ctx.message.author.avatar_url_as(static_format='png'))
                await message.edit(embed=embed)

                signed_versions.pop(signed_buildids.index(x))
                signed_buildids.pop(signed_buildids.index(x))
            else:
                saved_buildids.append(x)

        cursor.execute(
            'UPDATE autotss SET blobs = ? WHERE device_num = ? AND userid = ?', (str(saved_buildids), device[0], ctx.message.author.id))
        db.commit()

        saved_versions = str()
        for x in range(len(signed_buildids)):
            saved_versions += f'`iOS {signed_versions[x]} | {signed_buildids[x]}`, '

        if saved_versions == '':
            description = 'No blobs were saved.'
        else:
            description = f'Saved blobs for {saved_versions[:-2]}.'

        embed = discord.Embed(
            title='Save Blobs', description=description)
        embed.set_footer(text=ctx.message.author.nick,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))

        await message.edit(embed=embed)
        db.close()

    @tss_cmd.command(name='saveall')
    async def save_all_device_blobs(self, ctx):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        cursor.execute('SELECT * from autotss WHERE userid = ?',
                       (ctx.message.author.id,))
        devices = cursor.fetchall()

        if len(devices) == 0:
            embed = discord.Embed(
                title='Error', description='You have no devices added.', inline=False)
            embed.set_footer(text=ctx.message.author.nick,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await ctx.send(embed=embed)
            return

        blob_embed = discord.Embed(
            title='Save Blobs', description='Saving blobs for all of your devices...')
        blob_embed.set_footer(text=ctx.message.author.nick,
                              icon_url=ctx.message.author.avatar_url_as(static_format='png'))

        message = await ctx.send(embed=blob_embed)

        saved_blobs = int()
        for x in range(len(devices)):

            signed_buildids = await self.get_signed_buildids(devices[x])
            saved_buildids = ast.literal_eval(devices[x][6])
            for i in list(signed_buildids):
                if i in saved_buildids:
                    signed_buildids.pop(signed_buildids.index(i))

            signed_versions = list()
            for i in signed_buildids:
                signed_versions.append(await self.buildid_to_version(devices[x], i))

            for i in list(signed_buildids):
                blob = await self.save_blob(devices[x], i)

                if blob is False:
                    blob_embed.add_field(name='Error',
                                         value=f'Failed to save blobs for `{devices[x][2]} - iOS {signed_versions[signed_buildids.index(i)]} | {i}`.', inline=False)
                    await message.edit(embed=blob_embed)

                    signed_versions.pop(signed_buildids.index(i))
                    signed_buildids.pop(signed_buildids.index(i))
                else:
                    saved_buildids.append(i)

            cursor.execute(
                'UPDATE autotss SET blobs = ? WHERE device_num = ? AND userid = ?', (str(saved_buildids), devices[x][0], ctx.message.author.id))
            db.commit()

            saved_blobs += len(signed_buildids)

        if saved_blobs == 0:
            description = 'No blobs were saved.'
        else:
            description = f'Saved **{saved_blobs} blobs** for **{len(devices)} devices**.'

        embed = discord.Embed(
            title='Save Blobs', description=description)
        embed.set_footer(text=ctx.message.author.nick,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await message.edit(embed=embed)
        db.close()

    @tss_cmd.command(name='list')
    async def list_all_blobs(self, ctx):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        cursor.execute(
            'SELECT * from autotss WHERE userid = ?', (ctx.message.author.id,))
        devices = cursor.fetchall()

        saved_blobs = int()
        saved_devices = len(devices)

        for x in range(saved_devices):
            saved_blobs += len(ast.literal_eval(devices[x][6]))

        embed = discord.Embed(title=f"{ctx.message.author.nick}'s Saved Blobs",
                              description=f'**{saved_blobs} blobs** saved for **{saved_devices} devices**.')
        embed.set_footer(text=ctx.message.author.nick,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))

        for x in range(saved_devices):
            blobs = ast.literal_eval(devices[x][6])

            saved_blobs = str()

            for i in blobs:
                version = await self.buildid_to_version(devices[x], i)
                saved_blobs += f'`iOS {version} | {i}`, '

            embed.add_field(name=devices[x][2],
                            value=saved_blobs[:-2], inline=False)

        await ctx.send(embed=embed)
        db.close()

    @tss_cmd.command(name='download')
    async def download_all_blobs(self, ctx):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        embed = discord.Embed(title='Download Blobs',
                              description='Uploading blobs...')
        embed.set_footer(text=ctx.message.author.nick,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))

        message = await ctx.send(embed=embed)

        cursor.execute(
            'SELECT * from autotss WHERE userid = ?', (ctx.message.author.id,))
        devices = cursor.fetchall()
        db.close()
        ecids = list()

        if len(devices) == 0:
            embed = discord.Embed(
                title='Download Blobs', inline=False)
            embed.add_field(name='Error',
                            value='You have no devices added.')
            embed.set_footer(text=ctx.message.author.nick,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        for x in range(len(devices)):
            ecids.append(devices[x][4])

        if os.path.isdir('.tmp'):
            shutil.rmtree('.tmp')

        os.makedirs('.tmp/Blobs')

        for x in ecids:
            try:
                shutil.copytree(f'Data/Blobs/{x}', f'.tmp/Blobs/{x}')
            except FileNotFoundError:
                pass

        if len(glob.glob('.tmp/Blobs')) == 0:
            embed = discord.Embed(title='Download Blobs')
            embed.add_field(name='Error',
                            value='No blobs are saved for any of your devices.'
            )
            embed.set_footer(text=ctx.message.author.nick,
                            icon_url=ctx.message.author.avatar_url_as(static_format='png'))

            await message.edit(embed=embed)
            return

        shutil.make_archive('.tmp/blobs', 'zip', '.tmp/Blobs')

        url = await self.upload_zip('.tmp/blobs.zip')

        embed = discord.Embed(title='Download Blobs',
                              description=f'[Click here]({url}).')
        embed.set_footer(text=ctx.message.author.nick,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))

        await message.edit(embed=embed)

        shutil.rmtree('.tmp')


def setup(bot):
    bot.add_cog(TSS(bot))
