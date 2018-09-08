# Most of these tools are thanks to Sitryk.
# Credit for the findcog/cmd_lookup command belongs to Axas, thanks for the inspiration for
# the findcog command in Red v3.

from discord.ext import commands
from .utils.chat_formatting import pagify, box, escape_mass_mentions
from .utils.dataIO import dataIO
from .utils import checks
from __main__ import send_cmd_help
from tabulate import tabulate
import discord
import glob
import os
import datetime
import asyncio
import discord
import random
import inspect

ini = "```ini\n{0}\n```"


class Tools:
    """Mod and Admin tools."""

    def __init__(self, bot):
        self.bot = bot

    @checks.mod_or_permissions(manage_messages=True)
    @commands.group(pass_context=True, no_pm=True)
    async def access(self, ctx):
        """Check channel access."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @checks.mod_or_permissions(manage_messages=True)
    @access.command(pass_context=True)
    async def compare(self, ctx, user: discord.User, server: discord.Server = None):
        """Compare channel access with [user]"""
        author = ctx.message.author
        if user is None:
            return
        if server is None:
            server = ctx.message.server

        text_channels = [c for c in server.channels if str(c.type) == "text"]
        voice_channels = [c for c in server.channels if str(c.type) == "voice"]

        author_text_channels = [
            c.name for c in text_channels if c.permissions_for(author).read_messages is True
        ]
        author_voice_channels = [
            c.name for c in voice_channels if c.permissions_for(author).connect is True
        ]

        user_text_channels = [
            c.name for c in text_channels if c.permissions_for(user).read_messages is True
        ]
        user_voice_channels = [
            c.name for c in voice_channels if c.permissions_for(user).connect is True
        ]

        author_only_t = set(author_text_channels) - set(
            user_text_channels
        )  # text channels only the author has access to
        author_only_v = set(author_voice_channels) - set(
            user_voice_channels
        )  # voice channels only the author has access to

        user_only_t = set(user_text_channels) - set(
            author_text_channels
        )  # text channels only the user has access to
        user_only_v = set(user_voice_channels) - set(
            author_voice_channels
        )  # voice channels only the user has access to

        common_t = list(
            set(text_channels) - author_only_t - user_only_t
        )  # text channels that author and user have in common
        common_v = list(
            set(voice_channels) - author_only_v - user_only_v
        )  # voice channels that author and user have in common

        msg = "```ini\n"
        msg += "{} [TEXT CHANNELS IN COMMON]:\n\n{}\n\n".format(
            len(common_t), ", ".join([c.name for c in common_t])
        )
        msg += "{} [TEXT CHANNELS {} HAS ACCESS TO]:\n\n{}\n\n".format(
            len(user_only_t), user.name.upper(), ", ".join(list(user_only_t))
        )
        msg += "{} [TEXT CHANNELS YOU HAVE ACCESS TO]:\n\n{}\n\n".format(
            len(author_only_t), ", ".join(list(author_only_t))
        )
        msg += "{} [VOICE CHANNELS IN COMMON]:\n\n{}\n\n".format(
            len(common_v), ", ".join([c.name for c in common_v])
        )
        msg += "{} [VOICE CHANNELS {} HAS ACCESS TO]:\n\n{}\n\n".format(
            len(user_only_v), user.name.upper(), ", ".join(list(user_only_v))
        )
        msg += "{} [VOICE CHANNELS YOU HAVE ACCESS TO]:\n\n{}\n\n".format(
            len(author_only_v), ", ".join(list(author_only_v))
        )
        msg += "```"
        await self.bot.say(msg)

    @checks.mod_or_permissions(manage_messages=True)
    @access.command(pass_context=True)
    async def text(self, ctx, user: discord.Member = None, server: discord.Server = None):
        """Fetch which text channels you have access to."""
        author = ctx.message.author
        if server is None:
            server = ctx.message.server
        if user is None:
            user = author

        can_access = [
            c.name
            for c in server.channels
            if c.permissions_for(user).read_messages == True and str(c.type) == "text"
        ]
        text_channels = [c.name for c in server.channels if str(c.type) == "text"]

        prefix = "You have" if user.id == author.id else user.name + " has"
        msg = "```ini\n[{} access to {} out of {} text channels]\n\n".format(
            prefix, len(can_access), len(text_channels)
        )

        msg += "[ACCESS]:\n{}\n\n".format(", ".join(can_access))
        msg += "[NO ACCESS]:\n{}\n```".format(
            ", ".join(list(set(text_channels) - set(can_access)))
        )
        await self.bot.say(msg)

    @checks.mod_or_permissions(manage_messages=True)
    @access.command(pass_context=True)
    async def voice(self, ctx, user: discord.Member = None, server: discord.Server = None):
        """Fetch which voice channels you have access to."""
        author = ctx.message.author
        if server is None:
            server = ctx.message.server
        if user is None:
            user = author

        can_access = [
            c.name
            for c in server.channels
            if c.permissions_for(user).connect is True and str(c.type) == "voice"
        ]
        voice_channels = [c.name for c in server.channels if str(c.type) == "voice"]

        prefix = "You have" if user.id == author.id else user.name + " has"
        msg = "```ini\n[{} access to {} out of {} voice channels]\n\n".format(
            prefix, len(can_access), len(voice_channels)
        )

        msg += "[ACCESS]:\n{}\n\n".format(", ".join(can_access))
        msg += "[NO ACCESS]:\n{}\n```".format(
            ", ".join(list(set(voice_channels) - set(can_access)))
        )
        await self.bot.say(msg)

    @commands.command(pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def banlist(self, ctx):
        """Displays the server's banlist."""
        try:
            banlist = await self.bot.get_bans(ctx.message.server)
        except discord.errors.Forbidden:
            await self.bot.say("I do not have the `Ban Members` permission.")
            return
        bancount = len(banlist)
        if bancount == 0:
            banlist = "No users are banned from this server."
        else:
            banlist = ", ".join(map(str, banlist))

        for page in pagify(banlist, ["\n"], shorten_by=13, page_length=2000):
            await self.bot.say(box(page, "ini"))

    @commands.command(pass_context=True, no_pm=True)
    async def cid(self, ctx, channel: discord.Channel = None):
        """Shows the channel ID."""
        if not channel:
            channel = ctx.message.channel
        await self.bot.say("**#{0.name} ID:** {0.id}".format(channel))

    @commands.command(pass_context=True)
    async def cinfo(self, ctx, channel: discord.Channel = None):
        """Shows channel information. Defaults to current text channel."""
        yesno = {True: "Yes", False: "No"}
        if not channel:
            channel = ctx.message.channel

        load = "```\nLoading channel info...```"
        waiting = await self.bot.say(load)

        try:
            caller = inspect.currentframe().f_back.f_code.co_name
        except:
            pass

        data = "```ini\n"
        if caller == "whatis":
            data == "[Server]:     {}\n".format(channel.server.name)
        data += "[Name]:       {}\n".format(escape_mass_mentions(str(channel)))
        data += "[ID]:         {}\n".format(channel.id)
        data += "[Default]:    {}\n".format(yesno[channel.is_default])
        data += "[Private]:    {}\n".format(yesno[channel.is_private])
        if str(channel.type) == "text" and channel.topic != "":
            data += "[Topic]:      {}\n".format(channel.topic)
        data += "[Position]:   {}\n".format(channel.position)
        data += "[Created]:    {} ago\n".format(self._dynamic_time(channel.created_at))
        data += "[Type]:       {}\n".format(channel.type)
        if str(channel.type) == "voice":
            data += "[Users]:      {}\n".format(len(channel.voice_members))
            data += "[User limit]: {}\n".format(channel.user_limit)
            data += "[Bitrate]:    {}\n".format(channel.bitrate)
        data += "```"
        await asyncio.sleep(2)
        await self.bot.edit_message(waiting, data)

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def ecogs(self, ctx):
        """Lists status of installed cogs"""
        owner_cog = self.bot.get_cog("Owner")
        total_cogs = owner_cog._list_cogs()
        loaded = [c.__module__.split(".")[1] for c in self.bot.cogs.values()]
        unloaded = [c.split(".")[1] for c in total_cogs if c.split(".")[1] not in loaded]
        if not unloaded:
            unloaded = ["None"]

        items = {
            0: {
                "cogs": sorted(loaded),
                "msg": "**{} loaded:**\n".format(len(loaded)),
                "colour": discord.Colour.dark_green(),
            },
            1: {
                "cogs": sorted(unloaded),
                "msg": "**{} unloaded:**\n".format(len(unloaded)),
                "colour": discord.Colour.dark_red(),
            },
        }
        for index, em in enumerate(items):
            e = discord.Embed(
                description=items[index]["msg"] + ", ".join(items[index]["cogs"]),
                colour=items[index]["colour"],
            )
            await self.bot.say(embed=e)

    @commands.command(pass_context=True)
    async def eid(self, ctx, emoji):
        """Get an id for a custom emoji."""
        if emoji[0] != "<":
            await self.bot.say(
                "I could not an ID for this emoji, this may be because it is not a custom emoji."
            )
            return
        id = emoji.split(":")[2][:-1]
        await self.bot.say(id)

    @checks.is_owner()
    @commands.command(aliases=["find", "cmd_lookup"])
    async def findcog(self, command: str):
        """Cog search by command.
        This is only applicable for loaded cogs that were installed through [p]cog install."""
        try:
            cog_name = self.bot.get_cog(self.bot.get_command(command).cog_name).__module__[5:]
        except:
            await self.bot.say(
                "Either that command doesn't exist, or the cog this command belongs to wasn't added through the downloader cog."
            )
            return
        repos = dataIO.load_json("data/downloader/repos.json")
        cog_path = (
            lambda x: "\n".join(
                [
                    filename
                    for filename in glob.iglob("data/downloader/**/*.py", recursive=True)
                    if "{}.py".format(x) == filename[((len("{}.py".format(x))) * -1) :]
                ]
            )
        )(cog_name)
        if not cog_path:
            await self.bot.say("This is a command that's in a cog that's not published in a repo.")
            return
        if os.name == "nt":
            repo = cog_path.split(os.sep)[1]
        else:
            repo = cog_path.split(os.sep)[2]
        if "url" not in repos[repo]:
            with open("data/downloader/" + repo + "/.git/config", "r") as f:
                url = re.findall(r"(http(s)?:\/\/[a-zA-Z0-9\:\.\-\_\/\?\=\%]*)", f.read())[0][0]
        else:
            url = repos[repo]["url"]
        await self.bot.say(
            box(
                "Command name: {}\nMade by: {}\nRepo: {}\nCog Name: {}.py".format(
                    command, url.split("/")[3], url, cog_name
                )
            )
        )

    @checks.admin_or_permissions(manage_roles=True)
    @commands.command(pass_context=True)
    async def inrole(self, ctx, *, rolename):
        """Check members in the role specified."""
        await self.bot.send_typing(ctx.message.channel)
        role = discord.utils.find(
            lambda r: r.name.lower() == rolename.lower(), ctx.message.server.roles
        )

        if role is None:
            roles = []
            for r in ctx.message.server.roles:
                if rolename.lower() in r.name.lower():
                    roles.append(r)

            if len(roles) == 1:
                role = roles[0]
            elif len(roles) < 1:
                await self.bot.say("no roles found")
                return
            else:
                msg = "**Roles found with** {} **in the name.**\n\n".format(rolename)
                tbul8 = []
                for num, role in enumerate(roles):
                    tbul8.append([num + 1, role.name])
                m1 = await self.bot.say(msg + tabulate(tbul8, tablefmt="plain"))
                response = await self.bot.wait_for_message(
                    author=ctx.message.author, channel=ctx.message.channel, timeout=25
                )
                if response is None:
                    await self.bot.delete_message(m1)
                    return
                elif response.content.isdigit():
                    await self.bot.delete_message(m1)
                    return
                else:
                    response = int(response.content)

                if response not in range(0, len(roles) + 1):
                    await self.bot.delete_message(m1)
                    return
                elif response == 0:
                    await self.bot.delete_message(m1)
                    return
                else:
                    role = roles[response - 1]

        if (
            role is not None
            and len([m for m in ctx.message.server.members if role in m.roles]) < 50
        ):
            awaiter = await self.bot.say(
                embed=discord.Embed(description="Getting member names...")
            )
            await asyncio.sleep(2.5)
            role_member = discord.Embed(
                description="**{1} users found in the {0} role.**\n".format(
                    role.name, len([m for m in ctx.message.server.members if role in m.roles])
                )
            )
            role_users = [m.display_name for m in ctx.message.server.members if role in m.roles]
            if not role_users:
                role_member.add_field(name="Users", value="None.")
            else:
                role_member.add_field(name="Users", value="\n".join(role_users))
            await self.bot.edit_message(awaiter, embed=role_member)

        elif len([m for m in ctx.message.server.members if role in m.roles]) > 50:
            awaiter = await self.bot.say(
                embed=discord.Embed(description="Getting member names...")
            )
            await asyncio.sleep(2.5)
            await self.bot.edit_message(
                awaiter,
                embed=discord.Embed(
                    description="List is too long for **{0}** role, **{1}** members found.\n".format(
                        role.name, len([m.mention for m in server.members if role in m.roles])
                    )
                ),
            )
        else:
            embed = discord.Embed(description="Role was not found.")
            await self.bot.edit_message(embed=embed)

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def newusers(self, ctx, count: int = 5, server: discord.Server = None):
        """Lists the newest 5 members."""
        if server is None:
            server = ctx.message.server
        count = max(min(count, 25), 5)
        members = sorted(server.members, key=lambda m: m.joined_at, reverse=True)[:count]
        e = discord.Embed(title="New Members")
        for member in members:
            msg = "**Joined Server:** {} ago\n**Account created:** {} ago".format(
                self._dynamic_time(member.joined_at), self._dynamic_time(member.created_at)
            )
            e.add_field(
                name="{0.display_name} (ID: {0.id})".format(member), value=msg, inline=False
            )
        await self.bot.say(embed=e)

    @commands.command(pass_context=True, no_pm=True)
    async def sid(self, ctx):
        """Shows the server ID."""
        await self.bot.say("**{0.name} ID:** {0.id}".format(ctx.message.server))

    @commands.command(pass_context=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def userstats(self, ctx, this_server: bool = False):
        """A small amount of user stats."""
        embeds = {}
        if this_server:
            members = set([x for x in ctx.message.server.members])
        else:
            members = set([x for x in self.bot.get_all_members()])

        items = {
            2: {
                "users": len([e.name for e in members if e.status == discord.Status.idle]),
                "colour": discord.Colour.orange(),
            },
            3: {
                "users": len([e.name for e in members if e.status == discord.Status.dnd]),
                "colour": discord.Colour.red(),
            },
            4: {
                "users": len([e.name for e in members if e.status == discord.Status.offline]),
                "colour": discord.Colour.dark_grey(),
            },
            1: {
                "users": len([e.name for e in members if e.status == discord.Status.online]),
                "colour": discord.Colour.green(),
            },
            0: {
                "users": len([e.name for e in members if e.game and e.game.url]),
                "colour": discord.Colour.dark_purple(),
            },
        }

        for item in items:
            embeds[item] = discord.Embed(
                description="Users: {}".format(items[item]["users"]), colour=items[item]["colour"]
            )
        for i, em in enumerate(embeds):
            await self.bot.say(embed=embeds[i])

    @commands.command(pass_context=True, no_pm=True)
    async def sinfo(self, ctx, server: discord.Server = None):
        """Shows server information."""
        if server is None:
            server = ctx.message.server
        online = str(
            len(
                [
                    m.status
                    for m in server.members
                    if str(m.status) == "online" or str(m.status) == "idle"
                ]
            )
        )
        total_users = str(len(server.members))
        text_channels = [x for x in server.channels if str(x.type) == "text"]
        voice_channels = [x for x in server.channels if str(x.type) == "voice"]

        load = "```\nLoading server info...```"
        waiting = await self.bot.say(load)

        data = "```ini\n"
        data += "[Name]:     {}\n".format(server.name)
        data += "[ID]:       {}\n".format(server.id)
        data += "[Region]:   {}\n".format(server.region)
        data += "[Owner]:    {}\n".format(server.owner)
        data += "[Users]:    {}/{}\n".format(online, total_users)
        data += "[Text]:     {} channels\n".format(len(text_channels))
        data += "[Voice]:    {} channels\n".format(len(voice_channels))
        data += "[Emojis]:   {}\n".format(len(server.emojis))
        data += "[Roles]:    {} \n".format(len(server.roles))
        data += "[Created]:  {} ago\n```".format(self._dynamic_time(server.created_at))
        await asyncio.sleep(3)
        await self.bot.edit_message(waiting, data)

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def perms(self, ctx, user: discord.Member = None):
        """Fetch a specific user's permissions."""
        if user is None:
            user = ctx.message.author

        perms = iter(ctx.message.channel.permissions_for(user))
        perms_we_have = "```diff\n"
        perms_we_dont = ""
        for x in perms:
            if "True" in str(x):
                perms_we_have += "+\t{0}\n".format(str(x).split("'")[1])
            else:
                perms_we_dont += "-\t{0}\n".format(str(x).split("'")[1])
        await self.bot.say("{0}{1}```".format(perms_we_have, perms_we_dont))

    @commands.command(pass_context=True)
    async def rid(self, ctx, rolename):
        """Shows the id of a role, use quotes on the role."""
        await self.bot.send_typing(ctx.message.channel)
        if rolename is discord.Role:
            role = rolename
        else:
            role = self._role_from_string(ctx.message.server, rolename)
        if role is None:
            return await self.bot.say(embed=discord.Embed(description="Cannot find role."))
        await self.bot.say(
            embed=discord.Embed(description="**{}** ID: {}".format(rolename, role.id))
        )

    @commands.command(pass_context=True)
    async def rinfo(self, ctx, rolename):
        """Shows role info, use quotes on the role."""
        server = ctx.message.server
        colour = str(random.randint(0, 0xFFFFFF))
        colour = int(colour, 16)
        await self.bot.send_typing(ctx.message.channel)

        try:
            caller = inspect.currentframe().f_back.f_code.co_name
        except:
            pass

        if type(rolename) is not discord.Role:
            role = discord.utils.find(
                lambda r: r.name.lower() == rolename.lower(), ctx.message.server.roles
            )
        else:
            role = rolename
        if role is None:
            await self.bot.say("That role cannot be found.")
            return
        if role is not None:
            perms = iter(role.permissions)
            perms_we_have = ""
            perms_we_dont = ""
            for x in perms:
                if "True" in str(x):
                    perms_we_have += "{0}\n".format(str(x).split("'")[1])
                else:
                    perms_we_dont += "{0}\n".format(str(x).split("'")[1])
            msg = discord.Embed(description="Gathering role stats...", colour=role.color)
            if role.color is None:
                role.color = discord.Colour(value=colour)
            msg2 = await self.bot.say(embed=msg)
            em = discord.Embed(colour=role.colour)
            if caller == "whatis":
                em.add_field(name="Server", value=role.server.name)
            em.add_field(name="Role Name", value=role.name)
            em.add_field(name="Created", value=self._dynamic_time(role.created_at))
            em.add_field(
                name="Users in Role",
                value=len([m for m in ctx.message.server.members if role in m.roles]),
            )
            em.add_field(name="Id", value=role.id)
            em.add_field(name="Color", value=role.color)
            em.add_field(name="Position", value=role.position)
            em.add_field(name="Valid Permissons", value="{}".format(perms_we_have))
            em.add_field(name="Invalid Permissons", value="{}".format(perms_we_dont))
            em.set_thumbnail(url=role.server.icon_url)
        try:
            await self.bot.edit_message(msg2, embed=em)
        except discord.HTTPException:
            perms_msg = "```diff\n"
            role = discord.utils.find(
                lambda r: r.name.lower() == rolename.lower(), ctx.message.server.roles
            )
            if role is None:
                await bot.say("That role cannot be found.")
                return
            if role is not None:
                perms = iter(role.permissions)
                perms_we_have2 = ""
                perms_we_dont2 = ""
                for x in perms:
                    if "True" in str(x):
                        perms_we_have2 += "+{0}\n".format(str(x).split("'")[1])
                    else:
                        perms_we_dont2 += "-{0}\n".format(str(x).split("'")[1])
            await self.bot.say(
                "{}Name: {}\nCreated: {}\nUsers in Role : {}\nId : {}\nColor : {}\nPosition : {}\nValid Perms : \n{}\nInvalid Perms : \n{}```".format(
                    perms_msg,
                    role.name,
                    self._dynamic_time(role.created_at),
                    len([m for m in server.members if role in m.roles]),
                    role.id,
                    role.color,
                    role.position,
                    perms_we_have2,
                    perms_we_dont2,
                )
            )
            await self.bot.delete_message(msg2)

    @commands.command(pass_context=True, hidden=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def sharedservers(self, ctx, user: discord.Member = None):
        """Shows shared server info. Defaults to author."""
        author = ctx.message.author
        server = ctx.message.server
        if not user:
            user = author
        seen = len(
            set(
                [
                    member.server.name
                    for member in self.bot.get_all_members()
                    if member.name == user.name
                ]
            )
        )
        sharedservers = str(
            set(
                [
                    member.server.name
                    for member in self.bot.get_all_members()
                    if member.name == user.name
                ]
            )
        )
        for shared in sharedservers:
            shared = "".strip("'").join(sharedservers).strip("'")
            shared = shared.strip("{").strip("}")

        data = "[Servers]:     {} shared\n".format(seen)
        data += "[In Servers]:  {}\n".format(shared)

        for page in pagify(data, ["\n"], shorten_by=13, page_length=2000):
            await self.bot.say(box(page, "ini"))

    @commands.command(pass_context=True)
    async def uinfo(self, ctx, user: discord.Member = None):
        """Shows user information. Defaults to author."""
        if not user:
            user = ctx.message.author
        try:
            caller = inspect.currentframe().f_back.f_code.co_name
        except:
            pass
        roles = [x.name for x in user.roles if x.name != "@everyone"]
        if not roles:
            roles = ["None"]
        seen = str(
            len(
                set(
                    [
                        member.server.name
                        for member in self.bot.get_all_members()
                        if member.id == user.id
                    ]
                )
            )
        )

        load = "```\nLoading user info...```"
        waiting = await self.bot.say(load)

        data = "```ini\n"
        data += "[Name]:     {}\n".format(escape_mass_mentions(str(user)))
        data += "[Nickname]: {}\n".format(escape_mass_mentions(str(user.nick)))
        data += "[ID]:       {}\n".format(user.id)
        data += "[Status]:   {}\n".format(user.status)
        data += "[Servers]:  {} shared\n".format(seen)
        if user.game is None:
            pass
        elif user.game.url is None:
            data += "[Playing]:  {}\n".format(escape_mass_mentions(str(user.game)))
        else:
            data += "[Streaming]: [{}]({})\n".format(
                escape_mass_mentions(str(user.game)), escape_mass_mentions(user.game.url)
            )
        passed = (ctx.message.timestamp - user.created_at).days
        data += "[Created]:  {} ago\n".format(self._dynamic_time(user.created_at))
        joined_at = self.fetch_joined_at(user, ctx.message.server)
        if caller != "whatis":
            data += "[Joined]:   {} ago\n".format(self._dynamic_time(joined_at))
            data += "[Roles]:    {}\n".format(", ".join(roles))
            data += "[In Voice]: {}\n".format(str(user.voice_channel))
            data += "[AFK]:      {}\n".format(user.is_afk)
        data += "```"
        await asyncio.sleep(3)
        await self.bot.edit_message(waiting, data)

    @commands.command(pass_context=True)
    async def whatis(self, ctx, id):
        """What is it?"""
        server = ctx.message.server
        channel = ctx.message.channel
        author = ctx.message.author

        it_is = False
        msg = False

        if server.id == id:
            it_is = server
        elif channel.id == id:
            it_is = channel
        elif author.id == id:
            it_is = author

        if not it_is:
            for server in self.bot.servers:
                if server.id == id:
                    it_is = server
                    break
        if not it_is:
            for emoji in self.bot.get_all_emojis():
                if emoji.id == id:
                    it_is = emoji
                    break
        if not it_is:
            for server in self.bot.servers:
                for role in server.roles:
                    if role.id == id:
                        it_is = role
                        break
        if not it_is:
            for member in self.bot.get_all_members():
                if member.id == id:
                    it_is = member
                    break
        if not it_is:
            for channel in self.bot.get_all_channels():
                if channel.id == id:
                    it_is = channel
                    break

        if not msg:
            if type(it_is) == discord.Channel:
                await ctx.invoke(self.cinfo, it_is)
            elif type(it_is) == discord.Server:
                await ctx.invoke(self.sinfo, it_is)
            elif type(it_is) == discord.User or type(it_is) == discord.Member:
                await ctx.invoke(self.uinfo, it_is)
            elif type(it_is) == discord.Role:
                await ctx.invoke(self.roleinfo, it_is)
            elif type(it_is) == discord.Emoji:
                await self.bot.say(
                    "<:{0.name}:{0.id}>\n```ini\n[NAME]:     {0.name}\n[SERVER]:   {0.server}\n[URL]:      {0.url}```".format(
                        it_is
                    )
                )
            else:
                await self.bot.say(
                    "I could not find anything for this ID, I do not support Message IDs"
                )
        else:
            await self.bot.say("```\nNothing found for this ID```")

    @staticmethod
    def _dynamic_time(time):
        date_join = datetime.datetime.strptime(str(time), "%Y-%m-%d %H:%M:%S.%f")
        date_now = datetime.datetime.now(datetime.timezone.utc)
        date_now = date_now.replace(tzinfo=None)
        since_join = date_now - date_join

        m, s = divmod(int(since_join.total_seconds()), 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        if d > 0:
            msg = "{0}d {1}h"
        elif d == 0 and h > 0:
            msg = "{1}h {2}m"
        elif d == 0 and h == 0 and m > 0:
            msg = "{2}m {3}s"
        elif d == 0 and h == 0 and m == 0 and s > 0:
            msg = "{3}s"
        else:
            msg = ""
        return msg.format(d, h, m, s)

    def fetch_joined_at(self, user, server):
        return user.joined_at

    def _role_from_string(self, server, rolename, roles=None):
        if roles is None:
            roles = server.roles
        role = discord.utils.find(lambda r: r.name.lower() == rolename.lower(), roles)
        return role


def setup(bot):
    cmds = [
        "access",
        "banlist",
        "cid",
        "cinfo",
        "ecogs",
        "eid",
        "findcog",
        "inrole",
        "newusers",
        "perms",
        "rid",
        "rinfo",
        "sid",
        "sinfo",
        "uinfo",
        "userstatst",
        "whatis",
    ]
    for cmd in cmds:
        bot.remove_command(cmd)
    bot.add_cog(Tools(bot))
