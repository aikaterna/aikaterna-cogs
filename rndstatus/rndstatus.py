import discord
from redbot.core import Config, commands, checks
from random import choice as rndchoice
import time


class RndStatus:
    """Cycles random statuses or displays bot stats.

    If a custom status is already set, it won't change it until
    it's back to none. [p]set game"""

    def __init__(self, bot):
        self.bot = bot
        self.last_change = None
        self.config = Config.get_conf(self, 2752521001, force_registration=True)

        default_global = {
            "botstats": False,
            "delay": "300",
            "statuses": [
                "her Turn()",
                "Tomb Raider II",
                "Transistor",
                "NEO Scavenger",
                "Python",
                "with your heart.",
            ],
            "type": "1",
        }

        self.config.register_global(**default_global)

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
        await ctx.send(
            "Done. Redo this command with no parameters to see the current list of statuses."
        )

    @rndstatus.command()
    async def botstats(self, ctx, *statuses: str):
        """Toggle for a bot stats status instead of random messages."""
        botstats = await self.config.botstats()
        await self.config.botstats.set(not botstats)
        await ctx.send("Botstats toggle: {}.".format(not botstats))
        if not botstats == False:
            await self.bot.change_presence(activity=None)

    @rndstatus.command()
    async def delay(self, ctx, seconds: int):
        """Sets interval of random status switch.

        Must be 20 or superior."""
        if seconds < 20:
            seconds = 20
        await self.config.delay.set(seconds)
        await ctx.send(f"Interval set to {str(seconds)} seconds.")

    @rndstatus.command()
    async def type(self, ctx, type: int):
        """Define the rndstatus type.
        
        Type list:
        1 = Playing
        2 = Listening
        3 = Watching"""
        await self.config.type.set(type)
        await ctx.send("Rndstatus type set.")

    async def switch_status(self, message):
        try:
            current_game = str(message.guild.me.activity.name)
        except AttributeError:
            current_game = None
        statuses = await self.config.statuses()
        botstats = await self.config.botstats()
        prefix = await self.bot.db.prefix()

        if botstats:
            total_users = sum(len(s.members) for s in self.bot.guilds)
            servers = str(len(self.bot.guilds))
            botstatus = f"{prefix[0]}help | {total_users} users | {servers} servers"
            if self.last_change == None:
                type = await self.config.type()
                await self.bot.change_presence(
                    activity=discord.Activity(name=botstatus, type=type)
                )
                self.last_change = int(time.perf_counter())
            if message.author.id == self.bot.user.id:
                return
            delay = await self.config.delay()
            if abs(self.last_change - int(time.perf_counter())) < int(delay):
                return
            self.last_change = int(time.perf_counter())
            if (current_game != str(botstatus)) or current_game == None:
                type = await self.config.type()
                return await self.bot.change_presence(
                    activity=discord.Activity(name=botstatus, type=type)
                )

        if self.last_change == None:
            self.last_change = int(time.perf_counter())
            if len(statuses) > 0 and (current_game in statuses or current_game == None):
                new_status = self.random_status(message, statuses)
                type = await self.config.type()
                await self.bot.change_presence(
                    activity=discord.Activity(name=new_status, type=type)
                )

        if message.author.id != self.bot.user.id:
            delay = await self.config.delay()
            if abs(self.last_change - int(time.perf_counter())) >= int(delay):
                self.last_change = int(time.perf_counter())
                new_status = self.random_status(message, statuses)
                if current_game != new_status:
                    if current_game in statuses or current_game == None:
                        type = await self.config.type()
                        await self.bot.change_presence(
                            activity=discord.Activity(name=new_status, type=type)
                        )

    def random_status(self, msg, statuses):
        try:
            current = str(msg.guild.me.activity.name)
        except AttributeError:
            current = None
        try:
            new = str(msg.guild.me.activity.name)
        except AttributeError:
            new = None
        if len(statuses) > 1:
            while current == new:
                new = rndchoice(statuses)
        elif len(statuses) == 1:
            new = statuses[0]
        else:
            new = None
        return new
