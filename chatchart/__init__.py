from .chatchart import Chatchart


def setup(bot):
    bot.add_cog(Chatchart(bot))
