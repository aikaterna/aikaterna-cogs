import asyncio
import aiohttp
from aiohttp.client_proto import ResponseHandler
from aiohttp.http_parser import HttpResponseParserPy
import discord
import functools
import io
import lavalink
import logging
from pkg_resources import parse_version
import struct
import re
from types import SimpleNamespace
from typing import List, Pattern, Optional

from redbot.core import commands
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


log = logging.getLogger("red.aikaterna.icyparser")


HTML_CLEANUP: Pattern = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")


# Now utilizing Jack1142's answer for ICY 200 OK -> 200 OK at
# https://stackoverflow.com/questions/4247248/record-streaming-and-saving-internet-radio-in-python/71890980


class ICYHttpResponseParser(HttpResponseParserPy):
    def parse_message(self, lines):
        if lines[0].startswith(b"ICY "):
            lines[0] = b"HTTP/1.0 " + lines[0][4:]
        return super().parse_message(lines)


class ICYResponseHandler(ResponseHandler):
    def set_response_params(
        self,
        *,
        timer=None,
        skip_payload=False,
        read_until_eof=False,
        auto_decompress=True,
        read_timeout=None,
        read_bufsize=2 ** 16,
        timeout_ceil_threshold=5,
    ) -> None:
        # this is a copy of the implementation from here:
        # https://github.com/aio-libs/aiohttp/blob/v3.8.1/aiohttp/client_proto.py#L137-L165
        self._skip_payload = skip_payload

        self._read_timeout = read_timeout
        self._reschedule_timeout()

        self._timeout_ceil_threshold = timeout_ceil_threshold

        self._parser = ICYHttpResponseParser(
            self,
            self._loop,
            read_bufsize,
            timer=timer,
            payload_exception=aiohttp.ClientPayloadError,
            response_with_body=not skip_payload,
            read_until_eof=read_until_eof,
            auto_decompress=auto_decompress,
        )

        if self._tail:
            data, self._tail = self._tail, b""
            self.data_received(data)


