import discord
from redbot.core import Config, commands, checks


BaseCog = getattr(commands, "Cog", object)

class Away(BaseCog):
    """Le away cog"""

    default_global_settings = {"ign_servers": []}
    default_user_settings = {"MESSAGE": False, "IDLE_MESSAGE": False,
                             "DND_MESSAGE": False, "OFFLINE_MESSAGE": False}

    def __init__(self, bot):
        self.bot = bot
        self._away = Config.get_conf(self, 8423491260, force_registration=True)

        self._away.register_global(**self.default_global_settings)
        self._away.register_user(**self.default_user_settings)

    async def make_embed_message(self, author, message, state=None):
        """
            Makes the embed reply
        """
        avatar = author.avatar_url_as() # This will return default avatar if no avatar is present
        color = author.color

        if state == "away":
            em = discord.Embed(description=message, color=color)
            em.set_author(
                name="{} is currently away".format(author.display_name),
                icon_url=avatar
            )
        elif state == "idle":
            em = discord.Embed(description=message, color=color)
            em.set_author(
                name="{} is currently idle".format(author.display_name),
                icon_url=avatar
            )
        elif state == "dnd":
            em = discord.Embed(description=message, color=color)
            em.set_author(
                name="{} is currently do not disturb".format(author.display_name),
                icon_url=avatar
            )
        elif state == "offline":
            em = discord.Embed(description=message, color=color)
            em.set_author(
                name="{} is currently offline".format(author.display_name),
                icon_url=avatar
            )
        else:
            em = discord.Embed(color=color)
            em.set_author(
                name="{} is currently away".format(author.display_name),
                icon_url=avatar
            )
        return em

    async def find_user_mention(self, message):
        """
            Replaces user mentions with their username
        """
        for word in message.split():
            if word.startswith("<@") and word.endswith(">"):
                mention = word.replace("<@", "").replace(">", "").replace("!", "")
                user = await self.bot.get_user_info(int(mention))
                message = message.replace(word, "@" + user.name)
        return message

    async def make_text_message(self, author, message, state=None):
        """
            Makes the message to display if embeds aren't available
        """
        message = await self.find_user_mention(message)
        if state == "away":
            msg = "{} is currently away and has set the following message: `{}`".format(
                author.display_name, message
            )
        elif state == "idle":
            msg = "{} is currently away and has set the following message: `{}`".format(
                author.display_name, message
            )
        elif state == "dnd":
            msg = "{} is currently away and has set the following message: `{}`".format(
                author.display_name, message
            )
        elif state == "offline":
            msg = "{} is currently away and has set the following message: `{}`".format(
                author.display_name, message
            )
        else:
            msg = "{} is currently away".format(author.display_name)
        return msg

    async def on_message(self, message):
        tmp = {}
        guild = message.guild
        list_of_guilds_ign = await self._away.ign_servers()
        if not guild:
            return
        if not message.channel.permissions_for(guild.me).send_messages:
            return
        if guild.id not in list_of_guilds_ign:
            for mention in message.mentions:
                tmp[mention] = True
            for author in tmp:
                away_msg = await self._away.user(author).MESSAGE()
                if away_msg:
                    if message.channel.permissions_for(guild.me).embed_links:                            
                        em = await self.make_embed_message(author, away_msg, "away")
                        await message.channel.send(embed=em)
                    else:
                        msg = await self.make_text_message(author, away_msg, "away")
                        await message.channel.send(msg)
                idle_msg = await self._away.user(author).IDLE_MESSAGE()
                if idle_msg and author.status == discord.Status.idle:
                    if message.channel.permissions_for(guild.me).embed_links:                            
                        em = await self.make_embed_message(author, idle_msg, "idle")
                        await message.channel.send(embed=em)
                    else:
                        msg = await self.make_text_message(author, idle_msg, "idle")
                        await message.channel.send(msg)
                dnd_msg = await self._away.user(author).DND_MESSAGE()
                if dnd_msg and author.status == discord.Status.dnd:
                    if message.channel.permissions_for(guild.me).embed_links:                            
                        em = await self.make_embed_message(author, dnd_msg, "dnd")
                        await message.channel.send(embed=em)
                    else:
                        msg = await self.make_text_message(author, dnd_msg, "dnd")
                        await message.channel.send(msg)
                offline_msg = await self._away.user(author).OFFLINE_MESSAGE()
                if offline_msg and author.status == discord.Status.offline:
                    if message.channel.permissions_for(guild.me).embed_links:                            
                        em = await self.make_embed_message(author, offline_msg, "offline")
                        await message.channel.send(embed=em)
                    else:
                        msg = await self.make_text_message(author, offline_msg, "offline")
                        await message.channel.send(msg)


    @commands.command(name="away")
    async def away_(self, ctx, *, message:str=None):
        """Tell the bot you're away or back."""
        author = ctx.message.author
        print(message)
        mess = await self._away.user(author).MESSAGE()
        if mess:
            await self._away.user(author).MESSAGE.set(False)
            msg = "You're now back."
        else:
            if message is None:
                await self._away.user(author).MESSAGE.set(" ")
            else:
                await self._away.user(author).MESSAGE.set(message)
            msg = "You're now set as away."
        await ctx.send(msg)

    @commands.command(name="idle")
    async def idle_(self, ctx, *, message:str=None):
        """Set an automatic reply when you're idle"""
        author = ctx.message.author
        mess = await self._away.user(author).IDLE_MESSAGE()
        if mess:
            await self._away.user(author).IDLE_MESSAGE.set(False)
            msg = "The bot will no longer reply for you when you're idle."
        else:
            if message is None:
                await self._away.user(author).IDLE_MESSAGE.set(" ")
            else:
                await self._away.user(author).IDLE_MESSAGE.set(message)
            msg = "The bot will now reply for you when you're idle."
        await ctx.send(msg)

    @commands.command(name="offline")
    async def offline_(self, ctx, *, message:str=None):
        """Set an automatic reply when you're offline"""
        author = ctx.message.author
        mess = await self._away.user(author).OFFLINE_MESSAGE()
        if mess:
            await self._away.user(author).OFFLINE_MESSAGE.set(False)
            msg = "The bot will no longer reply for you when you're offline."
        else:
            if message is None:
                await self._away.user(author).OFFLINE_MESSAGE.set(" ")
            else:
                await self._away.user(author).OFFLINE_MESSAGE.set(message)
            msg = "The bot will now reply for you when you're offline."
        await ctx.send(msg)

    @commands.command(name="dnd", aliases=["donotdisturb"])
    async def donotdisturb_(self, ctx, *, message:str=None):
        """Set an automatic reply when you're dnd"""
        author = ctx.message.author
        mess = await self._away.user(author).DND_MESSAGE()
        if mess:
            await self._away.user(author).DND_MESSAGE.set(False)
            msg = "The bot will no longer reply for you when you're set to do not disturb."
        else:
            if message is None:
                await self._away.user(author).DND_MESSAGE.set(" ")
            else:
                await self._away.user(author).DND_MESSAGE.set(message)
            msg = "The bot will now reply for you when you're set to do not disturb."
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
