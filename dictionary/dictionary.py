from redbot.core import commands
from PyDictionary import PyDictionary


class Dictionary(commands.Cog):
    """Word, yo"""

    def __init__(self, bot):
        self.bot = bot
        self.dictionary = PyDictionary()

    @commands.command()
    async def define(self, ctx, *, word: str):
        """Displays definitions of a given word."""
        search_msg = await ctx.send("Searching...")
        search_term = word.split(" ", 1)[0]
        result = self.dictionary.meaning(search_term)
        str_buffer = ""
        if result is None:
            await search_msg.edit(content="This word is not in the dictionary.")
            return
        for key in result:
            str_buffer += "\n**" + key + "**: \n"
            counter = 1
            j = False
            for val in result[key]:
                if val.startswith("("):
                    str_buffer += str(counter) + ". *" + val + ")* "
                    counter += 1
                    j = True
                else:
                    if j:
                        str_buffer += val + "\n"
                        j = False
                    else:
                        str_buffer += str(counter) + ". " + val + "\n"
                        counter += 1
        await search_msg.edit(content=str_buffer)
