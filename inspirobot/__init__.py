from .inspirobot import Inspirobot


def setup(bot):
    bot.add_cog(Inspirobot(bot))
