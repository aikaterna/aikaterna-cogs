import discord

class OtherbotStatus:
    def __init__(self, bot):
        self.bot = bot

    async def on_member_update(self, before, after):
        if after.status == discord.Status.offline and after.id == "000000000000000000":  #  this is the bot id that you want to watch
            channel_object = self.bot.get_channel("000000000000000000") #  this is the channel id for the watcher bot to scream in
            await self.bot.send_message(channel_object, "<@000000000000000000>, the bot is offline.")  # this is the person to ping and the message
        else:
            pass


def setup(bot):
    n = OtherbotStatus(bot)
    bot.add_cog(n)
