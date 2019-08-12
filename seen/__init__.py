from .seen import Seen


async def setup(bot):
    cog = Seen(bot)
    await cog.initialize()
    bot.add_cog(cog)
