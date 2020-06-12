from .luigipoker import LuigiPoker


def setup(bot):
    bot.add_cog(LuigiPoker(bot))
