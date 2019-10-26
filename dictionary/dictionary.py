import aiohttp
from bs4 import BeautifulSoup
import re
from redbot.core import commands


class Dictionary(commands.Cog):
    """Word, yo
    Parts of this cog are adapted from the PyDictionary library."""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def _get_soup_object(self, url):
        try:
            async with self.session.request("GET", url) as response:
                return BeautifulSoup(await response.text(), "html.parser")
        except Exception as e:
            print(e)
            return

    @commands.command()
    async def antonym(self, ctx, *, word: str):
        """Displays antonyms for a given word."""
        search_msg = await ctx.send("Searching...")
        search_term = word.split(" ", 1)[0]
        result = await self._antonym(ctx, search_term)
        if not result:
            return await search_msg.edit(content="This word is not in the dictionary.")

        result_text = "*, *".join(result)
        await search_msg.edit(content=f"Antonyms for **{search_term}**: *{result_text}*")

    async def _antonym(self, ctx, word):
        data = await self._get_soup_object(f"http://www.thesaurus.com/browse/{word}")
        section = data.find_all("ul", {"class": "css-1lc0dpe et6tpn80"})
        try:
            section[1]
        except IndexError:
            return
        spans = section[1].findAll("li")
        antonyms = [span.text for span in spans[:50]]
        return antonyms

    @commands.command()
    async def define(self, ctx, *, word: str):
        """Displays definitions of a given word."""
        search_msg = await ctx.send("Searching...")
        search_term = word.split(" ", 1)[0]
        result = await self._definition(ctx, search_term)
        str_buffer = ""
        if not result:
            return await search_msg.edit(content="This word is not in the dictionary.")
        for key in result:
            str_buffer += f"\n**{key}**: \n"
            counter = 1
            j = False
            for val in result[key]:
                if val.startswith("("):
                    str_buffer += f"{str(counter)}. *{val})* "
                    counter += 1
                    j = True
                else:
                    if j:
                        str_buffer += f"{val}\n"
                        j = False
                    else:
                        str_buffer += f"{str(counter)}. {val}\n"
                        counter += 1
        await search_msg.edit(content=str_buffer)

    async def _definition(self, ctx, word):
        html = await self._get_soup_object(f"http://wordnetweb.princeton.edu/perl/webwn?s={word}")
        types = html.findAll("h3")
        length = len(types)
        lists = html.findAll("ul")
        out = {}
        if not lists:
            return
        for a in types:
            reg = str(lists[types.index(a)])
            meanings = []
            for x in re.findall(r">\s\((.*?)\)\s<", reg):
                if "often followed by" in x:
                    pass
                elif len(x) > 5 or " " in str(x):
                    meanings.append(x)
            name = a.text
            out[name] = meanings
        return out

    async def _synonym(self, ctx, word):
        data = await self._get_soup_object(f"http://www.thesaurus.com/browse/{word}")
        section = data.find_all("ul", {"class": "css-1lc0dpe et6tpn80"})
        try:
            section[1]
        except IndexError:
            return
        spans = section[0].findAll("li")
        synonyms = [span.text for span in spans[:50]]
        return synonyms

    @commands.command()
    async def synonym(self, ctx, *, word: str):
        """Displays synonyms for a given word."""
        search_msg = await ctx.send("Searching...")
        search_term = word.split(" ", 1)[0]
        result = await self._synonym(ctx, search_term)
        if not result:
            return await search_msg.edit(content="This word is not in the dictionary.")

        result_text = "*, *".join(result)
        await search_msg.edit(content=f"Synonyms for **{search_term}**: *{result_text}*")
