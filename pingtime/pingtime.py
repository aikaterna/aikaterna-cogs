from redbot.core import commands


BaseCog = getattr(commands, "Cog", object)


class Pingtime(BaseCog):
    """🏓"""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def pingtime(self, ctx):
        """Ping pong."""
        latencies = self.bot.latencies
        msg = "Pong!\n"
        for shard, pingt in latencies:
            msg += "Shard {}/{}: {}ms\n".format(shard + 1, len(latencies), round(pingt * 1000))
        await ctx.send(msg)
