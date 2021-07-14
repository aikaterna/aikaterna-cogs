from .discordexperiments import DiscordExperiments


def setup(bot):
    bot.add_cog(DiscordExperiments(bot))
