from discord.ext import commands, tasks

import asyncio
import discord
import json
import time


class EventsCog(commands.Cog, name='Events'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.utils = self.bot.get_cog('Utilities')
        self.blob_saver.start()

    @tasks.loop()
    async def blob_saver(self) -> None:
        await self.bot.wait_until_ready()

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

        if self.utils.saving_blobs:
            print(f"[AUTO] SHSH blob saver already running, continuing.")
            await asyncio.sleep(300)
            return

        self.utils.saving_blobs = True
        await self.bot.change_presence(activity=discord.Game(name='Currently saving SHSH blobs!'))

        description = None
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

                    else:
                        print('[AUTO] Saving SHSH Blobs.')

                    async with self.bot.db.execute('SELECT * from autotss WHERE enabled = ?', (True,)) as cursor:
                        data = await cursor.fetchall()

                    start_time = await asyncio.to_thread(time.time)
                    data = await asyncio.gather(*[self.utils.sem_call(self.utils.save_user_blobs, user_data[0], json.loads(user_data[1])) for user_data in data])
                    finish_time = round(await asyncio.to_thread(time.time) - start_time)

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

                    break

            else:
                self._api[device] = api[device]

            if description is not None:
                print(f"[AUTO] {description}")
                break

        self.utils.saving_blobs = False
        await self.utils.update_device_count()
        await asyncio.sleep(300)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.bot.wait_until_ready()

        embed = await self.utils.info_embed(self.bot.user)
        for channel in guild.text_channels:
            try:
                await channel.send(embed=embed)
                break
            except:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self.bot.wait_until_ready()

        async with self.bot.db.execute('SELECT * from autotss WHERE user = ?', (member.id,)) as cursor:
            if await cursor.fetchone() is None:
                return

        if len(member.mutual_guilds) == 0:
            await self.bot.db.execute('UPDATE autotss SET enabled = ? WHERE user = ?', (True, member.id))
            await self.bot.db.commit()

        await self.utils.update_device_count()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self.bot.wait_until_ready()

        async with self.bot.db.execute('SELECT * from autotss WHERE user = ?', (member.id,)) as cursor:
            if await cursor.fetchone() is None:
                return

        if len(member.mutual_guilds) == 0:
            await self.bot.db.execute('UPDATE autotss SET enabled = ? WHERE user = ?', (False, member.id))
            await self.bot.db.commit()

        await self.utils.update_device_count()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.utils.update_device_count()
        print('AutoTSS is now online.')

    @commands.Cog.listener()
    async def on_command_error(self, ctx: discord.ApplicationContext, error) -> None:
        await self.bot.wait_until_ready()
        if (isinstance(error, commands.errors.NotOwner)) or \
        (isinstance(error, commands.MissingPermissions)):
            pass

        else:
            raise error


def setup(bot):
    bot.add_cog(EventsCog(bot))
