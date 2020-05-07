from .quiz import Quiz

def setup(bot):
    bot.add_cog(Quiz(bot))
