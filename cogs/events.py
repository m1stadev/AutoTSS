from aioify import aioify
from discord.ext import commands, tasks

import aiosqlite
import asyncio
import discord
import json
import os
import shutil


class EventsCog(commands.Cog, name='Events'):
    def __init__(self, bot):
        self.bot = bot
        self.os = aioify(os, name='os')
        self.shutil = aioify(shutil, name='shutil')
        self.utils = self.bot.get_cog('Utilities')
        self.auto_clean_db.start()
        self.signing_party_detection.start()

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
        async with self.bot.session.get('https://api.ipsw.me/v4/devices') as resp:
            devices = [d for d in await resp.json() if any(x in d['identifier'] for x in ('iPhone', 'AppleTV', 'iPod', 'iPad'))]

        api = dict()
        for device in [d['identifier'] for d in devices]:
            api[device] = await self.utils.get_firms(device)

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
            embed.set_footer(text=message.author.name, icon_url=message.author.display_avatar.with_static_format('png').url)
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
    bot.add_cog(EventsCog(bot))
