import aiohttp
import re
from redbot.core import commands
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


class YouTube(commands.Cog):
    """Search YouTube for videos."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def _youtube_results(self, query: str):
        try:
            headers = {"user-agent": "Red-cog/3.0"}
            async with self.session.get(
                "https://www.youtube.com/results", params={"search_query": query}, headers=headers
            ) as r:
                result = await r.text()
            yt_find = re.findall(r"{\"videoId\":\"(.{11})", result)
            url_list = []
            for track in yt_find:
                url = f"https://www.youtube.com/watch?v={track}"
                if url not in url_list:
                    url_list.append(url)

        except Exception as e:
            url_list = [f"Something went terribly wrong! [{e}]"]

        return url_list

    @commands.command()
    async def youtube(self, ctx, *, query: str):
        """Search on Youtube."""
        result = await self._youtube_results(query)
        if result:
            await ctx.send(result[0])
        else:
            await ctx.send("Nothing found. Try again later.")

    @commands.command()
    async def ytsearch(self, ctx, *, query: str):
        """Search on Youtube, multiple results."""
        result = await self._youtube_results(query)
        if result:
            await menu(ctx, result, DEFAULT_CONTROLS)
        else:
            await ctx.send("Nothing found. Try again later.")

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
