from discord.ext import commands
import aiofiles
import aiohttp
import aiosqlite
import discord
import json
import remotezip
import requests


class Utils(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

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
