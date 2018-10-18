from .joinleave import JoinLeave


def setup(bot):
    bot.add_cog(JoinLeave(bot))
