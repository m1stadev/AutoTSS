from discord.ext import commands
from views.buttons import PaginatorView

import discord


class AutoTSSHelp(commands.HelpCommand): #TODO: Rename to Help once Help cog is gone
    def __init__(self):
        super().__init__(command_attrs={
            'aliases': ('h',),
            'help': 'Show info on all commands.'
        })

        self.utils = None #TODO: Make this less shit if possible

    async def send_bot_help(self, modules: dict):
        if self.utils is None:
            self.utils = self.context.bot.get_cog('Utilities')

        if await self.utils.whitelist_check(self.context) != True:
            return

        prefix = await self.utils.get_prefix(self.context.guild.id)
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
        if self.utils is None:
            self.utils = self.context.bot.get_cog('Utilities')

        if await self.utils.whitelist_check(self.context) != True:
            return

        commands = await self.filter_commands(cog.get_commands(), sort=True)
        if len(commands) == 0:
            return

        embeds = list()
        prefix = await self.utils.get_prefix(self.context.guild.id)
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
        if self.utils is None:
            self.utils = self.context.bot.get_cog('Utilities')

        if await self.utils.whitelist_check(self.context) != True:
            return

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
                embed['description'] += f'\n{aliases}'

        prefix = await self.utils.get_prefix(self.context.guild.id)
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
        if self.utils is None:
            self.utils = self.context.bot.get_cog('Utilities')

        if await self.utils.whitelist_check(self.context) != True:
            return

        if (not await cmd.can_run(self.context)) or (not self.get_command_signature(cmd)):
            return

        prefix = await self.utils.get_prefix(self.context.guild.id)
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


class HelpCog(commands.Cog, name='Help'):
    def __init__(self, bot):
        help_cmd = AutoTSSHelp()
        help_cmd.cog = self
        bot.help_command = help_cmd


def setup(bot):
    bot.add_cog(HelpCog(bot))
