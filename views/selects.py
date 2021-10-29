from typing import Optional

import discord


class DropdownSelect(discord.ui.Select['DropdownView']):
    def __init__(self, options: list[discord.SelectOption], placeholder: str):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.answer = self.values[0]
        await self.view.on_timeout()
        self.view.stop()

class DropdownView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption], placeholder: str='\u200b', *, public: bool=False, timeout: int=60):
        super().__init__(timeout=timeout)

        self.public = public
        self.options = options
        self.add_item(DropdownSelect(options, placeholder))
        self.answer = None

    async def interaction_check(self, interaction: discord.Interaction):
        if self.public == True or interaction.channel.type == discord.ChannelType.private:
            return True

        return interaction.user == self.message.reference.cached_message.author

    async def on_timeout(self):
        self.clear_items()
        await self.message.edit(view=self)
