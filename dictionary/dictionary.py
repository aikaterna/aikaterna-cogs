import aiohttp
import discord
import contextlib
from bs4 import BeautifulSoup
import json
import logging
import re
from redbot.core import commands
from redbot.core.utils.chat_formatting import pagify


log = logging.getLogger("red.aikaterna.dictionary")


class Dictionary(commands.Cog):
    """
    Word, yo
    Parts of this cog are adapted from the PyDictionary library.
    """

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.command()
    async def define(self, ctx, *, word: str):
        """Displays definitions of a given word."""
        search_msg = await ctx.send("Searching...")
        search_term = word.split(" ", 1)[0]
        result = await self._definition(ctx, search_term)
        str_buffer = ""
        if not result:
            with contextlib.suppress(discord.NotFound):
                await search_msg.delete()
            await ctx.send("This word is not in the dictionary.")
            return
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
        with contextlib.suppress(discord.NotFound):
            await search_msg.delete()
        for page in pagify(str_buffer, delims=["\n"]):
            await ctx.send(page)

    async def _definition(self, ctx, word):
        data = await self._get_soup_object(f"http://wordnetweb.princeton.edu/perl/webwn?s={word}")
        if not data:
            return await ctx.send("Error fetching data.")
        types = data.findAll("h3")
        length = len(types)
        lists = data.findAll("ul")
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

    @commands.command()
    async def antonym(self, ctx, *, word: str):
        """Displays antonyms for a given word."""
        search_term = word.split(" ", 1)[0]
        result = await self._antonym_or_synonym(ctx, "antonyms", search_term)
        if not result:
            await ctx.send("This word is not in the dictionary or nothing was found.")
            return

        result_text = "*, *".join(result)
        msg = f"Antonyms for **{search_term}**: *{result_text}*"
        for page in pagify(msg, delims=["\n"]):
            await ctx.send(page)

    @commands.command()
    async def synonym(self, ctx, *, word: str):
        """Displays synonyms for a given word."""
        search_term = word.split(" ", 1)[0]
        result = await self._antonym_or_synonym(ctx, "synonyms", search_term)
        if not result:
            await ctx.send("This word is not in the dictionary or nothing was found.")
            return

        result_text = "*, *".join(result)
        msg = f"Synonyms for **{search_term}**: *{result_text}*"
        for page in pagify(msg, delims=["\n"]):
            await ctx.send(page)

    async def _antonym_or_synonym(self, ctx, lookup_type, word):
        if lookup_type not in ["antonyms", "synonyms"]:
            return None
        data = await self._get_soup_object(f"http://www.thesaurus.com/browse/{word}")
        if not data:
            await ctx.send("Error getting information from the website.")
            return

        script = data.find("script", id="preloaded-state")
        if script:
            script_text = script.string
            script_text = script_text.strip()
            script_text = script_text.replace("window.__PRELOADED_STATE__ = ", "")
        else:
            await ctx.send("Error fetching script from the website.")
            return

        try:
            data = json.loads(script_text)
        except json.decoder.JSONDecodeError:
            await ctx.send("Error decoding script from the website.")
            return
        except Exception as e:
            log.exception(e, exc_info=e)
            await ctx.send("Something broke. Check your console for more information.")
            return

        try:
            data_prefix = data["thesaurus"]["thesaurusData"]["data"]["slugs"][0]["entries"][0]["partOfSpeechGroups"][0]["shortDefinitions"][0]
        except KeyError:
            return None

        if lookup_type == "antonyms":
            try:
                antonym_subsection = data_prefix["antonyms"]
            except KeyError:
                return None
            antonyms = []
            for item in antonym_subsection:
                try:
                    antonyms.append(item["targetWord"])
                except KeyError:
                    pass
            if antonyms:
                return antonyms
            else:
                return None

        if lookup_type == "synonyms":
            try:
                synonyms_subsection = data_prefix["synonyms"]
            except KeyError:
                return None
            synonyms = []
            for item in synonyms_subsection:
                try:
                    synonyms.append(item["targetWord"])
                except KeyError:
                    pass
            if synonyms:
                return synonyms
            else:
                return None

    async def _get_soup_object(self, url):
        try:
            async with self.session.request("GET", url) as response:
                return BeautifulSoup(await response.text(), "html.parser")
        except Exception:
            log.error("Error fetching dictionary.py related webpage", exc_info=True)
            return None
