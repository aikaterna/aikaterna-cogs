import discord
from fuzzywuzzy import fuzz, process
from typing import List
from unidecode import unidecode

from discord.ext.commands.converter import IDConverter, _get_from_guilds
from discord.ext.commands.errors import BadArgument

from redbot.core import commands


class FuzzyMember(IDConverter):
    """
    Original class written by TrustyJaid#0001
    https://github.com/TrustyJAID/Trusty-cogs/blob/c739903aa2c8111c58b3d5e695a1221cbe1f57d9/serverstats/converters.py

    This will accept partial names and perform a fuzzy search for
    members within the guild and return a list of member objects.

    Guidance code on how to do this from:
    https://github.com/Rapptz/discord.py/blob/rewrite/discord/ext/commands/converter.py#L85
    https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/mod/mod.py#L24
    """

    async def convert(self, ctx: commands.Context, argument: str) -> List[discord.Member]:
        bot = ctx.bot
        guild = ctx.guild
        result = []

        members = {m: unidecode(m.name) for m in guild.members}
        fuzzy_results = process.extract(argument, members, limit=1000, scorer=fuzz.partial_ratio)
        matching_names = [m[2] for m in fuzzy_results if m[1] > 90]
        for x in matching_names:
            result.append(x)

        nick_members = {m: unidecode(m.nick) for m in guild.members if m.nick and m not in matching_names}
        fuzzy_results2 = process.extract(argument, nick_members, limit=50, scorer=fuzz.partial_ratio)
        matching_nicks = [m[2] for m in fuzzy_results2 if m[1] > 90]
        for x in matching_nicks:
            result.append(x)

        if not result or result == [None]:
            raise BadArgument('Member "{}" not found'.format(argument))

        return result
