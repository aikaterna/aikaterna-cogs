from .dictionary import Dictionary


def setup(bot):
    bot.add_cog(Dictionary(bot))
