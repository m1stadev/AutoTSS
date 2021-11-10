from discord.ext import commands, tasks

import aiosqlite
import asyncio
import discord
import json
import time


class EventsCog(commands.Cog, name='Events'):
    def __init__(self, bot):
        self.bot = bot
        self.utils = self.bot.get_cog('Utilities')
        self.auto_clean_db.start()
        self.blob_saver.start()

    @tasks.loop()
    async def auto_clean_db(self) -> None:
        await self.bot.wait_until_ready()

        async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT devices from autotss') as cursor:
            data = await cursor.fetchall()

        for user_devices in data:
            devices = json.loads(user_devices[0])
            if devices == list():
                async with aiosqlite.connect('Data/autotss.db') as db:
                    await db.execute('DELETE FROM autotss WHERE devices = ?', (user_devices[0],))
                    await db.commit()

        await asyncio.sleep(300)

    @tasks.loop()
    async def blob_saver(self) -> None:
        await self.bot.wait_until_ready()

        if self.utils.saving_blobs:
            print(f"[AUTO] SHSH blob saver already running, continuing.")
            await asyncio.sleep(300)
            return

        self.utils.saving_blobs = True
        await self.bot.change_presence(activity=discord.Game(name='Ping me for help! | Currently saving SHSH blobs!'))

        async with self.bot.session.get('https://api.ipsw.me/v4/devices') as resp:
            devices = [d for d in await resp.json() if any(x in d['identifier'] for x in ('iPhone', 'AppleTV', 'iPod', 'iPad'))]

        api = dict()
        for device in [d['identifier'] for d in devices]:
            api[device] = await self.utils.get_firms(device)

        try:
            self._api
        except AttributeError:
            self._api = api
            self.utils.saving_blobs = False
            await self.utils.update_device_count()
            return

        for device in api.keys():
            if device not in self._api.keys(): # If new device is added to the API
                print(f"[AUTO] New device has been detected: {device}.")
                self._api[device] = api[device]
                continue

            for firm in api[device]:
                if firm['signed'] == True:
                    if firm not in self._api[device]: # If firmware was just released
                        print(f"[AUTO] iOS {firm['version']} ({firm['buildid']}) has been released, saving SHSH blobs.")

                    elif any(oldfirm['signed'] == False for oldfirm in self._api[device] if oldfirm['buildid'] == firm['buildid']): # If firmware has been resigned
                        print(f"[AUTO] iOS {firm['version']} ({firm['buildid']}) has been resigned for {device}, saving SHSH blobs.")

                    async with aiosqlite.connect('Data/autotss.db') as db, db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
                        data = await cursor.fetchall()

                    start_time = await asyncio.to_thread(time.time)
                    data = await asyncio.gather(*[self.utils.sem_call(self.utils.save_user_blobs, user_data[0], json.loads(user_data[1])) for user_data in data])
                    finish_time = round(await asyncio.to_thread(time.time) - start_time)
                    self.utils.saving_blobs = False

                    blobs_saved = sum(user['blobs_saved'] for user in data)
                    devices_saved = sum(user['devices_saved'] for user in data)

                    if blobs_saved > 0:
                        description = ' '.join((
                            f"Saved {blobs_saved} SHSH blob{'s' if blobs_saved > 1 else ''}",
                            f"for {devices_saved} device{'s' if devices_saved > 1 else ''}",
                            f"in {finish_time} second{'s' if finish_time != 1 else ''}."
                        ))

                    else:
                        description = 'All SHSH blobs have already been saved.'

                    print(f"[AUTO] {description}")
                    await self.utils.update_device_count()
                    await asyncio.sleep(300)
                    return

            else:
                self._api[device] = api[device]

        self.utils.saving_blobs = False
        await self.utils.update_device_count()
        await asyncio.sleep(300)

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
        await self.utils.update_device_count()
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
