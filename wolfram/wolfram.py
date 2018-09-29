import os
import aiohttp
from discord.ext import commands
import xml.etree.ElementTree as ET
from cogs.utils.dataIO import dataIO
from .utils import checks
from .utils.chat_formatting import escape_mass_mentions
from .utils.chat_formatting import box
from __main__ import send_cmd_help


class Wolfram:
    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json("data/wolfram/settings.json")

    @commands.command(pass_context=True, name="wolfram", aliases=["ask"])
    async def _wolfram(self, ctx, *arguments: str):
        """
        Ask Wolfram Alpha any question
        """
        api_key = self.settings["WOLFRAM_API_KEY"]
        if api_key:
            url = "http://api.wolframalpha.com/v2/query?"
            query = " ".join(arguments)
            payload = {"input": query, "appid": api_key}
            headers = {"user-agent": "Red-cog/1.0.0"}
            conn = aiohttp.TCPConnector(verify_ssl=False)
            session = aiohttp.ClientSession(connector=conn)
            async with session.get(url, params=payload, headers=headers) as r:
                result = await r.text()
            session.close()
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
            message = (
                "No API key set for Wolfram Alpha. Get one at http://products.wolframalpha.com/api/"
            )
        message = escape_mass_mentions(message)
        await self.bot.say(box(message))

    @commands.command(pass_context=True, name="setwolframapi", aliases=["setwolfram"])
    @checks.is_owner()
    async def _setwolframapi(self, ctx, key: str):
        """
        Set the api-key
        """
        if key:
            self.settings["WOLFRAM_API_KEY"] = key
            dataIO.save_json("data/wolfram/settings.json", self.settings)
            await self.bot.say("Key set.")
        else:
            await send_cmd_help(ctx)


def check_folder():
    if not os.path.exists("data/wolfram"):
        print("Creating data/wolfram folder...")
        os.makedirs("data/wolfram")


def check_file():
    data = {}
    data["WOLFRAM_API_KEY"] = False
    f = "data/wolfram/settings.json"
    if not dataIO.is_valid_json(f):
        print("Creating default settings.json...")
        dataIO.save_json(f, data)


def setup(bot):
    check_folder()
    check_file()
    n = Wolfram(bot)
    bot.add_cog(n)
