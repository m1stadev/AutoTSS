from utils.errors import *
from discord.ext import commands

import discord


class ErrorHandlerCog(commands.Cog, name='ErrorHandler'):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_application_command_error(
        self, ctx: discord.ApplicationContext, exc: commands.CommandError
    ) -> None:
        await self.bot.wait_until_ready()

        if isinstance(exc, discord.ApplicationCommandInvokeError):
            exc = exc.__cause__

        if isinstance(exc, StopCommand):
            embed = discord.Embed(title='Cancelled', color=discord.Color.gold())
            embed.set_footer(
                text=self.bot.user.name,
                icon_url=self.bot.user.avatar.with_static_format('png').url,
            )

        else:
            embed = discord.Embed(title='Error', color=discord.Color.red())
            embed.set_footer(
                text=self.bot.user.name,
                icon_url=self.bot.user.avatar.with_static_format('png').url,
            )

        if isinstance(exc, commands.NoPrivateMessage):
            embed.description = 'This command can only be used in a server.'

        elif isinstance(
            exc,
            (commands.MissingPermissions, commands.BotMissingPermissions),
        ):
            missing_perms = [
                perm.replace('_', ' ').replace('guild', 'server').title()
                for perm in exc.missing_permissions
            ]

            if len(missing_perms) > 2:
                fmt = '{}, and {}'.format(
                    ', '.join(missing_perms[:-1]), missing_perms[-1]
                )
            else:
                fmt = ' and '.join(missing_perms)

            if isinstance(exc, commands.MissingPermissions):
                embed.description = f'You are missing the following permissions required to run this command: {fmt}.'
            elif isinstance(exc, commands.BotMissingPermissions):
                embed.description = f'I am missing the following permissions required to run this command: {fmt}.'

        elif isinstance(exc, commands.UserNotFound):
            embed.description = 'I could not find that user.'

        elif isinstance(exc, NoDevicesFound):
            embed.description = f"{'You have' if exc.user.id == ctx.author.id else f'{exc.user.mention} has'} no devices added."

        elif isinstance(exc, NoSHSHFound):
            embed.description = f"{'You have' if exc.user.id == ctx.author.id else f'{exc.user.mention} has'} no SHSH blobs saved."

        elif isinstance(exc, commands.NotOwner):
            embed.description = 'You do not have permission to run this command.'

        elif isinstance(exc, SavingSHSHError):
            embed.description = "I'm automatically saving SHSH blobs right now, please wait until I'm finished to manually save SHSH blobs."

        elif isinstance(exc, NotWhitelisted):
            embed.description = f'AutoTSS can only be used in {exc.channel.mention}.'

        elif isinstance(exc, ViewTimeoutException):
            embed.description = f"No response given in {exc.timeout} second{'s' if exc.timeout != 1 else ''}, cancelling."

        elif isinstance(exc, TooManyDevices):
            embed.description = (
                f'You cannot add over {exc.max_devices} devices to AutoTSS.'
            )

        elif isinstance(exc, commands.BadArgument):
            embed.description = str(exc)

        else:
            owner = await self.bot.fetch_user(self.bot.owner_id)
            embed.description = (
                f'An unknown error occurred, please report this to {owner.mention}!'
            )
            embed.add_field(
                name='Error Info',
                value=f'Command: `/{ctx.command.qualified_name}`\nError message: `{str(exc)}`',
            )

        if ctx.interaction.response.is_done():
            await ctx.edit(embed=embed)
        else:
            await ctx.respond(embed=embed, ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(ErrorHandlerCog(bot))
