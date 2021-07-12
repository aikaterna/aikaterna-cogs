from base64 import b64decode
import json
from io import BytesIO
import struct
from types import SimpleNamespace

from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box


class TrackDecoder(commands.Cog):
    """Decodes a b64 encoded audio track string."""

    def __init__(self, bot):
        self.bot = bot

    @checks.is_owner()
    @commands.command()
    @commands.guild_only()
    async def trackdecode(self, ctx: commands.Context, *, track: str):
        """
        Decodes a b64 encoded audio track string.

        This command is possible thanks to devoxin#0001's work.
        `https://github.com/Devoxin/Lavalink.py`
        """
        decoded = self.decode_track(track)
        if not decoded:
            return await ctx.send(f"Not a valid track.")

        msg = (
            f"[Title]:      {decoded.title}\n"
            f"[Author]:     {decoded.author}\n"
            f"[URL]:        {decoded.uri}\n"
            f"[Identifier]: {decoded.identifier}\n"
            f"[Source]:     {decoded.source}\n"
            f"[Length]:     {decoded.length}\n"
            f"[Stream]:     {decoded.is_stream}\n"
            f"[Position]:   {decoded.position}\n"
        )

        await ctx.send(box(msg, lang="ini"))

    @staticmethod
    def decode_track(track, decode_errors="ignore"):
        """
        Source is derived from:
        https://github.com/Devoxin/Lavalink.py/blob/3688fe6aff265ff53928ec811279177a88aa9664/lavalink/utils.py
        """
        reader = DataReader(track)

        try:
            flags = (reader.read_int() & 0xC0000000) >> 30
        except struct.error:
            return None

        (version,) = struct.unpack("B", reader.read_byte()) if flags & 1 != 0 else 1

        track = SimpleNamespace(
            title=reader.read_utf().decode(errors=decode_errors),
            author=reader.read_utf().decode(),
            length=reader.read_long(),
            identifier=reader.read_utf().decode(),
            is_stream=reader.read_boolean(),
            uri=reader.read_utf().decode() if reader.read_boolean() else None,
            source=reader.read_utf().decode(),
            position=reader.read_long(),
        )

        return track


class DataReader:
    """
    Source is from:
    https://github.com/Devoxin/Lavalink.py/blob/3688fe6aff265ff53928ec811279177a88aa9664/lavalink/datarw.py
    """

    def __init__(self, ts):
        self._buf = BytesIO(b64decode(ts))

    def _read(self, n):
        return self._buf.read(n)

    def read_byte(self):
        return self._read(1)

    def read_boolean(self):
        (result,) = struct.unpack("B", self.read_byte())
        return result != 0

    def read_unsigned_short(self):
        (result,) = struct.unpack(">H", self._read(2))
        return result

    def read_int(self):
        (result,) = struct.unpack(">i", self._read(4))
        return result

    def read_long(self):
        (result,) = struct.unpack(">Q", self._read(8))
        return result

    def read_utf(self):
        text_length = self.read_unsigned_short()
        return self._read(text_length)
