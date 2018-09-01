from .otherbot import Otherbot


def setup(bot):
    bot.add_cog(Otherbot(bot))
