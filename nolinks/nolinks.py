import discord
import re
from redbot.core import Config, commands, checks

LINKS = re.compile(
    "(\|\|)?(([\w]+:)?\/\/)?(([\d\w]|%[a-fA-f\d]{2,2})+(:([\d\w]|%[a-fA-f\d]{2,2})+)?@)?([\d\w][-\d\w]{0,253}[\d\w]\.)+[\w]{2,63}(:[\d]+)?(\/([-+_~.\d\w]|%[a-fA-f\d]{2,2})*)*(\?(&?([-+_~.\d\w]|%[a-fA-f\d]{2,2})=?)*)?(#([-+_~.\d\w]|%[a-fA-f\d]{2,2})*)?(\|\|)?"
)


class NoLinks(commands.Cog):
    """A heavy-handed hammer for anything that looks like a link."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2740131001, force_registration=True)

        default_guild = {"report_channel": None, "role": [], "watching": []}

        self.config.register_guild(**default_guild)

    @commands.group()
    @checks.mod_or_permissions(administrator=True)
    @commands.guild_only()
    async def nolinks(self, ctx):
        """Configuration options."""
        pass

    @nolinks.command()
    async def channel(self, ctx, channel: discord.TextChannel = None):
        """Set the message transfer channel. Leave the channel blank to turn it off."""
        if not channel:
            await self.config.guild(ctx.guild).report_channel.clear()
            return await ctx.send("Message transfer channel turned off.")
        await self.config.guild(ctx.guild).report_channel.set(channel.id)
        await ctx.send(f"Message transfer channel set to: {channel.mention}.")

    @nolinks.command()
    async def rolelist(self, ctx):
        """List whitelisted roles."""
        role_list = await self.config.guild(ctx.guild).role()
        role_msg = "Whitelisted Roles:\n"
        for role in role_list:
            role_obj = discord.utils.get(ctx.guild.roles, id=role)
            role_msg += f"{role_obj.name}\n"
        await ctx.send(role_msg)

    @nolinks.command()
    async def removerole(self, ctx, *, role_name: discord.Role):
        """Remove a whitelisted role."""
        role_list = await self.config.guild(ctx.guild).role()
        if role_name.id in role_list:
            role_list.remove(role_name.id)
        else:
            return await ctx.send("Role not in whitelist.")
        await self.config.guild(ctx.guild).role.set(role_list)
        role_obj = discord.utils.get(ctx.guild.roles, id=role_name.id)
        await ctx.send(f"{role_obj.name} removed from the link whitelist.")

    @nolinks.command()
    async def role(self, ctx, *, role_name: discord.Role):
        """Add a whitelisted role."""
        role_list = await self.config.guild(ctx.guild).role()
        if role_name.id not in role_list:
            role_list.append(role_name.id)
        await self.config.guild(ctx.guild).role.set(role_list)
        role_obj = discord.utils.get(ctx.guild.roles, id=role_name.id)
        await ctx.send(f"{role_obj.name} appended to the role whitelist.")

    @nolinks.command()
    async def watch(self, ctx, channel: discord.TextChannel):
        """Add a channel to watch. Links will be removed in these channels."""
        channel_list = await self.config.guild(ctx.guild).watching()
        if channel.id not in channel_list:
            channel_list.append(channel.id)
        await self.config.guild(ctx.guild).watching.set(channel_list)
        await ctx.send(f"{self.bot.get_channel(channel.id).mention} will have links removed.")

    @nolinks.command()
    async def watchlist(self, ctx):
        """List the channels being watched."""
        channel_list = await self.config.guild(ctx.guild).watching()
        msg = "Links will be removed in:\n"
        if not channel_list:
            msg += "No channels."
        else:
            remove_list = []
            for channel in channel_list:
                channel_obj = self.bot.get_channel(channel)
                if not channel_obj:
                    remove_list.append(channel)
                else:
                    msg += f"{channel_obj.mention}\n"
            if remove_list:
                new_list = [x for x in channel_list if x not in remove_list]
                await self.config.guild(ctx.guild).watching.set(new_list)
                if len(remove_list) == len(channel_list):
                    msg += "No channels."
        await ctx.send(msg)

    @nolinks.command()
    async def unwatch(self, ctx, channel: discord.TextChannel):
        """Remove a channel from the watch list."""
        channel_list = await self.config.guild(ctx.guild).watching()
        if channel.id in channel_list:
            channel_list.remove(channel.id)
        else:
            return await ctx.send("Channel is not being watched.")
        await self.config.guild(ctx.guild).watching.set(channel_list)
        await ctx.send(f"{self.bot.get_channel(channel.id).mention} will not have links removed.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return
        if message.author.bot:
            return
        data = await self.config.guild(message.guild).all()
        watch_channel_list = data["watching"]
        if not watch_channel_list:
            return
        if message.channel.id not in watch_channel_list:
            return
        allowed_roles = []
        for role in data["role"]:
            whitelist_role = discord.utils.get(message.author.roles, id=role)
            if whitelist_role:
                allowed_roles.append(whitelist_role)
        message_channel = self.bot.get_channel(data["report_channel"])
        if not allowed_roles:
            try:
                sentence = message.content.split()
                for word in sentence:
                    if self._match_url(word):
                        msg = "**Message Removed in** {} ({})\n".format(message.channel.mention, message.channel.id)
                        msg += "**Message sent by**: {} ({})\n".format(message.author.name, message.author.id)
                        msg += "**Message content**:\n{}".format(message.content)
                        if message_channel:
                            await message_channel.send(msg)
                        await message.delete()
            except Exception as e:
                if message_channel:
                    await message_channel.send(e)
                pass

    @staticmethod
    def _match_url(url):
        return LINKS.match(url)
