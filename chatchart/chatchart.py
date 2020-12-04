#  This cog is influenced heavily by cacobot's stats module:
#  https://github.com/Orangestar12/cacobot/blob/master/cacobot/stats.py
#  Big thanks to Redjumpman for changing the beta version from
#  Imagemagick/cairosvg to matplotlib.
#  Thanks to violetnyte for suggesting this cog.

import asyncio
import discord
import heapq
from io import BytesIO
from typing import Optional

import matplotlib

matplotlib.use("agg")
import matplotlib.pyplot as plt

plt.switch_backend("agg")

from redbot.core import checks, commands, Config


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
    async def create_chart(top, others, channel):
        plt.clf()
        sizes = [x[1] for x in top]
        labels = ["{} {:g}%".format(x[0], x[1]) for x in top]
        if len(top) >= 20:
            sizes = sizes + [others]
            labels = labels + ["Others {:g}%".format(others)]
        if len(channel.name) >= 19:
            channel_name = "{}...".format(channel.name[:19])
        else:
            channel_name = channel.name
        title = plt.title("Stats in #{}".format(channel_name), color="white")
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

    @commands.guild_only()
    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.channel)
    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.bot_has_permissions(attach_files=True)
    async def chatchart(self, ctx, channel: Optional[discord.TextChannel] = None, messages=5000):
        """
        Generates a pie chart, representing the last 5000 messages in the specified channel.
        """
        if channel is None:
            channel = ctx.channel
        deny = await self.config.guild(ctx.guild).channel_deny()
        if channel.id in deny:
            return await ctx.send(f"I am not allowed to create a chatchart of {channel.mention}.")

        message_limit = await self.config.limit()
        if (message_limit != 0) and (messages > message_limit):
            messages = message_limit

        e = discord.Embed(
            description="This might take a while...", colour=await self.bot.get_embed_colour(location=channel)
        )
        em = await ctx.send(embed=e)

        history = []
        history_counter = 0

        if not channel.permissions_for(ctx.message.author).read_messages == True:
            try:
                await em.delete()
            except discord.NotFound:
                pass
            return await ctx.send("You're not allowed to access that channel.")
        try:
            async for msg in channel.history(limit=messages):
                history.append(msg)
                history_counter += 1
                await asyncio.sleep(0.005)
                if history_counter % 250 == 0:
                    new_embed = discord.Embed(
                        description=f"This might take a while...\n{history_counter}/{messages} messages gathered",
                        colour=await self.bot.get_embed_colour(location=channel),
                    )
                    if channel.permissions_for(ctx.guild.me).send_messages:
                        await channel.trigger_typing()
                    try:
                        await em.edit(embed=new_embed)
                    except discord.NotFound:
                        pass # for cases where the embed was deleted preventing the edit

        except discord.errors.Forbidden:
            try:
                await em.delete()
            except discord.NotFound:
                pass
            return await ctx.send("No permissions to read that channel.")

        msg_data = {"total count": 0, "users": {}}
        for msg in history:
            if len(msg.author.display_name) >= 20:
                short_name = "{}...".format(msg.author.display_name[:20]).replace("$", "\\$")
            else:
                short_name = msg.author.display_name.replace("$", "\\$").replace("_", "\\_ ").replace("*", "\\*")
            whole_name = "{}#{}".format(short_name, msg.author.discriminator)
            if msg.author.bot:
                pass
            elif whole_name in msg_data["users"]:
                msg_data["users"][whole_name]["msgcount"] += 1
                msg_data["total count"] += 1
            else:
                msg_data["users"][whole_name] = {}
                msg_data["users"][whole_name]["msgcount"] = 1
                msg_data["total count"] += 1

        if msg_data["users"] == {}:
            try:
                await em.delete()
            except discord.NotFound:
                pass
            return await ctx.send(f"Only bots have sent messages in {channel.mention} or I can't read message history.")

        for usr in msg_data["users"]:
            pd = float(msg_data["users"][usr]["msgcount"]) / float(msg_data["total count"])
            msg_data["users"][usr]["percent"] = round(pd * 100, 1)

        top_ten = heapq.nlargest(
            20,
            [
                (x, msg_data["users"][x][y])
                for x in msg_data["users"]
                for y in msg_data["users"][x]
                if (y == "percent" and msg_data["users"][x][y] > 0)
            ],
            key=lambda x: x[1],
        )
        others = 100 - sum(x[1] for x in top_ten)
        chart = await self.create_chart(top_ten, others, channel)

        try:
            await em.delete()
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
