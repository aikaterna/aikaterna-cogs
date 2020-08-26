import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import humanize_list


class Region(commands.Cog):
    """Change the guild voice region."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    @checks.mod_or_permissions(administrator=True)
    @commands.cooldown(1, 60, discord.ext.commands.BucketType.guild)
    @commands.command()
    async def region(self, ctx, *, region: str):
        """Set the current guild's voice region."""
        regions = [
            "japan",
            "singapore",
            "eu-central",
            "europe",
            "india",
            "us-central",
            "london",
            "eu-west",
            "amsterdam",
            "brazil",
            "dubai",
            "us-west",
            "hongkong",
            "us-south",
            "southafrica",
            "us-east",
            "sydney",
            "frankfurt",
            "russia",
        ]
        region = region.replace(" ", "-")
        if region not in regions:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"`{region}` was not found in the list of Discord voice regions. Valid regions are: {humanize_list(regions)}."
            )
        try:
            await ctx.guild.edit(region=region)
        except discord.errors.Forbidden:
            return await ctx.send("I don't have permissions to edit this guild's settings.")
        except discord.errors.HTTPException:
            return await ctx.send(f"Error: An invalid server region was passed: `{region}`")
        await ctx.send(f"The voice server region for `{ctx.guild.name}` has been changed to `{region}`.")
