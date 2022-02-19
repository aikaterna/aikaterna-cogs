from __future__ import annotations
import discord
from datetime import datetime
import re
from typing import List, Callable
from redbot.core import commands, checks, Config
from redbot.core.utils import chat_formatting as cf
from redbot.vendored.discord.ext import menus


OLD_CODE_RE = re.compile("^[0-9a-zA-Z]{16}$")
CODE_RE = re.compile("^[0-9a-zA-Z]{6,7}$")
NEW10_CODE_RE = re.compile("^[0-9a-zA-Z]{10}$")
NEW8_CODE_RE = re.compile("^[0-9a-zA-Z]{8}$")

FAILURE_MSG = "That invite doesn't seem to be valid."
PERM_MSG = "I need the Administrator permission on this guild to view invite information."

__version__ = "0.0.7"


class Invites(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2713371001, force_registration=True)

        default_guild = {"pinned_invites": []}

        self.config.register_guild(**default_guild)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    @commands.guild_only()
    @commands.group()
    async def invites(self, ctx: commands.Context):
        """Invite information."""
        pass

    @commands.max_concurrency(1, commands.BucketType.user)
    @invites.command()
    async def show(self, ctx: commands.Context, invite_code_or_url: str = None):
        """Show the stats for an invite, or show all invites."""
        if not ctx.channel.permissions_for(ctx.guild.me).administrator:
            return await self._send_embed(ctx, PERM_MSG)

        if not invite_code_or_url:
            pages = MenuInvitePages(await ctx.guild.invites())
        else:
            invite_code = await self._find_invite_code(invite_code_or_url)
            if not invite_code:
                return await self._send_embed(ctx, FAILURE_MSG)
            pages = MenuInvitePages([x for x in await ctx.guild.invites() if x.code == invite_code])
        await self._menu(ctx, pages)

    @invites.command()
    async def leaderboard(self, ctx: commands.Context, list_all_invites: bool = False):
        """List pinned invites or all invites in a leaderboard style."""
        if not ctx.channel.permissions_for(ctx.guild.me).administrator:
            return await self._send_embed(ctx, PERM_MSG)

        if not list_all_invites:
            pinned_invites = await self.config.guild(ctx.guild).pinned_invites()
            if not pinned_invites:
                return await self._send_embed(ctx, "No invites are pinned, or there are no invites to display.")
        else:
            pinned_invites = await ctx.guild.invites()
        invite_info = ""
        for i, invite_code_or_object in enumerate(pinned_invites):
            if not list_all_invites:
                inv_object = await self._get_invite_from_code(ctx, invite_code_or_object)
            else:
                inv_object = invite_code_or_object
            if not inv_object:
                # Someone deleted a pinned invite or it expired
                pinned_invites = await self.config.guild(ctx.guild).pinned_invites()
                pinned_invites.remove(invite_code_or_object)
                await self.config.guild(ctx.guild).pinned_invites.set(pinned_invites)
                continue
            max_uses = await self.get_invite_max_uses(ctx, inv_object)
            inv_details = f"{i+1}. {inv_object.url} [ {inv_object.uses} uses / {max_uses} max ]\n"
            invite_info += inv_details

        pagified_stings = [x for x in cf.pagify(invite_info, delims=["\n"], shorten_by=16)]
        pages = MenuLeaderboardPages(ctx, pagified_stings, show_all=list_all_invites)
        await self._menu(ctx, pages)

    @invites.command(aliases=["listpinned"])
    async def listpin(self, ctx: commands.Context):
        """List pinned invites."""
        pinned_invites = await self.config.guild(ctx.guild).pinned_invites()
        invite_list = "None." if len(pinned_invites) == 0 else "\n".join(pinned_invites)
        await self._send_embed(ctx, "Pinned Invites", invite_list)

    @invites.command()
    async def pin(self, ctx: commands.Context, invite_code_or_url: str):
        """Pin an invite to the leaderboard."""
        if not ctx.channel.permissions_for(ctx.guild.me).administrator:
            return await self._send_embed(ctx, PERM_MSG)

        invite_code = await self._find_invite_code(invite_code_or_url)
        invite_code = await self._check_invite_code(ctx, invite_code)
        if not invite_code:
            return await self._send_embed(ctx, FAILURE_MSG)

        existing_pins = await self.config.guild(ctx.guild).pinned_invites()
        if invite_code not in existing_pins:
            existing_pins.append(invite_code)
            await self.config.guild(ctx.guild).pinned_invites.set(existing_pins)
            await self._send_embed(ctx, f"{invite_code} was added to the pinned list.")
        else:
            await self._send_embed(ctx, f"{invite_code} is already in the pinned list.")

    @invites.command()
    async def unpin(self, ctx: commands.Context, invite_code_or_url: str):
        """Unpin an invite from the leaderboard."""
        invite_code = await self._find_invite_code(invite_code_or_url)
        if not invite_code:
            return await self._send_embed(ctx, FAILURE_MSG)

        pinned_invites = await self.config.guild(ctx.guild).pinned_invites()
        if invite_code in pinned_invites:
            pinned_invites.remove(invite_code)
        else:
            return await self._send_embed(ctx, f"{invite_code} isn't in the pinned list.")
        await self.config.guild(ctx.guild).pinned_invites.set(pinned_invites)
        await self._send_embed(ctx, f"{invite_code} was removed from the pinned list.")

    @invites.command(hidden=True)
    async def version(self, ctx):
        """Invites version."""
        await self._send_embed(ctx, __version__)

    @staticmethod
    async def _check_invite_code(ctx: commands.Context, invite_code: str):
        for invite in await ctx.guild.invites():
            if invite.code == invite_code:
                return invite_code
            else:
                continue

            return None

    @staticmethod
    async def _find_invite_code(invite_code_or_url: str):
        invite_match = (
            re.fullmatch(OLD_CODE_RE, invite_code_or_url)
            or re.fullmatch(CODE_RE, invite_code_or_url)
            or re.fullmatch(NEW10_CODE_RE, invite_code_or_url)
            or re.fullmatch(NEW8_CODE_RE, invite_code_or_url)
        )
        if invite_match:
            return invite_code_or_url
        else:
            sep = invite_code_or_url.rfind("/")
            if sep:
                try:
                    invite_code = invite_code_or_url.rsplit("/", 1)[1]
                    return invite_code
                except IndexError:
                    return None

            return None

    @staticmethod
    async def _get_invite_from_code(ctx: commands.Context, invite_code: str):
        for invite in await ctx.guild.invites():
            if invite.code == invite_code:
                return invite
            else:
                continue

            return None

    @classmethod
    async def get_invite_max_uses(self, ctx: commands.Context, invite_object: discord.Invite):
        if invite_object.max_uses == 0:
            return "\N{INFINITY}"
        else:
            return invite_object.max_uses

    async def _menu(self, ctx: commands.Context, pages: List[discord.Embed]):
        # `wait` in this function is whether the menus wait for completion.
        # An example of this is with concurrency:
        # If max_concurrency's wait arg is False (the default):
        # This function's wait being False will not follow the expected max_concurrency behaviour
        # This function's wait being True will follow the expected max_concurrency behaviour
        await MenuActions(source=pages, delete_message_after=False, clear_reactions_after=True, timeout=180).start(
            ctx, wait=True
        )

    @staticmethod
    async def _send_embed(ctx: commands.Context, title: str = None, description: str = None):
        title = "\N{ZERO WIDTH SPACE}" if title is None else title
        embed = discord.Embed()
        embed.title = title
        if description:
            embed.description = description
        embed.colour = await ctx.embed_colour()
        await ctx.send(embed=embed)


