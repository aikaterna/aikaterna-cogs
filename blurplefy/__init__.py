from .blurplefy import Blurplefy
from discord.ext import commands


def setup(bot: commands.Bot):
    bot.add_cog(Blurplefy(bot))
