from .rndstatus import RndStatus


def setup(bot):
    n = RndStatus(bot)
    bot.add_listener(n.switch_status, "on_message")
    bot.add_cog(n)
