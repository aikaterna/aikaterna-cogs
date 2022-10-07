from .voicelogs import VoiceLogs


async def setup(bot):
    cog = VoiceLogs(bot)
    bot.add_cog(cog)
