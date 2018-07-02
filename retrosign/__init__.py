from discord.ext import commands
from .retrosign import Retrosign


def setup(bot: commands.Bot):
    n = Retrosign(bot)
    bot.add_cog(n)
