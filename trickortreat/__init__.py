import asyncio

import discord

from .trickortreat import TrickOrTreat

__red_end_user_data_statement__ = (
    "This cog does not persistently store end user data. "
    "This cog does store discord IDs as needed for operation. "
    "This cog does store user stats for the cog such as their score. "
    "Users may remove their own content without making a data removal request."
    "This cog does not support data requests, "
    "but will respect deletion requests."
)


async def setup(bot):
    cog = TrickOrTreat(bot)
    if discord.__version__ > "1.7.3":
        await bot.add_cog(cog)
    else:
        bot.add_cog(cog)
    asyncio.create_task(cog.cleanup())
