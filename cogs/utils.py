from aioify import aioify
from discord.ext import commands
import aiofiles
import aiohttp
import aiosqlite
import discord
import glob
import json
import os
import remotezip
import requests
import shutil


class Utils(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.os = aioify(os, name='os')
		self.shutil = aioify(shutil, name='shutil')

	async def backup_blobs(self, tmpdir, *ecids):
		await self.os.mkdir(f'{tmpdir}/Blobs')

		for ecid in ecids:
			try:
				await self.shutil.copytree(f'Data/Blobs/{ecid}', f'{tmpdir}/Blobs/{ecid}')
			except FileNotFoundError:
				pass

		if len(glob.glob(f'{tmpdir}/Blobs/*')) == 0:
			return

		await self.shutil.make_archive(f'{tmpdir}_blobs', 'zip', tmpdir)
		return await self.upload_file(f'{tmpdir}_blobs.zip', 'blobs.zip')

	async def buildid_to_version(self, identifier, buildid):
		api_url = f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw'
		async with aiohttp.ClientSession() as session, session.get(api_url) as resp:
			api = await resp.json()

		return next(x['version'] for x in api['firmwares'] if x['buildid'] == buildid)

	def get_manifest(self, identifier, buildid, dir):
		api_url = f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw'
		api = requests.get(api_url).json()

		firm = next(x['url'] for x in api['firmwares'] if x['buildid'] == buildid)
		with remotezip.RemoteZip(firm) as ipsw:
			manifest = ipsw.read(next(f for f in ipsw.namelist() if 'BuildManifest' in f))

		with open(f'{dir}/BuildManifest.plist', 'wb') as f:
			f.write(manifest)

		return f'{dir}/BuildManifest.plist'

	async def get_cpid(self, session, identifier):
		async with session.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw') as resp:
			api = await resp.json()

		return hex(api['cpid'])

	async def get_prefix(self, guild):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT prefix FROM prefix WHERE guild = ?', (guild,)) as cursor:
			try:
				guild_prefix = (await cursor.fetchone())[0]
			except TypeError:
				await db.execute('INSERT INTO prefix(guild, prefix) VALUES(?,?)', (guild, 'b!'))
				await db.commit()
				guild_prefix = 'b!'

		return guild_prefix

	async def get_signed_buildids(self, identifier):
		api_url = f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw'
		async with aiohttp.ClientSession() as session, session.get(api_url) as resp:
			api = await resp.json()

		return [x['buildid'] for x in api['firmwares'] if x['signed'] == True]

	async def update_device_count(self):
		async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss WHERE enabled = ?', (True,)) as cursor:
			all_devices = (await cursor.fetchall())

		num_devices = int()
		for user_devices in all_devices:
			devices = json.loads(user_devices[0])
			num_devices += len(devices)

		await self.bot.change_presence(activity=discord.Game(name=f"Ping me for help! | Saving blobs for {num_devices} device{'s' if num_devices != 1 else ''}"))

	async def upload_file(self, file, name):
		async with aiohttp.ClientSession() as session, aiofiles.open(file, 'rb') as f, session.put(f'https://up.psty.io/{name}', data=f) as response:
			resp = await response.text()

		return resp.splitlines()[-1].split(':', 1)[1][1:]

def setup(bot):
	bot.add_cog(Utils(bot))
