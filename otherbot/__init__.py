from .otherbot import Otherbot


async def setup(bot):
    cog = Otherbot(bot)
    await cog.generate_cache()
    bot.add_cog(cog)
