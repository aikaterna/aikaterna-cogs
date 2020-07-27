import discord
from redbot.core import commands, checks
from redbot.core.utils.chat_formatting import box, pagify
import asyncio


class PartyCrash(commands.Cog):
    """Partycrash inspired by v2 Admin by Will
       Does not generate invites, only lists existing invites."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot

    async def _get_invites(self, guild, ctx):
        answers = ("yes", "y")
        if not guild:
            return await ctx.send("I'm not in that server.")
        try:
            invites = await guild.invites()
        except discord.errors.Forbidden:
            return await ctx.send(f"I don't have permission to view invites for {guild.name}.")
        if not invites:
            return await ctx.send("I couldn't access any invites.")
        await ctx.send(f"Are you sure you want to post the invite(s) to {guild.name} here?")

        def check(m):
            return m.author == ctx.author

        try:
            msg = await ctx.bot.wait_for("message", timeout=15.0, check=check)
            if msg.content.lower().strip() in answers:
                msg = f"Invite(s) for **{guild.name}**:"
                for url in invites:
                    msg += f"\n{url}"
                await ctx.send(msg)
            else:
                await ctx.send("Alright then.")
        except asyncio.TimeoutError:
            await ctx.send("I guess not.")

    @commands.command()
    @checks.is_owner()
    async def partycrash(self, ctx, idnum=None):
        """Lists servers and existing invites for them."""
        if idnum:
            guild = self.bot.get_guild(int(idnum))
            await self._get_invites(guild, ctx)
        else:
            msg = ""
            guilds = sorted(self.bot.guilds, key=lambda s: s.name)
            for i, guild in enumerate(guilds, 1):
                if len(guild.name) > 32:
                    guild_name = f"{guild.name[:32]}..."
                else:
                    guild_name = guild.name
                if i < 10:
                    i = f"0{i}"
                msg += f"{i}: {guild_name:35} ({guild.id})\n"
            msg += "\nTo post the existing invite(s) for a server just type its number."
            for page in pagify(msg, delims=["\n"]):
                await ctx.send(box(page))

            def check(m):
                return m.author == ctx.author

            try:
                msg = await ctx.bot.wait_for("message", timeout=20.0, check=check)
                try:
                    guild_no = int(msg.content.strip())
                    guild = guilds[guild_no - 1]
                except ValueError:
                    return await ctx.send("You must enter a number.")
                except IndexError:
                    return await ctx.send("Index out of range.")
                try:
                    await self._get_invites(guild, ctx)
                except discord.errors.Forbidden:
                    return await ctx.send(f"I don't have permission to get invites for {guild.name}.")
            except asyncio.TimeoutError:
                return await ctx.send("No server number entered, try again later.")
