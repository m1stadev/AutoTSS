from discord.commands import slash_command
from discord.ext import commands
from discord import Option
from views.buttons import PaginatorView

import discord


async def cmd_autocomplete(ctx: discord.AutocompleteContext):
    res = list()
    for cog in ctx.bot.cogs:
        for cmd in ctx.bot.cogs[cog].get_commands():
            if isinstance(cmd, discord.SlashCommandGroup):
                if cmd.name == 'admin' and not await ctx.bot.is_owner(ctx.interaction.user):
                    continue

                if len([_ for _ in cmd.subcommands if _.name == 'help']) == 0:
                    continue

                if ctx.value.lower() in cmd.name + ' help':
                    res.append('/' + cmd.name + ' help')

            elif isinstance(cmd, discord.SlashCommand):     
                if ctx.value.lower() in cmd.name:
                    res.append('/' + cmd.name)

    res.sort()
    return res

class HelpCog(commands.Cog, name='Help'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.utils = self.bot.get_cog('Utilities')

    @slash_command(name='help', description='See usage and descriptions for commands.')
    async def _help(self, ctx: discord.ApplicationContext, command: Option(str, autocomplete=cmd_autocomplete, required=False)) -> None:
        if command is None:
            cmd_embeds = dict()
            for cog in ctx.bot.cogs:
                for cmd in ctx.bot.cogs[cog].get_commands():
                    if isinstance(cmd, discord.SlashCommandGroup):
                        if cmd.name == 'admin' and not await ctx.bot.is_owner(ctx.author):
                            continue

                        cmd_embeds[cog] = await self.utils.group_help_embed(ctx, cmd)

                    elif isinstance(cmd, discord.SlashCommand):
                        if cog in cmd_embeds.keys():
                            continue

                        cmd_embeds[cog] = await self.utils.cog_help_embed(ctx, cog)

            cmd_embeds = sorted(cmd_embeds.values(), key=lambda _: _.title)
            paginator = PaginatorView(cmd_embeds, ctx, timeout=180)
            await ctx.respond(embed=cmd_embeds[paginator.embed_num], view=paginator)

        else:
            command = command.replace('/', '').lower()

            if ('admin' in command) and (not await self.bot.is_owner(ctx.author)):
                cmd = None

            elif len(command.split()) == 1: # Slash command/group
                cmd = self.bot.get_application_command(
                    name=command,
                    type=discord.ApplicationCommand
                )

            elif len(command.split()) > 1: # Slash group with sub-command
                group = self.bot.get_application_command(command.split()[0], type=discord.SlashCommandGroup)
                try:
                    cmd = next(_ for _ in group.subcommands if _.name == command.split()[1])
                except StopIteration:
                    cmd = None

            if cmd is None:
                embed = discord.Embed(title='Error', description='Command not found.')
                await ctx.respond(embed=embed)
            elif isinstance(cmd, discord.SlashCommand):
                embed = await self.utils.cmd_help_embed(ctx, cmd)
                await ctx.respond(embed=embed, ephemeral='admin' in cmd.name)
            elif isinstance(cmd, discord.SlashCommandGroup):
                cmd_embeds = [await self.utils.cmd_help_embed(ctx, _) for _ in cmd.subcommands]

                paginator = PaginatorView(cmd_embeds, ctx, timeout=180)
                await ctx.respond(embed=cmd_embeds[paginator.embed_num], view=paginator, ephemeral='admin' in cmd.name)


def setup(bot):
    bot.add_cog(HelpCog(bot))
