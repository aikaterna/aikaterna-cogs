from .antiphoneclapper import AntiPhoneClapper

__red_end_user_data_statemet__ = (
        "This cog does not persistently store data or metadata about users."
    )

async def setup(bot):
    bot.add_cog(AntiPhoneClapper(bot))
