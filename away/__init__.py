from discord.ext import commands
from .away import Away


def setup(bot: commands.Bot):
    n = Away(bot)
    bot.add_cog(n)
