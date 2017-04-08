from discord.ext import commands
try:
    from chatterbot import ChatBot
    chatbotInstalled = True
except:
    chatbotInstalled = False


class ChatterBot:
    """Chatter with the bot."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def chatterbot(self, ctx, message):
        """Talk with the bot via ChatterBot."""
        chatbot = ChatBot('Red-DiscordBot', trainer='chatterbot.trainers.ChatterBotCorpusTrainer')
        chatbot.train("chatterbot.corpus.english")
        await self.bot.say(chatbot.get_response(message))


def setup(bot):
    if chatbotInstalled is False:
        raise RuntimeError("Install ChatterBot:\n"
                           "[p]debug bot.pip_install('ChatterBot')\n"
                           "Then [p]load chatterbot")
    bot.add_cog(ChatterBot(bot))
