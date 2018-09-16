from .nolinks import NoLinks


def setup(bot):
    bot.add_cog(NoLinks(bot))