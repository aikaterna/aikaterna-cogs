import datetime
from typing import Literal

import discord
import logging
from redbot.core import Config, commands, checks, modlog
from redbot.core.utils.chat_formatting import box, pagify


log = logging.getLogger("red.aikaterna.dungeon")


class Dungeon(commands.Cog):
    """Auto-quarantine suspicious users."""

    async def red_delete_data_for_user(
        self, *, requester: Literal["discord", "owner", "user", "user_strict"], user_id: int,
    ):
        if requester == "discord":
            # user is deleted, just comply

            data = await self.config.all_guilds()
            for guild_id, guild_data in data.items():
                if user_id in guild_data.get("bypass", []):
                    bypass = guild_data.get("bypass", [])
                    bypass = set(bypass)
                    bypass.discard(user_id)
                    await self.config.guild_from_id(guild_id).bypass.set(list(bypass))

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2700081001, force_registration=True)

        default_guild = {
            "announce_channel": None,
            "auto_ban": False,
            "auto_ban_message": None,
            "auto_blacklist": False,
            "bypass": [],
            "dm_message": None,
            "dm_toggle": False,
            "dungeon_channel": None,
            "dungeon_role": None,
            "join_days": 7,
            "mod_log": False,
            "profile_toggle": False,
            "toggle": False,
            "user_role": None,
            "user_role_toggle": False,
        }

        self.config.register_guild(**default_guild)

    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def banish(self, ctx, user: discord.Member):
        """Strip a user of their roles, apply the dungeon role, and blacklist them.
		If the blacklist toggle is off, the user will not be blacklisted from the bot."""
        data = await self.config.guild(ctx.guild).all()
        blacklist = data["auto_blacklist"]
        dungeon_role_id = data["dungeon_role"]
        dungeon_role_obj = discord.utils.get(ctx.guild.roles, id=dungeon_role_id)

        if blacklist:
            # if you are reading this to learn, DON'T do this, there will be a real way
            # to interact with bot-owned data without touching config directly at some
            # point in the future after Red 3.2
            async with self.bot._config.blacklist() as blacklist_list:
                if user.id not in blacklist_list:
                    blacklist_list.append(user.id)

        if not dungeon_role_obj:
            return await ctx.send("No dungeon role set.")

        #Managed roles CANNOT be removed by the bot.
        remaining_roles = [r for r in user.roles if r.managed]
        try:
            await user.edit(roles=remaining_roles, reason=f"Removing all roles, {ctx.message.author} is banishing user")
        except discord.Forbidden:
            return await ctx.send(
                "I need permission to manage roles or the role hierarchy might not allow me to do this. I need a role higher than the person you're trying to banish."
            )

        await user.add_roles(dungeon_role_obj, reason=f"Adding dungeon role, {ctx.message.author} is banishing user")

        if blacklist:
            blacklist_msg = ", blacklisted from the bot,"
        else:
            blacklist_msg = ""
        msg = f"{user} has been sent to the dungeon{blacklist_msg} and has had all previous roles stripped."
        await ctx.send(msg)

    @commands.group(autohelp=True)
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def dungeon(self, ctx):
        """Main dungeon commands."""
        pass

    @dungeon.command()
    async def announce(self, ctx, channel: discord.TextChannel):
        """Sets the announcement channel for users moved to the dungeon."""
        await self.config.guild(ctx.guild).announce_channel.set(channel.id)
        announce_channel_id = await self.config.guild(ctx.guild).announce_channel()
        await ctx.send(f"User announcement channel set to: {self.bot.get_channel(announce_channel_id).mention}.")

    @dungeon.command()
    async def autoban(self, ctx):
        """Toggle auto-banning users instead of sending them to the dungeon."""
        auto_ban = await self.config.guild(ctx.guild).auto_ban()
        await self.config.guild(ctx.guild).auto_ban.set(not auto_ban)
        await ctx.send(f"Auto-ban instead of sending to the dungeon: {not auto_ban}.")

    @dungeon.command()
    async def banmessage(self, ctx, *, ban_message=None):
        """Set the message to send on an autoban. If message is left blank, no message will be sent."""
        auto_ban = await self.config.guild(ctx.guild).auto_ban()
        if not ban_message:
            await self.config.guild(ctx.guild).auto_ban_message.set(None)
            return await ctx.send("Auto-ban message removed. No message will be sent on an auto-ban.")
        await self.config.guild(ctx.guild).auto_ban_message.set(str(ban_message))
        await self.config.guild(ctx.guild).auto_ban.set(True)
        await ctx.send(f"Auto-ban has been turned on.\nMessage to send on ban:\n{ban_message}")

    @dungeon.command()
    async def blacklist(self, ctx):
        """Toggle auto-blacklisting for the bot for users moved to the dungeon."""
        auto_blacklist = await self.config.guild(ctx.guild).auto_blacklist()
        await self.config.guild(ctx.guild).auto_blacklist.set(not auto_blacklist)
        await ctx.send(f"Auto-blacklisting dungeon users from the bot: {not auto_blacklist}.")

    @dungeon.command()
    @commands.cooldown(1, 5, discord.ext.commands.BucketType.guild)
    async def bypass(self, ctx, user_id: int):
        """Add a user ID to the bypass list - user will be able to join without restrictions."""
        if not 17 <= len(str(user_id)) >= 18:
            return await ctx.send("This doesn't look like a Discord user id.")
        bypass_ids = await self.config.guild(ctx.guild).bypass()
        if user_id in bypass_ids:
            return await ctx.send(f"**{user_id}** is already in the list of bypassed users.")
        bypass_ids.append(user_id)
        await self.config.guild(ctx.guild).bypass.set(bypass_ids)
        bypassed_user = await self.bot.fetch_user(user_id)
        await ctx.send(
            f"**{bypassed_user}** ({user_id}) has been added to the bypass list. The next time they attempt to join this server, they will bypass any Dungeon restrictions."
        )

    @dungeon.command()
    @commands.cooldown(1, 5, discord.ext.commands.BucketType.guild)
    async def bypasslist(self, ctx):
        """Show the current bypass list."""
        bypass_ids = await self.config.guild(ctx.guild).bypass()
        msg = "[Bypassed IDs]\n"
        if not bypass_ids:
            msg += "None."
        for id in bypass_ids:
            msg += f"{id}\n"
        for page in pagify(msg, delims=["\n"], page_length=1000):
            await ctx.send(box(msg, lang="ini"))

    @dungeon.command()
    async def channel(self, ctx, channel: discord.TextChannel):
        """Sets the text channel to use for the dungeon."""
        await self.config.guild(ctx.guild).dungeon_channel.set(channel.id)
        dungeon_channel_id = await self.config.guild(ctx.guild).dungeon_channel()
        await ctx.send(f"Dungeon channel set to: {self.bot.get_channel(dungeon_channel_id).name}.")

    @dungeon.command()
    async def dm(self, ctx, *, dm_message=None):
        """Set the message to send on successful verification.
        A blank message will turn off the DM setting."""
        if not dm_message:
            await self.config.guild(ctx.guild).dm_toggle.set(False)
            await self.config.guild(ctx.guild).dm_message.set(None)
            return await ctx.send("DM message on verification turned off.")
        await self.config.guild(ctx.guild).dm_message.set(str(dm_message))
        await self.config.guild(ctx.guild).dm_toggle.set(True)
        await ctx.send(f"DM message on verification turned on.\nMessage to send:\n{dm_message}")

    @dungeon.command()
    async def joindays(self, ctx, days: int):
        """Set how old an account needs to be a trusted user."""
        await self.config.guild(ctx.guild).join_days.set(days)
        await ctx.send(
            f"Users must have accounts older than {days} day(s) to be awarded the member role instead of the dungeon role on join."
        )

    @dungeon.command()
    async def modlog(self, ctx):
        """Toggle using the Red mod-log for auto-bans.
        The mod-log has to be configured to display bans for this to work."""
        mod_log = await self.config.guild(ctx.guild).mod_log()
        await self.config.guild(ctx.guild).mod_log.set(not mod_log)
        await ctx.send(f"Mod-log entry on auto-ban: {not mod_log}.")

    @dungeon.command()
    async def role(self, ctx, role_name: discord.Role):
        """Sets the role to use for the dungeon."""
        await self.config.guild(ctx.guild).dungeon_role.set(role_name.id)
        dungeon_role_id = await self.config.guild(ctx.guild).dungeon_role()
        dungeon_role_obj = discord.utils.get(ctx.guild.roles, id=dungeon_role_id)
        await ctx.send(f"Dungeon role set to: {dungeon_role_obj.name}.")

    @dungeon.command()
    async def toggle(self, ctx):
        """Toggle the dungeon on or off."""
        dungeon_enabled = await self.config.guild(ctx.guild).toggle()
        await self.config.guild(ctx.guild).toggle.set(not dungeon_enabled)
        await ctx.send(f"Dungeon enabled: {not dungeon_enabled}.")

    @dungeon.command()
    async def profiletoggle(self, ctx):
        """Toggles flagging accounts that have a default profile pic.
        Accounts that are over the join days threshold will still be flagged if they have a default profile pic."""
        profile_toggle = await self.config.guild(ctx.guild).profile_toggle()
        await self.config.guild(ctx.guild).profile_toggle.set(not profile_toggle)
        await ctx.send(f"Default profile pic flagging: {not profile_toggle}.")

    @dungeon.command()
    async def userrole(self, ctx, *, role_name: discord.Role = None):
        """Sets the role to give to new users that are not sent to the dungeon."""
        if not role_name:
            await self.config.guild(ctx.guild).user_role.set(None)
            return await ctx.send("Member role cleared.")
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
        data = await self.config.guild(ctx.guild).all()
        announce_channel = data["announce_channel"]
        blacklist = data["auto_blacklist"]
        dungeon_role_id = data["dungeon_role"]
        dungeon_role_obj = discord.utils.get(ctx.guild.roles, id=dungeon_role_id)
        user_role_id = data["user_role"]
        user_role_obj = discord.utils.get(ctx.guild.roles, id=user_role_id)
        dm_toggle = data["dm_toggle"]
        dm_message = data["dm_message"]

        if blacklist:
            # if you are reading this to learn, DON'T do this, there will be a real way
            # to interact with bot-owned data without touching config directly at some
            # point in the future after Red 3.2
            async with self.bot._config.blacklist() as blacklist_list:
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
                        dungeon_role_obj, reason=f"Removing dungeon role, verified by {ctx.message.author}.",
                    )
                    if not user_role_obj:
                        return await ctx.send("Dungeon role removed, but no member role is set so I can't award one.")
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
        msg = f"{user} has been removed from the dungeon{blacklist_msg} and now has the initial user role."
        await ctx.send(msg)

        if dm_toggle:
            try:
                await user.send(dm_message)
            except discord.Forbidden:
                await ctx.send(f"I couldn't DM {user} to let them know they've been verified, they've blocked me.")

    @dungeon.command()
    async def autosetup(self, ctx):
        """Automatically set up the dungeon channel and role to apply to suspicious users.
        You must deny the default role (@ everyone) from viewing or typing in other channels in your server manually.
        """
        try:
            overwrites = {ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False, read_messages=False)}

            dungeon_role = await ctx.guild.create_role(name="Dungeon")

            dungeon_category = await ctx.guild.create_category("Dungeon", overwrites=overwrites)
            await dungeon_category.set_permissions(
                dungeon_role, read_messages=True, send_messages=False, read_message_history=True
            )

            dungeon_channel = await ctx.guild.create_text_channel("Silenced", category=dungeon_category)
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
                f"Done.\nDungeon channel created: {dungeon_channel.mention}\nDungeon role created: {dungeon_role.name}\n\nPlease set these items manually:\n- The announce channel for reporting new users that are moved to the dungeon ({ctx.prefix}dungeon announce)\n- The role you wish to award regular members when they join the server ({ctx.prefix}dungeon userrole)\n- The toggle for enabling the regular user role awarding ({ctx.prefix}dungeon usertoggle)"
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
        profile_toggle = data["profile_toggle"]
        dm_toggle = data["dm_toggle"]
        auto_ban = data["auto_ban"]
        ban_msg = data["auto_ban_message"]
        mod_log = data["mod_log"]

        if ban_msg:
            ban_msg = "True"

        msg = (
            "```ini\n----Dungeon Settings----\n"
            f"Dungeon Enabled:  [{dungeon_enabled}]\n"
            f"Dungeon Role:     [{drole}]\n"
            f"Dungeon Channel:  [{dchannel}]\n"
            f"Announce Channel: [{achannel}]\n"
            f"Autorole Enabled: [{user_role_enabled}]\n"
            f"Autorole Role:    [{urole}]\n"
            f"Auto-blacklist:   [{auto_blacklist}]\n"
            f"Default PFP Flag: [{profile_toggle}]\n"
            f"Day Threshold:    [{str(join_days)}]\n"
            f"Msg on Verify:    [{dm_toggle}]\n"
            f"Auto-ban:         [{auto_ban}]\n"
            f"Ban Message:      [{ban_msg}]\n"
            f"Mod-log on Ban:   [{mod_log}]\n```"
        )

        embed = discord.Embed(colour=ctx.guild.me.top_role.colour, description=msg)
        return await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        default_avatar = False
        toggle = await self.config.guild(member.guild).toggle()
        if not toggle:
            return
        if member.avatar_url == member.default_avatar_url:
            default_avatar = True
        try:
            join_date = datetime.datetime.strptime(str(member.created_at), "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            member_created_at = f"{str(member.created_at)}.0"
            join_date = datetime.datetime.strptime(member_created_at, "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        since_join = now - join_date
        join_days = await self.config.guild(member.guild).join_days()
        profile_toggle = await self.config.guild(member.guild).profile_toggle()
        announce_channel = await self.config.guild(member.guild).announce_channel()
        channel_object = self.bot.get_channel(announce_channel)
        auto_ban = await self.config.guild(member.guild).auto_ban()
        auto_ban_msg = await self.config.guild(member.guild).auto_ban_message()
        mod_log = await self.config.guild(member.guild).mod_log()
        bypassed_ids = await self.config.guild(member.guild).bypass()

        if member.id in bypassed_ids:
            bypassed_ids.remove(member.id)
            await self.config.guild(member.guild).bypass.set(bypassed_ids)
            user_role_id = await self.config.guild(member.guild).user_role()
            user_role_obj = discord.utils.get(member.guild.roles, id=user_role_id)
            try:
                await member.add_roles(
                    user_role_obj, reason="User has bypassed Dungeon checks. Assigning member role.",
                )
            except discord.Forbidden:
                pass
            except AttributeError:
                pass
            bypass_msg = f"**{member}** ({member.id}) was in the bypass list for **{member.guild.name}** ({member.guild.id}). They were allowed to join without Dungeon checks and I have assigned them the Member role specified in the settings, if any."
            if announce_channel:
                await channel_object.send(bypass_msg)
            else:
                log.debug(f"dungeon.py: {bypass_msg}")
            return

        if (since_join.days < join_days) or (profile_toggle and default_avatar):
            banned = False
            blacklist = await self.config.guild(member.guild).auto_blacklist()
            dungeon_role_id = await self.config.guild(member.guild).dungeon_role()
            dungeon_role_obj = discord.utils.get(member.guild.roles, id=dungeon_role_id)
            perm_msg = f"dungeon.py: Unable to auto-ban user, permissions needed and no announce channel set. Guild: {member.guild.id}"

            if auto_ban:
                banned = True
                if auto_ban_msg:
                    try:
                        await member.send(auto_ban_msg)
                    except discord.Forbidden:
                        if announce_channel:
                            await channel_object.send(
                                f"I couldn't DM {member} ({member.id}) to let them know they've been banned, they've blocked me."
                            )
                        else:
                            log.debug(perm_msg)
                            return
                try:
                    await member.guild.ban(member, reason="Dungeon auto-ban", delete_message_days=0)
                except discord.Forbidden:
                    if announce_channel:
                        return await channel_object.send(
                            f"I tried to auto-ban someone ({member}, {member.id}) but I don't have ban permissions."
                        )
                    else:
                        log.debug(perm_msg)
                        return

                if not mod_log:
                    if announce_channel:
                        msg = f"Auto-banned new user: \n**{member}** ({member.id})\n{self._dynamic_time(int(since_join.total_seconds()))} old account"
                        return await channel_object.send(msg)
                    else:
                        log.debug(perm_msg)
                        return
                else:
                    try:
                        await modlog.create_case(
                            self.bot, member.guild, now, "ban", member, member.guild.me, until=None, channel=None,
                        )
                    except RuntimeError:
                        log.error(
                            f"dungeon.py error while autobanning user and attempting to create modlog entry in guild: {member.guild.id}",
                            exc_info=True,
                        )

            if blacklist:
                # if you are reading this to learn, DON'T do this, there will be a real way
                # to interact with bot-owned data without touching config directly at some
                # point in the future after Red 3.2
                async with self.bot._config.blacklist() as blacklist_list:
                    if member.id not in blacklist_list:
                        blacklist_list.append(member.id)
            if banned:
                return
            try:
                if since_join.days < join_days:
                    reason = "Adding dungeon role, new account."
                else:
                    reason = "Adding dungeon role, default profile pic."
                await member.add_roles(dungeon_role_obj, reason=reason)
            except discord.Forbidden:
                if announce_channel:
                    return await channel_object.send(
                        "Someone suspicious joined but something went wrong. I need permissions to manage channels and manage roles."
                    )
                else:
                    log.info(
                        f"dungeon.py: I need permissions to manage channels and manage roles in {member.guild.name} ({member.guild.id})."
                    )
                    return

            msg = f"Auto-banished new user: \n**{member}** ({member.id})\n{self._dynamic_time(int(since_join.total_seconds()))} old account"
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
            except AttributeError:
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
