from redbot.core import commands
import aiohttp


class DadJokes(commands.Cog):
    """Random dad jokes from icanhazdadjoke.com"""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def dadjoke(self, ctx):
        """Gets a random dad joke."""
        api = "https://icanhazdadjoke.com/"
        async with aiohttp.request("GET", api, headers={"Accept": "text/plain"}) as r:
            result = await r.text()
            await ctx.send(f"`{result}`")
