from .warcraftlogs import WarcraftLogs


def setup(bot):
    bot.add_cog(WarcraftLogs(bot))
