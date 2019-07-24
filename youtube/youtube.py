import aiohttp
import re
from redbot.core import commands
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


class YouTube(commands.Cog):
    """Search YouTube for videos."""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def _youtube_results(self, query: str):
        try:
            search_url = "https://www.youtube.com/results?"
            payload = {"search_query": "".join(query)}
            headers = {"user-agent": "Red-cog/3.0"}
            async with self.session.get(search_url, params=payload, headers=headers) as r:
                result = await r.text()
            yt_find = re.findall(r"href=\"\/watch\?v=(.{11})", result)

            url_list = []
            for track in yt_find:
                url = f"https://www.youtube.com/watch?v={track}"
                url_list.append(url)

        except Exception as e:
            url_list = [f"Something went terribly wrong! [{e}]"]

        return list(set(url_list))

    @commands.command()
    async def youtube(self, ctx, *, query: str):
        """Search on Youtube."""
        result = await self._youtube_results(query)
        await ctx.send(result[0])

    @commands.command()
    async def ytsearch(self, ctx, *, query: str):
        """Search on Youtube, multiple results."""
        result = await self._youtube_results(query)
        await menu(ctx, result, DEFAULT_CONTROLS)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
