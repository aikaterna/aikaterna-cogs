import asyncio
import discord
from redbot.core import commands


class PressF(commands.Cog):
    """Pay some respects."""

    def __init__(self, bot):
        self.bot = bot
        self.channels = {}

    @commands.command()
    @commands.bot_has_permissions(add_reactions=True)
    async def pressf(self, ctx, *, user: discord.User = None):
        """Pay respects by pressing F"""
        if str(ctx.channel.id) in self.channels:
            return await ctx.send(
                "Oops! I'm still paying respects in this channel, you'll have to wait until I'm done."
            )

        if user:
            answer = user.display_name
        else:
            await ctx.send("What do you want to pay respects to?")

            def check(m):
                return m.author == ctx.author

            try:
                pressf = await ctx.bot.wait_for("message", timeout=120.0, check=check)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long to reply.")

            answer = pressf.content

        message = await ctx.send(
            f"Everyone, let's pay respects to **{answer}**! Press the f reaction on the this message to pay respects."
        )
        await message.add_reaction("\U0001f1eb")
        self.channels[str(ctx.channel.id)] = []
        await asyncio.sleep(120)
        await message.delete()
        amount = len(self.channels[str(ctx.channel.id)])
        word = "person has" if amount == 1 else "people have"
        await ctx.channel.send(f"**{amount}** {word} paid respects to **{answer}**.")
        del self.channels[str(ctx.channel.id)]

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if str(reaction.message.channel.id) not in self.channels:
            return
        if user.id == self.bot.user.id:
            return
        if str(user.id) not in self.channels[str(reaction.message.channel.id)]:
            if str(reaction.emoji) == "\U0001f1eb":
                await reaction.message.channel.send(f"**{user.display_name}** has paid respects.")
                self.channels[str(reaction.message.channel.id)].append(user.id)
