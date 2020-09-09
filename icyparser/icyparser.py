import aiohttp
import discord
import lavalink
import struct
import re
from redbot.core import commands


class IcyParser(commands.Cog):
    """Icyparser/Shoutcast stream reader."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def _icyparser(self, url: str):
        try:
            async with self.session.get(url, headers={"Icy-MetaData": "1"}) as resp:
                metaint = int(resp.headers["icy-metaint"])
                for _ in range(5):
                    await resp.content.readexactly(metaint)
                    metadata_length = struct.unpack("B", await resp.content.readexactly(1))[0] * 16
                    metadata = await resp.content.readexactly(metadata_length)
                    m = re.search(br"StreamTitle='([^']*)';", metadata.rstrip(b"\0"))
                    if m:
                        title = m.group(1)
                        if title:
                            title = title.decode("utf-8", errors="replace")
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

                    return title, streamurl, image

        except (KeyError, aiohttp.client_exceptions.ClientConnectionError):
            return None, None, None

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.guild_only()
    @commands.command(aliases=["icynp"])
    async def icyparser(self, ctx, url=None):
        """Show Icecast or Shoutcast stream information, if any."""
        if not url:
            audiocog = self.bot.get_cog("Audio")
            if not audiocog:
                return await ctx.send("Audio is not loaded.")
            try:
                player = lavalink.get_player(ctx.guild.id)
            except KeyError:
                return await ctx.send("The bot is not playing any music.")
            if not player.current:
                return await ctx.send("The bot is not playing any music.")
            if not player.current.is_stream:
                return await ctx.send("The bot is not playing a stream.")
            icy = await self._icyparser(player.current.uri)
        else:
            icy = await self._icyparser(url)
        if not icy[0]:
            return await ctx.send(
                f"Can't read the stream information for <{player.current.uri if not url else url}>, it may not be an Icecast or Shoutcast radio station or there may be no stream information available."
            )
        song = f"**[{icy[0]}]({player.current.uri if not url else url})**\n"
        embed = discord.Embed(colour=await ctx.embed_colour(), title="Now Playing", description=song)
        if icy[2]:
            embed.set_thumbnail(url=icy[1])
        await ctx.send(embed=embed)
