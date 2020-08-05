from discord.ext import commands
import aiohttp
import re


class YouTube:
    """Le YouTube Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def _youtube_results(self, query: str):
        try:
            headers = {"user-agent": "Red-cog/2.0"}
            async with self.session.get("https://www.youtube.com/results", params={"search_query": query}, headers=headers) as r:
                result = await r.text()
            yt_find = re.findall(r"{\"videoId\":\"(.{11})", result)
            url_list = []
            for track in yt_find:
                url = "https://www.youtube.com/watch?v={}".format(track)
                if url not in url_list:
                    url_list.append(url)

        except Exception as e:
            url_list = ["Something went terribly wrong! [{}]".format(e)]

        return url_list

    @commands.command()
    async def youtube(self, ctx, *, query: str):
        """Search on Youtube."""
        result = await self._youtube_results(query)
        if result:
            await self.bot.say(result[0])
        else:
            await self.bot.say("Nothing found. Try again later.")


def setup(bot):
    n = YouTube(bot)
    bot.add_cog(n)
