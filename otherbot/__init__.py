from .otherbot import Otherbot

__red_end_user_data_statement__ = (
    "This cog does not persistently store end user data. This cog does store discord IDs as needed for operation."
)


async def setup(bot):
    n = Otherbot(bot)
    await n.generate_cache()
    await bot.add_cog(n)
