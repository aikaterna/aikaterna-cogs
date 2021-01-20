from redbot.core.bot import Red
from .core import WarcraftLogs

__red_end_user_data_statement__ = (
    "This cog stores data provided by users "
    "for the express purpose of redisplaying. "
    "It does not store user data which was not "
    "provided through a command. "
    "Users may remove their own content "
    "without making a data removal request. "
    "This cog does not support data requests, "
    "but will respect deletion requests."
)


async def setup(bot: Red) -> None:
    cog = WarcraftLogs(bot)
    await cog._create_client()
    bot.add_cog(cog)
