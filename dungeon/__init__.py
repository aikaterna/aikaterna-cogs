from .dungeon import Dungeon

__red_end_user_data_statement__ = (
    "This cog does not persistently store end user data. " "This cog does store discord IDs as needed for operation. "
)


def setup(bot):
    bot.add_cog(Dungeon(bot))
