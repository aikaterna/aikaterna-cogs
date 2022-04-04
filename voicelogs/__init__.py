from .voicelogs import VoiceLogs


async def setup(bot):
    n = VoiceLogs(bot)
    await bot.add_cog(n)
