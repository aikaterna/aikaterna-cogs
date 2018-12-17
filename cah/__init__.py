from .cah import CardsAgainstHumanity


def setup(bot):
    bot.add_cog(CardsAgainstHumanity(bot))
