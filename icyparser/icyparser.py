import discord
import io
import lavalink
import logging
import struct
import re
from types import SimpleNamespace
from typing import List, Pattern, Optional
import urllib.error as urllib_error
import urllib.request as urllib_request

from redbot.core import commands
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


log = logging.getLogger("red.aikaterna.icyparser")


RUN_ONCE: bool = False
HTML_CLEANUP: Pattern = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")


def nice_to_icy(self):
    """
    Converts an Icecast/Shoutcast HTTP v0.9 response of "ICY 200 OK" to "200 OK" thanks to the power of monkeypatching
    dingles' answer on:
    https://stackoverflow.com/questions/4247248/record-streaming-and-saving-internet-radio-in-python/5465831
    """

    class InterceptedHTTPResponse:
        pass

    line = self.fp.readline().replace(b"ICY 200 OK\r\n", b"HTTP/1.0 200 OK\r\n")
    InterceptedSelf = InterceptedHTTPResponse()
    InterceptedSelf.fp = io.BufferedReader(io.BytesIO(line))
    InterceptedSelf.debuglevel = self.debuglevel
    InterceptedSelf._close_conn = self._close_conn
    return ORIGINAL_HTTP_CLIENT_READ_STATUS(InterceptedSelf)


if not RUN_ONCE:
    ORIGINAL_HTTP_CLIENT_READ_STATUS = urllib_request.http.client.HTTPResponse._read_status
    urllib_request.http.client.HTTPResponse._read_status = nice_to_icy
    RUN_ONCE = True


class IcyParser(commands.Cog):
    """Icyparser/Shoutcast stream reader."""

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    def __init__(self, bot):
        self.bot = bot

    async def _icyparser(self, url: Optional[str]) -> Optional[SimpleNamespace]:
        """
        Icecast/Shoutcast metadata reader.
        """
        # Catch for any playlist reader functions returning None back to the _icyparser function
        if not url:
            error = SimpleNamespace(error="That url didn't seem to contain any valid Icecast or Shoutcast links.")
            return error

        # Fetch the radio url
        try:
            request = urllib_request.Request(url, headers={"Icy-MetaData": 1})
        except ValueError:
            error = SimpleNamespace(
                error="Make sure you are using a full url formatted like `https://www.site.com/stream.mp3`."
            )
            return error

        try:
            resp = await self.bot.loop.run_in_executor(None, urllib_request.urlopen, request)
        except urllib_error.HTTPError as e:
            error = SimpleNamespace(
                error=f"There was an HTTP error returned while trying to access that url: {e.code} {e.reason}"
            )
            return error
        except urllib_error.URLError as e:
            error = SimpleNamespace(error=f"There was a timeout while trying to access that url.")
            return error
        except Exception:
            log.error(f"Icyparser encountered an unhandled error while trying to read a stream at {url}", exc_info=True)
            error = SimpleNamespace(error=f"There was an unexpected error while trying to fetch that url.")
            return error

        if url.endswith(".pls"):
            url = await self._pls_reader(resp.readlines())
            return await self._icyparser(url)

        metaint = resp.headers.get("icy-metaint", None)
        if not metaint:
            error = SimpleNamespace(
                error=f"The url provided doesn't seem like an Icecast or Shoutcast direct stream link: couldn't read the metadata length."
            )
            return error

        # Metadata reading
        try:
            for _ in range(5):
                resp.read(int(metaint))
                metadata_length = struct.unpack("B", resp.read(1))[0] * 16
                metadata = resp.read(metadata_length).rstrip(b"\0")
                m = re.search(br"StreamTitle='([^']*)';", metadata)
                if m:
                    title = m.group(1)
                    if len(title) > 0:
                        title = title.decode("utf-8", errors="replace")
                    else:
                        title = None
                else:
                    title = None

                image = False
                t = re.search(br"StreamUrl='([^']*)';", metadata)
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
            log.error(f"Icyparser encountered an error while trying to read a stream at {url}", exc_info=True)
        return None

    @commands.guild_only()
    @commands.command(aliases=["icynp"])
    async def icyparser(self, ctx, url=None):
        """Show Icecast or Shoutcast stream information, if any."""
        if not url:
            audiocog = self.bot.get_cog("Audio")
            if not audiocog:
                return await ctx.send(
                    "The Audio cog is not loaded. Provide a url with this command instead, to read from an online Icecast or Shoutcast stream."
                )
            try:
                player = lavalink.get_player(ctx.guild.id)
            except KeyError:
                return await ctx.send("The bot is not playing any music.")
            if not player.current:
                return await ctx.send("The bot is not playing any music.")
            if not player.current.is_stream:
                return await ctx.send("The bot is not playing a stream.")
            async with ctx.typing():
                radio_obj = await self._icyparser(player.current.uri)
        else:
            async with ctx.typing():
                radio_obj = await self._icyparser(url)

        if not radio_obj:
            return await ctx.send(
                f"Can't read the stream information for <{player.current.uri if not url else url}>, it may not be an Icecast or Shoutcast "
                "radio station or there may be no stream information available.\n"
                "This command needs a direct link to a MP3 or AAC encoded stream, or a PLS file that contains MP3 or AAC encoded streams."
            )

        if hasattr(radio_obj, "error"):
            return await ctx.send(radio_obj.error)

        embed_menu_list = []

        # Now Playing embed
        title = radio_obj.title if radio_obj.title is not None else "No stream title availible"
        song = f"**[{title}]({player.current.uri if not url else url})**\n"
        embed = discord.Embed(colour=await ctx.embed_colour(), title="Now Playing", description=song)

        # Set radio image if scraped or provided by the Icy headers
        if radio_obj.image:
            embed.set_thumbnail(url=radio_obj.image)
        else:
            icylogo = dict(radio_obj.resp_headers).get("icy-logo", None)
            if icylogo:
                embed.set_thumbnail(url=icylogo)

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

    @staticmethod
    def _clean_html(html: str) -> str:
        """
        Strip out any html, as subtle as a hammer.
        """
        plain_text = re.sub(HTML_CLEANUP, "", html)
        return plain_text

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
