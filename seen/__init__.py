from .seen import Seen


def setup(bot):
    bot.add_cog(Seen(bot))
