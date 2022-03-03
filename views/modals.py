import discord


class QuestionModal(discord.ui.Modal):
    def __init__(
        self,
        ctx: discord.ApplicationContext,
        title: str,
        embed: discord.Embed,
        *fields: discord.ui.InputText
    ) -> None:
        super().__init__(title=title)

        self.ctx = ctx
        self.embed = embed

        for i in fields:
            self.add_item(i)

    async def callback(self, interaction: discord.Interaction):
        self.answers = [x.value for x in self.children]

        self.ctx.interaction = await interaction.response.send_message(
            embed=self.embed, ephemeral=True
        )
        self.stop()
