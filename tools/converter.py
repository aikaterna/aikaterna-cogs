"""
Because discord.py rewrite doesn't come with a general channel converter anymore
Written by sitryk
"""
import discord
import re

from discord.ext.commands import converter, BadArgument


class GuildChannelConverter(converter.IDConverter, converter.Converter):
    """
    Check order is:

    1. Text Channels
    2. Voice Channels
    3. Categories
    """

    async def convert(self, ctx, argument):
        bot = ctx.bot
        match = self._get_id_match(argument) or re.match(r"<#([0-9]+)>$", argument)
        result = None
        guild = ctx.guild

        if match is None:
            order = [
                (discord.TextChannel, guild.text_channels),
                (discord.VoiceChannel, guild.voice_channels),
                (discord.CategoryChannel, guild.categories),
            ]

            # not a mention
            for c_types in order:
                if guild:
                    result = discord.utils.get(c_types[1], name=argument)
                    if result is not None:
                        break
                else:

                    def check(c):
                        return isinstance(c, c_types[0]) and c.name == argument

                    result = discord.utils.find(check, bot.get_all_channels())
                    if result is not None:
                        break
        else:
            channel_id = int(match.group(1))
            if guild:
                result = guild.get_channel(channel_id)
            else:
                result = converter._get_from_guilds(bot, "get_channel", channel_id)

        if not isinstance(result, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
            raise BadArgument('Channel "{}" not found.'.format(argument))

        return result
