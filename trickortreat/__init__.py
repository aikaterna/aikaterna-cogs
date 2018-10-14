from .trickortreat import TrickOrTreat


def setup(bot):
    bot.add_cog(TrickOrTreat(bot))
