from discord.ext import commands
import time


class Pingtime:

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def pingtime(self, ctx):
        """Ping pong."""
        channel = ctx.message.channel
        t1 = time.perf_counter()
        await channel.trigger_typing()
        t2 = time.perf_counter()
        await ctx.send("Pong: {}ms".format(round((t2-t1)*1000)))
