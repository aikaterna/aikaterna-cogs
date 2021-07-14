import discord
from discord.http import Route
from redbot.core import checks, commands


class DiscordExperiments(commands.Cog):
    """Create voice channel invites to access experimental applications on Discord."""

    def __init__(self, bot):
        self.bot = bot

    async def _create_invite(self, ctx, app_id: int, max_age: int, app_name: str):
        voice = ctx.author.voice
        if not voice:
            return await ctx.send("You have to be in a voice channel to use this command.")
        if not voice.channel.permissions_for(ctx.me).create_instant_invite == True:
            return await ctx.send(
                "I need the `Create Invite` permission for your channel before you can use this command."
            )

        r = Route("POST", "/channels/{channel_id}/invites", channel_id=voice.channel.id)
        payload = {"max_age": max_age, "target_type": 2, "target_application_id": app_id}
        code = (await self.bot.http.request(r, json=payload))["code"]

        await ctx.send(
            embed=discord.Embed(
                description=f"[Click here to join {app_name} in {voice.channel.name}!](https://discord.gg/{code})",
                color=0x2F3136,
            )
        )

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def ytparty(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a YouTube Together voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "YouTube Together"
        await self._create_invite(ctx, 755600276941176913, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def betrayal(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Betrayal.io voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "the Betrayal game"
        await self._create_invite(ctx, 773336526917861400, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def fishington(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Fishington.io voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "the Fishington game"
        await self._create_invite(ctx, 814288819477020702, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def pokernight(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Discord Poker Night voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Discord Poker Night"
        await self._create_invite(ctx, 755827207812677713, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def chess(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Chess in the Park voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Chess in the Park"
        await self._create_invite(ctx, 832012586023256104, invite_max_age_in_seconds, app_name)