class MenuInvitePages(menus.ListPageSource):
    def __init__(self, methods: List[discord.Invite]):
        super().__init__(methods, per_page=1)

    async def format_page(self, menu: MenuActions, invite: discord.Invite) -> discord.Embed:
        # Use the menu to generate pages as they are needed instead of giving it a list of
        # already-generated embeds.
        embed = discord.Embed(title=f"Invites for {menu.ctx.guild.name}")
        max_uses = await Invites.get_invite_max_uses(menu.ctx, invite)
        msg = f"{cf.bold(invite.url)}\n\n"
        msg += f"Uses: {invite.uses}/{max_uses}\n"
        msg += f"Target Channel: {invite.channel.mention}\n"
        msg += f"Created by: {invite.inviter.mention}\n"
        msg += f"Created at: {invite.created_at.strftime('%m-%d-%Y @ %H:%M:%S UTC')}\n"
        if invite.temporary:
            msg += "Temporary invite\n"
        if invite.max_age == 0:
            max_age = f""
        else:
            max_age = f"Max age: {self._dynamic_time(int(invite.max_age))}"
        msg += f"{max_age}"
        embed.description = msg

        return embed

    @staticmethod
    def _dynamic_time(time: int):
        m, s = divmod(time, 60)
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


class MenuLeaderboardPages(menus.ListPageSource):
    def __init__(self, ctx: commands.Context, entries: List[str], show_all: bool):
        super().__init__(entries, per_page=1)
        self.show_all = show_all
        self.ctx = ctx

    async def format_page(self, menu: MenuActions, page: str) -> discord.Embed:
        embed = discord.Embed(title=f"Invite Usage for {self.ctx.guild.name}", description=page)
        if self.show_all is False:
            embed.set_footer(text="Only displaying pinned invites.")
        else:
            embed.set_footer(text="Displaying all invites.")
        return embed


class MenuActions(menus.MenuPages, inherit_buttons=False):
    def reaction_check(self, payload):
        """The function that is used to check whether the payload should be processed.
        This is passed to :meth:`discord.ext.commands.Bot.wait_for <Bot.wait_for>`.

        There should be no reason to override this function for most users.
        This is done this way in this cog to let a bot owner operate the menu
        along with the original command invoker.

        Parameters
        ------------
        payload: :class:`discord.RawReactionActionEvent`
            The payload to check.

        Returns
        ---------
        :class:`bool`
            Whether the payload should be processed.
        """
        if payload.message_id != self.message.id:
            return False
        if payload.user_id not in (*self.bot.owner_ids, self._author_id):
            return False

        return payload.emoji in self.buttons

    async def show_checked_page(self, page_number: int) -> None:
        # This is a custom impl of show_checked_page that allows looping around back to the
        # beginning of the page stack when at the end and using next, or looping to the end
        # when at the beginning page and using prev.
        max_pages = self._source.get_max_pages()
        try:
            if max_pages is None:
                await self.show_page(page_number)
            elif page_number >= max_pages:
                await self.show_page(0)
            elif page_number < 0:
                await self.show_page(max_pages - 1)
            elif max_pages > page_number >= 0:
                await self.show_page(page_number)
        except IndexError:
            pass

    @menus.button("\N{UP-POINTING RED TRIANGLE}", position=menus.First(1))
    async def prev(self, payload: discord.RawReactionActionEvent):
        await self.show_checked_page(self.current_page - 1)

    @menus.button("\N{DOWN-POINTING RED TRIANGLE}", position=menus.First(2))
    async def next(self, payload: discord.RawReactionActionEvent):
        await self.show_checked_page(self.current_page + 1)

    @menus.button("\N{CROSS MARK}", position=menus.Last(0))
    async def close_menu(self, payload: discord.RawReactionActionEvent) -> None:
        self.stop()
