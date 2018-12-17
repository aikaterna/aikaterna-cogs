from redbot.core import commands, data_manager
from .cah import CardsAgainstHumanity


def setup(bot: commands.Bot):
    n = CardsAgainstHumanity(bot)
    data_manager.load_bundled_data(n, __file__)
    bot.add_cog(n)
