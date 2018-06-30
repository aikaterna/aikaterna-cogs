import os
import aiohttp
from redbot.core import Config, commands, checks
import xml.etree.ElementTree as ET


class Wolfram:
    """Ask Wolfram Alpha a question."""
    def __init__(self, bot):
        self.bot = bot
		
        default_global = {
            "WOLFRAM_API_KEY": None,
        }
		
        self.config = Config.get_conf(self, 2788801004)
        self.config.register_guild(**default_global)


    @commands.command(name='wolfram', aliases=['ask'])
    async def _wolfram(self, ctx, *arguments: str):
        """
        Ask Wolfram Alpha any question.
        """
        api_key = await self.config.WOLFRAM_API_KEY()
        if api_key:
            url = 'http://api.wolframalpha.com/v2/query?'
            query = ' '.join(arguments)
            payload = {'input': query, 'appid': api_key}
            headers = {'user-agent': 'Red-cog/2.0.0'}
            conn = aiohttp.TCPConnector(verify_ssl=False)
            session = aiohttp.ClientSession(connector=conn)
            async with session.get(url, params=payload, headers=headers) as r:
                result = await r.text()
            session.close()
            root = ET.fromstring(result)
            a = []
            for pt in root.findall('.//plaintext'):
                if pt.text:
                    a.append(pt.text.capitalize())
            if len(a) < 1:
                message = 'There is as yet insufficient data for a meaningful answer.'
            else:
                message = '\n'.join(a[0:3])
        else:
            message = 'No API key set for Wolfram Alpha. Get one at http://products.wolframalpha.com/api/'
        await ctx.send('```{0}```'.format(message))

    @commands.command(name='setwolframapi', aliases=['setwolfram'])
    @checks.is_owner()
    async def _setwolframapi(self, ctx, key: str):
        """
        Set the api-key.
        """
        if key:
            await self.config.WOLFRAM_API_KEY.set(key)
            await ctx.send("Key set.")
