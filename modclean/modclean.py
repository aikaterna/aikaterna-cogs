import discord
import re
from cogs.utils import checks
from discord.ext import commands


class ModClean:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(no_pm=True, pass_context=True)
    @checks.is_owner()
    async def modclean(self, ctx, modchannel: discord.Channel = None):
        """Clean a v2 mod-log channel of invite names."""
        if not modchannel:
            return await self.bot.say(
                "Please use the mod channel in the command. ({}modclean #channelname)".format(
                    ctx.prefix
                )
            )

        IL_raw = r"(discordapp.com/invite|discord.me|discord.gg)(?:/#)?(?:/invite)?/([a-z0-9\-]+)"
        InvLink = re.compile(IL_raw, re.I)

        try:
            async for m in self.bot.logs_from(modchannel, 100):
                if not (m.author == ctx.message.server.me):
                    continue
                elif InvLink.search(m.content) is None:
                    continue
                else:
                    new_cont = InvLink.sub("[REMOVED LINK]", m.content)
                    await self.bot.edit_message(m, new_cont)
        except discord.errors.Forbidden:
            return await self.bot.say("No permissions to read that channel.")
        await self.bot.say("Done.")


def setup(bot):
    bot.add_cog(ModClean(bot))
