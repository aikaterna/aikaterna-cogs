from .hunting import Hunting


async def setup(bot):
    bot.add_cog(Hunting(bot))
