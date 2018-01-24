#  forwarding.py is ported from another bot:
#  https://github.com/jacobcheatley/dankbot

import discord
from discord.ext import commands
from .utils.dataIO import dataIO
from .utils import checks


class Forwarding:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.owner = self.get_owner()

    def get_owner(self):
        owner_id = dataIO.load_json("data/red/settings.json")["OWNER"]
        return discord.utils.find(lambda m: m.id == owner_id, self.bot.get_all_members())

    async def send_to_owner(self, **kwargs):
        if self.owner is None:
            self.owner = self.get_owner()
        await self.bot.send_message(self.owner, **kwargs)

    async def on_message(self, message: discord.Message):
        if self.owner is None:
            self.owner = self.get_owner()
        if not message.channel.is_private or message.channel.user.id == self.owner.id:
            return

        embed = discord.Embed()
        if message.author == self.bot.user:
            embed.title = 'Sent PM to {}#{} ({}).'.format(message.channel.user.name, message.channel.user.discriminator, message.channel.user.id)
        else:
            embed.set_author(name=message.author, icon_url=message.author.avatar_url or message.author.default_avatar_url)
            embed.title = '{} messaged me:'.format(message.channel.user.id)
        embed.description = message.content
        embed.timestamp = message.timestamp

        await self.send_to_owner(embed=embed)

    @commands.command()
    @checks.is_owner()
    async def pm(self, user: discord.User, *, content: str):
        """PMs a person."""
        await self.bot.send_message(user, content)


def setup(bot):
    bot.add_cog(Forwarding(bot))
