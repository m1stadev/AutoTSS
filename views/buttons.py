import discord


class ConfirmButton(discord.ui.Button['ConfirmView']):
    def __init__(self, *, confirm: bool=False, cancel: bool=False):
        self.type = 'confirm' if confirm == True else 'cancel'

        if self.type == 'confirm':
            super().__init__(style=discord.ButtonStyle.danger, label='Confirm')
        elif self.type == 'cancel':
            super().__init__(style=discord.ButtonStyle.secondary, label='Cancel')


    async def callback(self, interaction: discord.Interaction):
        self.view.answer = self.type
        await self.view.on_timeout()
        self.view.stop()


class ConfirmView(discord.ui.View):
    def __init__(self, timeout: int=60):
        super().__init__(timeout=timeout)

        self.add_item(ConfirmButton(confirm=True))
        self.add_item(ConfirmButton(cancel=True))

    async def on_timeout(self):
        self.clear_items()
        await self.message.edit(view=self)


class PaginatorView(discord.ui.View):
    def __init__(self, embeds: list[dict], timeout: int=60):
        super().__init__(timeout=timeout)

        self.embeds = embeds
        self.embed_num = 0

    async def update_interaction(self, interaction: discord.Interaction):
        self.children[0].disabled = False if self.embed_num > 1 else True
        self.children[1].disabled = False if self.embed_num > 0 else True
        self.children[2].disabled = False if self.embed_num < (len(self.embeds) - 1) else True
        self.children[3].disabled = False if self.embed_num < (len(self.embeds) - 2) else True

        await interaction.response.edit_message(embed=discord.Embed.from_dict(self.embeds[self.embed_num]), view=self)

    @discord.ui.button(emoji='⏪', style=discord.ButtonStyle.grey, disabled=True)
    async def page_beginning(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.embed_num = 0
        await self.update_interaction(interaction)

    @discord.ui.button(emoji='⬅️', style=discord.ButtonStyle.grey, disabled=True)
    async def page_backward(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.embed_num -= 1
        await self.update_interaction(interaction)

    @discord.ui.button(emoji='➡️', style=discord.ButtonStyle.grey)
    async def page_forward(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.embed_num += 1
        await self.update_interaction(interaction)

    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.grey)
    async def page_end(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.embed_num = len(self.embeds) - 1
        await self.update_interaction(interaction)

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user == self.message.reference.cached_message.author

    async def on_timeout(self):
        self.clear_items()
        await self.message.edit(view=self)