class ICYConnector(aiohttp.TCPConnector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._factory = functools.partial(ICYResponseHandler, loop=self._loop)


class IcyParser(commands.Cog):
    """Icyparser/Shoutcast stream reader."""

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    def __init__(self, bot):
        self.bot = bot
        self.timeout = aiohttp.ClientTimeout(total=20)
        self.session = session = aiohttp.ClientSession(
            connector=ICYConnector(), headers={"Icy-MetaData": "1"}, timeout=self.timeout
        )

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.guild_only()
    @commands.command(aliases=["icynp"])
    async def icyparser(self, ctx, url=None):
        """Show Icecast or Shoutcast stream information, if any.

        Supported link formats:
        \tDirect links to MP3, AAC, or OGG/Opus encoded Icecast or Shoutcast streams
        \tLinks to PLS, M3U, or M3U8 files that contain said stream types
        """
        if not url:
            audiocog = self.bot.get_cog("Audio")
            if not audiocog:
                return await ctx.send(
                    "The Audio cog is not loaded. Provide a url with this command instead, to read from an online Icecast or Shoutcast stream."
                )

            if parse_version(lavalink.__version__) <=  parse_version("0.9.0"):
                try:
                    player = lavalink.get_player(ctx.guild.id)
                except KeyError:
                    return await ctx.send("The bot is not playing any music.")
            else:
                try:
                    player = lavalink.get_player(ctx.guild.id)
                except lavalink.PlayerNotFound:
                    return await ctx.send("The bot is not playing any music.")
            if not player.current:
                return await ctx.send("The bot is not playing any music.")
            if not player.current.is_stream:
                return await ctx.send("The bot is not playing a stream.")
            async with ctx.typing():
                radio_obj = await self._icyreader(ctx, player.current.uri)
        else:
            async with ctx.typing():
                radio_obj = await self._icyreader(ctx, url)

        if not radio_obj:
            return

        embed_menu_list = []

        # Now Playing embed
        title = radio_obj.title if radio_obj.title is not None else "No stream title available"
        song = f"**[{title}]({player.current.uri if not url else url})**\n"
        embed = discord.Embed(colour=await ctx.embed_colour(), title="Now Playing", description=song)

        # Set radio image if scraped or provided by the Icy headers
        if radio_obj.image:
            embed.set_thumbnail(url=radio_obj.image)
        else:
            icylogo = dict(radio_obj.resp_headers).get("icy-logo", None)
            if icylogo:
                embed.set_thumbnail(url=icylogo)
            else:
                icyfavicon = dict(radio_obj.resp_headers).get("icy-favicon", None)
                if icyfavicon:
                    embed.set_thumbnail(url=icyfavicon)

        # Set radio description if present
        radio_station_description = dict(radio_obj.resp_headers).get("icy-description", None)
        if radio_station_description == "Unspecified description":
            radio_station_description = None
        if radio_station_description:
            embed.set_footer(text=radio_station_description)

        embed_menu_list.append(embed)

        # Metadata info embed(s)
        stream_info_text = ""
        sorted_radio_obj_dict = dict(sorted(radio_obj.resp_headers))
        for k, v in sorted_radio_obj_dict.items():
            v = self._clean_html(v)
            stream_info_text += f"**{k}**: {v}\n"

        if len(stream_info_text) > 1950:
            for page in pagify(stream_info_text, delims=["\n"], page_length=1950):
                info_embed = discord.Embed(
                    colour=await ctx.embed_colour(), title="Radio Station Metadata", description=page
                )
                embed_menu_list.append(info_embed)
        else:
            info_embed = discord.Embed(
                colour=await ctx.embed_colour(), title="Radio Station Metadata", description=stream_info_text
            )
            embed_menu_list.append(info_embed)

        await menu(ctx, embed_menu_list, DEFAULT_CONTROLS)

    async def _icyreader(self, ctx: commands.Context, url: Optional[str]) -> Optional[SimpleNamespace]:
        """
        Icecast/Shoutcast stream reader.
        """
        try:
            extensions = [".pls", ".m3u", ".m3u8"]
            if any(url.endswith(x) for x in extensions):
                async with self.session.get(url) as resp:
                    lines = []
                    async for line in resp.content:
                        lines.append(line)

                    if url.endswith(".pls"):
                        url = await self._pls_reader(lines)
                    else:
                        url = await self._m3u_reader(lines)

                    if url:
                        await self._icyreader(ctx, url)
                    else:
                        await ctx.send("That url didn't seem to contain any valid Icecast or Shoutcast links.")
                        return

            async with self.session.get(url) as resp:
                metaint = await self._metaint_read(ctx, resp)
                if metaint:
                    radio_obj = await self._metadata_read(int(metaint), resp)
                    return radio_obj

        except aiohttp.client_exceptions.InvalidURL:
            await ctx.send(f"{url} is not a valid url.")
            return None
        except aiohttp.client_exceptions.ClientConnectorError:
            await ctx.send("The connection failed.")
            return None
        except aiohttp.client_exceptions.ClientPayloadError as e:
            friendly_msg = "The website closed the connection prematurely or the response was malformed.\n"
            friendly_msg += f"The error returned was: `{str(e)}`\n"
            await ctx.send(friendly_msg)
            return None
        except asyncio.exceptions.TimeoutError:
            await ctx.send("The bot timed out while trying to access that url.")
            return None
        except aiohttp.client_exceptions.ServerDisconnectedError:
            await ctx.send("The target server disconnected early without a response.")
            return None
        except Exception:
            log.error(
                f"Icyparser's _icyreader encountered an error while trying to read a stream at {url}", exc_info=True
            )
            return None

    @staticmethod
    async def _metaint_read(ctx: commands.Context, resp: aiohttp.client_reqrep.ClientResponse) -> Optional[int]:
        """Fetch the metaint value to know how much of the stream header to read, for metadata."""
        metaint = resp.headers.get("icy-metaint", None)
        if not metaint:
            error_msg = (
                "The url provided doesn't seem like an Icecast or Shoutcast direct stream link, "
                "or doesn't contain a supported format stream link: couldn't read the metadata length."
            )
            await ctx.send(error_msg)
            return None

        try:
            metaint = int(metaint)
            return metaint
        except ValueError:
            return None

    @staticmethod
    async def _metadata_read(metaint: int, resp: aiohttp.client_reqrep.ClientResponse) -> Optional[SimpleNamespace]:
        """Read the metadata at the beginning of the stream chunk."""
        try:
            for _ in range(5):
                await resp.content.readexactly(metaint)
                metadata_length = struct.unpack("B", await resp.content.readexactly(1))[0] * 16
                metadata = await resp.content.readexactly(metadata_length)
                m = re.search(br"StreamTitle='([^']*)';", metadata.rstrip(b"\0"))
                if m:
                    title = m.group(1)
                    if len(title) > 0:
                        title = title.decode("utf-8", errors="replace")
                    else:
                        title = None
                else:
                    title = None

                image = False
                t = re.search(br"StreamUrl='([^']*)';", metadata.rstrip(b"\0"))
                if t:
                    streamurl = t.group(1)
                    if streamurl:
                        streamurl = streamurl.decode("utf-8", errors="replace")
                        image_ext = ["webp", "png", "jpg", "gif"]
                        if streamurl.split(".")[-1] in image_ext:
                            image = True
                else:
                    streamurl = None

                radio_obj = SimpleNamespace(title=title, image=streamurl, resp_headers=resp.headers.items())
                return radio_obj

        except Exception:
            log.error(
                f"Icyparser's _metadata_read encountered an error while trying to read a stream at {resp.url}", exc_info=True
            )
        return None

    @staticmethod
    def _clean_html(html: str) -> str:
        """
        Strip out any html, as subtle as a hammer.
        """
        plain_text = re.sub(HTML_CLEANUP, "", html)
        return plain_text

    @staticmethod
    async def _m3u_reader(readlines: List[bytes]) -> Optional[str]:
        """
        Helper function for a quick and dirty M3U or M3U8 file read.
        M3U8's will most likely contain .ts files, which are not readable by this cog.

        Some M3Us seem to follow the standard M3U format, some only have a bare url in
        the file, so let's just return the very first url with an http or https prefix
        found, if it's formatted like a real url and not a relative url, and is not a .ts chunk.
        """
        for text_line in readlines:
            text_line_str = text_line.decode()
            if text_line_str.startswith("http"):
                if not text_line_str.endswith(".ts"):
                    return text_line_str

        return None

    @staticmethod
    async def _pls_reader(readlines: List[bytes]) -> Optional[str]:
        """
        Helper function for a quick and dirty PLS file read.
        """
        for text_line in readlines:
            text_line_str = text_line.decode()
            if text_line_str.startswith("File1="):
                return text_line_str[6:]

        return None
