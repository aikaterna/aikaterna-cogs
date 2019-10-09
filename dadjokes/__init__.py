from .dadjokes import DadJokes


def setup(bot):
    bot.add_cog(DadJokes(bot))
