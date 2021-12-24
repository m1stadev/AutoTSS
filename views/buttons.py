import discord


class ViewStoppedError(Exception):
    pass


class SelectButton(discord.ui.Button['SelectView']):
    def __init__(self, button: dict):
        super().__init__(**button)

        self.button_type = button['label']

    async def callback(self, interaction: discord.Interaction):
        self.view.answer = self.button_type
        await self.view.on_timeout()
        self.view.stop()


class SelectView(discord.ui.View):
    def __init__(self, buttons: list[dict], context: discord.ApplicationContext, *, public: bool=False, timeout: int=60):
        super().__init__(timeout=timeout)

        self.ctx = context
        self.public = public
        self.answer = None

        for button in buttons:
            self.add_item(SelectButton(button))

    async def interaction_check(self, interaction: discord.Interaction):
        if self.public == True or interaction.channel.type == discord.ChannelType.private:
            return True

        return interaction.user == self.ctx.author

    async def on_timeout(self):
        self.clear_items()
        await self.ctx.edit(view=self)


class PaginatorButton(discord.ui.Button['PaginatorView']):
    def __init__(self, emoji: str, disabled: bool):
        super().__init__(
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        if self == self.view.children[0]:
            self.view.embed_num = 0
        elif self == self.view.children[1]:
            self.view.embed_num -= 1
        elif self == self.view.children[2]:
            self.view.embed_num += 1
        elif self == self.view.children[3]:
            self.view.embed_num = len(self.view.embeds) - 1

        await self.view.update_view()

class PaginatorView(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed], context: discord.ApplicationContext, *, public: bool=False, timeout: int=60):
        super().__init__(timeout=timeout)

        self.ctx = context
        self.public = public
        self.embeds = embeds
        self.embed_num = 0

        for emoji in ('⏪', '⬅️', '➡️', '⏩'):
            disabled = False if (emoji == '➡️') or (emoji == '⏩' and len(self.embeds) >= 3) else True
            self.add_item(PaginatorButton(emoji, disabled))

    async def update_view(self):
        self.children[0].disabled = False if self.embed_num > 1 else True
        self.children[1].disabled = False if self.embed_num > 0 else True
        self.children[2].disabled = False if self.embed_num < (len(self.embeds) - 1) else True
        self.children[3].disabled = False if self.embed_num < (len(self.embeds) - 2) else True

        await self.ctx.edit(embed=self.embeds[self.embed_num], view=self)

    async def interaction_check(self, interaction: discord.Interaction):
        if self.public == True or interaction.channel.type == discord.ChannelType.private:
            return True

        return interaction.user == self.ctx.author

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        await self.ctx.edit(view=self)


class CancelView(discord.ui.View):
    def __init__(self, context: discord.ApplicationContext):
        super().__init__()

        self.ctx = context

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.on_timeout()
        self.stop()
        raise ViewStoppedError('Cancel button was pressed.')

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        raise error

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.channel.type == discord.ChannelType.private:
            return True

        return interaction.user == self.ctx.author

    async def on_timeout(self):
        self.clear_items()
        await self.ctx.edit(view=self)
