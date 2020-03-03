from .icyparser import IcyParser


def setup(bot):
    bot.add_cog(IcyParser(bot))
