from aioify import aioify
from discord.ext import commands
from typing import Optional, Union
import aiofiles
import aiohttp
import aiosqlite
import discord
import glob
import json
import os
import remotezip
import shutil


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.os = aioify(os, name='os')
        self.shutil = aioify(shutil, name='shutil')

    @property
    async def invite(self) -> str:
        return f'https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&scope=bot&permissions=93184'

    async def backup_blobs(self, tmpdir: str, *ecids: list):
        await self.os.mkdir(f'{tmpdir}/Blobs')

        for ecid in ecids:
            try:
                await self.shutil.copytree(f'Data/Blobs/{ecid}', f'{tmpdir}/Blobs/{ecid}')
            except FileNotFoundError:
                pass

        if len(glob.glob(f'{tmpdir}/Blobs/*')) == 0:
            return

        await self.shutil.make_archive(f'{tmpdir}_blobs', 'zip', tmpdir)
        return await self.upload_file(f'{tmpdir}_blobs.zip', 'shsh_blobs.zip')

    async def buildid_to_version(self, identifier: str, buildid: str) -> str:
        api_url = f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw'
        async with aiohttp.ClientSession() as session, session.get(api_url) as resp:
            api = await resp.json()

        return next(x['version'] for x in api['firmwares'] if x['buildid'] == buildid)

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

        async with session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
            api = await resp.json()

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
        else:
            return True

    async def check_name(self, name: str, user: str) -> Union[bool, int]: # This function will return different values based on where it errors out at
        if not 4 <= len(name) <= 20: # Length check
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

    async def get_cpid(self, session, identifier: str, boardconfig: str) -> str:
        async with session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
            api = await resp.json()

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

    async def get_signed_buildids(self, session, identifier: str) -> list:
        api_url = f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw'
        async with session.get(api_url) as resp:
            api = await resp.json()

        buildids = list()

        for firm in [x for x in api['firmwares'] if x['signed'] == True]:
            buildids.append({
                    'version': firm['version'],
                    'buildid': firm['buildid'],
                    'url': firm['url'],
                    'type': 'Release'

                })

        beta_api_url = f'https://api.m1sta.xyz/betas/{identifier}'
        async with session.get(beta_api_url) as resp:
            if resp.status != 200:
                beta_api = None
            else:
                beta_api = await resp.json()

        if beta_api is None:
            return buildids

        for firm in [x for x in beta_api if x['signed'] == True]:
            buildids.append({
                    'version': firm['version'],
                    'buildid': firm['buildid'],
                    'url': firm['url'],
                    'type': 'Beta'

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
            'AutoTSS checks for new versions to save SHSH blobs for **every 30 minutes**.'
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

def setup(bot):
    bot.add_cog(Utils(bot))
