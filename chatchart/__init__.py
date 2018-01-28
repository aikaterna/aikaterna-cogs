from discord.ext import commands
from .chatchart import Chatchart


def setup(bot: commands.Bot):
    n = Chatchart(bot)
    bot.add_cog(n)
