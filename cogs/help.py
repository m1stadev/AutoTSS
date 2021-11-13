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

        embeds = list()
        prefix = await self.utils.get_prefix(self.context.guild.id)
        for cog, cmds in modules.items():
            if cog is None:
                continue

            cmds = await self.filter_commands(cmds, sort=True)
            if len(cmds) == 0:
                continue

            embed_dict = {
                'title': f'{cog.qualified_name} Commands',
                'fields': list(),
                'footer': {
                    'text': self.context.author.display_name,
                    'icon_url': str(self.context.author.display_avatar.with_static_format('png').url)
                }
            }

            for cmd in cmds:
                if isinstance(cmd, commands.Group):
                    group_cmds = await self.filter_commands(cmd.commands, sort=True)
                    for group_cmd in group_cmds:
                        cmd_sig = self.get_command_signature(group_cmd).replace('_', ' ').replace(self.context.clean_prefix, prefix)
                        embed_dict['fields'].append({
                            'name': cmd_sig, # In case bot mention is used as prefix
                            'value': group_cmd.help or 'No help.'
                        })

                        if group_cmd.aliases:
                            embed_dict['fields'][-1]['value'] += f"\n**Aliases**: `{'`, `'.join(group_cmd.aliases)}`."

                else:
                    cmd_sig = self.get_command_signature(cmd).replace('_', ' ').replace(self.context.clean_prefix, prefix)
                    embed_dict['fields'].append({
                        'name': cmd_sig, # In case bot mention is used as prefix
                        'value': cmd.help or 'No help.'
                    })

            embeds.append(discord.Embed.from_dict(embed_dict))

        if len(embeds) in range(2):
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

        embeds = list()
        prefix = await self.utils.get_prefix(self.context.guild.id)
        cmds = await self.filter_commands(cog.get_commands(), sort=True)
        for cmd in cmds:
            if isinstance(cmd, commands.Group):
                group_cmds = await self.filter_commands(cmd.commands, sort=True)
                for group_cmd in group_cmds:
                    cmd_sig = self.get_command_signature(group_cmd).replace('_', ' ').replace(self.context.clean_prefix, prefix)
                    embed_dict = {
                        'title': cmd_sig, # In case bot mention is used as prefix
                        'description': group_cmd.help or 'No help.',
                        'footer': {
                            'text': self.context.author.display_name,
                            'icon_url': str(self.context.author.display_avatar.with_static_format('png').url)
                        }
                    }

                    if group_cmd.aliases:
                        embed_dict['description'] += f"\n**Aliases**: `{'`, `'.join(group_cmd.aliases)}`."

                    embeds.append(discord.Embed.from_dict(embed_dict))

            else:
                cmd_sig = self.get_command_signature(cmds).replace('_', ' ').replace(self.context.clean_prefix, prefix)
                embed_dict = {
                    'title': cmd_sig, # In case bot mention is used as prefix
                    'description': cmd.help or 'No help.',
                    'footer': {
                        'text': self.context.author.display_name,
                        'icon_url': str(self.context.author.display_avatar.with_static_format('png').url)
                    }
                }

                if cmd.aliases:
                    embed_dict['description'] += f"\n**Aliases**: `{'`, `'.join(cmd.aliases)}`."

                embeds.append(discord.Embed.from_dict(embed_dict))

        if len(embeds) in range(2):
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

        embed_dict = {
            'title': f"{group.name.capitalize() if group.name != 'tss' else group.name.upper()} Commands", #TODO: Make this less shit
            'description': group.help or 'No help.',
            'fields': list(),
            'footer': {
                'text': self.context.author.display_name,
                'icon_url': str(self.context.author.display_avatar.with_static_format('png').url)
            }
        }

        if group.aliases:
            embed_dict['description'] += f"\n**Aliases**: `{'`, `'.join(group.aliases)}`."

        prefix = await self.utils.get_prefix(self.context.guild.id)
        cmds = await self.filter_commands(group.commands, sort=True)
        for cmd in cmds:
            cmd_sig = self.get_command_signature(cmd).replace('_', ' ').replace(self.context.clean_prefix, prefix)
            embed_dict['fields'].append({
                'name': cmd_sig, # In case bot mention is used as prefix
                'value': cmd.help or 'No help.'
            })

            if cmd.aliases:
                embed_dict['fields'][-1]['value'] += f"\n**Aliases**: `{'`, `'.join(cmd.aliases)}`."

        await self.context.reply(embed=discord.Embed.from_dict(embed_dict))

    async def send_command_help(self, cmd: commands.Command):
        if self.utils is None:
            self.utils = self.context.bot.get_cog('Utilities')

        if await self.utils.whitelist_check(self.context) != True:
            return

        if not await cmd.can_run(self.context):
            return

        prefix = await self.utils.get_prefix(self.context.guild.id)
        cmd_sig = self.get_command_signature(cmd).replace('_', ' ').replace(self.context.clean_prefix, prefix)
        embed_dict = {
            'title': cmd_sig,
            'description': cmd.help or 'No help.',
            'footer': {
                'text': self.context.author.display_name,
                'icon_url': str(self.context.author.display_avatar.with_static_format('png').url)
            }
        }

        if cmd.aliases:
            embed_dict['description'] += f"\n**Aliases**: `{'`, `'.join(cmd.aliases)}`."

        await self.context.reply(embed=discord.Embed.from_dict(embed_dict))


class HelpCog(commands.Cog, name='Help'):
    def __init__(self, bot):
        help_cmd = AutoTSSHelp()
        help_cmd.cog = self
        bot.help_command = help_cmd


def setup(bot):
    bot.add_cog(HelpCog(bot))
