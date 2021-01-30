from discord.ext import commands
import discord
import os
import shutil
import sqlite3


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        cursor.execute('SELECT prefix from prefix WHERE guild = ?', (guild.id,))

        if cursor.fetchone() is not None:
            cursor.execute('DELETE from prefix where guild = ?', (guild.id,))
        db.commit()

        cursor.execute('INSERT INTO prefix(guild, prefix) VALUES(?,?)', (guild.id, 'b!'))
        db.commit()

        if guild.system_channel:
            channel = guild.system_channel
        else:
            channel = self.bot.get_channel(guild.text_channels[0].id)

        user = await self.bot.fetch_user(728035061781495878)

        embed = discord.Embed(title="Hi, I'm AutoTSS!")
        embed.add_field(name='What do I do?', value='I can automatically save SHSH blobs for all of your iOS devices!', inline=False)
        embed.add_field(name='Prefix', value='My prefix is `b!`. To see what I can do, run `b!help`!', inline=False)
        embed.add_field(name='Creator', value=user.mention, inline=False)
        embed.add_field(name='Disclaimer', value='This should NOT be your only source for saving blobs. I am not at fault for any issues you may experience with AutoTSS.', inline=False)
        embed.add_field(name='Notes', value='- There is a limit of 10 devices per user.\n- You must be in a server with AutoTSS, or your devices & blobs will be deleted. This **does not** have to be the same server that you added your devices to AutoTSS in.\n- Blobs are automatically saved every 30 minutes.', inline=False)
        embed.add_field(name='Source Code', value="AutoTSS's source code can be found on [GitHub](https://github.com/marijuanARM/autotss).", inline=False)
        embed.add_field(name='Support', value='For any questions about AutoTSS, join [discord](https://discord.gg/fAngssA).', inline=False)
        embed.set_thumbnail(url=self.bot.user.avatar_url_as(static_format='png'))
        embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))

        await channel.send(embed=embed)

        await self.bot.change_presence(activity=discord.Game(name=f'Ping me for help! | In {len(self.bot.guilds)} servers'))

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        cursor.execute('DELETE from prefix where guild = ?', (guild.id,))
        db.commit()

        db.close()

        await self.bot.change_presence(activity=discord.Game(name=f'Ping me for help! | In {len(self.bot.guilds)} servers'))

    @commands.Cog.listener()
    async def on_member_remove(self, member):  # Don't bother saving blobs for a user if the user doesn't share any servers with the bot.
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        if self.bot.get_user(member.id) is not None:
            pass

        cursor.execute('SELECT * from autotss WHERE userid = ?', (member.id,))
        devices = cursor.fetchall()

        if len(devices) == 0:
            return

        os.makedirs('Data/Deleted Blobs', exist_ok=True)

        for x in range(len(devices)):
            if not os.path.isdir(f'Data/Blobs/{devices[x][4]}'):
                continue

            shutil.copytree(f'Data/Blobs/{devices[x][4]}', f'Data/Deleted Blobs/{devices[x][4]}', dirs_exist_ok=True)  # Just in case someone deletes their device accidentally...
            shutil.rmtree(f'Data/Blobs/{devices[x][4]}')

        cursor.execute('DELETE * from autotss WHERE userid = ?', (member.id,))

        db.commit()
        db.close()

    @commands.Cog.listener()
    async def on_message(self, message):
        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()

        if message.channel.type is discord.ChannelType.private:
            embed = discord.Embed(title='Error', description='I only work inside of servers. Invite me to a server and use me there!')
            embed.set_footer(text=message.author.nick, icon_url=message.author.avatar_url_as(static_format='png'))
            await message.channel.send(embed=embed)
            return

        cursor.execute('SELECT prefix from prefix WHERE guild = ?', (message.guild.id,))

        if cursor.fetchone() is None:
            cursor.execute('INSERT INTO prefix(guild, prefix) VALUES(?,?)', (message.guild.id, 'b!'))
            db.commit()

        cursor.execute('SELECT prefix FROM prefix WHERE guild = ?', (message.guild.id,))
        prefix = cursor.fetchone()[0]

        if message.content.replace(' ', '').replace('!', '') == self.bot.user.mention:
            embed = discord.Embed(title='AutoTSS', description=f'My prefix is `{prefix}`. To see what I can do, run `{prefix}help`!')
            embed.set_footer(text=message.author.nick, icon_url=message.author.avatar_url_as(static_format='png'))
            await message.channel.send(embed=embed)

        db.close()

    @commands.Cog.listener()
    async def on_ready(self):
        os.makedirs('Data', exist_ok=True)

        db = sqlite3.connect('Data/autotss.db')
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS autotss(
            device_num INTEGER,
            userid INTEGER,
            name TEXT,
            identifier TEXT,
            ecid TEXT,
            boardconfig TEXT,
            blobs TEXT,
            apnonce TEXT
            )
            ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prefix(
            guild INTEGER,
            prefix TEXT
            )
            ''')
        db.commit()
        db.close()

        await self.bot.change_presence(activity=discord.Game(name=f'Ping me for help! | In {len(self.bot.guilds)} servers'))
        print('AutoTSS is now online.')

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            embed = discord.Embed(title='Error', description=f"That command doesn't exist! Use `{ctx.prefix}help` to see all the commands I can run.")
            embed.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url_as(static_format='png'))
            await ctx.send(embed=embed)
        else:
            raise error


def setup(bot):
    bot.add_cog(Events(bot))
