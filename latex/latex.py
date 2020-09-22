import aiohttp
import discord
import io
import logging
import re
from PIL import Image, ImageOps
import urllib.parse as parse
from redbot.core import commands


log = logging.getLogger("red.aikaterna.latex")

START_CODE_BLOCK_RE = re.compile(r"^((```(la)?tex)(?=\s)|(```))")


class Latex(commands.Cog):
    """LaTeX expressions via an image."""

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    @staticmethod
    def cleanup_code_block(content):
        # remove ```latex\n```/```tex\n```/``````
        if content.startswith("```") and content.endswith("```"):
            return START_CODE_BLOCK_RE.sub("", content)[:-3]
        
        # remove `foo`
        return content.strip("` \n")

    @commands.guild_only()
    @commands.command()
    async def latex(self, ctx, *, equation):
        """Takes a LaTeX expression and makes it pretty."""
        base_url = "https://latex.codecogs.com/gif.latex?%5Cbg_white%20%5CLARGE%20"
        equation = self.cleanup_code_block(equation)
        equation = parse.quote(equation)
        url = f"{base_url}{equation}"

        try:
            async with self.session.get(url) as r:
                image = await r.read()
            image = Image.open(io.BytesIO(image)).convert("RGBA")
        except Exception as exc:
            log.exception("Something went wrong while trying to read the image:\n ", exc_info=exc)
            image = None

        if not image:
            return await ctx.send("I can't get the image from the website, check your console for more information.")

        image = ImageOps.expand(image, border=10, fill="white")
        image_file_object = io.BytesIO()
        image.save(image_file_object, format="png")
        image_file_object.seek(0)
        image_final = discord.File(fp=image_file_object, filename="latex.png")
        await ctx.send(file=image_final)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
