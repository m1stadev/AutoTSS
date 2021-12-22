from discord.ext import commands
from typing import Optional, Union

import aiofiles
import aiopath
import asyncio
import discord
import json
import pathlib
import remotezip
import shutil
import sys


class UtilsCog(commands.Cog, name='Utilities'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.saving_blobs = False

    @property
    def invite(self) -> str:
        """ Returns an invite URL for the bot.

        This is a much better implementation that utilizes
        available tools in the discord library rather than
        being lazy and using a long string. """
        return discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(93184), scopes=('bot', 'applications.commands'))

    async def _upload_file(self, file: aiopath.AsyncPath) -> str:
        async with file.open('rb') as f, self.bot.session.put(f'https://up.psty.io/{file.name}', data=f) as resp:
            data = await resp.text()

        return data.splitlines()[-1].split(':', 1)[1][1:]

    async def backup_blobs(self, tmpdir: aiopath.AsyncPath, *ecids: list[str]) -> Optional[str]:
        blobdir = aiopath.AsyncPath('Data/Blobs')
        tmpdir = tmpdir / 'SHSH Blobs'
        await tmpdir.mkdir()

        if len(ecids) == 1:
            async for firm in blobdir.glob(f'{ecids[0]}/*'):
                await asyncio.to_thread(shutil.copytree, firm, tmpdir / firm.name)
    
        else:
            for ecid in ecids:
                try:
                    await asyncio.to_thread(shutil.copytree, blobdir / ecid, tmpdir / ecid)
                except FileNotFoundError:
                    pass

        if len([_ async for _ in tmpdir.glob('*/') if await _.is_dir()]) == 0:
            return

        await asyncio.to_thread(shutil.make_archive, tmpdir.parent / 'shsh_blobs', 'zip', tmpdir)
        return await self._upload_file(tmpdir.parent / 'shsh_blobs.zip')

    async def censor_ecid(self, ecid: str) -> str: return ('*' * len(ecid))[:-4] + ecid[-4:]

    async def check_apnonce(self, cpid: int, nonce: str) -> bool:
        try:
            int(nonce, 16)
        except ValueError or TypeError:
            return False

        if 0x8010 <= cpid < 0x8900: # A10+ device ApNonces are 64 characters long
            apnonce_len = 64
        else: # A9 and below device ApNonces are 40 characters
            apnonce_len = 40

        if len(nonce) != apnonce_len:
            return False

        return True

    async def check_boardconfig(self, identifier: str, boardconfig: str) -> bool:
        if boardconfig[-2:] != 'ap':
            return False

        api = await self.fetch_ipswme_api(identifier)
        if not any(x['boardconfig'].lower() == boardconfig for x in api['boards']): # If no boardconfigs for the given device identifier match the boardconfig, then return False
            return False
        else:
            return True

    async def check_ecid(self, ecid: str) -> Union[int, bool]:
        if not 7 <= len(ecid) <= 20: # All ECIDs are between 7-20 characters
            return 0

        try:
            int(ecid, 16) # Make sure the ECID provided is hexadecimal, not decimal
        except ValueError or TypeError:
            return 0

        async with self.bot.db.execute('SELECT devices from autotss') as cursor:  # Make sure the ECID the user provided isn't already a device added to AutoTSS.
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

    async def check_identifier(self, identifier: str) -> bool:
        async with self.bot.session.get('https://api.ipsw.me/v4/devices') as resp:
            api = await resp.json()

        if identifier not in [device['identifier'] for device in api]:
            return False

        return True

    async def check_name(self, name: str, user: int) -> Union[bool, int]: # This function will return different values based on where it errors out at
        if not len(name) <= 20: # Length check
            return 0

        async with self.bot.db.execute('SELECT devices from autotss WHERE user = ?', (user,)) as cursor: # Make sure the user doesn't have any other devices with the same name added
            try:
                devices = json.loads((await cursor.fetchone())[0])
            except:
                return True

        if any(x['name'] == name.lower() for x in devices):
            return -1

        return True

    async def fetch_ipswme_api(self, identifier: str) -> dict:
        async with self.bot.session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
            return await resp.json()

    async def get_cpid(self, identifier: str, boardconfig: str) -> str:
        api = await self.fetch_ipswme_api(identifier)
        return next(board['cpid'] for board in api['boards'] if board['boardconfig'].lower() == boardconfig.lower())

    def _get_manifest(self, url: str, path: str) -> Union[bool, aiopath.AsyncPath]:
        try:
            with remotezip.RemoteZip(url) as ipsw:
                manifest = ipsw.read(next(f for f in ipsw.namelist() if 'BuildManifest' in f))
        except remotezip.RemoteIOError:
            return False

        manifest_path = (pathlib.Path(path) / 'manifest.plist')
        with manifest_path.open('wb') as f:
            f.write(manifest)

        return aiopath.AsyncPath(manifest_path)

    async def get_firms(self, identifier: str) -> list:
        api = await self.fetch_ipswme_api(identifier)

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
        async with self.bot.session.get(beta_api_url) as resp:
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

    async def get_whitelist(self, guild: int) -> Optional[Union[bool, discord.TextChannel]]:
        async with self.bot.db.execute('SELECT * FROM whitelist WHERE guild = ?', (guild,)) as cursor:
            data = await cursor.fetchone()

        if (data is None) or (data[2] == False):
            return None

        try:
            return await self.bot.fetch_channel(data[1])
        except discord.errors.NotFound:
            await self.bot.db.execute('DELETE FROM whitelist WHERE guild = ?', (guild,))
            await self.bot.db.commit()

    async def info_embed(self, member: discord.Member) -> discord.Embed:
        notes = (
            'There is a limit of **10 devices per user**.',
            "You **must** share a server with AutoTSS, or else **AutoTSS won't automatically save SHSH blobs for you**.",
            'AutoTSS checks for new versions to save SHSH blobs for **every 5 minutes**.'
        )

        embed = {
            'title': "Hey, I'm AutoTSS!",
            'thumbnail': {
                'url': str(self.bot.user.display_avatar.with_static_format('png').url)
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
                'value': '`/help`',
                'inline': True
            },
            {
                'name': 'Add Device',
                'value': '`/devices add`',
                'inline': True
            },
            {
                'name': 'Save SHSH Blobs',
                'value': '`/tss save`',
                'inline': True
            },
            {
                'name': 'Notes',
                'value': '- '+ '\n- '.join(notes),
                'inline': False
            }],
            'footer': {
                'text': member.display_name,
                'icon_url': str(member.display_avatar.with_static_format('png').url)
            }
        }

        return discord.Embed.from_dict(embed)

    async def update_device_count(self) -> None:
        async with self.bot.db.execute('SELECT devices from autotss WHERE enabled = ?', (True,)) as cursor:
            num_devices = sum(len(json.loads(devices[0])) for devices in await cursor.fetchall())

        await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving SHSH blobs for {num_devices} device{'s' if num_devices != 1 else ''}."))

    async def whitelist_check(self, ctx: discord.ApplicationContext) -> bool:
        if (await ctx.bot.is_owner(ctx.author)) or (ctx.author.guild_permissions.manage_messages):
            return True

        whitelist = await self.get_whitelist(ctx.guild.id)
        if (whitelist is not None) and (whitelist.id != ctx.channel.id):
            embed = discord.Embed(title='Hey!', description=f'AutoTSS can only be used in {whitelist.mention}.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.respond(embed=embed)

            return False

        return True

    # SHSH Blob saving functions

    async def _save_blob(self, device: dict, firm: dict, manifest: str, tmpdir: aiopath.AsyncPath) -> bool:
        generators = list()
        save_path = [
            'Data',
            'Blobs',
            device['ecid'],
            firm['version'],
            firm['buildid']
        ]

        args = [
            'tsschecker' if sys.platform != 'win32' else next(_ async for _ in aiopath.AsyncPath(__file__).parent.glob('tsschecker*.exe') if await _.is_file()),
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

        save_path = aiopath.AsyncPath('/'.join(save_path))
        if len(generators) == 0:
            if len([_ async for _ in save_path.glob('*.shsh*')]) == 1:
                return True

            cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
            stdout = (await cmd.communicate())[0]

            if 'Saved shsh blobs!' not in stdout.decode():
                return False

        else:
            if len([_ async for _ in save_path.glob('*.shsh*')]) == len(generators):
                return True

            elif len([_ async for _ in save_path.glob('*.shsh*')]) > 0:
                async for blob in save_path.glob('*.shsh*'):
                    await blob.unlink()

            args.append('-g')
            for gen in generators:
                args.append(gen)
                cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
                stdout = (await cmd.communicate())[0]

                if 'Saved shsh blobs!' not in stdout.decode():
                    return False

                args.pop(-1)

        await save_path.mkdir(parents=True, exist_ok=True)
        async for blob in tmpdir.glob('*.shsh*'):
            await blob.rename(save_path / blob.name)

        return True

    async def save_device_blobs(self, device: dict) -> None:
        stats = {
            'saved_blobs': list(),
            'failed_blobs': list(),
        }

        firms = await self.get_firms(device['identifier'])
        for firm in [f for f in firms if f['signed'] == True]:
            if any(firm['buildid'] == saved_firm['buildid'] for saved_firm in device['saved_blobs']): # If we've already saved blobs for this version, skip
                continue

            async with aiofiles.tempfile.TemporaryDirectory() as tmpdir:
                manifest = await asyncio.to_thread(self._get_manifest, firm['url'], tmpdir)
                saved_blob = await self._save_blob(device, firm, manifest, manifest.parent) if manifest != False else False

            if saved_blob is True:
                device['saved_blobs'].append({x:y for x,y in firm.items() if x not in ('url', 'signed')})
                stats['saved_blobs'].append(firm)
            else:
                stats['failed_blobs'].append(firm)

        stats['device'] = device

        return stats

    async def save_user_blobs(self, user: int, devices: list[dict]) -> None:
        tasks = [self.save_device_blobs(device) for device in devices]
        data = await asyncio.gather(*tasks)
  
        await self.bot.db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps([d['device'] for d in data]), user))
        await self.bot.db.commit()

        user_stats = {
            'blobs_saved': sum([len(d['saved_blobs']) for d in data]),
            'devices_saved': len([d for d in data if d['saved_blobs']]),
            'devices': [d['device'] for d in data]
        }

        for d in range(len(user_stats['devices'])):
            user_stats['devices'][d]['failed_blobs'] = data[d]['failed_blobs']

        return user_stats

    async def sem_call(self, func, *args):
        async with self.sem:
            return await func(*args)

def setup(bot):
    bot.add_cog(UtilsCog(bot))
