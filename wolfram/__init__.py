from discord.ext import commands
from .wolfram import Wolfram


def setup(bot: commands.Bot):
    n = Wolfram(bot)
    bot.add_cog(n)
