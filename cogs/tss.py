from discord.ext import commands
import aiohttp
import asyncio
import discord
import glob
import os
import sqlite3


class TSS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        save_path = f"Data/Blobs/{device[3]}/{device[4]}/{version}/{buildid}"
        os.makedirs(save_path, exist_ok=True)

        #TODO: Add code to check database & see if we've already saved blobs for this ver

        if len(glob.glob(f'{save_path}/*.shsh*')) > 0:  # If we've already saved blobs then no point in re-saving them
            return True

        cmd = await asyncio.create_subprocess_exec('tsschecker', '-d', device[3],  '-e', device[4], '--buildid', buildid, '-B', device[5], '-s', '--save-path', save_path, stdout=asyncio.subprocess.PIPE)

        stdout, stderr = await cmd.communicate()

        if 'Saved shsh blobs!' not in stdout.decode():
            return False

    @commands.group(name='tss', invoke_without_command=True)
    async def tss_cmd(self, ctx):
        embed = discord.Embed(title='TSS Commands')
        embed.add_field(name='Save blobs for all of your devices',
                        value=f'`{ctx.prefix}tss saveall`', inline=False)
        embed.add_field(name='Save blobs for one of your devices',
                        value=f'`{ctx.prefix}tss save`', inline=False)
        embed.add_field(name='List all of the blobs saved for your devices',
                        value=f'`{ctx.prefix}tss listall`', inline=False)
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @tss_cmd.command(name='save')
    async def save_single_device_blobs(self, ctx):  # 90% of this was taken from the `device remove` command
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
            title='Save Blobs', description="Choose the number of the device you'd like to save blobs for.\nType `cancel` to cancel.")

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
            await answer.delete()
        except ValueError:
            embed = discord.Embed(
                title='Error', description='Invalid input given.')
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            await answer.delete()
            return

        if not 0 <= num <= len(result):
            embed = discord.Embed(
                title='Error', description=f'Device `{num}` does not exist.')
            embed.set_footer(text=ctx.message.author.name,
                             icon_url=ctx.message.author.avatar_url_as(static_format='png'))
            await message.edit(embed=embed)
            return

        cursor.execute(
            'SELECT * from autotss WHERE device_num = ? AND userid = ?', (num, ctx.message.author.id))
        result = cursor.fetchall()

        embed = discord.Embed(
            title='Save Blobs', description=f'Saving blobs for `{result[0][2]}`...')
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await message.edit(embed=embed)

        signed_buildids = await self.get_signed_buildids(result[0])
        signed_versions = []
        for x in signed_buildids:
            signed_versions.append(await self.buildid_to_version(result[0], x))

        for x in list(signed_buildids):
            blob = await self.save_blob(result[0], x)

            if blob is False:
                embed = discord.Embed(
                    title='Error', description=f'Failed to save blobs for `{result[0][2]}`, `iOS {await self.buildid_to_version(result[0], x)}`\nContinuing to save blobs...')
                embed.set_footer(text=ctx.message.author.name,
                                    icon_url=ctx.message.author.avatar_url_as(static_format='png'))
                await message.edit(embed=embed)

                signed_versions.pop(signed_buildids.index(x))
                signed_buildids.pop(signed_buildids.index(x))

        saved_versions = str()

        for x in range(len(signed_buildids)):
            saved_versions += f'`iOS {signed_versions[x]}, {signed_buildids[x]}`, '

        embed = discord.Embed(
            title='Save Blobs', description=f'Saved blobs for {saved_versions[:-2]}.')
        embed.set_footer(text=ctx.message.author.name,
                         icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await message.edit(embed=embed)

        db.close()

    @tss_cmd.command(name='saveall')
    async def save_all_device_blobs(self, ctx):
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

        cursor.execute(
            'SELECT * from autotss WHERE userid = ?', (ctx.message.author.id,))
        result = cursor.fetchall()

        blob_embed = discord.Embed(
            title='Save Blobs', description=f'Saving blobs for all of your devices...')
        blob_embed.set_footer(text=ctx.message.author.name,
                        icon_url=ctx.message.author.avatar_url_as(static_format='png'))

        message = await ctx.send(embed=blob_embed)

        saved_blobs = int()

        for x in range(len(result)):

            signed_buildids = await self.get_signed_buildids(result[x])
            signed_versions = []
            for i in signed_buildids:
                signed_versions.append(await self.buildid_to_version(result[x], i))

            for i in list(signed_buildids):
                blob = await self.save_blob(result[x], i)

                if blob is False:
                    blob_embed.add_field(name='Error',
                                         value=f'Failed to save blobs for `{result[x][2]}`, `iOS {await self.buildid_to_version(result[x], i)}`\nContinuing to save blobs...', inline=False)
                    await message.edit(embed=blob_embed)

                    signed_versions.pop(signed_buildids.index(i))
                    signed_buildids.pop(signed_buildids.index(i))

            saved_versions = str()

            for i in range(len(signed_buildids)):
                saved_versions += f'`iOS {signed_versions[i]}, {signed_buildids[i]}`, '

            saved_blobs += len(signed_buildids)

        embed = discord.Embed(
            title='Save Blobs', description=f'Saved {saved_blobs} blobs for {len(result)} devices.')
        embed.set_footer(text=ctx.message.author.name,
                        icon_url=ctx.message.author.avatar_url_as(static_format='png'))
        await message.edit(embed=embed)

        db.close()


    @tss_cmd.command(name='listall')
    async def list_all_blobs(self, ctx):
        await ctx.send("stfu i haven't implemented this yet")


def setup(bot):
    bot.add_cog(TSS(bot))
