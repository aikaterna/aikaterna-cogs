from discord.ext import commands
from .utils import checks

class Post:
    def __init__(self,bot):
        self.bot = bot

    @commands.command(no_pm=True, pass_context=True)
    @checks.is_owner()
    async def postsongs(self, ctx, playlist):
        """Posts a playlist."""
        try:
             await self.bot.send_file(ctx.message.channel, 'data/audio/playlists/{}/{}.txt'.format(ctx.message.server.id, playlist))
        except FileNotFoundError:
             try:
                 await self.bot.send_file(ctx.message.channel, 'data/audio/playlists/{}.txt'.format(playlist))
             except FileNotFoundError:
                 await self.bot.say("No playlist named {}.".format(playlist))

    @commands.command(no_pm=True, pass_context=True)
    @checks.is_owner()
    async def postcog(self, ctx, cogname):
        """Posts a cog."""
        try:
             await self.bot.send_file(ctx.message.channel, 'cogs/{}.py'.format(cogname))
        except FileNotFoundError:
             await self.bot.say("No cog named {}.".format(cogname))

def setup(bot):
    n = Post(bot)
    bot.add_cog(n)
