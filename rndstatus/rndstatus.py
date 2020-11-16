import re
import discord
from redbot.core import Config, commands, checks
from redbot.core.utils import AsyncIter
from random import choice as rndchoice
from collections import defaultdict
import contextlib
import asyncio
import logging


log = logging.getLogger("red.aikaterna.rndstatus")


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

        self.presence_task = asyncio.create_task(self.maybe_update_presence())

        default_global = {
            "botstats": False,
            "delay": 300,
            "statuses": ["her Turn()", "Tomb Raider II", "Transistor", "NEO Scavenger", "Python", "with your heart.",],
            "streamer": "rndstatusstreamer",
            "type": 0,
            "status": 0,
        }
        self.config.register_global(**default_global)

    def cog_unload(self):
        self.presence_task.cancel()

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
            msg = (
                f"Current statuses: {(' | ').join(saved_status)}\n"
                f"To set new statuses, use the instructions in `{ctx.prefix}help rndstatus set`."
            )
            return await ctx.send(msg)
        await self.config.statuses.set(list(statuses))
        await self.presence_updater()
        await ctx.send("Done. Redo this command with no parameters to see the current list of statuses.")

    @rndstatus.command(name="streamer")
    async def _streamer(self, ctx: commands.Context, *, streamer=None):
        """Set the streamer name needed for streaming statuses."""
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
        await self.presence_updater()

    @rndstatus.command()
    async def delay(self, ctx, seconds: int):
        """Sets interval of random status switch.
        Must be 20 or superior."""
        if seconds < 20:
            seconds = 20
        await self.config.delay.set(seconds)
        await ctx.send(f"Interval set to {seconds} seconds.")

    @rndstatus.command(name="type")
    async def _rndstatus_type(self, ctx, status_type: int):
        """Define the rndstatus game type.

        Type list:
        0 = Playing
        1 = Streaming
        2 = Listening
        3 = Watching
        5 = Competing"""
        if 0 <= status_type <= 3 or 0 != 5:
            rnd_type = {0: "playing", 1: "streaming", 2: "listening", 3: "watching", 5: "competing"}
            await self.config.type.set(status_type)
            await self.presence_updater()
            await ctx.send(f"Rndstatus activity type set to {rnd_type[status_type]}.")
        else:
            await ctx.send(
                f"Status activity type must be between 0 and 3 or 5. "
                f"See `{ctx.prefix}help rndstatus type` for more information."
            )

    @rndstatus.command()
    async def status(self, ctx, status: int):
        """Define the rndstatus presence status.

        Status list:
        0 = Online
        1 = Idle
        2 = DND
        3 = Invisible"""
        if 0 <= status <= 3:
            rnd_status = {0: "online", 1: "idle", 2: "DND", 3: "invisible"}
            await self.config.status.set(status)
            await self.presence_updater()
            await ctx.send(f"Rndstatus presence status set to {rnd_status[status]}.")
        else:
            await ctx.send(
                f"Status presence type must be between 0 and 3. "
                f"See `{ctx.prefix}help rndstatus status` for more information."
            )

    async def maybe_update_presence(self):
        await self.bot.wait_until_red_ready()
        delay = await self.config.delay()
        while True:
            try:
                await self.presence_updater()
                await asyncio.sleep(int(delay))
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.exception(e, exc_info=e)

    async def presence_updater(self):
        pattern = re.compile(rf"<@!?{self.bot.user.id}>")
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
        _status = cog_settings["status"]

        url = f"https://www.twitch.tv/{streamer}"
        prefix = await self.bot.get_valid_prefixes()

        if _status == 0:
            status = discord.Status.online
        elif _status == 1:
            status = discord.Status.idle
        elif _status == 2:
            status = discord.Status.dnd
        elif _status == 3:
            status = discord.Status.offline

        if botstats:
            me = self.bot.user
            clean_prefix = pattern.sub(f"@{me.name}", prefix[0])
            total_users = len(self.bot.users)
            servers = str(len(self.bot.guilds))
            botstatus = f"{clean_prefix}help | {total_users} users | {servers} servers"
            if (current_game != str(botstatus)) or current_game is None:
                if _type == 1:
                    await self.bot.change_presence(activity=discord.Streaming(name=botstatus, url=url))
                else:
                    await self.bot.change_presence(activity=discord.Activity(name=botstatus, type=_type), status=status)
        else:
            if len(statuses) > 0:
                new_status = self.random_status(guild, statuses)
                if (current_game != new_status) or (current_game is None) or (len(statuses) == 1):
                    if _type == 1:
                        await self.bot.change_presence(activity=discord.Streaming(name=new_status, url=url))
                    else:
                        await self.bot.change_presence(
                            activity=discord.Activity(name=new_status, type=_type), status=status
                        )

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
