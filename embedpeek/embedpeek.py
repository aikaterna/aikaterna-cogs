import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import box, pagify


class EmbedPeek(commands.Cog):
    """Take a closer look at an embed."""

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    def __init__(self, bot):
        self.bot = bot
        self._grave = "\N{GRAVE ACCENT}"

    @commands.command()
    async def embedpeek(self, ctx, message_link: str):
        """
        Take a closer look at an embed.

        On a webhook message or other multi-embed messages, this will only display the first embed.
        """
        bad_link_msg = "That doesn't look like a message link, I can't reach that message, or that link does not have an embed."
        no_message_msg = "That message wasn't found."

        if "discord.com/channels/" not in message_link:
            return await ctx.send(bad_link_msg)
        ids = message_link.split("/")
        if len(ids) != 7:
            return await ctx.send(bad_link_msg)

        guild = self.bot.get_guild(int(ids[4]))
        channel = self.bot.get_channel(int(ids[5]))
        try:
            message = await channel.fetch_message(int(ids[6]))
        except discord.errors.NotFound:
            return await ctx.send(no_message_msg)

        if ctx.author not in guild.members:
            no_guild_msg = "You aren't in that guild."
            return await ctx.send(no_guild_msg)
        if not channel.permissions_for(ctx.author).read_messages:
            no_channel_msg = "You can't view that channel."
            return await ctx.send(no_channel_msg)

        components = [guild, channel, message]
        valid_components = [x for x in components if x != None]
        if len(valid_components) < 3:
            return await ctx.send(bad_link_msg)

        try:
            embed = message.embeds[0]
        except IndexError:
            return await ctx.send(bad_link_msg)

        info = embed.to_dict()
        sorted_info = dict(sorted(info.items()))
        msg = ""

        for k, v in sorted_info.items():
            if k == "type":
                continue
            msg += f"+ {k}\n"
            if isinstance(v, str):
                msg += f"{v.replace(self._grave, '~')}\n\n"
            elif isinstance(v, list):
                for i, field in enumerate(v):
                    msg += f"--- field {i+1} ---\n"
                    for m, n in field.items():
                        msg += f"- {str(m).replace(self._grave, '~')}\n"
                        msg += f"{str(n).replace(self._grave, '~')}\n"
                    msg += "\n"
            elif isinstance(v, dict):
                msg += self._dict_cleaner(v)
                msg += "\n"
            else:
                msg += f"{str(v)}\n\n"

        for page in pagify(msg, delims=f"{'-' * 20}", page_length=1500):
            await ctx.send(box(page, lang="diff"))

    def _dict_cleaner(self, d: dict):
        msg = ""
        for k, v in d.items():
            k = str(k).replace(self._grave, "~")
            v = str(v).replace(self._grave, "~")
            msg += f"- {k}\n{v}\n"
        return msg
