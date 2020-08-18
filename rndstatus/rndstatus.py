import re
import discord
from redbot.core import Config, commands, checks
from redbot.core.utils import AsyncIter
from random import choice as rndchoice
from collections import defaultdict
import contextlib
import asyncio
import logging


log = logging.getLogger("red.aikaterna-cogs.rndstatus")


class RndStatus(commands.Cog):
    """Cycles random statuses or displays bot stats.
    If a custom status is already set, it won't change it until
    it's back to none. [p]set game"""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.last_change = None
        self.config = Config.get_conf(self, 2752521001, force_registration=True)
        self._user_count = 0

        self.user_task = asyncio.create_task(self._get_user_count())
        self.presence_task = asyncio.create_task(self.maybe_update_presence())

        default_global = {
            "botstats": False,
            "delay": 300,
            "statuses": [
                "her Turn()",
                "Tomb Raider II",
                "Transistor",
                "NEO Scavenger",
                "Python",
                "with your heart.",
            ],
            "streamer": "rndstatusstreamer",
            "type": 1,
        }
        self.config.register_global(**default_global)

    def cog_unload(self):
        self.user_task.cancel()
        self.presence_task.cancel()

    async def _get_user_count(self):
        await self.bot.wait_until_ready()
        with contextlib.suppress(asyncio.CancelledError):
            self._user_count = len(self.bot.users)
            while True:
                temp_data = defaultdict(set)
                async for s in AsyncIter(self.bot.guilds):
                    if s.unavailable:
                        continue
                    async for m in AsyncIter(s.members):
                        temp_data["Unique Users"].add(m.id)
                self._user_count = len(temp_data["Unique Users"])
                await asyncio.sleep(30)

    @commands.group(autohelp=True)
    @commands.guild_only()
    @checks.is_owner()
    async def rndstatus(self, ctx):
        """Rndstatus group commands."""
        pass

    @rndstatus.command(name="set")
    async def _set(self, ctx, *statuses: str):
        """Sets Red's random statuses.
        Accepts multiple statuses.
        Must be enclosed in double quotes in case of multiple words.
        Example:
        [p]rndstatus set \"Tomb Raider II\" \"Transistor\" \"with your heart.\"
        Shows current list if empty."""
        saved_status = await self.config.statuses()
        if statuses == () or "" in statuses:
            return await ctx.send("Current statuses: " + " | ".join(saved_status))
        await self.config.statuses.set(list(statuses))
        await ctx.send("Done. Redo this command with no parameters to see the current list of statuses.")

    @rndstatus.command(name="streamer")
    async def _streamer(self, ctx: commands.Context, *, streamer=None):
        """Set the streamer needed for streaming statuses.
        """

        saved_streamer = await self.config.streamer()
        if streamer is None:
            return await ctx.send(f"Current Streamer: {saved_streamer}")
        await self.config.streamer.set(streamer)
        await ctx.send("Done. Redo this command with no parameters to see the current streamer.")

    @rndstatus.command()
    async def botstats(self, ctx, *statuses: str):
        """Toggle for a bot stats status instead of random messages."""
        botstats = await self.config.botstats()
        await self.config.botstats.set(not botstats)
        await ctx.send(f"Botstats toggle: {not botstats}.")
        if botstats is not False:
            await self.bot.change_presence(activity=None)

    @rndstatus.command()
    async def delay(self, ctx, seconds: int):
        """Sets interval of random status switch.
        Must be 20 or superior."""
        if seconds < 20:
            seconds = 20
        await self.config.delay.set(seconds)
        await ctx.send(f"Interval set to {seconds} seconds.")

    @rndstatus.command()
    async def type(self, ctx, type: int):
        """Define the rndstatus type.

        Type list:
        0 = Playing
        1 = Streaming
        2 = Listening
        3 = Watching"""
        if 0 <= type <= 3:
            await self.config.type.set(type)
            await ctx.send("Rndstatus type set.")
        else:
            await ctx.send("Type must be between 0 and 3.")

    async def maybe_update_presence(self):
        await self.bot.wait_until_ready()
        pattern = re.compile(rf"<@!?{self.bot.user.id}>")
        delay = 0
        while True:
            try:
                cog_settings = await self.config.all()
                guilds = self.bot.guilds
                guild = next(g for g in guilds if not g.unavailable)
                try:
                    current_game = str(guild.me.activity.name)
                except AttributeError:
                    current_game = None
                statuses = cog_settings["statuses"]
                botstats = cog_settings["botstats"]
                streamer = cog_settings["streamer"]
                _type = cog_settings["type"]
                delay = cog_settings["delay"]

                url = f"https://www.twitch.tv/{streamer}"
                prefix = await self.bot.get_valid_prefixes()

                if botstats:
                    me = self.bot.user
                    clean_prefix = pattern.sub(f"@{me.name}", prefix[0])
                    total_users = self._user_count
                    servers = str(len(self.bot.guilds))
                    botstatus = f"{clean_prefix}help | {total_users} users | {servers} servers"
                    if (current_game != str(botstatus)) or current_game is None:
                        if _type == 1:
                            await self.bot.change_presence(activity=discord.Streaming(name=botstatus, url=url))
                        else:
                            await self.bot.change_presence(activity=discord.Activity(name=botstatus, type=_type))
                else:
                    if len(statuses) > 0:
                        new_status = self.random_status(guild, statuses)
                        if current_game != new_status:
                            if (current_game != new_status) or current_game is None:
                                if _type == 1:
                                    await self.bot.change_presence(activity=discord.Streaming(name=new_status, url=url))
                                else:
                                    await self.bot.change_presence(
                                        activity=discord.Activity(name=new_status, type=_type)
                                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.exception(e, exc_info=e)
            await asyncio.sleep(int(delay))
            

    def random_status(self, guild, statuses):
        try:
            current = str(guild.me.activity.name)
        except AttributeError:
            current = None
        new_statuses = [s for s in statuses if s != current]
        if len(new_statuses) > 1:
            return rndchoice(new_statuses)
        elif len(new_statuses) == 1:
            return new_statuses[0]
        return current
