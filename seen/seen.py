import asyncio
import contextlib
import datetime
from typing import Union, Literal

import discord
import time

from redbot.core import Config, commands

_SCHEMA_VERSION = 2


class Seen(commands.Cog):
    """Shows last time a user was seen in chat."""

    async def red_delete_data_for_user(
        self, *, requester: Literal["discord", "owner", "user", "user_strict"], user_id: int,
    ):
        if requester in ["discord", "owner"]:
            data = await self.config.all_members()
            for guild_id, members in data.items():
                if user_id in members:
                    await self.config.member_from_ids(guild_id, user_id).clear()

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2784481001, force_registration=True)

        default_global = dict(schema_version=1)
        default_member = dict(seen=None)

        self.config.register_global(**default_global)
        self.config.register_member(**default_member)

        self._cache = {}
        self._task = self.bot.loop.create_task(self._save_to_config())

    async def initialize(self):
        asyncio.ensure_future(
            self._migrate_config(from_version=await self.config.schema_version(), to_version=_SCHEMA_VERSION)
        )

    async def _migrate_config(self, from_version: int, to_version: int):
        if from_version == to_version:
            return
        elif from_version < to_version:
            all_guild_data = await self.config.all_members()
            users_data = {}
            for guild_id, guild_data in all_guild_data.items():
                for user_id, user_data in guild_data.items():
                    for _, v in user_data.items():
                        if not v:
                            v = None
                        if user_id not in users_data:
                            users_data[guild_id][user_id] = {"seen": v}
                        else:
                            if (v and not users_data[guild_id][user_id]["seen"]) or (
                                v
                                and users_data[guild_id][user_id]["seen"]
                                and v > users_data[guild_id][user_id]["seen"]
                            ):
                                users_data[guild_id][user_id] = {"seen": v}

            group = self.config._get_base_group(self.config.MEMBER)  # Bulk update to new scope
            async with group.all() as new_data:
                for guild_id, member_data in users_data.items():
                    new_data[guild_id] = member_data

            # new schema is now in place
            await self.config.schema_version.set(_SCHEMA_VERSION)

            # migration done, now let's delete all the old stuff
            await self.config.clear_all_members()

    @commands.guild_only()
    @commands.command(name="seen")
    @commands.bot_has_permissions(embed_links=True)
    async def _seen(self, ctx, author: discord.Member):
        """Shows last time a user was seen in chat."""
        member_seen_config = await self.config.member(author).seen()
        member_seen_cache = self._cache.get(author.guild.id, {}).get(author.id, None)

        if not member_seen_cache and not member_seen_config:
            embed = discord.Embed(colour=discord.Color.red(), title="I haven't seen that user yet.")
            return await ctx.send(embed=embed)

        if not member_seen_cache:
            member_seen = member_seen_config
        elif not member_seen_config:
            member_seen = member_seen_cache
        elif member_seen_cache > member_seen_config:
            member_seen = member_seen_cache
        elif member_seen_config > member_seen_cache:
            member_seen = member_seen_config
        else:
            member_seen = member_seen_cache or member_seen_config

        now = int(time.time())
        time_elapsed = int(now - member_seen)
        output = self._dynamic_time(time_elapsed)

        if output[2] < 1:
            ts = "just now"
        else:
            ts = ""
            if output[0] == 1:
                ts += "{} day, ".format(output[0])
            elif output[0] > 1:
                ts += "{} days, ".format(output[0])
            if output[1] == 1:
                ts += "{} hour, ".format(output[1])
            elif output[1] > 1:
                ts += "{} hours, ".format(output[1])
            if output[2] == 1:
                ts += "{} minute ago".format(output[2])
            elif output[2] > 1:
                ts += "{} minutes ago".format(output[2])
        em = discord.Embed(colour=discord.Color.green())
        avatar = author.avatar_url or author.default_avatar_url
        em.set_author(name="{} was seen {}".format(author.display_name, ts), icon_url=avatar)
        await ctx.send(embed=em)

    @staticmethod
    def _dynamic_time(time_elapsed):
        m, s = divmod(time_elapsed, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        return d, h, m

    @commands.Cog.listener()
    async def on_message(self, message):
        if getattr(message, "guild", None):
            if message.guild.id not in self._cache:
                self._cache[message.guild.id] = {}
            self._cache[message.guild.id][message.author.id] = int(time.time())

    @commands.Cog.listener()
    async def on_typing(
        self, channel: discord.abc.Messageable, user: Union[discord.User, discord.Member], when: datetime.datetime,
    ):
        if getattr(user, "guild", None):
            if user.guild.id not in self._cache:
                self._cache[user.guild.id] = {}
            self._cache[user.guild.id][user.id] = int(time.time())

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if getattr(after, "guild", None):
            if after.guild.id not in self._cache:
                self._cache[after.guild.id] = {}
            self._cache[after.guild.id][after.author.id] = int(time.time())

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        if getattr(user, "guild", None):
            if user.guild.id not in self._cache:
                self._cache[user.guild.id] = {}
            self._cache[user.guild.id][user.id] = int(time.time())

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        if getattr(user, "guild", None):
            if user.guild.id not in self._cache:
                self._cache[user.guild.id] = {}
            self._cache[user.guild.id][user.id] = int(time.time())

    def cog_unload(self):
        self.bot.loop.create_task(self._clean_up())

    async def _clean_up(self):
        if self._task:
            self._task.cancel()
        if self._cache:
            group = self.config._get_base_group(self.config.MEMBER)  # Bulk update to config
            async with group.all() as new_data:
                for guild_id, member_data in self._cache.items():
                    if str(guild_id) not in new_data:
                        new_data[str(guild_id)] = {}
                    for member_id, seen in member_data.items():
                        new_data[str(guild_id)][str(member_id)] = {"seen": seen}

    async def _save_to_config(self):
        await self.bot.wait_until_ready()
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                users_data = self._cache.copy()
                self._cache = {}
                group = self.config._get_base_group(self.config.MEMBER)  # Bulk update to config
                async with group.all() as new_data:
                    for guild_id, member_data in users_data.items():
                        if str(guild_id) not in new_data:
                            new_data[str(guild_id)] = {}
                        for member_id, seen in member_data.items():
                            new_data[str(guild_id)][str(member_id)] = {"seen": seen}

                await asyncio.sleep(60)
