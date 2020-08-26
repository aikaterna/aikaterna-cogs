from typing import Literal

import asyncio
import discord
import datetime
import math
import random
import time

from redbot.core import checks, commands, Config
from redbot.core.utils.chat_formatting import bold, box, humanize_list, humanize_number, pagify
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


__version__ = "3.1.4"


class Hunting(commands.Cog):
    """Hunting, it hunts birds and things that fly."""

    async def red_delete_data_for_user(
        self, *, requester: Literal["discord", "owner", "user", "user_strict"], user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2784481002, force_registration=True)

        self.animals = {
            "dove": ":dove: **_Coo!_**",
            "penguin": ":penguin: **_Noot!_**",
            "chicken": ":chicken: **_Bah-gawk!_**",
            "duck": ":duck: **_Quack!_**",
        }
        self.in_game = []
        self.paused_games = []
        self.next_bang = {}
        self.game_tasks = []

        default_guild = {
            "hunt_interval_minimum": 900,
            "hunt_interval_maximum": 3600,
            "wait_for_bang_timeout": 20,
            "channels": [],
            "bang_time": False,
            "bang_words": True,
        }
        default_user = {"score": {}, "total": 0}
        self.config.register_user(**default_user)
        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @commands.group()
    async def hunting(self, ctx):
        """Hunting, it hunts birds and things that fly."""
        if ctx.invoked_subcommand is None:
            guild_data = await self.config.guild(ctx.guild).all()
            if not guild_data["channels"]:
                channel_names = ["No channels set."]
            else:
                channel_names = []
                for channel_id in guild_data["channels"]:
                    channel_obj = self.bot.get_channel(channel_id)
                    channel_names.append(channel_obj.name)

            hunting_mode = "Words" if guild_data["bang_words"] else "Reactions"
            reaction_time = "On" if guild_data["bang_time"] else "Off"

            msg = f"[Hunting in]:                 {humanize_list(channel_names)}\n"
            msg += f"[Bang timeout]:               {guild_data['wait_for_bang_timeout']} seconds\n"
            msg += f"[Hunt interval minimum]:      {guild_data['hunt_interval_minimum']} seconds\n"
            msg += f"[Hunt interval maximum]:      {guild_data['hunt_interval_maximum']} seconds\n"
            msg += f"[Hunting mode]:               {hunting_mode}\n"
            msg += f"[Bang response time message]: {reaction_time}\n"

            for page in pagify(msg, delims=["\n"]):
                await ctx.send(box(page, lang="ini"))

    @hunting.command()
    async def leaderboard(self, ctx, global_leaderboard=False):
        """
        This will show the top 50 hunters for the server.
        Use True for the global_leaderboard variable to show the global leaderboard.
        """
        userinfo = await self.config._all_from_scope(scope="USER")
        if not userinfo:
            return await ctx.send(bold("Please shoot something before you can brag about it."))

        async with ctx.typing():
            sorted_acc = sorted(userinfo.items(), key=lambda x: (x[1]["total"]), reverse=True)[:50]

        if not hasattr(ctx.guild, "members"):
            global_leaderboard = True

        pound_len = len(str(len(sorted_acc)))
        score_len = 10
        header = "{score:{score_len}}{name:2}\n".format(
            score="# Birds Shot",
            score_len=score_len + 5,
            name="Name" if not str(ctx.author.mobile_status) in ["online", "idle", "dnd"] else "Name",
        )
        temp_msg = header
        for account in sorted_acc:
            if account[1]["total"] == 0:
                continue
            if global_leaderboard or (account[0] in [member.id for member in ctx.guild.members]):
                user_obj = self.bot.get_user(account[0]) or account[0]
            else:
                continue
            if isinstance(user_obj, discord.User) and len(str(user_obj)) > 28:
                user_name = f"{user_obj.name[:19]}...#{user_obj.discriminator}"
            else:
                user_name = str(user_obj)
            if user_obj == ctx.author:
                temp_msg += f"{humanize_number(account[1]['total']) + '   ': <{score_len + 4}} <<{user_name}>>\n"
            else:
                temp_msg += f"{humanize_number(account[1]['total']) + '   ': <{score_len + 4}} {user_name}\n"

        page_list = []
        pages = 1
        for page in pagify(temp_msg, delims=["\n"], page_length=800):
            if global_leaderboard:
                title = "Global Hunting Leaderboard"
            else:
                title = f"Hunting Leaderboard For {ctx.guild.name}"
            embed = discord.Embed(
                colour=await ctx.bot.get_embed_color(location=ctx.channel),
                description=box(title, lang="prolog") + (box(page, lang="md")),
            )
            embed.set_footer(text=f"Page {humanize_number(pages)}/{humanize_number(math.ceil(len(temp_msg) / 800))}")
            pages += 1
            page_list.append(embed)
        if len(page_list) == 1:
            await ctx.send(embed=page_list[0])
        else:
            await menu(ctx, page_list, DEFAULT_CONTROLS)

    @checks.mod_or_permissions(manage_guild=True)
    @hunting.command()
    async def bangtime(self, ctx):
        """Toggle displaying the bang response time from users."""
        toggle = await self.config.guild(ctx.guild).bang_time()
        await self.config.guild(ctx.guild).bang_time.set(not toggle)
        toggle_text = "will not" if toggle else "will"
        await ctx.send(f"Bang reaction time {toggle_text} be shown.\n")

    @checks.mod_or_permissions(manage_guild=True)
    @hunting.command()
    async def mode(self, ctx):
        """Toggle whether the bot listens for 'bang' or a reaction."""
        toggle = await self.config.guild(ctx.guild).bang_words()
        await self.config.guild(ctx.guild).bang_words.set(not toggle)
        toggle_text = "Use the reaction" if toggle else "Type 'bang'"
        await ctx.send(f"{toggle_text} to react to the bang message when it appears.\n")

    @checks.mod_or_permissions(manage_guild=True)
    @hunting.command()
    async def next(self, ctx):
        """When will the next occurrence happen?"""
        try:
            self.next_bang[ctx.guild.id]
            time = abs(datetime.datetime.utcnow() - self.next_bang[ctx.guild.id])
            total_seconds = int(time.total_seconds())
            hours, remainder = divmod(total_seconds, 60 * 60)
            minutes, seconds = divmod(remainder, 60)
            message = f"The next occurrence will be in {hours} hours and {minutes} minutes."
        except KeyError:
            message = "There is currently no hunt."
        await ctx.send(bold(message))

    @hunting.command(name="score")
    async def score(self, ctx, member: discord.Member = None):
        """This will show the score of a hunter."""
        if not member:
            member = ctx.author
        score = await self.config.user(member).score()
        total = 0
        kill_list = []
        if not score:
            message = "Please shoot something before you can brag about it."

        for animal in score.items():
            total = total + animal[1]
            if animal[1] == 1 or animal[0][-1] == "s":
                kill_list.append(f"{animal[1]} {animal[0].capitalize()}")
            else:
                kill_list.append(f"{animal[1]} {animal[0].capitalize()}s")
            message = f"{member.name} shot a total of {total} animals ({humanize_list(kill_list)})"
        await ctx.send(bold(message))

    @checks.mod_or_permissions(manage_guild=True)
    @hunting.command()
    async def start(self, ctx, channel: discord.TextChannel = None):
        """Start the hunt."""
        if not channel:
            channel = ctx.channel

        if not channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.send(bold("I can't send messages in that channel!"))

        channel_list = await self.config.guild(ctx.guild).channels()
        if channel.id in channel_list:
            message = f"We're already hunting in {channel.mention}!"
        else:
            channel_list.append(channel.id)
            message = f"The hunt has started in {channel.mention}. Good luck to all."
            await self.config.guild(ctx.guild).channels.set(channel_list)

        await ctx.send(bold(message))

    @checks.mod_or_permissions(manage_guild=True)
    @hunting.command()
    async def stop(self, ctx, channel: discord.TextChannel = None):
        """Stop the hunt."""
        if not channel:
            channel = ctx.channel
        channel_list = await self.config.guild(ctx.guild).channels()

        if channel.id not in channel_list:
            message = f"We're not hunting in {channel.mention}!"
        else:
            channel_list.remove(channel.id)
            message = f"The hunt has stopped in {channel.mention}."
            await self.config.guild(ctx.guild).channels.set(channel_list)

        await ctx.send(bold(message))

    @checks.mod_or_permissions(manage_guild=True)
    @hunting.command()
    async def timing(self, ctx, interval_min: int, interval_max: int, bang_timeout: int):
        """
        Change the hunting timing.
        
        `interval_min` = Minimum time in seconds for a new bird. (120s min)
        `interval_max` = Maximum time in seconds for a new bird. (240s min)
        `bang_timeout` = Time in seconds for users to shoot a bird before it flies away. (10s min)
        """
        message = ""
        if interval_min > interval_max:
            return await ctx.send("`interval_min` needs to be lower than `interval_max`.")
        if interval_min < 0 and interval_max < 0 and bang_timeout < 0:
            return await ctx.send("Please no negative numbers!")
        if interval_min < 120:
            interval_min = 120
            message += "Minimum interval set to minimum of 120s.\n"
        if interval_max < 240:
            interval_max = 240
            message += "Maximum interval set to minimum of 240s.\n"
        if bang_timeout < 10:
            bang_timeout = 10
            message += "Bang timeout set to minimum of 10s.\n"

        await self.config.guild(ctx.guild).hunt_interval_minimum.set(interval_min)
        await self.config.guild(ctx.guild).hunt_interval_maximum.set(interval_max)
        await self.config.guild(ctx.guild).wait_for_bang_timeout.set(bang_timeout)
        message += (
            f"Timing has been set:\nMin time {interval_min}s\nMax time {interval_max}s\nBang timeout {bang_timeout}s"
        )
        await ctx.send(bold(message))

    @hunting.command()
    async def version(self, ctx):
        """Show the cog version."""
        await ctx.send(f"Hunting version {__version__}.")

    async def _add_score(self, guild, author, avian):
        user_data = await self.config.user(author).all()
        try:
            user_data["score"][avian] += 1
        except KeyError:
            user_data["score"][avian] = 1
        user_data["total"] += 1
        await self.config.user(author).set_raw(value=user_data)

    async def _latest_message_check(self, channel):
        hunt_int_max = await self.config.guild(channel.guild).hunt_interval_maximum()
        async for message in channel.history(limit=5):
            delta = datetime.datetime.utcnow() - message.created_at
            if delta.total_seconds() < hunt_int_max * 2 and message.author.id != self.bot.user.id:
                if channel.id in self.paused_games:
                    self.paused_games.remove(channel.id)
                return True
        if channel.id not in self.paused_games:
            self.paused_games.append(channel.id)
            await channel.send(
                bold("It seems there are no hunters here. The hunt will be resumed when someone treads here again.")
            )
        return False

    def _next_sorter(self, guild_id, value):
        try:
            self.next_bang[guild_id]
        except KeyError:
            self.next_bang[guild_id] = value

    async def _wait_for_bang(self, guild, channel):
        animal = random.choice(list(self.animals.keys()))
        animal_message = await channel.send(self.animals[animal])
        now = time.time()
        timeout = await self.config.guild(guild).wait_for_bang_timeout()

        shooting_type = await self.config.guild(guild).bang_words()
        if shooting_type:

            def check(message):
                if guild != message.guild:
                    return False
                if channel != message.channel:
                    return False
                return message.content.lower().split(" ")[0] == "bang" if message.content else False

            try:
                bang_msg = await self.bot.wait_for("message", check=check, timeout=timeout)
            except asyncio.TimeoutError:
                self.in_game.remove(channel.id)
                return await channel.send(f"The {animal} got away!")
            author = bang_msg.author

        else:
            emoji = "\N{COLLISION SYMBOL}"
            await animal_message.add_reaction(emoji)

            def check(reaction, user):
                if user.bot:
                    return False
                if guild != reaction.message.guild:
                    return False
                if channel != reaction.message.channel:
                    return False
                return user and str(reaction.emoji) == "💥"

            try:
                await self.bot.wait_for("reaction_add", check=check, timeout=timeout)
            except asyncio.TimeoutError:
                self.in_game.remove(channel.id)
                return await channel.send(f"The {animal} got away!")

            message_with_reacts = await animal_message.channel.fetch_message(animal_message.id)
            reacts = message_with_reacts.reactions[0]
            async for user in reacts.users():
                if user.bot:
                    continue
                author = user
                break

        bang_now = time.time()
        time_for_bang = "{:.3f}".format(bang_now - now)
        bangtime = "" if not await self.config.guild(guild).bang_time() else f" in {time_for_bang}s"

        if random.randrange(0, 17) > 1:
            await self._add_score(guild, author, animal)
            msg = f"{author.display_name} shot a {animal}{bangtime}!"
        else:
            msg = f"{author.display_name} missed the shot and the {animal} got away!"

        self.in_game.remove(channel.id)
        await channel.send(bold(msg))

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if message.author.bot:
            return
        if not message.channel.permissions_for(message.guild.me).send_messages:
            return
        if message.channel.id in self.in_game:
            return
        channel_list = await self.config.guild(message.guild).channels()
        if not channel_list:
            return
        if message.channel.id not in channel_list:
            return

        if await self._latest_message_check(message.channel):
            self.in_game.append(message.channel.id)

        guild_data = await self.config.guild(message.guild).all()
        wait_time = random.randrange(guild_data["hunt_interval_minimum"], guild_data["hunt_interval_maximum"])
        self.next_bang[message.guild.id] = datetime.datetime.fromtimestamp(
            int(time.mktime(datetime.datetime.utcnow().timetuple())) + wait_time
        )
        await asyncio.sleep(wait_time)
        task = self.bot.loop.create_task(self._wait_for_bang(message.guild, message.channel))
        self.game_tasks.append(task)
        try:
            del self.next_bang[message.guild.id]
        except KeyError:
            pass

    def cog_unload(self):
        for task in self.game_tasks:
            task.cancel()
