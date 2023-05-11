import asyncio
import datetime
import discord
import inspect
import itertools
import logging
import re

from contextlib import suppress as sps
from tabulate import tabulate
from typing import Optional

from redbot.core import checks, commands
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils.common_filters import filter_invites
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS, close_menu

from .converter import FuzzyMember

log = logging.getLogger("red.aikaterna.tools")


class Tools(commands.Cog):
    """Mod and Admin tools."""

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    def __init__(self, bot):
        self.bot = bot

    async def _Tools__error(self, ctx, error):
        if error.__cause__:
            cause = error.__cause__
            log.info(f"Tools Cog :: Error Occured ::\n{error}\n{cause}\n")
        else:
            cause = error
            log.info(f"Tools Cog :: Error Occured :: \n{cause}\n")

    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    @commands.group()
    async def access(self, ctx):
        """Check channel access"""
        pass

    @access.command()
    async def compare(self, ctx, user: discord.Member, guild: int = None):
        """Compare channel access with another user."""
        if guild is None:
            guild = ctx.guild
        else:
            guild = self.bot.get_guild(guild)

        try:
            tcs = guild.text_channels
            vcs = guild.voice_channels
        except AttributeError:
            return await ctx.send("User is not in that guild or I do not have access to that guild.")

        author_text_channels = [c for c in tcs if c.permissions_for(ctx.author).read_messages is True]
        author_voice_channels = [c for c in vcs if c.permissions_for(ctx.author).connect is True]

        user_text_channels = [c for c in tcs if c.permissions_for(user).read_messages is True]
        user_voice_channels = [c for c in vcs if c.permissions_for(user).connect is True]

        # text channels only the author has access to
        author_only_t = set(author_text_channels) - set(user_text_channels)
        # voice channels only the author has access to
        author_only_v = set(author_voice_channels) - set(user_voice_channels)

        # text channels only the user has access to
        user_only_t = set(user_text_channels) - set(author_text_channels)
        # voice channels only the user has access to
        user_only_v = set(user_voice_channels) - set(author_voice_channels)

        # text channels that author and user have in common
        common_t = list(set([c for c in tcs]) - author_only_t - user_only_t)
        # voice channels that author and user have in common
        common_v = list(set([c for c in vcs]) - author_only_v - user_only_v)

        text_common_access = ", ".join([c.name for c in common_t])
        text_user_exclusive_access = ", ".join([c.name for c in user_only_t])
        text_author_exclusive_access = ", ".join([c.name for c in author_only_t])
        voice_common_access = ", ".join([c.name for c in common_v])
        voice_user_exclusive_access = ", ".join([c.name for c in user_only_v])
        voice_author_exclusive_access = ", ".join([c.name for c in author_only_v])

        msg = f"{len(common_t)} [TEXT CHANNELS IN COMMON]:\n\n{text_common_access}\n\n"
        msg += f"{len(user_only_t)} [TEXT CHANNELS {user.name.upper()} HAS EXCLUSIVE ACCESS TO]:\n\n{text_user_exclusive_access}\n\n"
        msg += f"{len(author_only_t)} [TEXT CHANNELS YOU HAVE EXCLUSIVE ACCESS TO]:\n\n{text_author_exclusive_access}\n\n\n"
        msg += f"{len(common_v)} [VOICE CHANNELS IN COMMON]:\n\n{voice_common_access}\n\n"
        msg += f"{len(user_only_v)} [VOICE CHANNELS {user.name.upper()} HAS EXCLUSIVE ACCESS TO]:\n\n{voice_user_exclusive_access}\n\n"
        msg += f"{len(author_only_v)} [VOICE CHANNELS YOU HAVE EXCLUSIVE ACCESS TO]:\n\n{voice_author_exclusive_access}\n\n"
        for page in cf.pagify(cf.box(msg, lang="ini"), delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @access.command()
    async def text(self, ctx, user: discord.Member = None, guild: int = None):
        """Check text channel access."""
        if user is None:
            user = ctx.author
        if guild is None:
            guild = ctx.guild
        else:
            guild = self.bot.get_guild(guild)

        try:
            can_access = [c.name for c in guild.text_channels if c.permissions_for(user).read_messages == True]
            text_channels = [c.name for c in guild.text_channels]
        except AttributeError:
            return await ctx.send("User is not in that guild or I do not have access to that guild.")

        prefix = "You have" if user.id == ctx.author.id else user.name + " has"
        no_access = ", ".join(list(set(text_channels) - set(can_access)))
        msg = f"\n[{prefix} access to {len(can_access)} out of {len(text_channels)} text channels]\n\n"
        msg += f"[ACCESS]:\n{', '.join(can_access)}\n\n"
        msg += f"[NO ACCESS]:\n{no_access}"
        for page in cf.pagify(cf.box(msg, lang="ini"), delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @access.command()
    async def voice(self, ctx, user: discord.Member = None, guild: int = None):
        """Check voice channel access."""
        if user is None:
            user = ctx.author
        if guild is None:
            guild = ctx.guild
        else:
            guild = self.bot.get_guild(guild)

        try:
            can_access = [c.name for c in guild.voice_channels if c.permissions_for(user).connect is True]
            voice_channels = [c.name for c in guild.voice_channels]
        except AttributeError:
            return await ctx.send("User is not in that guild or I do not have access to that guild.")

        prefix = "You have" if user.id == ctx.author.id else user.name + " has"
        no_access = ", ".join(list(set(voice_channels) - set(can_access)))
        msg = f"\n[{prefix} access to {len(can_access)} out of {len(voice_channels)} voice channels]\n\n"
        msg += f"[ACCESS]:\n{', '.join(can_access)}\n\n"
        msg += f"[NO ACCESS]:\n{no_access}"
        for page in cf.pagify(cf.box(msg, lang="ini"), delims=["\n"], shorten_by=16):
            await ctx.send(page)

    @commands.guild_only()
    @commands.command()
    @checks.mod_or_permissions(manage_guild=True)
    async def banlist(self, ctx):
        """Displays the server's banlist."""
        try:
            banlist = [bans async for bans in ctx.guild.bans()]
        except discord.errors.Forbidden:
            await ctx.send("I do not have the `Ban Members` permission.")
            return
        bancount = len(banlist)
        ban_list = []
        if bancount == 0:
            msg = "No users are banned from this server."
        else:
            msg = ""
            for user_obj in banlist:
                user_name = f"{user_obj.user.name}#{user_obj.user.discriminator}"
                msg += f"`{user_obj.user.id} - {user_name}`\n"

        banlist = sorted(msg)
        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            embed_list = []
            for page in cf.pagify(msg, shorten_by=1400):
                embed = discord.Embed(
                    description=f"**Total bans:** {bancount}\n\n{page}",
                    colour=await ctx.embed_colour(),
                )
                embed_list.append(embed)
            await menu(ctx, embed_list, DEFAULT_CONTROLS)
        else:
            text_list = []
            for page in cf.pagify(msg, shorten_by=1400):
                text = f"**Total bans:** {bancount}\n{page}"
                text_list.append(text)
            await menu(ctx, text_list, DEFAULT_CONTROLS)

    @commands.guild_only()
    @commands.command()
    async def cid(self, ctx):
        """Shows the channel id for the current channel."""
        await ctx.send(f"**#{ctx.channel.name} ID:** {ctx.channel.id}")

    @commands.guild_only()
    @commands.command()
    async def chinfo(self, ctx, channel: int = None):
        """Shows channel information. Defaults to current text channel."""
        if channel is None:
            channel = ctx.channel
        else:
            channel = self.bot.get_channel(channel)

        if channel is None:
            return await ctx.send("Not a valid channel.")

        if channel:
            guild = channel.guild

        yesno = {True: "Yes", False: "No"}
        typemap = {
            discord.TextChannel: "Text Channel",
            discord.VoiceChannel: "Voice Channel",
            discord.CategoryChannel: "Category",
            discord.StageChannel: "Stage Channel",
            discord.Thread: "Thread",
        }

        with sps(Exception):
            caller = inspect.currentframe().f_back.f_code.co_name.strip()

        data = ""
        if caller == "invoke" or channel.guild != ctx.guild:
            data += f"[Server]:          {channel.guild.name}\n"
        data += f"[Name]:            {cf.escape(str(channel))}\n"
        data += f"[ID]:              {channel.id}\n"
        data += f"[Private]:         {yesno[isinstance(channel, discord.abc.PrivateChannel)]}\n"
        if isinstance(channel, discord.TextChannel) and channel.topic != None:
            data += f"[Topic]:           {channel.topic}\n"
        try:
            data += f"[Position]:        {channel.position}\n"
        except AttributeError:
            # this is a thread
            data += f"[Parent Channel]:  {channel.parent.name} ({channel.parent.id})\n"
            data += f"[Parent Position]: {channel.parent.position}\n"
        try:
            data += f"[Created]:         {self._dynamic_time(channel.created_at)}\n"
        except AttributeError:
            # this is a thread
            data += f"[Updated]:         {self._dynamic_time(channel.archive_timestamp)}\n"
        data += f"[Type]:            {typemap[type(channel)]}\n"
        if isinstance(channel, discord.TextChannel) and channel.is_news():
            data += f"[News Channel]:    {yesno[channel.is_news()]}\n"
        if isinstance(channel, discord.VoiceChannel):
            data += f"[Users]:           {len(channel.members)}\n"
            data += f"[User limit]:      {channel.user_limit}\n"
            data += f"[Bitrate]:         {int(channel.bitrate / 1000)}kbps\n"

        await ctx.send(cf.box(data, lang="ini"))

    @commands.guild_only()
    @commands.command()
    async def eid(self, ctx, emoji: discord.Emoji):
        """Get an id for an emoji."""
        await ctx.send(f"**ID for {emoji}:**   {emoji.id}")

    @commands.guild_only()
    @commands.command()
    async def einfo(self, ctx, emoji: discord.Emoji):
        """Emoji information."""
        yesno = {True: "Yes", False: "No"}
        header = f"{str(emoji)}\n"
        m = (
            f"[Name]:       {emoji.name}\n"
            f"[Guild]:      {emoji.guild}\n"
            f"[URL]:        {emoji.url}\n"
            f"[Animated]:   {yesno[emoji.animated]}"
        )
        await ctx.send(header + cf.box(m, lang="ini"))

    @commands.guild_only()
    @commands.command()
    @checks.mod_or_permissions(manage_guild=True)
    async def inrole(self, ctx, *, rolename: str):
        """Check members in the role specified."""
        guild = ctx.guild
        await ctx.typing()
        if rolename.startswith("<@&"):
            role_id = int(re.search(r"<@&(.{17,19})>$", rolename)[1])
            role = discord.utils.get(ctx.guild.roles, id=role_id)
        elif len(rolename) in [17, 18, 19] and rolename.isdigit():
            role = discord.utils.get(ctx.guild.roles, id=int(rolename))
        else:
            role = discord.utils.find(lambda r: r.name.lower() == rolename.lower(), guild.roles)

        if role is None:
            roles = []
            for r in guild.roles:
                if rolename.lower() in r.name.lower():
                    roles.append(r)

            if len(roles) == 1:
                role = roles[0]
            elif len(roles) < 1:
                await ctx.send(f"No roles containing `{rolename}` were found.")
                return
            else:
                msg = (
                    f"**{len(roles)} roles found with** `{rolename}` **in the name.**\n"
                    f"Type the number of the role you wish to see.\n\n"
                )
                tbul8 = []
                for num, role in enumerate(roles):
                    tbul8.append([num + 1, role.name])
                m1 = await ctx.send(msg + tabulate(tbul8, tablefmt="plain"))

                def check(m):
                    if (m.author == ctx.author) and (m.channel == ctx.channel):
                        return True

                try:
                    response = await self.bot.wait_for("message", check=check, timeout=25)
                except asyncio.TimeoutError:
                    await m1.delete()
                    return
                if not response.content.isdigit():
                    await m1.delete()
                    return
                else:
                    response = int(response.content)

                if response not in range(0, len(roles) + 1):
                    return await ctx.send("Cancelled.")
                elif response == 0:
                    return await ctx.send("Cancelled.")
                else:
                    role = roles[response - 1]

        users_in_role = "\n".join(sorted(m.display_name for m in guild.members if role in m.roles))
        if len(users_in_role) == 0:
            if ctx.channel.permissions_for(ctx.guild.me).embed_links:
                embed = discord.Embed(
                    description=cf.bold(f"0 users found in the {role.name} role."),
                    colour=await ctx.embed_colour(),
                )
                return await ctx.send(embed=embed)
            else:
                return await ctx.send(cf.bold(f"0 users found in the {role.name} role."))

        embed_list = []
        role_len = len([m for m in guild.members if role in m.roles])
        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            for page in cf.pagify(users_in_role, delims=["\n"], page_length=200):
                embed = discord.Embed(
                    description=cf.bold(f"{role_len} users found in the {role.name} role.\n"),
                    colour=await ctx.embed_colour(),
                )
                embed.add_field(name="Users", value=page)
                embed_list.append(embed)
            final_embed_list = []
            for i, embed in enumerate(embed_list):
                embed.set_footer(text=f"Page {i + 1}/{len(embed_list)}")
                final_embed_list.append(embed)
            if len(embed_list) == 1:
                close_control = {"\N{CROSS MARK}": close_menu}
                await menu(ctx, final_embed_list, close_control)
            else:
                await menu(ctx, final_embed_list, DEFAULT_CONTROLS)
        else:
            for page in cf.pagify(users_in_role, delims=["\n"], page_length=200):
                msg = f"**{role_len} users found in the {role.name} role.**\n"
                msg += page
                embed_list.append(msg)
            if len(embed_list) == 1:
                close_control = {"\N{CROSS MARK}": close_menu}
                await menu(ctx, embed_list, close_control)
            else:
                await menu(ctx, embed_list, DEFAULT_CONTROLS)

    @commands.guild_only()
    @commands.command()
    async def joined(self, ctx, user: discord.Member = None):
        """Show when a user joined the guild."""
        if not user:
            user = ctx.author
        if user.joined_at:
            user_joined = user.joined_at.strftime("%d %b %Y %H:%M")
            since_joined = (ctx.message.created_at - user.joined_at).days
            joined_on = f"{user_joined} ({since_joined} days ago)"
        else:
            joined_on = "a mysterious date that not even Discord knows."

        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            embed = discord.Embed(
                description=f"{user.mention} joined this guild on {joined_on}.",
                color=await ctx.embed_colour(),
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"**{user.display_name}** joined this guild on **{joined_on}**.")

    @commands.command(name="listguilds", aliases=["listservers", "guildlist", "serverlist"])
    @checks.mod_or_permissions()
    async def listguilds(self, ctx):
        """List the guilds|servers the bot is in."""
        guilds = sorted(self.bot.guilds, key=lambda g: -g.member_count)
        plural = "s" if len(guilds) > 1 else ""
        header = f"The bot is in the following {len(guilds)} server{plural}:\n"
        max_zpadding = max([len(str(g.member_count)) for g in guilds])
        form = "{gid} :: {mems:0{zpadding}} :: {name}"
        all_forms = [
            form.format(gid=g.id, mems=g.member_count, name=filter_invites(cf.escape(g.name)), zpadding=max_zpadding)
            for g in guilds
        ]
        final = "\n".join(all_forms)

        await ctx.send(cf.box(header))
        page_list = []
        for page in cf.pagify(final, delims=["\n"], page_length=1000):
            page_list.append(cf.box(page, lang="asciidoc"))

        if len(page_list) == 1:
            return await ctx.send(cf.box(page, lang="asciidoc"))
        await menu(ctx, page_list, DEFAULT_CONTROLS)

    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    @commands.command(name="listchannel", aliases=["channellist"])
    async def listchannel(self, ctx):
        """
        List the channels of the current server
        """
        top_channels, category_channels = self.sort_channels(ctx.guild.channels)

        top_channels_formed = "\n".join(self.channels_format(top_channels))
        categories_formed = "\n\n".join([self.category_format(tup) for tup in category_channels])

        await ctx.send(
            f"{ctx.guild.name} has {len(ctx.guild.channels)} channel{'s' if len(ctx.guild.channels) > 1 else ''}."
        )

        for page in cf.pagify(top_channels_formed, delims=["\n"], shorten_by=16):
            await ctx.send(cf.box(page, lang="asciidoc"))

        for page in cf.pagify(categories_formed, delims=["\n\n"], shorten_by=16):
            await ctx.send(cf.box(page, lang="asciidoc"))

    @commands.guild_only()
    @commands.command()
    @checks.mod_or_permissions(manage_guild=True)
    async def newusers(self, ctx, count: int = 5, text_format: str = "py"):
        """
        Lists the newest 5 members.

        `text_format` is the markdown language to use. Defaults to `py`.
        """
        count = max(min(count, 25), 5)
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)[:count]

        header = f"{count} newest members"
        disp = "{:>33}\n{}\n\n".format(header, "-" * 57)

        user_body = " {mem} ({memid})\n"
        user_body += " {spcs}Joined Guild:    {sp1}{join}\n"
        user_body += " {spcs}Account Created: {sp2}{created}\n\n"

        spcs = [" " * (len(m.name) // 2) for m in members]
        smspc = min(spcs, key=lambda it: len(it))

        def calculate_diff(date1, date2):
            date1str, date2str = self._dynamic_time(date1), self._dynamic_time(date2)
            date1sta, date2sta = date1str.split(" ")[0], date2str.split(" ")[0]

            if len(date1sta) == len(date2sta):
                return (0, 0)
            else:
                ret = len(date2sta) - len(date1sta)
                return (abs(ret), 0 if ret > 0 else 1)

        for member in members:
            req = calculate_diff(member.joined_at, member.created_at)
            sp1 = req[0] if req[1] == 0 else 0
            sp2 = req[0] if req[1] == 1 else 0

            disp += user_body.format(
                mem=member.display_name,
                memid=member.id,
                join=self._dynamic_time(member.joined_at),
                created=self._dynamic_time(member.created_at),
                spcs=smspc,
                sp1="0" * sp1,
                sp2="0" * sp2,
            )

        for page in cf.pagify(disp, delims=["\n\n"]):
            await ctx.send(cf.box(page, lang=text_format))

    @commands.guild_only()
    @commands.command()
    @checks.mod_or_permissions(manage_guild=True)
    async def perms(self, ctx, user: discord.Member = None):
        """Fetch a specific user's permissions."""
        if user is None:
            user = ctx.author

        perms = iter(ctx.channel.permissions_for(user))
        perms_we_have = ""
        perms_we_dont = ""
        for x in sorted(perms):
            if "True" in str(x):
                perms_we_have += "+ {0}\n".format(str(x).split("'")[1])
            else:
                perms_we_dont += "- {0}\n".format(str(x).split("'")[1])
        await ctx.send(cf.box(f"{perms_we_have}{perms_we_dont}", lang="diff"))

    @commands.guild_only()
    @commands.command()
    async def rid(self, ctx, *, rolename):
        """Shows the id of a role."""
        await ctx.typing()
        if rolename is discord.Role:
            role = rolename
        else:
            role = self.role_from_string(ctx.guild, rolename)
        if role is None:
            await ctx.send(f"Cannot find role: `{rolename}`")
            return
        await ctx.send(f"**{rolename} ID:** {role.id}")

    @commands.guild_only()
    @commands.command()
    async def rinfo(self, ctx, *, rolename: discord.Role):
        """Shows role info."""
        await ctx.typing()

        try:
            caller = inspect.currentframe().f_back.f_code.co_name
        except:
            pass

        if not isinstance(rolename, discord.Role):
            role = self.role_from_string(ctx.guild, rolename, ctx.guild.roles)
        else:
            role = rolename
        if role is None:
            await ctx.send("That role cannot be found.")
            return

        perms = iter(role.permissions)
        perms_we_have = ""
        perms_we_dont = ""

        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            for x in sorted(perms):
                if "True" in str(x):
                    perms_we_have += "{0}\n".format(str(x).split("'")[1])
                else:
                    perms_we_dont += "{0}\n".format(str(x).split("'")[1])
            if perms_we_have == "":
                perms_we_have = "None"
            if perms_we_dont == "":
                perms_we_dont = "None"
            role_color = role.color if role.color else discord.Colour(value=0x000000)
            em = discord.Embed(colour=role_color)
            if caller == "invoke":
                em.add_field(name="Server", value=role.guild.name)
            em.add_field(name="Role Name", value=role.name)
            em.add_field(name="Created", value=self._dynamic_time(role.created_at))
            em.add_field(name="Users in Role", value=len([m for m in ctx.guild.members if role in m.roles]))
            em.add_field(name="ID", value=role.id)
            em.add_field(name="Color", value=role.color)
            em.add_field(name="Position", value=role.position)
            em.add_field(name="Valid Permissions", value=perms_we_have)
            em.add_field(name="Invalid Permissions", value=perms_we_dont)
            if role.guild.icon:
                em.set_thumbnail(url=role.guild.icon.url)
            await ctx.send(embed=em)
        else:
            role = self.role_from_string(ctx.guild, rolename, ctx.guild.roles)
            if role is None:
                await ctx.send("That role cannot be found.")
                return

            for x in sorted(perms):
                if "True" in str(x):
                    perms_we_have += "+ {0}\n".format(str(x).split("'")[1])
                else:
                    perms_we_dont += "- {0}\n".format(str(x).split("'")[1])
            msg = ""
            msg += f"Name: {role.name}\n"
            msg += f"Created: {self._dynamic_time(role.created_at)}\n"
            msg += f"Users in Role : {len([m for m in role.guild.members if role in m.roles])}\n"
            msg += f"ID: {role.id}\n"
            msg += f"Color: {role.color}\n"
            msg += f"Position: {role.position}\n"
            msg += f"Valid Perms: \n{perms_we_have}\n"
            msg += f"Invalid Perms: \n{perms_we_dont}"
            await ctx.send(cf.box(msg, lang="diff"))

    @commands.guild_only()
    @commands.command(aliases=["listroles"])
    @checks.mod_or_permissions(manage_guild=True)
    async def rolelist(self, ctx):
        """Displays the server's roles."""
        form = "`{rpos:0{zpadding}}` - `{rid}` - `{rcolor}` - {rment} "
        max_zpadding = max([len(str(r.position)) for r in ctx.guild.roles])
        rolelist = [
            form.format(rpos=r.position, zpadding=max_zpadding, rid=r.id, rment=r.mention, rcolor=r.color)
            for r in ctx.guild.roles
        ]
        rolelist = sorted(rolelist, reverse=True)
        rolelist = "\n".join(rolelist)
        embed_list = []
        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            for page in cf.pagify(rolelist, shorten_by=1400):
                embed = discord.Embed(
                    description=f"**Total roles:** {len(ctx.guild.roles)}\n\n{page}",
                    colour=await ctx.embed_colour(),
                )
                embed_list.append(embed)
        else:
            for page in cf.pagify(rolelist, shorten_by=1400):
                msg = f"**Total roles:** {len(ctx.guild.roles)}\n{page}"
                embed_list.append(msg)

        await menu(ctx, embed_list, DEFAULT_CONTROLS)

    @commands.command(hidden=True)
    async def sharedservers(self, ctx, user: discord.Member = None):
        """Shows shared server info. Defaults to author."""
        if not user:
            user = ctx.author

        mutual_guilds = user.mutual_guilds
        data = f"[Guilds]:     {len(mutual_guilds)} shared\n"
        shared_servers = sorted([g.name for g in mutual_guilds], key=lambda v: (v.upper(), v[0].islower()))
        data += f"[In Guilds]:  {cf.humanize_list(shared_servers, style='unit')}"

        for page in cf.pagify(data, ["\n"], page_length=1800):
            await ctx.send(cf.box(data, lang="ini"))

    @commands.guild_only()
    @commands.command()
    async def sid(self, ctx):
        """Show the server id."""
        await ctx.send(f"**{ctx.guild.name} ID:** {ctx.guild.id}")

    @commands.guild_only()
    @commands.command(aliases=["ginfo"])
    async def sinfo(self, ctx, guild=None):
        """Shows server information."""
        if guild is None:
            guild = ctx.guild
        else:
            try:
                guild = self.bot.get_guild(int(guild))
            except ValueError:
                return await ctx.send("Not a valid guild id.")
        online = str(len([m.status for m in guild.members if str(m.status) == "online" or str(m.status) == "idle"]))
        total_users = str(len(guild.members))
        text_channels = [x for x in guild.channels if isinstance(x, discord.TextChannel)]
        voice_channels = [x for x in guild.channels if isinstance(x, discord.VoiceChannel)]

        data = f"[Name]:     {guild.name}\n"
        data += f"[ID]:       {guild.id}\n"
        data += f"[Owner]:    {guild.owner}\n"
        data += f"[Users]:    {online}/{total_users}\n"
        data += f"[Text]:     {len(text_channels)} channels\n"
        data += f"[Voice]:    {len(voice_channels)} channels\n"
        data += f"[Emojis]:   {len(guild.emojis)}\n"
        data += f"[Stickers]: {len(guild.stickers)}\n"
        data += f"[Roles]:    {len(guild.roles)}\n"
        data += f"[Created]:  {self._dynamic_time(guild.created_at)}\n"

        await ctx.send(cf.box(data, lang="ini"))

    @commands.guild_only()
    @commands.command(aliases=["stickerinfo"])
    async def stinfo(self, ctx, message_link: str = None):
        """
        Sticker information.

        Attach a sticker to the command message or provide a link to a message with a sticker.
        """
        if message_link:
            message = await self.message_from_message_link(ctx, message_link)
        else:
            message = ctx.message

        if isinstance(message, str):
            return await ctx.send(message)

        stickers = message.stickers
        for sticker_item in stickers:
            sticker = await sticker_item.fetch()

            msg = f"[Name]:        {sticker.name}\n"
            msg += f"[Guild]:       {sticker.guild if sticker.guild != None else 'Guild name is unavailable'}\n"
            msg += f"[ID]:          {sticker.id}\n"
            msg += f"[URL]:         {str(sticker.url)}\n"
            msg += f"[Format]:      {sticker.format.file_extension if sticker.format.file_extension else 'lottie'}\n"
            if sticker.description:
                msg += f"[Description]: {sticker.description}\n"
            msg += f"[Created]:     {self._dynamic_time(sticker.created_at)}\n"

            await ctx.send(cf.box(msg, lang="ini"))

    @commands.guild_only()
    @commands.command()
    async def uid(self, ctx, partial_name_or_nick: Optional[FuzzyMember]):
        """Get a member's id from a fuzzy name search."""
        if partial_name_or_nick is None:
            partial_name_or_nick = [ctx.author]

        table = []
        headers = ["ID", "Name", "Nickname"]
        for user_obj in partial_name_or_nick:
            table.append([user_obj.id, user_obj.name, user_obj.nick if not None else ""])
        msg = tabulate(table, headers, tablefmt="simple")

        pages = []
        for page in cf.pagify(msg, delims=["\n"], page_length=1800):
            pages.append(cf.box(page))

        if len(pages) == 1:
            close_control = {"\N{CROSS MARK}": close_menu}
            await menu(ctx, pages, close_control)
        else:
            await menu(ctx, pages, DEFAULT_CONTROLS)

    @commands.guild_only()
    @commands.command()
    async def uimages(self, ctx, user: discord.Member = None, embed=False):
        """
        Shows user image urls. Defaults to author.

        `embed` is a True/False value for whether to display the info in an embed.
        """
        if user is None:
            user = ctx.author

        fetch_user = await self.bot.fetch_user(user.id)

        if not embed or not ctx.channel.permissions_for(ctx.guild.me).embed_links:
            data = f"[Name]:              {cf.escape(str(user))}\n"
            data += f"[Avatar URL]:        {user.avatar if user.avatar is not None else user.default_avatar}\n"
            if user.guild_avatar:
                data += f"[Server Avatar URL]: {user.guild_avatar}\n"
            if fetch_user.banner:
                data += f"[Banner URL]:        {fetch_user.banner}\n"

            await ctx.send(cf.box(data, lang="ini"))
        else:
            embed = discord.Embed(
                description=f"**{cf.escape(str(user))}**",
                colour=await ctx.embed_colour(),
            )
            if user.guild_avatar:
                embed.add_field(name="Server Avatar", value=user.guild_avatar, inline=False)
            embed.set_thumbnail(url=user.avatar if user.avatar is not None else user.default_avatar)
            if fetch_user.banner:
                embed.set_image(url=fetch_user.banner)
            await ctx.send(embed=embed)

    @commands.guild_only()
    @commands.command()
    async def uinfo(self, ctx, user: discord.Member = None):
        """Shows user information. Defaults to author."""
        if user is None:
            user = ctx.author

        with sps(Exception):
            caller = inspect.currentframe().f_back.f_code.co_name

        try:
            roles = [r for r in user.roles if r.name != "@everyone"]
            _roles = [
                roles[0].name,
            ] + [f"{r.name:>{len(r.name)+17}}" for r in roles[1:]]
        except IndexError:
            _roles = ["None"]

        seen = str(len(set([member.guild.name for member in self.bot.get_all_members() if member.id == user.id])))

        data = f"[Name]:          {cf.escape(str(user))}\n"
        data += f"[ID]:            {user.id}\n"
        data += f"[Status]:        {user.status}\n"
        data += f"[Servers]:       {seen} shared\n"
        if actplay := discord.utils.get(user.activities, type=discord.ActivityType.playing):
            data += f"[Playing]:       {cf.escape(str(actplay.name))}\n"
        if actlisten := discord.utils.get(user.activities, type=discord.ActivityType.listening):
            if isinstance(actlisten, discord.Spotify):
                _form = f"{actlisten.artist} - {actlisten.title}"
            else:
                _form = actlisten.name
            data += f"[Listening]:     {cf.escape(_form)}\n"
        if actwatch := discord.utils.get(user.activities, type=discord.ActivityType.watching):
            data += f"[Watching]:      {cf.escape(str(actwatch.name))}\n"
        if actstream := discord.utils.get(user.activities, type=discord.ActivityType.streaming):
            data += f"[Streaming]: [{cf.escape(str(actstream.name))}]({cf.escape(actstream.url)})\n"
        if actcustom := discord.utils.get(user.activities, type=discord.ActivityType.custom):
            if actcustom.name is not None:
                data += f"[Custom Status]: {cf.escape(str(actcustom.name))}\n"
        passed = (ctx.message.created_at - user.created_at).days
        data += f"[Created]:       {self._dynamic_time(user.created_at)}\n"
        joined_at = self.fetch_joined_at(user, ctx.guild)
        if caller != "invoke":
            role_list = "\n".join(_roles)
            data += f"[Joined]:        {self._dynamic_time(joined_at)}\n"
            data += f"[Roles]:         {role_list}\n"
            if len(_roles) > 1:
                data += "\n"
            data += f"[In Voice]:      {user.voice.channel if user.voice is not None else None}\n"
            data += f"[AFK]:           {user.voice.afk if user.voice is not None else False}\n"

        await ctx.send(cf.box(data, lang="ini"))

    @commands.guild_only()
    @commands.command()
    async def whatis(self, ctx, what_is_this_id: int):
        """What is it?"""
        it_is = False
        msg = False
        roles = []
        rls = [s.roles for s in self.bot.guilds]
        for rl in rls:
            roles.extend(rl)

        guild_list = [g for g in self.bot.guilds]
        emoji_list = [e for e in self.bot.emojis]

        look_at = (
            guild_list
            + emoji_list
            + roles
            + [m for m in self.bot.get_all_members()]
            + [c for c in self.bot.get_all_channels()]
        )

        if ctx.guild.id == what_is_this_id:
            it_is = ctx.guild
        elif ctx.channel.id == what_is_this_id:
            it_is = ctx.channel
        elif ctx.author.id == what_is_this_id:
            it_is = ctx.author

        if not it_is:
            it_is = discord.utils.get(look_at, id=what_is_this_id)

        if not it_is:
            for g in guild_list:
                thread_or_sticker = g.get_thread(what_is_this_id)
                if thread_or_sticker:
                    return await ctx.invoke(self.chinfo, what_is_this_id)

                for sticker in g.stickers:
                    if sticker.id == what_is_this_id:
                        return await ctx.invoke(self.stinfo, sticker)

        if isinstance(it_is, discord.Guild):
            await ctx.invoke(self.sinfo, what_is_this_id)
        elif isinstance(it_is, discord.abc.GuildChannel):
            await ctx.invoke(self.chinfo, what_is_this_id)
        elif isinstance(it_is, discord.Thread):
            await ctx.invoke(self.chinfo, what_is_this_id)
        elif isinstance(it_is, (discord.User, discord.Member)):
            await ctx.invoke(self.uinfo, it_is)
        elif isinstance(it_is, discord.Role):
            await ctx.invoke(self.rinfo, rolename=it_is)
        elif isinstance(it_is, discord.Emoji):
            await ctx.invoke(self.einfo, it_is)
        else:
            await ctx.send("I could not find anything for this ID.")

    @staticmethod
    def count_months(days):
        lens = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        cy = itertools.cycle(lens)
        months = 0
        m_temp = 0
        mo_len = next(cy)
        for i in range(1, days + 1):
            m_temp += 1
            if m_temp == mo_len:
                months += 1
                m_temp = 0
                mo_len = next(cy)
                if mo_len == 28 and months >= 48:
                    mo_len += 1

        weeks, days = divmod(m_temp, 7)
        return months, weeks, days

    def category_format(self, cat_chan_tuple: tuple):
        cat = cat_chan_tuple[0]
        chs = cat_chan_tuple[1]

        chfs = self.channels_format(chs)
        if chfs != []:
            ch_forms = ["\t" + f for f in chfs]
            return "\n".join([f"{cat.name} :: {cat.id}"] + ch_forms)
        else:
            return "\n".join([f"{cat.name} :: {cat.id}"] + ["\tNo Channels"])

    @staticmethod
    def channels_format(channels: list):
        if channels == []:
            return []

        channel_form = "{name} :: {ctype} :: {cid}"

        def type_name(channel):
            return channel.__class__.__name__[:-7]

        name_justify = max([len(c.name[:24]) for c in channels])
        type_justify = max([len(type_name(c)) for c in channels])

        return [
            channel_form.format(
                name=c.name[:24].ljust(name_justify),
                ctype=type_name(c).ljust(type_justify),
                cid=c.id,
            )
            for c in channels
        ]

    def _dynamic_time(self, time):
        try:
            date_join = datetime.datetime.strptime(str(time), "%Y-%m-%d %H:%M:%S.%f%z")
        except ValueError:
            time = f"{str(time)}.0"
            date_join = datetime.datetime.strptime(str(time), "%Y-%m-%d %H:%M:%S.%f%z")
        date_now = discord.utils.utcnow()
        since_join = date_now - date_join

        mins, secs = divmod(int(since_join.total_seconds()), 60)
        hrs, mins = divmod(mins, 60)
        days, hrs = divmod(hrs, 24)
        mths, wks, days = self.count_months(days)
        yrs, mths = divmod(mths, 12)

        m = f"{yrs}y {mths}mth {wks}w {days}d {hrs}h {mins}m {secs}s"
        m2 = [x for x in m.split() if x[0] != "0"]
        s = " ".join(m2[:2])
        if s:
            return f"{s} ago"
        else:
            return ""

    @staticmethod
    def fetch_joined_at(user, guild):
        return user.joined_at

    async def message_from_message_link(self, ctx: commands.Context, message_link: str):
        bad_link_msg = "That doesn't look like a message link, I can't reach that message, "
        bad_link_msg += "or you didn't attach a sticker to the command message."
        no_guild_msg = "You aren't in that guild."
        no_channel_msg = "You can't view that channel."
        no_message_msg = "That message wasn't found."
        no_sticker_msg = "There are no stickers attached to that message."

        if not "discord.com/channels/" in message_link:
            return bad_link_msg
        ids = message_link.split("/")
        if len(ids) != 7:
            return bad_link_msg

        guild = self.bot.get_guild(int(ids[4]))
        if not guild:
            return bad_link_msg

        channel = guild.get_channel_or_thread(int(ids[5]))
        if not channel:
            channel = self.bot.get_channel(int(ids[5]))
        if not channel:
            return bad_link_msg

        if ctx.author not in guild.members:
            return no_guild_msg
        if not channel.permissions_for(ctx.author).read_messages:
            return no_channel_msg

        try:
            message = await channel.fetch_message(int(ids[6]))
        except discord.errors.NotFound:
            return no_message_msg

        if not message.stickers:
            return no_sticker_msg

        return message

    @staticmethod
    def role_from_string(guild, rolename, roles=None):
        if roles is None:
            roles = guild.roles
        if rolename.startswith("<@&"):
            role_id = int(re.search(r"<@&(.{17,19})>$", rolename)[1])
            role = guild.get_role(role_id)
        else:
            role = discord.utils.find(lambda r: r.name.lower() == str(rolename).lower(), roles)
        return role

    def sort_channels(self, channels):
        temp = {}

        channels = sorted(channels, key=lambda c: c.position)

        for c in channels[:]:
            if isinstance(c, discord.CategoryChannel):
                channels.pop(channels.index(c))
                temp[c] = list()

        for c in channels[:]:
            if c.category:
                channels.pop(channels.index(c))
                temp[c.category].append(c)

        category_channels = sorted(
            [(cat, sorted(chans, key=lambda c: c.position)) for cat, chans in temp.items()],
            key=lambda t: t[0].position,
        )
        return channels, category_channels
