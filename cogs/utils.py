from aioify import aioify
from discord.ext import commands
from typing import Optional, Union
import aiofiles
import aiohttp
import aiosqlite
import asyncio
import discord
import glob
import json
import os
import remotezip
import shutil
import time


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.os = aioify(os, name='os')
        self.shutil = aioify(shutil, name='shutil')
        self.time = aioify(time, name='time')

    @property
    def invite(self) -> str:
        """ Returns an invite URL for the bot.

        This is a much better implementation that utilizes
        available tools in the discord library rather than
        being lazy and using a long string. """
        perms = discord.Permissions(93184)
        return discord.utils.oauth_url(self.bot.user.id, perms)

    async def backup_blobs(self, tmpdir: str, *ecids: list):
        await self.os.mkdir(f'{tmpdir}/SHSH Blobs')

        for ecid in ecids:
            try:
                await self.shutil.copytree(f'Data/Blobs/{ecid}', f'{tmpdir}/SHSH Blobs/{ecid}')
            except FileNotFoundError:
                pass

        if len(glob.glob(f'{tmpdir}/SHSH Blobs/*')) == 0:
            return

        await self.shutil.make_archive(f'{tmpdir}_blobs', 'zip', tmpdir)
        return await self.upload_file(f'{tmpdir}_blobs.zip', 'shsh_blobs.zip')

    async def censor_ecid(self, ecid: str) -> str: return ('*' * len(ecid))[:-4] + ecid[-4:]

    async def check_apnonce(self, cpid: int, nonce: str) -> bool:
        try:
            int(nonce, 16)
        except ValueError or TypeError:
            return False

        if 32784 <= cpid < 35072: # A10+ device apnonce's are 64 characters long, 
            apnonce_len = 64
        else: # A9 and below device apnonce's are 40 characters.
            apnonce_len = 40

        if len(nonce) != apnonce_len:
            return False

        return True

    async def check_boardconfig(self, session, identifier: str, boardconfig: str) -> bool:
        if boardconfig[-2:] != 'ap':
            return False

        api = await self.fetch_ipswme_api(session, identifier)
        if not any(x['boardconfig'].lower() == boardconfig for x in api['boards']): # If no boardconfigs for the given device identifier match the boardconfig, then return False
            return False
        else:
            return True

    async def check_ecid(self, ecid: str) -> Union[int, bool]:
        if not 9 <= len(ecid) <= 16: # All ECIDs are between 9-16 characters
            return 0

        try:
            int(ecid, 16) # Make sure the ECID provided is hexadecimal, not decimal
        except ValueError or TypeError:
            return 0

        async with aiosqlite.connect('Data/autotss.db') as db: # Make sure the ECID the user provided isn't already a device added to AutoTSS.
            async with db.execute('SELECT devices from autotss') as cursor:
                try:
                    devices = [device[0] for device in (await cursor.fetchall())]
                except TypeError:
                    return 0

        if any(ecid in device_info for device_info in devices): # There's no need to convert the json string to a dict here
            return -1

        return True

    async def check_generator(self, generator: str) -> bool:
        if not generator.startswith('0x'): # Generator must start wth '0x'
            return False

        if len(generator) != 18: # Generator must be 18 characters long, including '0x' prefix
            return False

        try:
            int(generator, 16) # Generator must be hexadecimal
        except:
            return False

        return True

    async def check_identifier(self, session, identifier: str) -> bool:
        async with session.get('https://api.ipsw.me/v4/devices') as resp:
            api = await resp.json()

        if identifier not in [device['identifier'] for device in api]:
            return False

        return True

    async def check_name(self, name: str, user: str) -> Union[bool, int]: # This function will return different values based on where it errors out at
        if not len(name) <= 20: # Length check
            return 0

        async with aiosqlite.connect('Data/autotss.db') as db: # Make sure the user doesn't have any other devices with the same name added
            async with db.execute('SELECT devices from autotss WHERE user = ?', (user,)) as cursor:
                try:
                    devices = json.loads((await cursor.fetchone())[0])
                except:
                    return True

        if any(x['name'] == name.lower() for x in devices):
            return -1

        return True

    async def fetch_ipswme_api(self, session, identifier: str) -> dict:
        async with session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
            return await resp.json()

    async def get_cpid(self, session, identifier: str, boardconfig: str) -> str:
        api = await self.fetch_ipswme_api(session, identifier)
        return next(board['cpid'] for board in api['boards'] if board['boardconfig'].lower() == boardconfig.lower())

    def get_manifest(self, url: str, dir: str) -> Union[bool, str]:
        try:
            with remotezip.RemoteZip(url) as ipsw:
                manifest = ipsw.read(next(f for f in ipsw.namelist() if 'BuildManifest' in f))
        except remotezip.RemoteIOError:
            return False

        with open(f'{dir}/BuildManifest.plist', 'wb') as f:
            f.write(manifest)

        return f'{dir}/BuildManifest.plist'

    async def get_prefix(self, guild: int) -> str:
        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT prefix FROM prefix WHERE guild = ?', (guild,)) as cursor:
            try:
                guild_prefix = (await cursor.fetchone())[0]
            except TypeError:
                await db.execute('INSERT INTO prefix(guild, prefix) VALUES(?,?)', (guild, 'b!'))
                await db.commit()
                guild_prefix = 'b!'

        return guild_prefix

    async def get_firms(self, session, identifier: str) -> list:
        api = await self.fetch_ipswme_api(session, identifier)

        buildids = list()
        for firm in api['firmwares']:
            buildids.append({
                    'version': firm['version'],
                    'buildid': firm['buildid'],
                    'url': firm['url'],
                    'type': 'Release',
                    'signed': firm['signed']

                })

        beta_api_url = f'https://api.m1sta.xyz/betas/{identifier}'
        async with session.get(beta_api_url) as resp:
            if resp.status != 200:
                return buildids
            else:
                beta_api = await resp.json()

        for firm in beta_api:
            if any(firm['buildid'] == f['buildid'] for f in buildids):
                continue

            if 'signed' not in firm.keys():
                continue

            buildids.append({
                    'version': firm['version'],
                    'buildid': firm['buildid'],
                    'url': firm['url'],
                    'type': 'Beta',
                    'signed': firm['signed']
                })

        return buildids

    async def get_whitelist(self, guild) -> Optional[Union[bool, discord.TextChannel]]:
        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * FROM whitelist WHERE guild = ?', (guild,)) as cursor:
            data = await cursor.fetchone()

        if (data == None) or (data[2] == False):
            return None

        try:
            return await self.bot.fetch_channel(data[1])
        except discord.errors.NotFound:
            return None

    async def info_embed(self, prefix: str, member: discord.Member) -> discord.Embed:
        notes = (
            'There is a limit of **10 devices per user**.',
            "You **must** share a server with AutoTSS, or else **AutoTSS won't automatically save SHSH blobs for you**.",
            'AutoTSS checks for new versions to save SHSH blobs for **every 3 hours**.'
        )

        embed = {
            'title': "Hey, I'm AutoTSS!",
            'thumbnail': {
                'url': str(self.bot.user.avatar_url_as(static_format='png'))
            },
            'fields': [{
                'name': 'What do I do?',
                'value': 'I can automatically save SHSH blobs for all of your iOS devices!',
                'inline': False
            },
            {
                'name': 'What are SHSH blobs?',
                'value': 'A great explanation that takes an in-depth look at what SHSH blobs are, what they can be used for, and more can be found [here](https://www.reddit.com/r/jailbreak/comments/m3744k/tutorial_shsh_generatorbootnonce_apnonce_nonce/).',
                'inline': False
            },
            {
                'name': 'Disclaimer',
                'value': 'I am not at fault for any issues you may experience with AutoTSS.',
                'inline': False
            },
            {
                'name': 'Support',
                'value': 'For AutoTSS support, join my [Discord](https://m1sta.xyz/discord).',
                'inline': False
            },
            {
                'name': 'All Commands',
                'value': f'`{prefix}help`',
                'inline': True
            },
            {
                'name': 'Add Device',
                'value': f'`{prefix}devices add`',
                'inline': True
            },
            {
                'name': 'Save SHSH Blobs',
                'value': f'`{prefix}tss save`',
                'inline': True
            },
            {
                'name': 'Notes',
                'value': '- '+ '\n- '.join(notes),
                'inline': False
            }],
            'footer': {
                'text': member.display_name,
                'icon_url': str(member.avatar_url_as(static_format='png'))
            }
        }

        return discord.Embed.from_dict(embed)

    async def watch_pagination(self, embeds: list, message: discord.Message, *, get_answer: bool=False, timeout: int=300) -> Optional[int]:
        arrows = ['⬅', '➡'] # [left arrow, right arrow]
        start_time = await self.time.time()
        embed_num = embeds.index(next(embed for embed in embeds if message.embeds[0].title == embed['title']))

        while round(await self.time.time() - start_time) < timeout:
            if embed_num > 0:
                await message.add_reaction(arrows[0])

            if embed_num < (len(embeds) - 1):
                await message.add_reaction(arrows[1])

            if get_answer:
                await message.add_reaction('✅')

            reaction, user = await self.bot.wait_for('reaction_add', check=lambda reaction, user: reaction.message == message)
            if user != message.reference.cached_message.author:
                await reaction.remove(user)
                continue

            if reaction.emoji not in arrows:
                if (reaction.emoji == '✅') and get_answer:
                    await message.clear_reactions()
                    return embed_num

                await reaction.clear()
                continue

            if reaction.emoji == arrows[0]:
                embed_num -= 1

            elif reaction.emoji == arrows[1]:
                embed_num += 1

            await message.clear_reactions()
            await message.edit(embed=discord.Embed.from_dict(embeds[embed_num]))
            
        await message.clear_reactions()

    async def save_blob(self, device: dict, version: str, buildid: str, manifest: str, tmpdir: str) -> bool:
        generators = list()
        save_path = [
            'Data',
            'Blobs',
            device['ecid'],
            version,
            buildid
        ]

        args = [
            'tsschecker',
            '-d', device['identifier'],
            '-B', device['boardconfig'],
            '-e', f"0x{device['ecid']}",
            '-m', manifest,
            '--save-path', tmpdir,
            '-s'
        ]

        if device['apnonce'] is not None:
            args.append('--apnonce')
            args.append(device['apnonce'])
            save_path.append(device['apnonce'])
        else:
            generators.append('0x1111111111111111')
            generators.append('0xbd34a880be0b53f3')
            save_path.append('no-apnonce')

        if device['generator'] is not None and device['generator'] not in generators:
            generators.append(device['generator'])

        path = '/'.join(save_path)

        if len(generators) == 0:
            if len(glob.glob(f'{path}/*.shsh*')) == 1:
                return True

            cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
            stdout = (await cmd.communicate())[0]

            if 'Saved shsh blobs!' not in stdout.decode():
                return False

        else:
            if len(glob.glob(f'{path}/*.shsh*')) == len(generators):
                return True

            elif len(glob.glob(f'{path}/*.shsh*')) > 0:
                await self.os.remove(*[f for f in glob.glob(f'{tmpdir}/*.shsh*')])

            args.append('-g')
            for gen in generators:
                args.append(gen)
                cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
                stdout = (await cmd.communicate())[0]

                if 'Saved shsh blobs!' not in stdout.decode():
                    return False

                args.pop(-1)

        if not await self.os.path.isdir(path):
            await self.os.makedirs(path)

        for blob in glob.glob(f'{tmpdir}/*.shsh*'):
            await self.os.rename(blob, f"{path}/{blob.split('/')[-1]}")

        return True

    async def update_auto_saver_frequency(self, time: int=10800) -> None:
        async with aiosqlite.connect('Data/autotss.db') as db:
            async with db.execute('SELECT time FROM auto_frequency') as cursor:
                if await cursor.fetchone() is None:
                    sql = 'INSERT INTO auto_frequency(time) VALUES(?)'
                else:
                    sql = 'UPDATE auto_frequency SET time = ?'

            await db.execute(sql, (time,))
            await db.commit()

    async def update_device_count(self) -> None:
        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE enabled = ?', (True,)) as cursor:
            all_devices = (await cursor.fetchall())

        num_devices = int()
        for user_devices in all_devices:
            devices = json.loads(user_devices[0])
            num_devices += len(devices)

        await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving SHSH blobs for {num_devices} device{'s' if num_devices != 1 else ''}."))

    async def upload_file(self, file: str, name: str) -> str:
        async with aiohttp.ClientSession() as session, aiofiles.open(file, 'rb') as f, session.put(f'https://up.psty.io/{name}', data=f) as response:
            resp = await response.text()

        return resp.splitlines()[-1].split(':', 1)[1][1:]

    async def whitelist_check(self, ctx: commands.Context) -> bool:
        if (await ctx.bot.is_owner(ctx.author)) or (ctx.author.guild_permissions.administrator):
            return True

        whitelist = await self.get_whitelist(ctx.guild.id)
        if (whitelist is not None) and (whitelist.id != ctx.channel.id):
            embed = discord.Embed(title='Hey!', description=f'AutoTSS can only be used in {whitelist.mention}.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await ctx.reply(embed=embed)

            return False

        return True


def setup(bot):
    bot.add_cog(Utils(bot))
