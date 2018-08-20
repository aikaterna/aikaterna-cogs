from .wolfram import Wolfram


def setup(bot):
    bot.add_cog(Wolfram(bot))
