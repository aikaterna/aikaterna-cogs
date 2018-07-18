from .dungeon import Dungeon


def setup(bot):
    bot.add_cog(Dungeon(bot))
