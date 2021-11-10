from discord.ext import commands
from typing import Optional, Union

import aiofiles
import aiosqlite
import asyncio
import discord
import glob
import json
import os
import remotezip
import shutil


class UtilsCog(commands.Cog, name='Utilities'):
    def __init__(self, bot):
        self.bot = bot
        self.saving_blobs = False

    @property
    def invite(self) -> str:
        """ Returns an invite URL for the bot.

        This is a much better implementation that utilizes
        available tools in the discord library rather than
        being lazy and using a long string. """
        return discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(93184), scopes=('bot', 'applications.commands'))

    async def _upload_file(self, file: str, name: str) -> str:
        async with aiofiles.open(file, 'rb') as f, self.bot.session.put(f'https://up.psty.io/{name}', data=f) as response:
            resp = await response.text()

        return resp.splitlines()[-1].split(':', 1)[1][1:]

    async def backup_blobs(self, tmpdir: str, *ecids: list[str]):
        await asyncio.to_thread(os.mkdir, f'{tmpdir}/SHSH Blobs')

        if len(ecids) == 1:
            for firm in glob.glob(f'Data/Blobs/{ecids[0]}/*'):
                await asyncio.to_thread(shutil.copytree, firm, f"{tmpdir}/SHSH Blobs/{firm.split('/')[-1]}")
        else:
            for ecid in ecids:
                try:
                    await asyncio.to_thread(shutil.copytree, f'Data/Blobs/{ecid}', f'{tmpdir}/SHSH Blobs/{ecid}')
                except FileNotFoundError:
                    pass

        if len(glob.glob(f'{tmpdir}/SHSH Blobs/*')) == 0:
            return

        await asyncio.to_thread(shutil.make_archive, f'{tmpdir}_blobs', 'zip', tmpdir)
        return await self._upload_file(f'{tmpdir}_blobs.zip', 'shsh_blobs.zip')

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

    async def check_identifier(self, identifier: str) -> bool:
        async with self.bot.session.get('https://api.ipsw.me/v4/devices') as resp:
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

    async def fetch_ipswme_api(self, identifier: str) -> dict:
        async with self.bot.session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
            return await resp.json()

    async def get_cpid(self, identifier: str, boardconfig: str) -> str:
        api = await self.fetch_ipswme_api(identifier)
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
                'icon_url': str(member.display_avatar.with_static_format('png').url)
            }
        }

        return discord.Embed.from_dict(embed)

    async def update_device_count(self) -> None:
        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE enabled = ?', (True,)) as cursor:
            num_devices = sum(len(json.loads(devices[0])) for devices in await cursor.fetchall())

        await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving SHSH blobs for {num_devices} device{'s' if num_devices != 1 else ''}."))

    async def whitelist_check(self, ctx: commands.Context) -> bool:
        if (await ctx.bot.is_owner(ctx.author)) or (ctx.author.guild_permissions.administrator):
            return True

        whitelist = await self.get_whitelist(ctx.guild.id)
        if (whitelist is not None) and (whitelist.id != ctx.channel.id):
            embed = discord.Embed(title='Hey!', description=f'AutoTSS can only be used in {whitelist.mention}.')
            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
            await ctx.reply(embed=embed)

            return False

        return True

    # SHSH Blob saving functions

    async def _save_blob(self, device: dict, firm: dict, manifest: str, tmpdir: str) -> bool:
        generators = list()
        save_path = [
            'Data',
            'Blobs',
            device['ecid'],
            firm['version'],
            firm['buildid']
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
                await asyncio.to_thread(os.remove, *[f for f in glob.glob(f'{tmpdir}/*.shsh*')])

            args.append('-g')
            for gen in generators:
                args.append(gen)
                cmd = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE)
                stdout = (await cmd.communicate())[0]

                if 'Saved shsh blobs!' not in stdout.decode():
                    return False

                args.pop(-1)

        if not await asyncio.to_thread(os.path.isdir, path):
            await asyncio.to_thread(os.makedirs, path)

        for blob in glob.glob(f'{tmpdir}/*.shsh*'):
            await asyncio.to_thread(os.rename, blob, f"{path}/{blob.split('/')[-1]}")

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
                manifest = await asyncio.to_thread(self.get_manifest, firm['url'], tmpdir)
                saved_blob = await self._save_blob(device, firm, manifest, tmpdir) if manifest != False else False

            if saved_blob is True:
                device['saved_blobs'].append({x:y for x,y in firm.items() if x != 'url'})
                stats['saved_blobs'].append(firm)
            else:
                stats['failed_blobs'].append(firm)

        stats['device'] = device

        return stats

    async def save_user_blobs(self, user: int, devices: list[dict]) -> None:
        tasks = [self.save_device_blobs(device) for device in devices]
        data = await asyncio.gather(*tasks)

        async with aiosqlite.connect('Data/autotss.db') as db:        
            await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps([d['device'] for d in data]), user))
            await db.commit()

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
