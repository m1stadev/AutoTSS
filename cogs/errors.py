from discord.ext import commands

import asyncio
import discord


class NoDevicesFound(Exception):
    def __init__(self, user: discord.User = None, *args):
        super().__init__(
            f"{'You have' if user is None else f'{user.mention} has'} no devices to AutoTSS.",
            *args,
        )


class TooManyDevices(Exception):
    def __init__(self, max_devices: int, *args):
        super().__init__(
            f'You cannot add over {max_devices} devices to AutoTSS.', *args
        )


class ViewTimeoutException(asyncio.exceptions.TimeoutError):
    def __init__(self, timeout: int, *args):
        self.timeout = timeout
        super().__init__(
            f"No response given in {timeout} second{'s' if timeout != 1 else ''}, cancelling.",
            *args,
        )


class ErrorsCog(commands.Cog, name='Errors'):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_application_command_error(
        self, ctx: discord.ApplicationContext, exc: commands.CommandError
    ) -> None:
        await self.bot.wait_until_ready()

        if isinstance(exc, discord.ApplicationCommandInvokeError):
            exc = exc.__cause__

        embed = discord.Embed(title='FDRBot Error', color=discord.Color.red())
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
            embed.description = 'You have no devices added to AutoTSS.'

        elif isinstance(
            exc, (commands.BadArgument, ViewTimeoutException, TooManyDevices)
        ):
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
    bot.add_cog(ErrorsCog(bot))
