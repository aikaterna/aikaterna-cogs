import asyncio
import datetime
import discord
from redbot.core import Config, commands, checks
from redbot.core.data_manager import cog_data_path


class Dungeon:
    """Auto-quarantine suspicious users."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2700081001, force_registration=True)

        default_guild = {
            "announce_channel": None,
            "auto_blacklist": False,
            "dungeon_channel": None,
            "dungeon_role": None,
            "join_days": 7,
            "toggle": False,
            "user_role": None,
            "user_role_toggle": False,
        }

        self.config.register_guild(**default_guild)

    @commands.group(autohelp=True)
    @commands.guild_only()
    @checks.admin_or_permissions(manage_server=True)
    async def dungeon(self, ctx):
        pass

    @dungeon.command()
    async def announce(self, ctx, channel: discord.TextChannel):
        """Sets the announcement channel for users moved to the dungeon."""
        await self.config.guild(ctx.guild).announce_channel.set(channel.id)
        announce_channel_id = await self.config.guild(ctx.guild).announce_channel()
        await ctx.send(
            f"User announcement channel set to: {self.bot.get_channel(announce_channel_id).mention}."
        )

    @dungeon.command()
    async def blacklist(self, ctx):
        """Toggle auto-blacklisting for the bot for users moved to the dungeon."""
        auto_blacklist = await self.config.guild(ctx.guild).auto_blacklist()
        await self.config.guild(ctx.guild).auto_blacklist.set(not auto_blacklist)
        await ctx.send(f"Auto-blacklisting dungeon users from the bot: {not auto_blacklist}.")

    @dungeon.command()
    async def channel(self, ctx, channel: discord.TextChannel):
        """Sets the text channel to use for the dungeon."""
        await self.config.guild(ctx.guild).dungeon_channel.set(channel.id)
        dungeon_channel_id = await self.config.guild(ctx.guild).dungeon_channel()
        await ctx.send(f"Dungeon channel set to: {self.bot.get_channel(dungeon_channel_id).name}.")

    @dungeon.command()
    async def joindays(self, ctx, days: int):
        """Set how old an account needs to be a trusted user."""
        await self.config.guild(ctx.guild).join_days.set(days)
        await ctx.send(
            f"Users must have accounts older than {days} day(s) to be awarded the member role instead of the dungeon role on join."
        )

    @dungeon.command()
    async def role(self, ctx, role_name: discord.Role):
        """Sets the role to use for the dungeon."""
        await self.config.guild(ctx.guild).dungeon_role.set(role_name.id)
        dungeon_role_id = await self.config.guild(ctx.guild).dungeon_role()
        dungeon_role_obj = discord.utils.get(ctx.guild.roles, id=dungeon_role_id)
        await ctx.send(f"Dungeon role set to: {dungeon_role_obj.name}.")

    @dungeon.command()
    async def dungeontoggle(self, ctx):
        """Toggle the dungeon on or off."""
        dungeon_enabled = await self.config.guild(ctx.guild).toggle()
        await self.config.guild(ctx.guild).toggle.set(not dungeon_enabled)
        await ctx.send(f"New user dungeon role enabled: {not dungeon_enabled}.")

    @dungeon.command()
    async def userrole(self, ctx, role_name: discord.Role):
        """Sets the role to give to new users that are not sent to the dungeon."""
        await self.config.guild(ctx.guild).user_role.set(role_name.id)
        user_role_id = await self.config.guild(ctx.guild).user_role()
        user_role_obj = discord.utils.get(ctx.guild.roles, id=user_role_id)
        await ctx.send(f"Member role set to: {user_role_obj.name}.")

    @dungeon.command()
    async def usertoggle(self, ctx):
        """Toggle the user role on or off."""
        user_role_toggle = await self.config.guild(ctx.guild).user_role_toggle()
        await self.config.guild(ctx.guild).user_role_toggle.set(not user_role_toggle)
        await ctx.send(f"New user dungeon role enabled: {not user_role_toggle}.")

    @dungeon.command()
    async def verify(self, ctx, user: discord.Member):
        """Verify a user: remove the dungeon role and add initial user role."""
        blacklist = await self.config.guild(ctx.guild).auto_blacklist()
        dungeon_role_id = await self.config.guild(ctx.guild).dungeon_role()
        dungeon_role_obj = discord.utils.get(ctx.guild.roles, id=dungeon_role_id)
        user_role_id = await self.config.guild(ctx.guild).user_role()
        user_role_obj = discord.utils.get(ctx.guild.roles, id=user_role_id)

        if blacklist:
            async with self.bot.db.blacklist() as blacklist_list:
                if user.id in blacklist_list:
                    blacklist_list.remove(user.id)

        role_check = False
        for role in user.roles:
            if not dungeon_role_obj:
                return await ctx.send("No dungeon role set.")
            if role == dungeon_role_obj:
                role_check = True
                try:
                    await user.remove_roles(
                        dungeon_role_obj,
                        reason=f"Removing dungeon role, verified by {ctx.message.author.name}.",
                    )
                    await user.add_roles(user_role_obj, reason="Adding member role.")
                except discord.Forbidden:
                    return await ctx.send(
                        "I need permissions to manage roles or the role hierarchy might not allow me to do this."
                    )

        if not role_check:
            return await ctx.send("User is not in the dungeon.")

        if blacklist:
            blacklist_msg = " and the bot blacklist"
        else:
            blacklist_msg = ""
        msg = f"{user.name} has been removed from the dungeon{blacklist_msg} and now has the initial user role."
        await ctx.send(msg)

    @dungeon.command()
    async def autosetup(self, ctx):
        """Automatically set up the dungeon channel and role to apply to suspicious users.
        You must deny the default role (@ everyone) from viewing or typing in other channels in your server manually.
        """
        try:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(
                    send_messages=False, read_messages=False
                )
            }

            dungeon_role = await ctx.guild.create_role(name="Dungeon")

            dungeon_category = await ctx.guild.create_category("Dungeon", overwrites=overwrites)
            await dungeon_category.set_permissions(
                dungeon_role, read_messages=True, send_messages=False, read_message_history=True
            )

            dungeon_channel = await ctx.guild.create_text_channel(
                "Silenced", category=dungeon_category
            )
            await dungeon_channel.set_permissions(
                dungeon_role, read_messages=True, send_messages=False, read_message_history=True
            )
            await dungeon_channel.set_permissions(
                ctx.guild.me, read_messages=True, send_messages=True, read_message_history=True
            )
            await dungeon_channel.send("Please wait while an admin verifies your account.")

            await self.config.guild(ctx.guild).dungeon_channel.set(dungeon_channel.id)
            await self.config.guild(ctx.guild).dungeon_role.set(dungeon_role.id)
            await self.config.guild(ctx.guild).announce_channel.set(ctx.channel.id)
            toggle = await self.config.guild(ctx.guild).toggle()
            if not toggle:
                await ctx.invoke(self.usertoggle)
            await ctx.send(
                f"Done.\nDungeon channel created: {dungeon_channel.mention}\nDungeon role created: {dungeon_role.name}\n\nPlease set these items manually:\n- The announce channel for reporting new users that are moved to the dungeon ([p]dungeon announce)\n- The role you wish to award regular members when they join the server ([p]dungeon userrole)\n- The toggle for enabling the regular user role awarding ([p]dungeon usertoggle)"
            )

        except discord.Forbidden:
            await ctx.send("I need permissions to manage channels and manage roles.")

    @dungeon.command()
    async def settings(self, ctx):
        """Show the current settings."""
        data = await self.config.guild(ctx.guild).all()

        try:
            drole = discord.utils.get(ctx.guild.roles, id=data["dungeon_role"]).name
        except AttributeError:
            drole = None
        try:
            urole = discord.utils.get(ctx.guild.roles, id=data["user_role"]).name
        except AttributeError:
            urole = None
        try:
            achannel = self.bot.get_channel(data["announce_channel"]).name
        except AttributeError:
            achannel = None
        try:
            dchannel = self.bot.get_channel(data["dungeon_channel"]).name
        except AttributeError:
            dchannel = None
        dungeon_enabled = data["toggle"]
        user_role_enabled = data["user_role_toggle"]
        join_days = data["join_days"]
        auto_blacklist = data["auto_blacklist"]

        msg = (
            "```ini\n----Dungeon Settings----\n"
            f"Dungeon Enabled:  [{dungeon_enabled}]\n"
            f"Dungeon Role:     [{drole}]\n"
            f"Dungeon Channel:  [{dchannel}]\n"
            f"Announce Channel: [{achannel}]\n"
            f"Autorole Enabled: [{user_role_enabled}]\n"
            f"Autorole Role:    [{urole}]\n"
            f"Auto-blacklist:   [{auto_blacklist}]\n```"
        )

        embed = discord.Embed(colour=ctx.guild.me.top_role.colour, description=msg)
        return await ctx.send(embed=embed)

    async def on_member_join(self, member):
        toggle = await self.config.guild(member.guild).toggle()
        if not toggle:
            return
        if member.avatar_url == member.default_avatar_url:
            default_avatar = True
        join_date = datetime.datetime.strptime(str(member.created_at), "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        since_join = now - join_date
        join_days = await self.config.guild(member.guild).join_days()

        if since_join.days < join_days:
            blacklist = await self.config.guild(member.guild).auto_blacklist()
            dungeon_role_id = await self.config.guild(member.guild).dungeon_role()
            dungeon_role_obj = discord.utils.get(member.guild.roles, id=dungeon_role_id)
            if blacklist:
                async with self.bot.db.blacklist() as blacklist_list:
                    if member.id not in blacklist_list:
                        blacklist_list.append(member.id)
            try:
                await member.add_roles(
                    dungeon_role_obj, reason="Adding dungeon role, new account."
                )
            except discord.Forbidden:
                pass

            announce_channel = await self.config.guild(member.guild).announce_channel()
            channel_object = self.bot.get_channel(announce_channel)
            msg = f"Auto-banished new user: \n**{member.name}#{member.discriminator}** ({member.id})\n{self._dynamic_time(since_join.seconds)} old account"
            if default_avatar:
                msg += ", no profile picture set"
            await channel_object.send(msg)
        else:
            user_role_toggle = await self.config.guild(member.guild).user_role_toggle()
            if not user_role_toggle:
                return
            user_role_id = await self.config.guild(member.guild).user_role()
            user_role_obj = discord.utils.get(member.guild.roles, id=user_role_id)
            try:
                await member.add_roles(user_role_obj, reason="Adding member role to new user.")
            except discord.Forbidden:
                pass

    @staticmethod
    def _dynamic_time(time):
        m, s = divmod(time, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        if d > 0:
            msg = "{0}d {1}h"
        elif d == 0 and h > 0:
            msg = "{1}h {2}m"
        elif d == 0 and h == 0 and m > 0:
            msg = "{2}m {3}s"
        elif d == 0 and h == 0 and m == 0 and s > 0:
            msg = "{3}s"
        else:
            msg = ""
        return msg.format(d, h, m, s)
