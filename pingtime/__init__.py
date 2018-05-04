from .pingtime import Pingtime


def setup(bot):
    bot.add_cog(Pingtime(bot))
