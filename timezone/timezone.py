import discord
import pytz
from datetime import datetime
from pytz import common_timezones
from pytz import country_timezones
from typing import Optional, Literal, Tuple, Union
from redbot.core import Config, commands, checks


class Timezone(commands.Cog):
    """Gets times across the world..."""

    async def red_delete_data_for_user(
        self, *, requester: Literal["discord", "owner", "user", "user_strict"], user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 278049241001, force_registration=True)
        default_user = {"usertime": None}
        self.config.register_user(**default_user)

    async def get_usertime(self, user: discord.User):
        tz = None
        usertime = await self.config.user(user).usertime()
        if usertime:
            tz = pytz.timezone(usertime)

        return usertime, tz

    @commands.guild_only()
    @commands.group()
    async def time(self, ctx):
        """
            Checks the time.

            For the list of supported timezones, see here:
            https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        """
        pass

    @time.command()
    async def tz(self, ctx, *, tz: Optional[str] = None):
        """Gets the time in any timezone."""
        try:
            if tz is None:
                time = datetime.now()
                fmt = "**%H:%M** %d-%B-%Y"
                await ctx.send(f"Current system time: {time.strftime(fmt)}")
            else:
                if "'" in tz:
                    tz = tz.replace("'", "")
                if len(tz) > 4 and "/" not in tz:
                    await ctx.send(
                        "Error: Incorrect format. Use:\n **Continent/City** with correct capitals. "
                        "e.g. `America/New_York`\n See the full list of supported timezones here:\n "
                        "<https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
                    )
                else:
                    tz = tz.title() if "/" in tz else tz.upper()
                    if tz not in common_timezones:
                        raise Exception(tz)
                    fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
                    time = datetime.now(pytz.timezone(tz))
                    await ctx.send(time.strftime(fmt))
        except Exception as e:
            await ctx.send(f"**Error:** {str(e)} is an unsupported timezone.")

    @time.command()
    async def iso(self, ctx, *, code=None):
        """Looks up ISO3166 country codes and gives you a supported timezone."""
        if code is None:
            await ctx.send("That doesn't look like a country code!")
        else:
            exist = True if code in country_timezones else False
            if exist is True:
                tz = str(country_timezones(code))
                msg = (
                    f"Supported timezones for **{code}:**\n{tz[:-1][1:]}"
                    f"\n**Use** `{ctx.prefix}time tz Continent/City` **to display the current time in that timezone.**"
                )
                await ctx.send(msg)
            else:
                await ctx.send(
                    "That code isn't supported. For a full list, see here: "
                    "<https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes>"
                )

    @time.command()
    async def me(self, ctx, *, tz=None):
        """
            Sets your timezone.
            Usage: [p]time me Continent/City
        """
        if tz is None:
            usertime, tz = await self.get_usertime(ctx.author)
            if not usertime:
                await ctx.send(
                    f"You haven't set your timezone. Do `{ctx.prefix}time me Continent/City`: "
                    "see <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
                )
            else:
                time = datetime.now(tz)
                time = time.strftime("**%H:%M** %d-%B-%Y **%Z (UTC %z)**")
                msg = f"Your current timezone is **{usertime}.**\n" f"The current time is: {time}"
                await ctx.send(msg)
        else:
            exist = True if tz.title() in common_timezones else False
            if exist:
                if "'" in tz:
                    tz = tz.replace("'", "")
                await self.config.user(ctx.author).usertime.set(tz.title())
                await ctx.send(f"Successfully set your timezone to **{tz.title()}**.")
            else:
                await ctx.send(
                    f"**Error:** Unrecognized timezone. Try `{ctx.prefix}time me Continent/City`: "
                    "see <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
                )

    @time.command()
    @commands.is_owner()
    async def set(self, ctx, user: discord.Member, *, tz=None):
        """Allows the mods to edit timezones."""
        if not user:
            user = ctx.author
        if tz is None:
            await ctx.send("That timezone is invalid.")
            return
        else:
            exist = True if tz.title() in common_timezones else False
            if exist:
                if "'" in tz:
                    tz = tz.replace("'", "")
                await self.config.user(user).usertime.set(tz.title())
                await ctx.send(f"Successfully set {user.name}'s timezone to **{tz.title()}**.")
            else:
                await ctx.send(
                    f"**Error:** Unrecognized timezone. Try `{ctx.prefix}time set @user Continent/City`: "
                    "see <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
                )

    @time.command()
    async def user(self, ctx, user: discord.Member = None):
        """Shows the current time for user."""
        if not user:
            await ctx.send("That isn't a user!")
        else:
            usertime, tz = await self.get_usertime(user)
            if usertime:
                time = datetime.now(tz)
                fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
                time = time.strftime(fmt)
                await ctx.send(
                    f"{user.name}'s current timezone is: **{usertime}**\n" f"The current time is: {str(time)}"
                )
            else:
                await ctx.send("That user hasn't set their timezone.")

    @time.command()
    async def compare(self, ctx, user: discord.Member = None):
        """Compare your saved timezone with another user's timezone."""
        if not user:
            return await ctx.send_help()

        usertime, user_tz = await self.get_usertime(ctx.author)
        othertime, other_tz = await self.get_usertime(user)

        if not usertime:
            return await ctx.send(
                f"You haven't set your timezone. Do `{ctx.prefix}time me Continent/City`: "
                "see <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
            )
        if not othertime:
            return await ctx.send(f"That user's timezone isn't set yet.")

        user_now = datetime.now(user_tz)
        user_diff = user_now.utcoffset().total_seconds() / 60 / 60
        other_now = datetime.now(other_tz)
        other_diff = other_now.utcoffset().total_seconds() / 60 / 60
        time_diff = int(abs(user_diff - other_diff))
        fmt = "**%H:%M %Z (UTC %z)**"
        other_time = other_now.strftime(fmt)
        plural = "" if time_diff == 1 else "s"
        time_amt = "the same time zone as you" if time_diff == 0 else f"{time_diff} hour{plural}"
        position = "ahead of" if user_diff < other_diff else "behind"
        position_text = "" if time_diff == 0 else f" {position} you"

        await ctx.send(f"{user.display_name}'s time is {other_time} which is {time_amt}{position_text}.")
