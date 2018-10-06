import aiohttp
import discord
import os
import pytz
from datetime import datetime
from pytz import all_timezones
from pytz import country_timezones
from redbot.core import Config, commands, checks


BaseCog = getattr(commands, "Cog", object)

class Timezone(BaseCog):
    """Gets times across the world..."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 278049241001, force_registration=True)

        default_member = {"usertime": None}

        self.config.register_member(**default_member)
        self.session = aiohttp.ClientSession()

    def __unload(self):
        self.session.detach()

    @commands.guild_only()
    @commands.group()
    async def time(self, ctx):
        """Checks the time.

        For the list of supported timezones, see here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"""
        pass

    @time.command()
    async def tz(self, ctx, *, tz):
        """Gets the time in any timezone."""
        try:
            if tz == "":
                time = datetime.now()
                fmt = "**%H:%M** %d-%B-%Y"
                await ctx.send(f"Current system time: {time.strftime(fmt)}")
            else:
                fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
                if "'" in tz:
                    tz = tz.replace("'", "")
                if len(tz) > 4 and "/" not in tz:
                    await ctx.send(
                        "Error: Incorrect format. Use:\n **Continent/City** with correct capitals. e.g. `America/New_York`\n See the full list of supported timezones here:\n <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
                    )
                else:
                    time = datetime.now(pytz.timezone(tz))
                    await ctx.send(time.strftime(fmt))
        except Exception as e:
            await ctx.send(f"**Error:** {str(e)} is an unsupported timezone.")

    @time.command()
    async def iso(self, ctx, *, code):
        """Looks up ISO3166 country codes and gives you a supported timezone."""
        if code == "":
            await ctx.send("That doesn't look like a country code!")
        else:
            if code in country_timezones:
                exist = True
            else:
                exist = False
            if exist == True:
                msg = f"Supported timezones for **{code}:**\n"
                tz = str(country_timezones(code))
                tz = tz[:-1]
                tz = tz[1:]
                msg += tz
                msg += f"\n**Use** `[p]time tz Continent/City` **to display the current time in that timezone.**"
                await ctx.send(msg)
            else:
                await ctx.send(
                    "That code isn't supported. For a full list, see here: <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
                )

    @time.command()
    async def me(self, ctx, *tz):
        """Sets your timezone.
        Usage: [p]time me Continent/City"""
        tz = " ".join(tz)
        if tz in all_timezones:
            exist = True
        else:
            exist = False
        usertime = await self.config.member(ctx.message.author).usertime()
        if tz == "":
            if not usertime:
                await ctx.send(
                    "You haven't set your timezone. Do `[p]time me Continent/City`: see <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
                )
            else:
                msg = f"Your current timezone is **{usertime}.**\n"
                time = datetime.now(pytz.timezone(usertime))
                time = time.strftime("**%H:%M** %d-%B-%Y **%Z (UTC %z)**")
                msg += f"The current time is: {time}"
                await ctx.send(msg)
        elif exist == True:
            if "'" in tz:
                tz = tz.replace("'", "")
            await self.config.member(ctx.message.author).usertime.set(tz)
            await ctx.send(f"Successfully set your timezone to **{tz}**.")
        else:
            await ctx.send(
                "**Error:** Unrecognized timezone. Try `[p]time me Continent/City`: see <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
            )

    @time.command()
    @checks.admin_or_permissions(manage_server=True)
    async def set(self, ctx, user: discord.Member, *, tz):
        """Allows the mods to edit timezones."""
        author = ctx.message.author
        if not user:
            user = author

        if tz is None:
            await ctx.send("That timezone is invalid.")
            return
        else:
            space = " "
            timezone = tz.split(space, 1)[0]
            if timezone in all_timezones:
                if "'" in tz:
                    timezone = timezone.replace("'", "")
                await self.config.member(user).usertime.set(timezone)
                await ctx.send(f"Successfully set {user.name}'s timezone.")
            else:
                await ctx.send(
                    "**Error:** Unrecognized timezone. Try `[p]time set @user Continent/City`: see <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>"
                )

    @time.command()
    async def user(self, ctx, user: discord.Member = None):
        """Shows the current time for user."""
        if not user:
            await ctx.send("That isn't a user!")
        else:
            usertime = await self.config.member(user).usertime()
            if usertime:
                time = datetime.now(pytz.timezone(usertime))
                fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
                time = time.strftime(fmt)
                await ctx.send(f"{user.name}'s current time is: {str(time)}")
            else:
                await ctx.send("That user hasn't set their timezone.")
