# This cog was originally by ZeLarpMaster for Red v2, and can be found at:
# https://github.com/ZeLarpMaster/ZeCogs/blob/master/voice_logs/voice_logs.py

import asyncio
import contextlib
import discord
import logging

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Literal, Union

from redbot.core import checks, commands, Config
from redbot.core.utils.chat_formatting import bold


log = logging.getLogger("red.aikaterna.voicelogs")


class VoiceLogs(commands.Cog):
    """Logs information about voice channel connection times."""

    __author__ = ["ZeLarpMaster#0818", "aikaterna"]
    __version__ = "0.1.1"

    TIME_FORMATS = ["{} seconds", "{} minutes", "{} hours", "{} days", "{} weeks"]
    TIME_FRACTIONS = [60, 60, 24, 7]
    ENTRY_TIME_LIMIT = timedelta(weeks=1)
    CLEANUP_DELAY = timedelta(days=1).total_seconds()

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2708181003, force_registration=True)

        default_guild = {"toggle": False}
        default_user = {"history": []}

        #    history is a list of dict entries
        #    {"channel_id": int,
        #    "channel_name": str,
        #    "joined_at": datetime,
        #    "left_at": datetime}

        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)

        asyncio.ensure_future(self.cleanup_loop())

    # Commands
    @commands.group(name="voicelog", aliases=["voicelogs"])
    async def _command_voicelog(self, ctx):
        """
        Access voice activity data.

        You must have the bot Mod or Admin role or View Audit Log permissions to view and use the commands.
        """
        pass

    @_command_voicelog.command(name="user", aliases=["u"])
    @checks.mod_or_permissions(view_audit_log=True)
    async def _command_voicelog_user(self, ctx: commands.Context, *, user: discord.Member):
        """
        Look up the voice activity of a user.

        Timestamps are in UTC.
        """
        entries = await self.config.user(user).history()
        embed = discord.Embed(description=f"**Voice Activity for** {user.mention}")
        for entry in self.process_entries(entries, limit=25):
            joined_at = self.format_time(entry["joined_at"])
            left_at = entry.get("left_at")
            left_at = self.format_time(left_at) if left_at is not None else "now"
            embed.add_field(
                name=f"#{entry['channel_name']} ({entry['channel_id']})",
                value=f"**{joined_at}** until **{left_at}**",
                inline=False,
            )
        if len(embed.fields) == 0:
            embed.description = f"No voice activity for {user.mention}"
        await ctx.channel.send(embed=embed)

    @_command_voicelog.command(name="channel", aliases=["c"])
    @checks.mod_or_permissions(view_audit_log=True)
    async def _command_voicelog_channel(self, ctx: commands.Context, *, voice_channel_name_or_id: discord.VoiceChannel):
        """
        Look up the voice activity on a voice channel.

        `voice_channel_name_or_id` is either the exact name of the target voice channel (proper case), or its ID.
        """
        entries = []
        all_entries = await self.config.all_users()

        for user_id, user_entries in all_entries.items():
            for history_key, entry_list in user_entries.items():
                for entry in entry_list:
                    if entry["channel_id"] == voice_channel_name_or_id.id:
                        entry["user_id"] = user_id
                        entries.append(entry)

        embed = discord.Embed(title=f"Voice Activity in {voice_channel_name_or_id.name}", description="")
        for entry in self.process_entries(entries, limit=25):
            time_spent = ""
            left_at = entry.get("left_at", None)
            if left_at is None:
                time_spent = "+"
                left_at = datetime.now(timezone.utc)
            time_diff = left_at - entry["joined_at"]
            time_spent = self.humanize_time(round(time_diff.total_seconds())) + time_spent
            user_obj = ctx.guild.get_member(entry["user_id"])
            if not user_obj:
                user_obj = SimpleNamespace(name="Unknown User", id=entry["user_id"])
            embed.description += f"**{user_obj.name}** ({user_obj.id}) for **{time_spent}**\n"
        if len(embed.description) == 0:
            embed.description = f"No voice activity in {voice_channel_name_or_id.mention}"
        await ctx.send(embed=embed)

    @_command_voicelog.command(name="toggle")
    @checks.mod_or_permissions(view_audit_log=True)
    async def _command_voicelog_toggle(self, ctx: commands.Context):
        """Toggle voice activity recording on and off."""
        toggle = await self.config.guild(ctx.guild).toggle()
        await self.config.guild(ctx.guild).toggle.set(not toggle)
        await ctx.send(f"Voice channel watching is now toggled {bold('ON') if toggle == False else bold('OFF')}")

    # Events
    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        if before.channel == after.channel:
            return

        toggle = await self.config.guild(member.guild).toggle()
        if not toggle:
            return

        try:
            # Left that channel
            if before.channel is not None:
                async with self.config.user(member).history() as user_data:
                    entry = discord.utils.find(
                        lambda e: e["channel_id"] == before.channel.id and "left_at" not in e, user_data
                    )
                    if entry is not None:
                        entry["left_at"] = datetime.now(timezone.utc).timestamp()

            # Joined that channel
            if after.channel is not None:
                async with self.config.user(member).history() as user_info:
                    entry = {
                        "channel_id": after.channel.id,
                        "channel_name": after.channel.name,
                        "joined_at": datetime.now(timezone.utc).timestamp(),
                    }
                    user_info.append(entry)

        except Exception as e:
            log.error(f"Error in on_voice_state_update:\n{e}", exc_info=True)

    async def cleanup_loop(self):
        await self.bot.wait_until_red_ready()

        # Suppress the "Event loop is closed" error
        with contextlib.suppress(RuntimeError, asyncio.CancelledError):
            while True:
                try:
                    await self.cleanup_entries()
                    await asyncio.sleep(self.CLEANUP_DELAY)
                except Exception as e:
                    log.error(f"Error in cleanup_loop:\n{e}", exc_info=True)

    async def cleanup_entries(self):
        try:
            delete_threshold = datetime.now(timezone.utc) - self.ENTRY_TIME_LIMIT
            to_delete = {"history": []}
            user_data = await self.config.all_users()
            for user_id, history in user_data.items():
                for dict_title, entry_list in history.items():
                    for entry in entry_list:
                        left_at = entry.get("left_at", None)
                        if left_at is not None and datetime.fromtimestamp(left_at, timezone.utc) < delete_threshold:
                            entry_list_index = [i for i, d in enumerate(entry_list) if left_at in d.values()]
                            entry_list.pop(entry_list_index[0])
                    await self.config.user_from_id(user_id).history.set(entry_list)
        except Exception as e:
            log.error(f"Error in cleanup_entries:\n{e}", exc_info=True)

    def process_entries(self, entries, *, limit=None):
        return sorted(self.map_entries(entries), key=lambda o: o["joined_at"], reverse=True)[:limit]

    def map_entries(self, entries):
        for entry in entries:
            new_entry = entry.copy()
            joined_at = datetime.fromtimestamp(entry["joined_at"], timezone.utc)
            new_entry["joined_at"] = joined_at
            left_at = entry.get("left_at")
            if left_at is not None:
                new_entry["left_at"] = datetime.fromtimestamp(left_at, timezone.utc)
            yield new_entry

    def format_time(self, moment: datetime):
        if date.today() == moment.date():
            return "today " + moment.strftime("%X")
        else:
            return moment.strftime("%c")

    def humanize_time(self, time: int) -> str:
        """
        Returns a string of the humanized given time keeping only the 2 biggest formats.

        Examples:
        1661410 --> 2 weeks 5 days (hours, mins, seconds are ignored)
        30 --> 30 seconds
        """
        times = []
        # 90 --> divmod(90, 60) --> (1, 30) --> (1m + 30s)
        for time_f in zip(self.TIME_FRACTIONS, self.TIME_FORMATS):
            time, units = divmod(time, time_f[0])
            if units > 0:
                times.append(self.plural_format(units, time_f[1]))
        if time > 0:
            times.append(self.plural_format(time, self.TIME_FORMATS[-1]))
        return " ".join(reversed(times[-2:]))

    def plural_format(self, raw_amount: Union[int, float], format_string: str, *, singular_format: str = None) -> str:
        """
        Formats a string for plural and singular forms of an amount.

        The amount given is rounded.
        `raw_amount` is an integer (rounded if something else is given)
        `format_string` is the string to use when formatting in plural
        `singular_format` is the string to use for singular

        By default uses the plural and removes the last character.
        """
        amount = round(raw_amount)
        result = format_string.format(raw_amount)
        if singular_format is None:
            result = format_string.format(raw_amount)[: -1 if amount == 1 else None]
        elif amount == 1:
            result = singular_format.format(raw_amount)
        return result
