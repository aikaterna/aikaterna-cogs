from discord.ext import commands
import time


class Pingtime:

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def pingtime(self, ctx):
        """Ping pong."""
        latencies = self.bot.latencies
        for shard, pingt in latencies:
            msg = "Pong!\n"
            msg += "Shard {}/{}: {}ms\n".format(shard + 1, len(latencies), round(pingt*1000))
        await ctx.send(msg)
