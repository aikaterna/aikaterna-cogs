import discord
from discord.ext import commands


class Riot:

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, no_pm=True)
    async def riot(self, ctx, *, text: str):
        """RIOT!"""
        await self.bot.say('ヽ༼ຈل͜ຈ༽ﾉ **' + str(text) + '** ヽ༼ຈل͜ຈ༽ﾉ')


def setup(bot):
    bot.add_cog(Riot(bot))
