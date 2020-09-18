from redbot.core import commands

from .rss import RSS


async def setup(bot: commands.Bot):
    n = RSS(bot)
    bot.add_cog(n)
    n.initialize()
