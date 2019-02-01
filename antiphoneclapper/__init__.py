from .antiphoneclapper import AntiPhoneClapper


async def setup(bot):
    bot.add_cog(AntiPhoneClapper(bot))
