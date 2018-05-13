from discord.ext import commands
from .seen import Seen


def setup(bot: commands.Bot):
    n = Seen(bot)
    bot.add_cog(n)
