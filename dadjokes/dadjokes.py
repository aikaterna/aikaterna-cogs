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
        try:
            async with aiohttp.request("GET", "https://icanhazdadjoke.com/", headers={"Accept": "text/plain"}) as r:
                if r.status != 200:
                    return await ctx.send("Oops! Cannot get a dad joke...")
                result = await r.text(encoding="UTF-8")
        except aiohttp.ClientConnectionError:
            return await ctx.send("Oops! Cannot get a dad joke...")

        await ctx.send(f"`{result}`")
