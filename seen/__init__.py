from .seen import Seen

__red_end_user_data_statement__ = (
    "This cog does not persistently store end user data. "
    "This cog does store discord IDs and last seen timestamp as needed for operation. "
)


async def setup(bot):
    cog = Seen(bot)
    await cog.initialize()
    bot.add_cog(cog)
