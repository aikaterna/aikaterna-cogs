from discord.ext import commands
from .partycrash import PartyCrash


def setup(bot: commands.Bot): 
    bot.add_cog(PartyCrash(bot))
