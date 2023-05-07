#  This cog is influenced heavily by cacobot's stats module:
#  https://github.com/Orangestar12/cacobot/blob/master/cacobot/stats.py
#  Big thanks to Redjumpman for changing the beta version from
#  Imagemagick/cairosvg to matplotlib.
#  Thanks to violetnyte for suggesting this cog.

import asyncio
import discord
import heapq
from io import BytesIO
from typing import List, Optional, Tuple, Union

from redbot.core import checks, commands, Config

import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
plt.switch_backend("agg")


class Chatchart(commands.Cog):
    """Show activity."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2766691001, force_registration=True)

        default_guild = {"channel_deny": []}
        default_global = {"limit": 0}

        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

    @staticmethod
    def calculate_member_perc(history: List[discord.Message]) -> dict:
        """Calculate the member count from the message history"""
        msg_data = {"total_count": 0, "users": {}}
        for msg in history:
            # Name formatting
            if len(msg.author.display_name) >= 20:
                short_name = "{}...".format(msg.author.display_name[:20]).replace("$", "\\$")
            else:
                short_name = msg.author.display_name.replace("$", "\\$").replace("_", "\\_ ").replace("*", "\\*")
            whole_name = "{}#{}".format(short_name, msg.author.discriminator)
            if msg.author.bot:
                pass
            elif whole_name in msg_data["users"]:
                msg_data["users"][whole_name]["msgcount"] += 1
                msg_data["total_count"] += 1
            else:
                msg_data["users"][whole_name] = {}
                msg_data["users"][whole_name]["msgcount"] = 1
                msg_data["total_count"] += 1
        return msg_data

    @staticmethod
    def calculate_top(msg_data: dict) -> Tuple[list, int]:
        """Calculate the top 20 from the message data package"""
        for usr in msg_data["users"]:
            pd = float(msg_data["users"][usr]["msgcount"]) / float(msg_data["total_count"])
            msg_data["users"][usr]["percent"] = pd * 100
        top_twenty = heapq.nlargest(
            20,
            [
                (x, msg_data["users"][x][y])
                for x in msg_data["users"]
                for y in msg_data["users"][x]
                if (y == "percent" and msg_data["users"][x][y] > 0)
            ],
            key=lambda x: x[1],
        )
        others = 100 - sum(x[1] for x in top_twenty)
        return top_twenty, others

    @staticmethod
    async def create_chart(top, others, channel_or_guild: Union[discord.Guild, discord.TextChannel]):
        plt.clf()
        sizes = [x[1] for x in top]
        labels = ["{} {:g}%".format(x[0], round(x[1], 1)) for x in top]
        if len(top) >= 20:
            sizes = sizes + [others]
            labels = labels + ["Others {:g}%".format(round(others, 1))]
        if len(channel_or_guild.name) >= 19:
            if isinstance(channel_or_guild, discord.Guild):
                channel_or_guild_name = "{}...".format(channel_or_guild.name[:19])
            else:
                channel_or_guild_name = "#{}...".format(channel_or_guild.name[:19])
        else:
            channel_or_guild_name = channel_or_guild.name
        title = plt.title("Stats in {}".format(channel_or_guild_name), color="white")
        title.set_va("top")
        title.set_ha("center")
        plt.gca().axis("equal")
        colors = [
            "r",
            "darkorange",
            "gold",
            "y",
            "olivedrab",
            "green",
            "darkcyan",
            "mediumblue",
            "darkblue",
            "blueviolet",
            "indigo",
            "orchid",
            "mediumvioletred",
            "crimson",
            "chocolate",
            "yellow",
            "limegreen",
            "forestgreen",
            "dodgerblue",
            "slateblue",
            "gray",
        ]
        pie = plt.pie(sizes, colors=colors, startangle=0)
        plt.legend(
            pie[0],
            labels,
            bbox_to_anchor=(0.7, 0.5),
            loc="center",
            fontsize=10,
            bbox_transform=plt.gcf().transFigure,
            facecolor="#ffffff",
        )
        plt.subplots_adjust(left=0.0, bottom=0.1, right=0.45)
        image_object = BytesIO()
        plt.savefig(image_object, format="PNG", facecolor="#36393E")
        image_object.seek(0)
        return image_object

    async def fetch_channel_history(
        self,
        channel: discord.TextChannel,
        animation_message: discord.Message,
        messages: int
    ) -> List[discord.Message]:
        """Fetch the history of a channel while displaying an status message with it"""
        animation_message_deleted = False
        history = []
        history_counter = 0
        async for msg in channel.history(limit=messages):
            history.append(msg)
            history_counter += 1
            await asyncio.sleep(0.005)
            if history_counter % 250 == 0:
                new_embed = discord.Embed(
                    title=f"Fetching messages from #{channel.name}",
                    description=f"This might take a while...\n{history_counter}/{messages} messages gathered",
                    colour=await self.bot.get_embed_colour(location=channel),
                )
                if channel.permissions_for(channel.guild.me).send_messages:
                    await channel.typing()
                if animation_message_deleted is False:
                    try:
                        await animation_message.edit(embed=new_embed)
                    except discord.NotFound:
                        animation_message_deleted = True
        return history

    @commands.guild_only()
    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.bot_has_permissions(attach_files=True)
    async def chatchart(self, ctx, channel: Optional[discord.TextChannel] = None, messages:int = 5000):
        """
        Generates a pie chart, representing the last 5000 messages in the specified channel.
        """
        if channel is None:
            channel = ctx.channel

        # --- Early terminations
        if channel.permissions_for(ctx.message.author).read_messages is False:
            return await ctx.send("You're not allowed to access that channel.")
        if channel.permissions_for(ctx.guild.me).read_messages is False:
            return await ctx.send("I cannot read the history of that channel.")
        blacklisted_channels = await self.config.guild(ctx.guild).channel_deny()
        if channel.id in blacklisted_channels:
            return await ctx.send(f"I am not allowed to create a chatchart of {channel.mention}.")
        if messages < 5:
            return await ctx.send("Don't be silly.")

        message_limit = await self.config.limit()
        if (message_limit != 0) and (messages > message_limit):
            messages = message_limit

        embed = discord.Embed(
            title=f"Fetching messages from #{channel.name}",
            description="This might take a while...",
            colour=await self.bot.get_embed_colour(location=channel)
        )
        loading_message = await ctx.send(embed=embed)
        try:
            history = await self.fetch_channel_history(channel, loading_message, messages)
        except discord.errors.Forbidden:
            try:
                await loading_message.delete()
            except discord.NotFound:
                pass
            return await ctx.send("No permissions to read that channel.")

        msg_data = self.calculate_member_perc(history)
        # If no members are found.
        if len(msg_data["users"]) == 0:
            try:
                await loading_message.delete()
            except discord.NotFound:
                pass
            return await ctx.send(f"Only bots have sent messages in {channel.mention} or I can't read message history.")

        top_twenty, others = self.calculate_top(msg_data)
        chart = await self.create_chart(top_twenty, others, channel)

        try:
            await loading_message.delete()
        except discord.NotFound:
            pass
        await ctx.send(file=discord.File(chart, "chart.png"))

    @checks.mod_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.command(aliases=["guildchart"])
    @commands.cooldown(1, 30, commands.BucketType.guild)
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.bot_has_permissions(attach_files=True)
    async def serverchart(self, ctx: commands.Context, messages: int = 1000):
        """
        Generates a pie chart, representing the last 1000 messages from every allowed channel in the server.

        As example:
        For each channel that the bot is allowed to scan. It will take the last 1000 messages from each channel.
        And proceed to build a chart out of that.
        """
        if messages < 5:
            return await ctx.send("Don't be silly.")
        channel_list = []
        blacklisted_channels = await self.config.guild(ctx.guild).channel_deny()
        for channel in ctx.guild.text_channels:
            channel: discord.TextChannel
            if channel.id in blacklisted_channels:
                continue
            if channel.permissions_for(ctx.message.author).read_messages is False:
                continue
            if channel.permissions_for(ctx.guild.me).read_messages is False:
                continue
            channel_list.append(channel)

        if len(channel_list) == 0:
            return await ctx.send("There are no channels to read... This should theoretically never happen.")

        embed = discord.Embed(
            description="Fetching messages from the entire server this **will** take a while.",
            colour=await self.bot.get_embed_colour(location=ctx.channel),
        )
        global_fetch_message = await ctx.send(embed=embed)
        global_history = []

        for channel in channel_list:
            embed = discord.Embed(
                title=f"Fetching messages from #{channel.name}",
                description="This might take a while...",
                colour=await self.bot.get_embed_colour(location=channel)
            )
            loading_message = await ctx.send(embed=embed)
            try:
                history = await self.fetch_channel_history(channel, loading_message, messages)
                global_history += history
                await loading_message.delete()
            except discord.errors.Forbidden:
                try:
                    await loading_message.delete()
                except discord.NotFound:
                    continue
            except discord.NotFound:
                try:
                    await loading_message.delete()
                except discord.NotFound:
                    continue 

        msg_data = self.calculate_member_perc(global_history)
        # If no members are found.
        if len(msg_data["users"]) == 0:
            try:
                await global_fetch_message.delete()
            except discord.NotFound:
                pass
            return await ctx.send(f"Only bots have sent messages in this server... Wauw...")

        top_twenty, others = self.calculate_top(msg_data)
        chart = await self.create_chart(top_twenty, others, ctx.guild)

        try:
            await global_fetch_message.delete()
        except discord.NotFound:
            pass
        await ctx.send(file=discord.File(chart, "chart.png"))

    @checks.mod_or_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.command()
    async def ccdeny(self, ctx, channel: discord.TextChannel):
        """Add a channel to deny chatchart use."""
        channel_list = await self.config.guild(ctx.guild).channel_deny()
        if channel.id not in channel_list:
            channel_list.append(channel.id)
        await self.config.guild(ctx.guild).channel_deny.set(channel_list)
        await ctx.send(f"{channel.mention} was added to the deny list for chatchart.")

    @checks.mod_or_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.command()
    async def ccdenylist(self, ctx):
        """List the channels that are denied."""
        no_channels_msg = "Chatchart is currently allowed everywhere in this server."
        channel_list = await self.config.guild(ctx.guild).channel_deny()
        if not channel_list:
            msg = no_channels_msg
        else:
            msg = "Chatchart is not allowed in:\n"
            remove_list = []
            for channel in channel_list:
                channel_obj = self.bot.get_channel(channel)
                if not channel_obj:
                    remove_list.append(channel)
                else:
                    msg += f"{channel_obj.mention}\n"
            if remove_list:
                new_list = [x for x in channel_list if x not in remove_list]
                await self.config.guild(ctx.guild).channel_deny.set(new_list)
                if len(remove_list) == len(channel_list):
                    msg = no_channels_msg
        await ctx.send(msg)

    @checks.mod_or_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.command()
    async def ccallow(self, ctx, channel: discord.TextChannel):
        """Remove a channel from the deny list to allow chatchart use."""
        channel_list = await self.config.guild(ctx.guild).channel_deny()
        if channel.id in channel_list:
            channel_list.remove(channel.id)
        else:
            return await ctx.send("Channel is not on the deny list.")
        await self.config.guild(ctx.guild).channel_deny.set(channel_list)
        await ctx.send(f"{channel.mention} will be allowed for chatchart use.")

    @checks.is_owner()
    @commands.command()
    async def cclimit(self, ctx, limit_amount: int = None):
        """
        Limit the amount of messages someone can request.

        Use `0` for no limit.
        """
        if limit_amount is None:
            return await ctx.send_help()
        if limit_amount < 0:
            return await ctx.send("You need to use a number larger than 0.")
        await self.config.limit.set(limit_amount)
        await ctx.send(f"Chatchart is now limited to {limit_amount} messages.")
