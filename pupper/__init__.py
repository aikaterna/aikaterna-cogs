from .pupper import Pupper


async def setup(bot):
    bot.add_cog(Pupper(bot))
