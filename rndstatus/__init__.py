from .rndstatus import RndStatus


def setup(bot):
    bot.add_cog(RndStatus(bot))
