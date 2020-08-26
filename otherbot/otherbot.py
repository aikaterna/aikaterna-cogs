from typing import Literal

import discord
from redbot.core.bot import Red
from redbot.core import commands, checks, Config

from datetime import datetime

DEFAULT_OFFLINE_EMOJI = "\N{LARGE RED CIRCLE}"
DEFAULT_ONLINE_EMOJI = "\N{WHITE HEAVY CHECK MARK}"


class Otherbot(commands.Cog):
    __author__ = ["aikaterna", "Predä 。#1001"]
    __version__ = "0.10"

    async def red_delete_data_for_user(
        self, *, requester: Literal["discord", "owner", "user", "user_strict"], user_id: int,
    ):
        if requester == "discord":
            # user is deleted, just comply

            data = await self.config.all_guilds()
            for guild_id, guild_data in data.items():
                if user_id in guild_data.get("watching", []):
                    bypass = guild_data.get("watching", [])
                    bypass = set(bypass)
                    bypass.discard(user_id)
                    await self.config.guild_from_id(guild_id).bypass.set(list(bypass))

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, 2730321001, force_registration=True)
        self.config.register_guild(
            ping=None,
            reporting=None,
            watching=[],
            online_watching=[],
            offline_emoji=DEFAULT_OFFLINE_EMOJI,
            online_emoji=DEFAULT_ONLINE_EMOJI,
            embed_offline=True,
            embed_online=True,
        )

    async def generate_cache(self):
        self.otherbot_cache = await self.config.all_guilds()

    def cog_unload(self):
        self.otherbot_cache.clear()

    async def get_watching(self, watch_list: list, watch_type: str, guild: int):
        data = []
        for user_id in watch_list:
            user = self.bot.get_user(user_id)
            if not user:
                async with self.config.guild_from_id(guild).all() as config:
                    config[watch_type].remove(user_id)
            else:
                data.append(user.mention)
        return data

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def otherbot(self, ctx: commands.Context):
        """Otherbot configuration options."""
        # Following logic from Trusty's welcome cog:
        # https://github.com/TrustyJAID/Trusty-cogs/blob/master/welcome/welcome.py#L81
        guild = ctx.guild
        if not ctx.invoked_subcommand:
            guild_data = await self.config.guild(guild).all()
            settings_name = dict(
                ping="Ping role",
                reporting="Channel reporting",
                watching="Offline tracking",
                online_watching="Online tracking",
                offline_emoji="Offline emoji",
                online_emoji="Online emoji",
                embed_offline="Offline embed",
                embed_online="Online embed",
            )
            msg = ""
            if ctx.channel.permissions_for(ctx.me).embed_links:
                em = discord.Embed(
                    color=await ctx.embed_colour(), title=f"Otherbot settings for {guild.name}"
                )
                for attr, name in settings_name.items():
                    if attr == "ping":
                        role = guild.get_role(guild_data["ping"])
                        if role:
                            msg += f"**{name}**: {role.mention}\n"
                        else:
                            msg += f"**{name}**: Not set.\n"
                    elif attr == "reporting":
                        channel = guild.get_channel(guild_data["reporting"])
                        if channel:
                            msg += f"**{name}**: {channel.mention}\n"
                        else:
                            msg += f"**{name}**: Not set.\n"
                    elif attr == "watching":
                        if guild_data["watching"]:
                            msg += (
                                f"**{name}**: "
                                + " ".join(
                                    await self.get_watching(
                                        guild_data["watching"], "watching", guild.id
                                    )
                                )
                                + "\n"
                            )
                        else:
                            msg += f"**{name}**: Not set.\n"
                    elif attr == "online_watching":
                        if guild_data["online_watching"]:
                            msg += (
                                f"**{name}**: "
                                + " ".join(
                                    await self.get_watching(
                                        guild_data["online_watching"], "online_watching", guild.id
                                    )
                                )
                                + "\n"
                            )
                        else:
                            msg += f"**{name}**: Not set.\n"
                    else:
                        msg += f"**{name}**: {guild_data[attr]}\n"
                em.description = msg
                em.set_thumbnail(url=guild.icon_url)
                await ctx.send(embed=em)
            else:
                msg = "```\n"
                for attr, name in settings_name.items():
                    if attr == "ping":
                        role = guild.get_role(guild_data["ping"])
                        if role:
                            msg += f"{name}: {role.mention}\n"
                        else:
                            msg += f"{name}: Not set.\n"
                    elif attr == "reporting":
                        channel = guild.get_channel(guild_data["reporting"])
                        if channel:
                            msg += f"{name}: {channel.mention}\n"
                        else:
                            msg += f"{name}: Not set.\n"
                    elif attr == "watching":
                        if guild_data["watching"]:
                            msg += (
                                f"{name}: "
                                + " ".join(
                                    await self.get_watching(
                                        guild_data["watching"], "watching", guild.id
                                    )
                                )
                                + "\n"
                            )
                        else:
                            msg += f"{name}: Not set."
                    elif attr == "online_watching":
                        if guild_data["online_watching"]:
                            msg += (
                                f"{name}: "
                                + " ".join(
                                    await self.get_watching(
                                        guild_data["online_watching"], "online_watching", guild.id
                                    )
                                )
                                + "\n"
                            )
                        else:
                            msg += f"{name}: Not set.\n"
                    else:
                        msg += f"**{name}**: {guild_data[attr]}\n"
                msg += "```"
                await ctx.send(msg)

    @otherbot.command()
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """
        Sets the channel to report in.
        
        Default to the current one.
        """
        if not channel:
            channel = ctx.channel
        await self.config.guild(ctx.guild).reporting.set(channel.id)
        await ctx.send(f"Reporting channel set to: {channel.mention}.")
        await self.generate_cache()

    @otherbot.command()
    async def pingrole(self, ctx: commands.Context, role_name: discord.Role = None):
        """Sets the role to use for pinging. Leave blank to reset it."""
        if not role_name:
            await self.config.guild(ctx.guild).ping.set(None)
            return await ctx.send("Ping role cleared.")
        await self.config.guild(ctx.guild).ping.set(role_name.id)
        pingrole_id = await self.config.guild(ctx.guild).ping()
        pingrole_obj = discord.utils.get(ctx.guild.roles, id=pingrole_id)
        await ctx.send(f"Ping role set to: `{pingrole_obj.name}`.")
        await self.generate_cache()

    @otherbot.group(name="watch", aliases=["watching"])
    async def otherbot_watch(self, ctx: commands.Context):
        """Watch settings."""

    @otherbot_watch.group(name="offline")
    async def otherbot_watch_offline(self, ctx: commands.Context):
        """Manage offline notifications."""

    @otherbot_watch_offline.command(name="add")
    async def otherbot_watch_offline_add(self, ctx: commands.Context, bot: discord.Member):
        """Add a bot that will be tracked when it goes offline."""
        if not bot.bot:
            return await ctx.send(
                "You can't track normal users. Please try again with a bot user."
            )

        async with self.config.guild(ctx.guild).watching() as watch_list:
            watch_list.append(bot.id)
        await ctx.send(f"I will now track {bot.mention} when it goes offline.")
        await self.generate_cache()

    @otherbot_watch_offline.command(name="remove")
    async def otherbot_watch_offline_remove(self, ctx: commands.Context, bot: discord.Member):
        """Removes a bot currently tracked."""
        if not bot.bot:
            return await ctx.send(
                "You can't choose a normal user. Please try again with a bot user."
            )

        async with self.config.guild(ctx.guild).watching() as watch_list:
            try:
                watch_list.remove(bot.id)
                await ctx.send(
                    f"Successfully removed {bot.mention} from offline tracked bot list."
                )
            except ValueError:
                await ctx.send(f"{bot.mention} is not currently tracked.")
        await self.generate_cache()

    @otherbot_watch_offline.command(name="list")
    async def otherbot_watch_offline_list(self, ctx: commands.Context):
        """Lists currently tracked bots."""
        watching = await self.config.guild(ctx.guild).watching()
        if not watching:
            return await ctx.send("There is currently no bots tracked for offline status.")

        watching_list = await self.get_watching(watching, "watching", ctx.guild.id)
        await ctx.send(
            f"{len(watching):,} bot{'s' if len(watching) > 1 else ''} are currently tracked for offline status:\n"
            + ", ".join(watching_list)
        )
        await self.generate_cache()

    @otherbot_watch_offline.command(name="emoji")
    async def otherbot_watch_offline_emoji(self, ctx: commands.Context, *, emoji: str = None):
        """Choose which emoji that will be used for offline messages."""
        if not emoji:
            await self.config.guild(ctx.guild).offline_emoji.set(DEFAULT_OFFLINE_EMOJI)
            await ctx.send(f"Offline emoji resetted to default: {DEFAULT_OFFLINE_EMOJI}")
        else:
            await self.config.guild(ctx.guild).offline_emoji.set(emoji)
            await ctx.tick()
        await self.generate_cache()

    @otherbot_watch_offline.command(name="embed")
    async def otherbot_watch_offline_embed(self, ctx: commands.Context):
        """Set wether you want to receive notifications in embed or not."""
        current = await self.config.guild(ctx.guild).embed_offline()
        await self.config.guild(ctx.guild).embed_offline.set(not current)
        await ctx.send(
            "I will now send offline notifications in embeds."
            if not current
            else "I will no longer send offline notifications in embeds."
        )
        await self.generate_cache()

    @otherbot_watch.group(name="online")
    async def otherbot_watch_online(self, ctx: commands.Context):
        """Manage online notifications."""

    @otherbot_watch_online.command(name="add")
    async def otherbot_watch_online_add(self, ctx: commands.Context, bot: discord.Member):
        """Add a bot that will be tracked when it comes back online."""
        if not bot.bot:
            return await ctx.send(
                "You can't track normal users. Please try again with a bot user."
            )

        async with self.config.guild(ctx.guild).online_watching() as watch_list:
            watch_list.append(bot.id)
        await ctx.send(f"I will now track {bot.mention} when it goes back online.")
        await self.generate_cache()

    @otherbot_watch_online.command(name="remove")
    async def otherbot_watch_online_remove(self, ctx: commands.Context, bot: discord.Member):
        """Removes a bot currently tracked."""
        if not bot.bot:
            return await ctx.send(
                "You can't choose a normal user. Please try again with a bot user."
            )

        async with self.config.guild(ctx.guild).online_watching() as watch_list:
            try:
                watch_list.remove(bot.id)
                await ctx.send(f"Successfully removed {bot.mention} from online tracked bot list.")
            except ValueError:
                await ctx.send(f"{bot.mention} is not currently tracked.")
        await self.generate_cache()

    @otherbot_watch_online.command(name="list")
    async def otherbot_watch_online_list(self, ctx: commands.Context):
        """Lists currently tracked bots."""
        watching = await self.config.guild(ctx.guild).online_watching()
        if not watching:
            return await ctx.send("There is currently no bots tracked for online status.")

        watching_list = await self.get_watching(watching, "online_watching", ctx.guild.id)
        await ctx.send(
            f"{len(watching):,} bot{'s' if len(watching) > 1 else ''} are currently tracked for online status:\n"
            + ", ".join(watching_list)
        )
        await self.generate_cache()

    @otherbot_watch_online.command(name="emoji")
    async def otherbot_watch_online_emoji(self, ctx: commands.Context, *, emoji: str = None):
        """Choose which emoji that will be used for online messages."""
        if not emoji:
            await self.config.guild(ctx.guild).online_emoji.set(DEFAULT_ONLINE_EMOJI)
            await ctx.send(f"Online emoji resetted to default: {DEFAULT_ONLINE_EMOJI}")
        else:
            await self.config.guild(ctx.guild).online_emoji.set(emoji)
            await ctx.tick()
        await self.generate_cache()

    @otherbot_watch_online.command(name="embed")
    async def otherbot_watch_online_embed(self, ctx: commands.Context):
        """Set wether you want to receive notifications in embed or not."""
        current = await self.config.guild(ctx.guild).embed_online()
        await self.config.guild(ctx.guild).embed_online.set(not current)
        await ctx.send(
            "I will now send online notifications in embeds."
            if not current
            else "I will no longer send online notifications in embeds."
        )
        await self.generate_cache()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.guild is None or not after.bot:
            return

        data = self.otherbot_cache.get(after.guild.id)
        if data is None:
            return
        channel = self.bot.get_channel(data["reporting"])
        if not channel:
            return
        if not (data["watching"] or data["online_watching"]):
            return
        if (
            before.status != discord.Status.offline
            and after.status == discord.Status.offline
            and (after.id in data["watching"])
        ):
            try:
                if data["embed_offline"]:
                    em = discord.Embed(
                        color=0x8B0000,
                        description=f"{after.mention} is offline. {data['offline_emoji']}",
                        timestamp=datetime.utcnow(),
                    )
                    if not data["ping"]:
                        await channel.send(embed=em)
                    else:
                        if discord.version_info.minor < 4:
                            await channel.send(f"<@&{data['ping']}>", embed=em)
                        else:
                            await channel.send(
                                f"<@&{data['ping']}>",
                                embed=em,
                                allowed_mentions=discord.AllowedMentions(roles=True),
                            )
                else:
                    if not data["ping"]:
                        await channel.send(f"{after.mention} is offline. {data['offline_emoji']}")
                    else:
                        await channel.send(
                            f"<@&{data['ping']}>, {after.mention} is offline. {data['offline_emoji']}"
                        )
            except discord.Forbidden:
                async with self.config.guild(after.guild).watching() as old_data:
                    old_data.remove(after.id)
        elif (
            before.status == discord.Status.offline
            and after.status != discord.Status.offline
            and (after.id in data["online_watching"])
        ):
            try:
                if data["embed_online"]:
                    em = discord.Embed(
                        color=0x008800,
                        description=f"{after.mention} is back online. {data['online_emoji']}",
                        timestamp=datetime.utcnow(),
                    )
                    if not data["ping"]:
                        await channel.send(embed=em)
                    else:
                        if discord.version_info.minor < 4:
                            await channel.send(f"<@&{data['ping']}>", embed=em)
                        else:
                            await channel.send(
                                f"<@&{data['ping']}>",
                                embed=em,
                                allowed_mentions=discord.AllowedMentions(roles=True),
                            )
                else:
                    if not data["ping"]:
                        await channel.send(
                            f"{after.mention} is back online. {data['online_emoji']}"
                        )
                    else:
                        await channel.send(
                            f"<@&{data['ping']}>, {after.mention} is back online. {data['online_emoji']}"
                        )
            except discord.Forbidden:
                async with self.config.guild(after.guild).online_watching() as old_data:
                    old_data.remove(after.id)
