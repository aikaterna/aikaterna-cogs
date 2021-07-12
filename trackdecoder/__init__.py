from .trackdecoder import TrackDecoder


def setup(bot):
    bot.add_cog(TrackDecoder(bot))
