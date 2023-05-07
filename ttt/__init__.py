from .ttt import TTT

__red_end_user_data_statement__ = "This cog does store temporarily (in memory) data about users, which is cleared after the game is done."

async def setup(bot):
    await bot.add_cog(TTT(bot))
