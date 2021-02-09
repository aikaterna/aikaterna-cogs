from .urlfetch import UrlFetch


def setup(bot):
    bot.add_cog(UrlFetch(bot))
