import discord
from redbot.core import Config, commands, checks


BaseCog = getattr(commands, "Cog", object)

class Away(BaseCog):
    """Le away cog"""

    default_global_settings = {"ign_servers": []}
    default_user_settings = {"MESSAGE": False}

    def __init__(self, bot):
        self.bot = bot
        self._away = Config.get_conf(self, 8423491260, force_registration=True)

        self._away.register_global(**self.default_global_settings)
        self._away.register_user(**self.default_user_settings)

    async def on_message(self, message):
        tmp = {}
        guild = message.guild
        list_of_guilds_ign = await self._away.ign_servers()
        if not guild:
            return
        if guild.id not in list_of_guilds_ign:
            for mention in message.mentions:
                tmp[mention] = True
            if message.author.id != guild.me.id:
                for author in tmp:
                    test = await self._away.user(author).MESSAGE()
                    if test:
                        try:
                            avatar = (
                                author.avatar_url if author.avatar else author.default_avatar_url
                            )

                            if test:
                                em = discord.Embed(description=test, color=discord.Color.blue())
                                em.set_author(
                                    name="{} is currently away".format(author.display_name),
                                    icon_url=avatar,
                                )
                            else:
                                em = discord.Embed(color=discord.Color.blue())
                                em.set_author(
                                    name="{} is currently away".format(author.display_name),
                                    icon_url=avatar,
                                )
                            await message.channel.send(embed=em)
                        except:
                            if test:
                                msg = "{} is currently away and has set the following message: `{}`".format(
                                    author.display_name, test
                                )
                            else:
                                msg = "{} is currently away".format(author.display_name)
                            await message.channel.send(msg)

    @commands.command(name="away")
    async def away_(self, ctx, *message):
        """Tell the bot you're away or back."""
        author = ctx.message.author
        mess = await self._away.user(author).MESSAGE()
        if mess:
            await self._away.user(author).clear()
            msg = "You're now back."
        else:
            length = len(str(message))
            if length < 256 and length > 2:
                await self._away.user(author).MESSAGE.set(
                    " ".join(ctx.message.clean_content.split()[1:])
                )
            else:
                await self._away.user(author).MESSAGE.set(" ")
            msg = "You're now set as away."
        await ctx.send(msg)

    @commands.command(name="toggleaway")
    @checks.admin_or_permissions(administrator=True)
    async def _ignore(self, ctx):
        """Toggle away messages on the whole server."""
        guild = ctx.message.guild
        if guild.id in (await self._away.ign_servers()):
            guilds = await self._away.ign_servers()
            guilds.remove(guild.id)
            await self._away.ign_servers.set(guilds)
            message = "Not ignoring this guild anymore."
        else:
            guilds = await self._away.ign_servers()
            guilds.append(guild.id)
            await self._away.ign_servers.set(guilds)
            message = "Ignoring this guild."
        await ctx.send(message)
