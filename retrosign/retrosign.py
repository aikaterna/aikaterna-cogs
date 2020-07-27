# This is a rewrite port of a cog from Anismash:
# https://github.com/Anismash/Ani-Cogs/blob/master/retrosign/retrosign.py

import aiohttp
from bs4 import BeautifulSoup as bs
import discord
from redbot.core import commands
from io import BytesIO
from random import choice
import re
import unicodedata


class Retrosign(commands.Cog):
    """Make an 80s retro sign. Originally by Anismash"""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    @commands.cooldown(1, 15, discord.ext.commands.BucketType.guild)
    @commands.command(name="retrosign")
    async def retrosign(self, ctx, *, content: str):
        """Make a retrosign with 3 words seperated by ';' or with one word in the middle."""
        texts = [t.strip() for t in content.split(";")]
        if len(texts) == 1:
            lenstr = len(texts[0])
            if lenstr <= 15:
                data = dict(bcg=choice([1, 2, 3, 4, 5]), txt=choice([1, 2, 3, 4]), text1="", text2=texts[0], text3="",)
            else:
                return await ctx.send("\N{CROSS MARK} Your line is too long (14 character limit)")
        elif len(texts) == 3:
            texts[0] = unicodedata.normalize("NFD", texts[0]).encode("ascii", "ignore")
            texts[0] = texts[0].decode("UTF-8")
            texts[0] = re.sub(r"[^A-Za-z0-9 ]", "", texts[0])
            if len(texts[0]) >= 15:
                return await ctx.send("\N{CROSS MARK} Your first line is too long (14 character limit)")
            if len(texts[1]) >= 13:
                return await ctx.send("\N{CROSS MARK} Your second line is too long (12 character limit)")
            if len(texts[2]) >= 26:
                return await ctx.send("\N{CROSS MARK} Your third line is too long (25 character limit)")
            data = dict(
                bcg=choice([1, 2, 3, 4, 5]), txt=choice([1, 2, 3, 4]), text1=texts[0], text2=texts[1], text3=texts[2],
            )
        else:
            return await ctx.send("\N{CROSS MARK} please provide three words seperated by ';' or one word")

        async with ctx.channel.typing():
            async with self.session.post("https://photofunia.com/effects/retro-wave", data=data) as response:
                if response.status == 200:
                    soup = bs(await response.text(), "html.parser")
                    download_url = soup.find("div", class_="downloads-container").ul.li.a["href"]
                    async with self.session.request("GET", download_url) as image_response:
                        if image_response.status == 200:
                            image_data = await image_response.read()
                            with BytesIO(image_data) as temp_image:
                                image = discord.File(fp=temp_image, filename="image.png")
                                await ctx.channel.send(file=image)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
