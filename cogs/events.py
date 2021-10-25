from aioify import aioify
from discord.ext import commands, tasks
import aiohttp
import aiosqlite
import asyncio
import discord
import json
import os
import shutil


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.os = aioify(os, name='os')
        self.shutil = aioify(shutil, name='shutil')
        self.utils = self.bot.get_cog('Utils')
        self.auto_clean_db.start()
        self.signing_party_detection.start()
        self.auto_invalid_device_check.start()

    @tasks.loop()
    async def auto_clean_db(self) -> None:
        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss') as cursor:
            data = await cursor.fetchall()

        for user_devices in data:
            devices = json.loads(user_devices[0])
            if devices == list():
                async with aiosqlite.connect('Data/autotss.db') as db:
                    await db.execute('DELETE FROM autotss WHERE devices = ?', (user_devices[0],))
                    await db.commit()

        await asyncio.sleep(300)

    @auto_clean_db.before_loop
    async def before_auto_clean_db(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(3) # If first run, give on_ready() some time to create the database

    @tasks.loop()
    async def signing_party_detection(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.ipsw.me/v4/devices') as resp:
                devices = await resp.json()

            devices = [d for d in devices if any(x in d['identifier'] for x in ('iPhone', 'AppleTV', 'iPod', 'iPad'))]
            api = dict()
            for device in [d['identifier'] for d in devices]:
                api[device] = await self.utils.get_firms(session, device)

            try:
                self._api
            except AttributeError:
                self._api = api
                return

            for device in self._api.keys():
                for firm in [x for x in self._api[device] if x['signed'] == False]:
                    if any(new_firm['signed'] == True for new_firm in api[device] if new_firm['buildid'] == firm['buildid']):
                        print(f"[SIGN] Detected resigned firmware for: {device}, iOS {firm['version']}")
                        await self.utils.update_auto_saver_frequency(60) # Set blob saver frequency to 1 minute
                        tss = self.bot.get_cog('TSS') # Get TSS class
                        tss.blobs_loop = False

                        tss.auto_blob_saver.cancel() # Restart auto blob saver
                        await asyncio.sleep(1)
                        await self.utils.update_device_count()
                        tss.auto_blob_saver.start()

                        await asyncio.sleep(600) # Wait 10 minutes

                        await self.utils.update_auto_saver_frequency() # Set blob saver frequency back to 3 hours
                        tss.auto_blob_saver.cancel() # Restart auto blob saver
                        await asyncio.sleep(1)
                        tss.auto_blob_saver.start()

                        return
                else:
                    self._api[device] = api[device]

        await asyncio.sleep(30)

    @signing_party_detection.before_loop
    async def before_signing_party_detection(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(3) # If first run, give on_ready() some time to create the database

    @tasks.loop()
    async def auto_invalid_device_check(self) -> None: # If any users are saving SHSH blobs for A12+ devices without using custom apnonces, attempt to DM them saying they need to re-add the device
        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * FROM autotss') as cursor:
            data = await cursor.fetchall()

        if len(data) == 0:
            return

        invalid_devices = dict()
        async with aiohttp.ClientSession() as session:
            for userinfo in data:
                userid = userinfo[0]
                devices = json.loads(userinfo[1])
                invalid_devices[userid] = list()

                for device in devices:
                    cpid = await self.utils.get_cpid(session, device['identifier'], device['boardconfig'])
                    if (device['apnonce'] is not None) and (await self.utils.check_apnonce(cpid, device['apnonce']) == False):
                        invalid_devices[userid].append(device)
                        continue

                    if (device['generator'] is not None) and (await self.utils.check_generator(device['generator']) == False):
                        invalid_devices[userid].append(device)
                        continue

                    if (0x8020 <= cpid < 0x8900) and (device['apnonce'] is None):
                        invalid_devices[userid].append(device)

        for userid in [x for x in invalid_devices.keys() if len(invalid_devices[x]) > 0]:
            embed = discord.Embed(title='Hey!')
            msg = (
                'One or more of your devices were added incorrectly to AutoTSS, and are saving **invalid SHSH blobs**.',
                'Due to this, they have been removed from AutoTSS so they are no longer continuing to save invalid SHSH blobs.'
                'To fix this, please re-add the following devices to AutoTSS:'
            )
            embed.description = '\n'.join(msg)

            for device in invalid_devices[userid]:
                device_info = [
                    f"Device Identifier: `{device['identifier']}`",
                    f"ECID: `{device['ecid']}`",
                    f"Boardconfig: `{device['boardconfig']}`"
                ]

                if device['generator'] is not None:
                    device_info.insert(-1, f"Custom generator: `{device['generator']}`")

                if device['apnonce'] is not None:
                    device_info.insert(-1, f"Custom ApNonce: `{device['apnonce']}`")

                embed.add_field(name=f"**{device['name']}**", value='\n'.join(device_info))

            user = await self.bot.fetch_user(userid)

            try:
                await user.send(embed=embed)
            except:
                pass

            async with aiosqlite.connect('Data/autotss.db') as db:
                for device in invalid_devices[userid]:
                    await self.shutil.rmtree(f"Data/Blobs/{device['ecid']}")
                    async with db.execute('SELECT devices FROM autotss WHERE user = ?', (userid,)) as cursor:
                        devices = json.loads((await cursor.fetchone())[0])

                    devices.pop(next(devices.index(x) for x in devices if x['ecid'] == device['ecid']))

                    await db.execute('UPDATE autotss SET devices = ? WHERE user = ?', (json.dumps(devices), userid))
                    await db.commit()

        await asyncio.sleep(259200)

    @auto_invalid_device_check.before_loop
    async def before_invalid_device_check(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(3) # If first run, give on_ready() some time to create the database

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.bot.wait_until_ready()

        async with aiosqlite.connect('Data/autotss.db') as db:
            async with db.execute('SELECT prefix from prefix WHERE guild = ?', (guild.id,)) as cursor:
                if await cursor.fetchone() is not None:
                    await db.execute('DELETE from prefix where guild = ?', (guild.id,))
                    await db.commit()

            await db.execute('INSERT INTO prefix(guild, prefix) VALUES(?,?)', (guild.id, 'b!'))
            await db.commit()


        embed = await self.utils.info_embed('b!', self.bot.user)
        for channel in guild.text_channels:
            try:
                await channel.send(embed=embed)
                break
            except:
                pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.bot.wait_until_ready()

        async with aiosqlite.connect('Data/autotss.db') as db:
            await db.execute('DELETE from prefix where guild = ?', (guild.id,))
            await db.commit()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self.bot.wait_until_ready()

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE user = ?', (member.id,)) as cursor:
            data = await cursor.fetchone()

        if data is None:
            return

        async with aiosqlite.connect('Data/autotss.db') as db:
            await db.execute('UPDATE autotss SET enabled = ? WHERE user = ?', (True, member.id))
            await db.commit()

        await self.utils.update_device_count()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self.bot.wait_until_ready()

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE user = ?', (member.id,)) as cursor:
            data = await cursor.fetchone()

        if data is None:
            return

        if len(member.mutual_guilds) == 0:
            async with aiosqlite.connect('Data/autotss.db') as db:
                await db.execute('UPDATE autotss SET enabled = ? WHERE user = ?', (False, member.id))
                await db.commit()

            await self.utils.update_device_count()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if message.channel.type == discord.ChannelType.private:
            return

        if message.content.replace(' ', '').replace('!', '') == self.bot.user.mention:
            whitelist = await self.utils.get_whitelist(message.guild.id)
            if (whitelist is not None) and (whitelist.id != message.channel.id):
                return

            prefix = await self.utils.get_prefix(message.guild.id)

            embed = discord.Embed(title='AutoTSS', description=f'My prefix is `{prefix}`. To see all of my commands, run `{prefix}help`.')
            embed.set_footer(text=message.author.name, icon_url=message.author.avatar_url_as(static_format='png'))
            try:
                await message.reply(embed=embed)
            except:
                pass

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.os.makedirs('Data', exist_ok=True)

        async with aiosqlite.connect('Data/autotss.db') as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS autotss(
                user INTEGER,
                devices JSON,
                enabled BOOLEAN
                )
                ''')
            await db.commit()

            await db.execute('''
                CREATE TABLE IF NOT EXISTS prefix(
                guild INTEGER,
                prefix TEXT
                )
                ''')
            await db.commit()

            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelist(
                guild INTEGER,
                channel INTEGER,
                enabled BOOLEAN
                )
                ''')
            await db.commit()

            await db.execute('''
                CREATE TABLE IF NOT EXISTS auto_frequency(
                time INTEGER
                )
                ''')
            await db.commit()

        await self.utils.update_device_count()
        await self.utils.update_auto_saver_frequency()
        print('AutoTSS is now online.')

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error) -> None:
        await self.bot.wait_until_ready()

        embed = discord.Embed(title='Error')

        if ctx.message.channel.type == discord.ChannelType.private:
            embed.description = 'AutoTSS cannot be used in DMs. Please use AutoTSS in a Discord server.'
            await ctx.reply(embed=embed)
            return

        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)
        if isinstance(error, commands.CommandNotFound):
            if ctx.prefix.replace('!', '').replace(' ', '') == self.bot.user.mention:
                return

            embed.description = f"That command doesn't exist! Use `{prefix}help` to see all the commands I can run."
            await ctx.reply(embed=embed)

        elif isinstance(error, commands.MaxConcurrencyReached):
            embed.description = f"`{prefix + ctx.command.qualified_name}` cannot be ran more than once at the same time!"
            await ctx.reply(embed=embed)

        elif isinstance(error, commands.ChannelNotFound):
            embed = discord.Embed(title='Error', description='That channel does not exist.')
            await ctx.reply(embed=embed)

        elif (isinstance(error, commands.errors.NotOwner)) or \
        (isinstance(error, commands.MissingPermissions)):
            return

        else:
            raise error


def setup(bot):
    bot.add_cog(Events(bot))
