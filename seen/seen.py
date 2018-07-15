import asyncio
import discord
import time
from discord.ext import commands
from datetime import datetime
from redbot.core import Config


class Seen:
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2784481001, force_registration=True)

        default_member = {
            "member_seen": []
        }

        self.config.register_member(**default_member)

    @commands.guild_only()
    @commands.command(name='seen')
    async def _seen(self, ctx, author: discord.Member):
        '''Shows last time a user was seen in chat'''
        member_seen = await self.config.member(author).member_seen()
        now = int(time.time())
        try:
            time_elapsed = int(now - member_seen)
        except TypeError:
            embed = discord.Embed(colour=discord.Color.red(), title='I haven\'t seen that user yet.')
            return await ctx.send(embed=embed)
        output = self._dynamic_time(time_elapsed)
        if output[2] < 1:
            ts = 'just now'
        else:
            ts = ''
            if output[0] == 1:
                ts += '{} day, '.format(output[0])
            elif output[0] > 1:
                ts += '{} days, '.format(output[0])
            if output[1] == 1:
                ts += '{} hour, '.format(output[1])
            elif output[1] > 1:
                ts += '{} hours, '.format(output[1])
            if output[2] == 1:
                ts += '{} minute ago'.format(output[2])
            elif output[2] > 1:
                ts += '{} minutes ago'.format(output[2])
        em = discord.Embed(colour=discord.Color.green())
        avatar = author.avatar_url if author.avatar else author.default_avatar_url
        em.set_author(name='{} was seen {}'.format(author.display_name, ts), icon_url=avatar)
        await ctx.send(embed=em)

    def _dynamic_time(self, time_elapsed):
        m, s = divmod(time_elapsed, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        return (d, h, m)

    async def on_message(self, message):
        if not isinstance(message.channel, discord.abc.PrivateChannel) and self.bot.user.id != message.author.id:
            prefixes = await self.bot.get_prefix(message)
            if not any(message.content.startswith(n) for n in prefixes):
                author = message.author
                ts = int(time.time())
                try:
                    await self.config.member(author).member_seen.set(ts)
                except AttributeError:
                    pass
