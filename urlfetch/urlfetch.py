import asyncio
import aiohttp
import logging
from urllib.parse import urlparse

from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

log = logging.getLogger("red.aikaterna.urlfetch")


__version__ = "1.1.0"


class UrlFetch(commands.Cog):
    """Grab stuff from a text API."""

    def __init__(self, bot):
        self.bot = bot

        self._headers = {'User-Agent': 'Python/3.8'}

    @commands.command()
    async def urlfetch(self, ctx, url: str):
        """
        Input a URL to read.
        """
        async with ctx.typing():
            valid_url = await self._valid_url(ctx, url)
            if valid_url:
                text = await self._get_url_content(url)
                if text:
                    page_list = []
                    for page in pagify(text, delims=["\n"], page_length=1800):
                        page_list.append(box(page))
                    if len(page_list) == 1:
                        await ctx.send(box(page))
                    else:
                        await menu(ctx, page_list, DEFAULT_CONTROLS)
            else:
                return

    async def _get_url_content(self, url: str):
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(headers=self._headers, timeout=timeout) as session:
                async with session.get(url) as resp:
                    text = await resp.text()
            return text
        except aiohttp.client_exceptions.ClientConnectorError:
            log.error(f"aiohttp failure accessing site at url:\n\t{url}", exc_info=True)
            return None
        except asyncio.exceptions.TimeoutError:
            log.error(f"asyncio timeout while accessing feed at url:\n\t{url}")
            return None
        except Exception:
            log.error(f"General failure accessing site at url:\n\t{url}", exc_info=True)
            return None

    async def _valid_url(self, ctx, url: str):
        try:
            result = urlparse(url)
        except Exception as e:
            log.exception(e, exc_info=e)
            await ctx.send("There was an issue trying to fetch that site. Please check your console for the error.")
            return None

        if all([result.scheme, result.netloc]):
            text = await self._get_url_content(url)
            if not text:
                await ctx.send("No text present at the given url.")
                return None
            else:
                return text
        else:
            await ctx.send(f"That url seems to be incomplete.")
            return None
