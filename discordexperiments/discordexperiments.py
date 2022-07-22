import discord
from discord.http import Route
from redbot.core import checks, commands


class DiscordExperiments(commands.Cog):
    """Create voice channel invites to access experimental applications on Discord."""

    def __init__(self, bot):
        self.bot = bot

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

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
        await self._create_invite(ctx, 880218394199220334, invite_max_age_in_seconds, app_name)

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
        Create a Poker Night voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Poker Night"
        await self._create_invite(ctx, 755827207812677713, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def chess(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Chess in the Park voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Chess in the Park"
        await self._create_invite(ctx, 832012774040141894, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def sketchheads(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Sketch Heads voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "the Sketch Heads game"
        await self._create_invite(ctx, 902271654783242291, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def letterleague(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Letter League voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "the Letter League game"
        await self._create_invite(ctx, 879863686565621790, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def wordsnacks(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Word Snacks voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "the Word Snacks game"
        await self._create_invite(ctx, 879863976006127627, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def spellcast(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a SpellCast voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "the SpellCast game"
        await self._create_invite(ctx, 852509694341283871, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def checkers(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Checkers in the Park voice channel invite.

        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Checkers in the Park"
        await self._create_invite(ctx, 832013003968348200, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def blazing8s(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Blazing 8s voice channel invite.
        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Blazing 8s"
        await self._create_invite(ctx, 832025144389533716, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def puttparty(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Putt Party voice channel invite.
        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Putt Party"
        await self._create_invite(ctx, 945737671223947305, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def landio(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Land-io voice channel invite.
        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Land-io"
        await self._create_invite(ctx, 903769130790969345, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def bobbleleague(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Bobble League voice channel invite.
        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Bobble League"
        await self._create_invite(ctx, 947957217959759964, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def askaway(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create an Ask Away voice channel invite.
        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Ask Away"
        await self._create_invite(ctx, 976052223358406656, invite_max_age_in_seconds, app_name)

    @commands.cooldown(1, 10, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def knowwhatimeme(self, ctx, invite_max_age_in_seconds=86400):
        """
        Create a Know What I Meme voice channel invite.
        Use `0` for `invite_max_age_in_seconds` if you want the invite to be permanent.
        """
        app_name = "Know What I Meme"
        await self._create_invite(ctx, 950505761862189096, invite_max_age_in_seconds, app_name)
