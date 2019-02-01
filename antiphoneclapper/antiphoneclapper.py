from PIL import Image
from io import BytesIO
import aiohttp
import discord

from redbot.core import commands, checks, Config

BaseCog = getattr(commands, "Cog", object)


class AntiPhoneClapper(BaseCog):
    """This cog deletes bad GIFs that will crash phone clients."""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2719371001, force_registration=True)

        default_guild = {"watching": []}

        self.config.register_guild(**default_guild)

    @commands.group()
    @checks.mod_or_permissions(administrator=True)
    @commands.guild_only()
    async def nogif(self, ctx):
        """Configuration options."""
        pass

    @nogif.command()
    async def watch(self, ctx, channel: discord.TextChannel):
        """Add a channel to watch. Gifs that break mobile clients will be removed in these channels."""
        channel_list = await self.config.guild(ctx.guild).watching()
        if channel.id not in channel_list:
            channel_list.append(channel.id)
        await self.config.guild(ctx.guild).watching.set(channel_list)
        await ctx.send(f"{self.bot.get_channel(channel.id).mention} will have bad gifs removed.")

    @nogif.command()
    async def watchlist(self, ctx):
        """List the channels being watched."""
        channel_list = await self.config.guild(ctx.guild).watching()
        msg = "Bad gifs will be removed in:\n"
        for channel in channel_list:
            channel_obj = self.bot.get_channel(channel)
            msg += f"{channel_obj.mention}\n"
        await ctx.send(msg)

    @nogif.command()
    async def unwatch(self, ctx, channel: discord.TextChannel):
        """Remove a channel from the watch list."""
        channel_list = await self.config.guild(ctx.guild).watching()
        if channel.id in channel_list:
            channel_list.remove(channel.id)
        else:
            return await ctx.send("Channel is not being watched.")
        await self.config.guild(ctx.guild).watching.set(channel_list)
        await ctx.send(f"{self.bot.get_channel(channel.id).mention} will not have bad gifs removed.")

    def is_phone_clapper(self, im):
        limit = im.size
        tile_sizes = []
        for frame in range(im.n_frames):
            im.seek(frame)
            tile_sizes.append(im.tile[0][1][2:])
        return any([x[0] > limit[0] or x[1] > limit[1] for x in tile_sizes])

    async def on_message(self, m):
        if not m.attachments:
            return
        if isinstance(m.channel, discord.abc.PrivateChannel):
            return
        if m.author.bot:
            return
        watch_channel_list = await self.config.guild(m.guild).watching()
        if not watch_channel_list:
            return

        for att in m.attachments:
            if not att.filename.endswith('.gif') or att.size > 200000:
                continue

            async with aiohttp.ClientSession().get(att.url) as resp:
                data = await resp.content.read()
                f = BytesIO(data)
                try:
                    img = Image.open(f)
                    phone_clapper = self.is_phone_clapper(img)
                except Image.DecompressionBombError:
                    phone_clapper = True

            if phone_clapper:
                try:
                    await m.delete()
                    await m.channel.send(f"{m.author.mention} just tried to send a phone-killing GIF and I removed it.")
                    return
                except discord.errors.Forbidden:
                    await m.channel.send(f"Don't send GIFs that do that, {m.author.mention}")
                    print(f'Failed to delete message ({m.id}) that contained phone killing gif')
                    return
            else:
                return
