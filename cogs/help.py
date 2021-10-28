from discord.ext import commands
from views.buttons import PaginatorView

import discord


class AutoTSSHelp(commands.HelpCommand): #TODO: Rename to Help once Help cog is gone
    async def send_bot_help(self, modules: dict):
        prefix = await self.context.bot.get_cog('Utils').get_prefix(self.context.guild.id)
        embeds = list()
        for cog, commands in modules.items():
            if cog is None:
                continue

            commands = await self.filter_commands(commands, sort=True)
            if len([self.get_command_signature(cmd) for cmd in commands]) == 0:
                continue

            embed_dict = {
                'title': f'{cog.qualified_name} Commands',
                'fields': list(),
                'footer': {
                    'text': self.context.author.display_name,
                    'icon_url': str(self.context.author.display_avatar.with_static_format('png').url)
                }
            }

            for cmd in commands:
                embed_dict['fields'].append({
                    'name': self.get_command_signature(cmd).replace(self.context.clean_prefix, prefix), # In case bot mention is used as prefix
                    'value': cmd.help or 'No help.'
                })

            embeds.append(discord.Embed.from_dict(embed_dict))

        if len(embeds) == 1:
            await self.context.reply(embed=embeds[0])
            return

        embeds = sorted(embeds, key=lambda embed: embed.title)
        view = PaginatorView(embeds, timeout=180)
        view.message = await self.context.reply(embed=embeds[0], view=view)

    async def send_cog_help(self, cog: commands.Cog):
        commands = await self.filter_commands(cog.get_commands(), sort=True)
        if len(commands) == 0:
            return

        embeds = list()
        prefix = await self.context.bot.get_cog('Utils').get_prefix(self.context.guild.id)
        for command in commands:
            if len([self.get_command_signature(cmd) for cmd in commands]) == 0:
                continue

            embed_dict = {
                'title': self.get_command_signature(command).replace(self.context.clean_prefix, prefix), # In case bot mention is used as prefix
                'description': command.help or 'No help.',
                'footer': {
                    'text': self.context.author.display_name,
                    'icon_url': str(self.context.author.display_avatar.with_static_format('png').url)
                }
            }

            embeds.append(discord.Embed.from_dict(embed_dict))

        if len(embeds) == 1:
            await self.context.reply(embed=embeds[0])
            return

        view = PaginatorView(embeds, timeout=180)
        view.message = await self.context.reply(embed=embeds[0], view=view)

    async def send_group_help(self, group: commands.Group):
        commands = await self.filter_commands(group.commands, sort=True)
        if len(commands) == 0:
            return

        embed = {
            'title': f"{group.name.capitalize() if group.name != 'tss' else group.name.upper()} Commands", #TODO: Make this less shit
            'description': group.help or str(),
            'fields': list(),
            'footer': {
                'text': self.context.author.display_name,
                'icon_url': str(self.context.author.display_avatar.with_static_format('png').url)
            }
        }

        if group.aliases:
            aliases = f"**Aliases**: `{'`, `'.join(group.aliases)}`."

            if embed['description'] == str():
                embed['description'] = aliases
            else:
                embed['description'] += aliases

        prefix = await self.context.bot.get_cog('Utils').get_prefix(self.context.guild.id)
        for cmd in commands:
            if not self.get_command_signature(cmd):
                continue

            cmd_info = {
                'name': self.get_command_signature(cmd).replace('_', ' ').replace(self.context.clean_prefix, prefix), # In case bot mention is used as prefix
                'value': cmd.help or 'No help.'
            }

            if cmd.aliases:
                cmd_info['value'] += f"\n**Aliases**: `{'`, `'.join(cmd.aliases)}`."

            embed['fields'].append(cmd_info)

        await self.context.reply(embed=discord.Embed.from_dict(embed))

    async def send_command_help(self, cmd: commands.Command):
        if (not await cmd.can_run(self.context)) or (not self.get_command_signature(cmd)):
            return

        prefix = await self.context.bot.get_cog('Utils').get_prefix(self.context.guild.id)
        embed = {
            'title': self.get_command_signature(cmd).replace('_', ' ').replace(self.context.clean_prefix, prefix),
            'description': cmd.help or 'No help.',
            'footer': {
                'text': self.context.author.display_name,
                'icon_url': str(self.context.author.display_avatar.with_static_format('png').url)
            }
        }

        if cmd.aliases:
            embed['description'] += f"\n**Aliases**: `{'`, `'.join(cmd.aliases)}`."

        await self.context.reply(embed=discord.Embed.from_dict(embed))

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = self.bot.get_cog('Utils')

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def help_command(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='Commands')
        embed.add_field(name='AutoTSS Info & Help', value=f'`{prefix}info`', inline=False)
        if await ctx.bot.is_owner(ctx.author):
            embed.add_field(name='Admin Commands', value=f'`{prefix}help admin`', inline=False)
        embed.add_field(name='Device Commands', value=f'`{prefix}help device`', inline=False)
        embed.add_field(name='TSS Commands', value=f'`{prefix}help tss`', inline=False)
        embed.add_field(name='Miscellaneous Commands', value=f'`{prefix}help misc`', inline=False)
        if ctx.author.guild_permissions.administrator:
            embed.add_field(name='Whitelist Commands', value=f'`{prefix}help whitelist`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)

    @help_command.command(name='devices', aliases=('device',))
    @commands.guild_only()
    async def device_commands(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='Device Commands')
        embed.add_field(name='Add a device', value=f'`{prefix}devices add`', inline=False)
        embed.add_field(name='Remove a device', value=f'`{prefix}devices remove`', inline=False)
        embed.add_field(name='List your devices', value=f'`{prefix}devices list`', inline=False)
        if await ctx.bot.is_owner(ctx.author):
            embed.add_field(name='Transfer devices to new user', value=f'`{prefix}devices transfer <old user> <new user>`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)

    @help_command.command(name='tss')
    @commands.guild_only()
    async def tss_commands(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='TSS Commands')
        embed.add_field(name='Save SHSH blobs for all of your devices', value=f'`{prefix}tss save`', inline=False)
        embed.add_field(name='List all SHSH blobs saved for your devices', value=f'`{prefix}tss list`', inline=False)
        embed.add_field(name='Download all SHSH blobs saved for your devices', value=f'`{prefix}tss download`', inline=False)
        if await ctx.bot.is_owner(ctx.author):
            embed.add_field(name='Download all SHSH blobs saved for all devices', value=f'`{prefix}tss downloadall`', inline=False)
            embed.add_field(name='Save SHSH blobs for all devices', value=f'`{prefix}tss saveall`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)

    @help_command.command(name='misc')
    @commands.guild_only()
    async def misc_commands(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='Miscellaneous Commands')
        embed.add_field(name='AutoTSS Info & Help', value=f'`{prefix}info`', inline=False)
        embed.add_field(name='AutoTSS invite', value=f'`{prefix}invite`', inline=False)
        embed.add_field(name='AutoTSS ping', value=f'`{prefix}ping`', inline=False)
        if ctx.author.guild_permissions.administrator:
            embed.add_field(name="Change AutoTSS's prefix", value=f'`{prefix}prefix <prefix>`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)

    @help_command.command(name='whitelist')
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelist_commands(self, ctx: commands.Context) -> None:
        if await self.utils.whitelist_check(ctx) != True:
            return

        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='Whitelist Commands')
        embed.add_field(name='Set whitelist channel', value=f'`{prefix}whitelist set <channel>`', inline=False)
        embed.add_field(name='Toggle channel whitelist', value=f'`{prefix}whitelist toggle`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)

    @help_command.command(name='admin')
    @commands.guild_only()
    @commands.is_owner()
    async def admin_commands(self, ctx: commands.Context) -> None:
        prefix = await self.utils.get_prefix(ctx.guild.id)

        embed = discord.Embed(title='Admin Commands')
        embed.add_field(name='See module subcommands', value=f'`{prefix}module`', inline=False)

        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.with_static_format('png').url)
        await ctx.reply(embed=embed)


def setup(bot):
    bot.help_command = AutoTSSHelp()
    #bot.add_cog(Help(bot))
