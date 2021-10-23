import discord


class Paginator(discord.ui.View):
    def __init__(self, embeds: list[dict], timeout: int=60):
        super().__init__()

        self.embeds = embeds
        self.timeout = timeout

        self.embed_num = 0

    async def update_interaction(self, interaction: discord.Interaction):
        self.children[0].disabled = False if self.embed_num > 1 else True
        self.children[1].disabled = False if self.embed_num > 0 else True
        self.children[2].disabled = False if self.embed_num < (len(self.embeds) - 1) else True
        self.children[3].disabled = False if self.embed_num < (len(self.embeds) - 2) else True

        await interaction.response.edit_message(embed=discord.Embed.from_dict(self.embeds[self.embed_num]), view=self)

    @discord.ui.button(label='⏪', style=discord.ButtonStyle.grey, disabled=True)
    async def page_beginning(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.embed_num = 0
        self.update_interaction(interaction)

    @discord.ui.button(label='⬅️', style=discord.ButtonStyle.grey, disabled=True)
    async def page_backward(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.embed_num -= 1
        self.update_interaction(interaction)

    @discord.ui.button(label='➡️', style=discord.ButtonStyle.grey)
    async def page_forward(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.embed_num += 1
        self.update_interaction(interaction)

    @discord.ui.button(label='⏩', style=discord.ButtonStyle.grey)
    async def page_end(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.embed_num = len(self.embeds) - 1
        self.update_interaction(interaction)

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user == self.message.reference.cached_message.author

    async def on_timeout(self):
        self.clear_items()
        await self.message.edit(view=self)
