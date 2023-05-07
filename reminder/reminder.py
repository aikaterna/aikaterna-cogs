# Reminder was originally written by ZeLarpMaster#0818
# https://github.com/ZeLarpMaster/ZeCogsV3/blob/master/reminder/reminder.py

import asyncio
import collections
import datetime
import discord
import hashlib
from itertools import islice
from math import ceil
import re
from typing import List, Literal, Optional

from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.commands import Context
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


class Reminder(commands.Cog):
    """Utilities to remind yourself of whatever you want"""

    __author__ = ["ZeLarpMaster#0818", "aikaterna#1393"]

    TIME_AMNT_REGEX = re.compile("([1-9][0-9]*)([a-z]+)", re.IGNORECASE)
    TIME_QUANTITIES = collections.OrderedDict(
        [
            ("seconds", 1),
            ("minutes", 60),
            ("hours", 3600),
            ("days", 86400),
            ("weeks", 604800),
            ("months", 2628000),
            ("years", 31540000),
        ]
    )
    MAX_SECONDS = TIME_QUANTITIES["years"] * 2

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        unique_id = int(hashlib.sha512((self.__author__[0] + "@" + self.__class__.__name__).encode()).hexdigest(), 16)
        self.config = Config.get_conf(self, identifier=unique_id, force_registration=True)
        self.config.register_user(reminders=[], offset=0)
        self.futures = {}
        asyncio.ensure_future(self.start_saved_reminders())

    def cog_unload(self):
        for user_futures in self.futures.values():
            for future in user_futures:
                future.cancel()

    @commands.group(invoke_without_command=True, aliases=["remindme"], name="remind")
    async def command_remind(self, ctx: Context, time: str, *, reminder_text: str):
        """
        Remind yourself of something in a specific amount of time

        Examples for time: `5d`, `10m`, `10m30s`, `1h`, `1y1mo2w5d10h30m15s`
        Abbreviations: `s` for seconds, `m` for minutes, `h` for hours, `d` for days, `w` for weeks, `mo` for months, `y` for years
        Any longer abbreviation is accepted. `m` assumes minutes instead of months.
        One month is counted as exact 365/12 days.
        Ignores all invalid abbreviations.
        """
        seconds = self.get_seconds(time)
        if seconds is None:
            response = ":x: Invalid time format."
        elif seconds >= self.MAX_SECONDS:
            response = f":x: Too long amount of time. Maximum: 2 years"
        else:
            user = ctx.message.author
            time_now = datetime.datetime.utcnow()
            days, secs = divmod(seconds, 3600 * 24)
            end_time = time_now + datetime.timedelta(days=days, seconds=secs)
            reminder = {"content": reminder_text, "start_time": time_now.timestamp(), "end_time": end_time.timestamp()}
            async with self.config.user(user).reminders() as user_reminders:
                user_reminders.append(reminder)
            self.futures.setdefault(user.id, []).append(
                asyncio.ensure_future(self.remind_later(user, seconds, reminder_text, reminder))
            )
            user_offset = await self.config.user(ctx.author).offset()
            offset = user_offset * 3600
            formatted_time = round(end_time.timestamp()) + offset
            if seconds > 86400:
                response = f":white_check_mark: I will remind you of that on <t:{int(formatted_time)}:F>."
            else:
                response = f":white_check_mark: I will remind you of that in {self.time_from_seconds(seconds)}."
        await ctx.send(response)

    @command_remind.group(name="forget")
    async def command_remind_forget(self, ctx: Context):
        """Forget your reminders"""
        pass

    @command_remind_forget.command(name="all")
    async def command_remind_forget_all(self, ctx: Context):
        """Forget **all** of your reminders"""
        for future in self.futures.get(ctx.message.author.id, []):
            future.cancel()
        async with self.config.user(ctx.message.author).reminders() as user_reminders:
            user_reminders.clear()
        await ctx.send(":put_litter_in_its_place: Forgot **all** of your reminders!")

    @command_remind_forget.command(name="one")
    async def command_remind_forget_one(self, ctx: Context, index_number_of_reminder: int):
        """
        Forget one of your reminders

        Use `[p]remind list` to find the index number of the reminder you wish to forget.
        """
        async with self.config.user(ctx.message.author).all() as user_data:
            if not user_data["reminders"]:
                await ctx.send("You don't have any reminders saved.")
                return
            time_sorted_reminders = sorted(user_data["reminders"], key=lambda x: (x["end_time"]))
            try:
                removed = time_sorted_reminders.pop(index_number_of_reminder - 1)
            except IndexError:
                await ctx.send(f"There is no reminder at index {index_number_of_reminder}.")
                return
            user_data["reminders"] = time_sorted_reminders
            offset = user_data["offset"] * 3600
            end_time = round((removed["end_time"]) + offset)
            msg = f":put_litter_in_its_place: Forgot reminder **#{index_number_of_reminder}**\n"
            msg += f"Date: <t:{end_time}:f>\nContent: `{removed['content']}`"
            await ctx.send(msg)

    @command_remind.command(name="list")
    async def command_remind_list(self, ctx: Context):
        """List your reminders"""
        user_data = await self.config.user(ctx.message.author).all()
        if not user_data["reminders"]:
            await ctx.send("There are no reminders to show.")
            return

        if not ctx.channel.permissions_for(ctx.me).embed_links:
            return await ctx.send("I need the `Embed Messages` permission here to be able to display this information.")

        embed_pages = await self.create_remind_list_embeds(ctx, user_data)
        await ctx.send(embed=embed_pages[0]) if len(embed_pages) == 1 else await menu(
            ctx, embed_pages, DEFAULT_CONTROLS
        )

    @command_remind.command(name="offset")
    async def command_remind_offset(self, ctx: Context, offset_time_in_hours: str):
        """
        Set a basic timezone offset
        from the default of UTC for use in [p]remindme list.

        This command accepts number values from `-23.75` to `+23.75`.
        You can look up your timezone offset on https://en.wikipedia.org/wiki/List_of_UTC_offsets
        """
        offset = self.remind_offset_check(offset_time_in_hours)
        if offset is not None:
            await self.config.user(ctx.author).offset.set(offset)
            await ctx.send(f"Your timezone offset was set to {str(offset).replace('.0', '')} hours from UTC.")
        else:
            await ctx.send(f"That doesn't seem like a valid hour offset. Check `{ctx.prefix}help remind offset`.")

    @staticmethod
    async def chunker(input: List[dict], chunk_size: int) -> List[List[str]]:
        chunk_list = []
        iterator = iter(input)
        while chunk := list(islice(iterator, chunk_size)):
            chunk_list.append(chunk)
        return chunk_list

    async def create_remind_list_embeds(self, ctx: Context, user_data: dict) -> List[discord.Embed]:
        """Embed creator for command_remind_list."""
        offset = user_data["offset"] * 3600
        reminder_list = []
        time_sorted_reminders = sorted(user_data["reminders"], key=lambda x: (x["end_time"]))
        entry_size = len(str(len(time_sorted_reminders)))

        for i, reminder_dict in enumerate(time_sorted_reminders, 1):
            entry_number = f"{str(i).zfill(entry_size)}"
            end_time = round((reminder_dict["end_time"]) + offset)
            exact_time_timestamp = f"<t:{end_time}:f>"
            relative_timestamp = f"<t:{end_time}:R>"
            content = reminder_dict["content"]
            display_content = content if len(content) < 200 else f"{content[:200]} [...]"
            reminder = f"`{entry_number}`. {exact_time_timestamp}, {relative_timestamp}:\n{display_content}\n\n"
            reminder_list.append(reminder)

        reminder_text_chunks = await self.chunker(reminder_list, 7)
        max_pages = ceil(len(reminder_list) / 7)
        offset_hours = str(user_data["offset"]).replace(".0", "")
        offset_text = f" • UTC offset of {offset_hours}h applied" if offset != 0 else ""
        menu_pages = []
        for chunk in reminder_text_chunks:
            embed = discord.Embed(title="", description="".join(chunk))
            embed.set_author(name=f"Reminders for {ctx.author}", icon_url=ctx.author.avatar.url)
            embed.set_footer(text=f"Page {len(menu_pages) + 1} of {max_pages}{offset_text}")
            menu_pages.append(embed)
        return menu_pages

    def get_seconds(self, time: str):
        """Returns the amount of converted time or None if invalid"""
        seconds = 0
        for time_match in self.TIME_AMNT_REGEX.finditer(time):
            time_amnt = int(time_match.group(1))
            time_abbrev = time_match.group(2)
            time_quantity = discord.utils.find(lambda t: t[0].startswith(time_abbrev), self.TIME_QUANTITIES.items())
            if time_quantity is not None:
                seconds += time_amnt * time_quantity[1]
        return None if seconds == 0 else seconds

    async def remind_later(self, user: discord.User, time: float, content: str, reminder):
        """Reminds the `user` in `time` seconds with a message containing `content`"""
        await asyncio.sleep(time)
        embed = discord.Embed(title="Reminder", description=content, color=discord.Colour.blue())
        await user.send(embed=embed)
        async with self.config.user(user).reminders() as user_reminders:
            user_reminders.remove(reminder)

    @staticmethod
    def remind_offset_check(offset: str) -> Optional[float]:
        """Float validator for command_remind_offset."""
        try:
            offset = float(offset.replace("+", ""))
        except ValueError:
            return None
        offset = round(offset * 4) / 4.0
        if not -23.75 < offset < 23.75 or 23.75 < offset < -23.75:
            return None
        return offset

    async def start_saved_reminders(self):
        await self.bot.wait_until_red_ready()
        user_configs = await self.config.all_users()
        for user_id, user_config in list(user_configs.items()):  # Making a copy
            for reminder in user_config["reminders"]:
                user = self.bot.get_user(user_id)
                if user is None:
                    # Delete the reminder if the user doesn't have a mutual server anymore
                    await self.config.user_from_id(user_id).clear()
                else:
                    time_diff = datetime.datetime.fromtimestamp(reminder["end_time"]) - datetime.datetime.utcnow()
                    time = max(0.0, time_diff.total_seconds())
                    fut = asyncio.ensure_future(self.remind_later(user, time, reminder["content"], reminder))
                    self.futures.setdefault(user.id, []).append(fut)

    @staticmethod
    def time_from_seconds(seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            msg = f"{hours} hour" if hours == 1 else f"{hours} hours"
            if minutes != 0:
                msg += f" and {minutes} minute" if minutes == 1 else f" and {minutes} minutes"
        elif minutes:
            msg = f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
            if seconds != 0:
                msg += f" and {seconds} second" if seconds == 1 else f" and {seconds} seconds"
        else:
            msg = f"{seconds} seconds" if seconds == 1 else f"and {seconds} seconds"
        return msg
