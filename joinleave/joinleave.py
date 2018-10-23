import asyncio
import datetime
import discord
from redbot.core import Config, commands, checks

BaseCog = getattr(commands, "Cog", object)


class JoinLeave(BaseCog):
    """Report users that join and leave quickly, with new accounts."""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2713731002, force_registration=True)

        default_global = {
            "announce_channel": None,
            "join_days": 7,
            "toggle": False,
            "cooldown": 120,
            "pingrole": None,
        }

        default_user = {"last_join": "2018-01-01 00:00:00.000001", "new": True}

        self.config.register_user(**default_user)
        self.config.register_global(**default_global)

    @commands.group()
    @commands.guild_only()
    @checks.is_owner()
    async def joinleave(self, ctx):
        """Main joinleave commands."""
        pass

    @joinleave.command()
    async def channel(self, ctx, channel: discord.TextChannel):
        """Sets the announcement channel."""
        await self.config.announce_channel.set(channel.id)
        announce_channel_id = await self.config.announce_channel()
        await ctx.send(
            f"User announcement channel set to: {self.bot.get_channel(announce_channel_id).mention}."
        )

    @joinleave.command()
    async def cooldown(self, ctx, cooldown_time: int = 0):
        """Set the time window in seconds for a valid join/leave flag.

        Leave time blank to reset to default (2m)."""
        cooldown = await self.config.cooldown()
        if not cooldown_time:
            await self.config.cooldown.set(120)
            await ctx.send("Join/leave time window reset to 2m.")
        else:
            await self.config.cooldown.set(cooldown_time)
            await ctx.send(
                f"Join/leave time window set to {self._dynamic_time(int(cooldown_time))}."
            )

    @joinleave.command()
    async def days(self, ctx, days: int):
        """Set how old an account needs to be a trusted user."""
        await self.config.join_days.set(days)
        await ctx.send(f"Users must have accounts older than {days} day(s) to be ignored.")

    @joinleave.command()
    async def role(self, ctx, *, role_name: discord.Role = None):
        """Set the role to ping on a first sighting. Leave blank to turn off."""
        if not role_name:
            await self.config.pingrole.set(None)
            return await ctx.send(
                "Role has been removed. No pinging will occur on a first sighting."
            )

        await self.config.pingrole.set(role_name.id)
        role_obj = discord.utils.get(ctx.guild.roles, id=await self.config.pingrole())
        await ctx.send(f"Pingable role set to: {role_obj.name}.")

    @joinleave.command()
    async def settings(self, ctx):
        """Show the current settings."""
        data = await self.config.all()

        try:
            achannel = self.bot.get_channel(data["announce_channel"]).name
        except AttributeError:
            achannel = None
        joinleave_enabled = data["toggle"]
        join_days = data["join_days"]
        cooldown = data["cooldown"]
        pingrole_id = data["pingrole"]
        if not pingrole_id:
            pingrole = "None"
        else:
            pingrole_obj = discord.utils.get(ctx.guild.roles, id=pingrole_id)
            pingrole = pingrole_obj.name

        msg = (
            "```ini\n---JoinLeave Settings---               \n"
            f"Announce Channel: [{achannel}]\n"
            f"Join/Leave Span:  [{self._dynamic_time(int(cooldown))}]\n"
            f"Day Threshold:    [{str(join_days)}]\n"
            f"Ping role:        [{pingrole}]\n"
            f"JoinLeave Active: [{joinleave_enabled}]\n```"
        )

        embed = discord.Embed(colour=ctx.guild.me.top_role.colour, description=msg)
        return await ctx.send(embed=embed)

    @joinleave.command()
    async def toggle(self, ctx):
        """Toggle the joinleave on or off. This is global."""
        joinleave_enabled = await self.config.toggle()
        announce_channel = await self.config.announce_channel()
        if not announce_channel:
            await self.config.announce_channel.set(ctx.message.channel.id)
        await self.config.toggle.set(not joinleave_enabled)
        await ctx.send(f"JoinLeave enabled: {not joinleave_enabled}.")
        if not announce_channel:
            await ctx.send(f"JoinLeave report channel set to: {ctx.message.channel.mention}.")

    async def on_member_join(self, member):
        global_data = await self.config.all()
        if not global_data["toggle"]:
            return

        join_date = datetime.datetime.strptime(str(member.created_at), "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        since_join = now - join_date

        if since_join.days < global_data["join_days"]:
            await self.config.user(member).last_join.set(str(now))

    async def on_member_remove(self, member):
        user_data = await self.config.user(member).all()
        global_data = await self.config.all()
        if not global_data["toggle"]:
            return

        channel_obj = self.bot.get_channel(global_data["announce_channel"])

        if not channel_obj:
            print("joinleave.py: toggled on but no announce channel")
            return

        last_time = datetime.datetime.strptime(str(user_data["last_join"]), "%Y-%m-%d %H:%M:%S.%f")

        join_date = datetime.datetime.strptime(str(member.created_at), "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        since_join = now - join_date

        if int((now - last_time).total_seconds()) < global_data["cooldown"]:
            await channel_obj.send(f"**{member.id}**")
            msg = f"User: {member} ({member.id})\nServer: {member.guild.name} ({member.guild.id})\nAccount is {self._dynamic_time(int(since_join.total_seconds()))} old"
            if user_data["new"]:
                await self.config.user(member).new.set(False)
                if not global_data["pingrole"]:
                    return await channel_obj.send(f"\N{WARNING SIGN} First sighting\n{msg}")
                else:
                    role_obj = discord.utils.get(
                        member.guild.roles, id=await self.config.pingrole()
                    )
                    print(role_obj)
                    print(role_obj.name)
                    try:
                        await role_obj.edit(mentionable=True)
                        await channel_obj.send(
                            f"{role_obj.mention}\n\N{WARNING SIGN} First sighting\n{msg}"
                        )
                        return await role_obj.edit(mentionable=False)
                    except AttributeError:
                        return await channel_obj.send(
                            f"I can't find the role that's set to ping (is it on another server?)\n\N{WARNING SIGN} First sighting\n{msg}"
                        )
                    except discord.errors.Forbidden:
                        return await channel_obj.send(
                            f"I tried to ping for this alert but I don't have permissons to manage roles!\n\N{WARNING SIGN} First sighting\n{msg}"
                        )
            else:
                print("not new")
                await channel_obj.send(msg)

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
