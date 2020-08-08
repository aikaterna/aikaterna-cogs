from .invites import Invites


def setup(bot):
    bot.add_cog(Invites(bot))
