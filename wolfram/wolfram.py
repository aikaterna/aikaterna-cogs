import aiohttp
import discord
from io import BytesIO
import xml.etree.ElementTree as ET
import urllib.parse

from redbot.core import Config, commands, checks
from redbot.core.utils.chat_formatting import box, pagify


class Wolfram(commands.Cog):
    """Ask Wolfram Alpha any question."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

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
        if not api_key:
            return await ctx.send("No API key set for Wolfram Alpha. Get one at http://products.wolframalpha.com/api/")

        url = "http://api.wolframalpha.com/v2/query?"
        query = " ".join(question)
        payload = {"input": query, "appid": api_key}
        headers = {"user-agent": "Red-cog/2.0.0"}
        async with ctx.typing():
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
            if "Current geoip location" in message:
                message = "There is as yet insufficient data for a meaningful answer."

        await ctx.send(box(message))

    @commands.command(name="wolframimage")
    async def _image(self, ctx, *arguments: str):
        """Ask Wolfram Alpha any question. Returns an image."""
        if not arguments:
            return await ctx.send_help()
        api_key = await self.config.WOLFRAM_API_KEY()
        if not api_key:
            return await ctx.send("No API key set for Wolfram Alpha. Get one at http://products.wolframalpha.com/api/")

        width = 800
        font_size = 30
        layout = "labelbar"
        background = "193555"
        foreground = "white"
        units = "metric"
        query = " ".join(arguments)
        query = urllib.parse.quote(query)
        url = f"http://api.wolframalpha.com/v1/simple?appid={api_key}&i={query}%3F&width={width}&fontsize={font_size}&layout={layout}&background={background}&foreground={foreground}&units={units}&ip=127.0.0.1"

        async with ctx.typing():
            async with self.session.request("GET", url) as r:
                img = await r.content.read()
                if len(img) == 43:
                    # img = b'Wolfram|Alpha did not understand your input'
                    return await ctx.send("There is as yet insufficient data for a meaningful answer.")
                wolfram_img = BytesIO(img)
                try:
                    await ctx.channel.send(file=discord.File(wolfram_img, f"wolfram{ctx.author.id}.png"))
                except Exception as e:
                    await ctx.send(f"Oops, there was a problem: {e}")

    @commands.command(name="wolframsolve")
    async def _solve(self, ctx, *, query: str):
        """Ask Wolfram Alpha any math question. Returns step by step answers."""
        api_key = await self.config.WOLFRAM_API_KEY()
        if not api_key:
            return await ctx.send("No API key set for Wolfram Alpha. Get one at http://products.wolframalpha.com/api/")

        url = f"http://api.wolframalpha.com/v2/query"
        params = {
            "appid": api_key,
            "input": query,
            "podstate": "Step-by-step solution",
            "format": "plaintext",
        }
        msg = ""

        async with ctx.typing():
            async with self.session.request("GET", url, params=params) as r:
                text = await r.content.read()
                root = ET.fromstring(text)
                for pod in root.findall(".//pod"):
                    if pod.attrib["title"] == "Number line":
                        continue
                    msg += f"{pod.attrib['title']}\n"
                    for pt in pod.findall(".//plaintext"):
                        if pt.text:
                            strip = pt.text.replace(" | ", " ").replace("| ", " ")
                            msg += f"- {strip}\n\n"
                if len(msg) < 1:
                    msg = "There is as yet insufficient data for a meaningful answer."
                for text in pagify(msg):
                    await ctx.send(box(text))

    @checks.is_owner()
    @commands.command(name="setwolframapi", aliases=["setwolfram"])
    async def _setwolframapi(self, ctx, key: str):
        """Set the api-key. The key is the AppID of your application on the Wolfram|Alpha Developer Portal."""

        if key:
            await self.config.WOLFRAM_API_KEY.set(key)
            await ctx.send("Key set.")

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
