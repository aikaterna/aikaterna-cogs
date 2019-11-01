from .snacktime import Snacktime


async def setup(bot):
    bot.add_cog(Snacktime(bot))
