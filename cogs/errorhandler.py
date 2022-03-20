from datetime import datetime
from discord.ext import commands
from utils.errors import *
from utils.logger import WebhookLogger
from typing import Optional

import asyncio
import discord


class ErrorHandlerCog(commands.Cog, name='ErrorHandler'):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.webhook: Optional[discord.Webhook] = next(
            iter(
                h.webhook
                for h in self.bot.logger.handlers
                if isinstance(h, WebhookLogger)
            ),
            None,
        )

    @commands.Cog.listener()
    async def on_application_command_error(
        self, ctx: discord.ApplicationContext, exc: commands.CommandError
    ) -> None:
        await self.bot.wait_until_ready()

        if isinstance(exc, discord.ApplicationCommandInvokeError):
            exc = exc.__cause__

        embed = discord.Embed(title='Error', color=discord.Color.red())
        embed.timestamp = await asyncio.to_thread(datetime.now)
        embed.set_footer(
            text=self.bot.user.name,
            icon_url=self.bot.user.avatar.with_static_format('png').url,
        )

        if isinstance(exc, StopCommand):
            embed.title = 'Cancelled'
            embed.color = discord.Color.gold()

            if ctx.interaction.response.is_done():
                await ctx.edit(embed=embed)
            else:
                await ctx.respond(embed=embed, ephemeral=True)

            return

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

        elif isinstance(exc, APIError):
            embed.description = (
                f'{exc} Please try again later.\nError code: `{exc.status}`.'
            )

            if self.webhook is not None:
                try:
                    await self.webhook.send(embed=embed)
                except:
                    pass

        elif isinstance(exc, (commands.BadArgument, DeviceError)):
            embed.description = str(exc)

        else:
            owner = await self.bot.fetch_user(self.bot.owner_id)
            embed.description = (
                f'An unknown error occurred, please report this to {owner.mention}!'
            )
            embed.add_field(
                name='Error Info',
                value=f'Command: `/{ctx.command.qualified_name}`\nError message: `{str(exc) or None}`',
            )

            if self.webhook is not None:
                try:
                    await self.webhook.send(embed=embed)
                except:
                    pass

        if ctx.interaction.response.is_done():
            await ctx.edit(embed=embed)
        else:
            await ctx.respond(embed=embed, ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(ErrorHandlerCog(bot))
