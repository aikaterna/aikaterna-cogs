from .retrosign import Retrosign


def setup(bot):
    bot.add_cog(Retrosign(bot))
