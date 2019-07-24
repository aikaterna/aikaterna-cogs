from .youtube import YouTube


def setup(bot):
    bot.add_cog(YouTube(bot))
