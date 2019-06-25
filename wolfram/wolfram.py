import aiohttp
import os
from redbot.core import Config, commands, checks
from redbot.core.utils.chat_formatting import box
import xml.etree.ElementTree as ET


class Wolfram(commands.Cog):
    """Ask Wolfram Alpha any question."""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

        default_global = {"WOLFRAM_API_KEY": None}

        self.config = Config.get_conf(self, 2788801004)
        self.config.register_guild(**default_global)

    @commands.command(name="wolfram", aliases=["ask"])
    async def _wolfram(self, ctx, *question: str):
        """Ask Wolfram Alpha any question."""

        api_key = await self.config.WOLFRAM_API_KEY()

        if api_key:
            url = "http://api.wolframalpha.com/v2/query?"
            query = " ".join(question)
            payload = {"input": query, "appid": api_key}
            headers = {"user-agent": "Red-cog/2.0.0"}
            async with self.session.get(url, params=payload, headers=headers) as r:
                result = await r.text()
            root = ET.fromstring(result)
            a = []
            for pt in root.findall(".//plaintext"):
                if pt.text:
                    a.append(pt.text.capitalize())
            if len(a) < 1:
                message = "There is as yet insufficient data for a meaningful answer."
            else:
                message = "\n".join(a[0:3])
        else:
            message = "No API key set for Wolfram Alpha. Get one at http://products.wolframalpha.com/api/"
        await ctx.send(box(message))

    @checks.is_owner()
    @commands.command(name="setwolframapi", aliases=["setwolfram"])
    async def _setwolframapi(self, ctx, key: str):
        """Set the api-key."""

        if key:
            await self.config.WOLFRAM_API_KEY.set(key)
            await ctx.send("Key set.")

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
