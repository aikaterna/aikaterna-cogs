import asyncio
import datetime
import discord
import logging
import random
from redbot.core import commands, checks, Config, bank
from redbot.core.errors import BalanceTooHigh
from redbot.core.utils.chat_formatting import box, humanize_list, pagify


log = logging.getLogger("red.aikaterna.pupper")


class Pupper(commands.Cog):
    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2767241393, force_registration=True)
        self.pets = {}

        default_guild = {
            "borf_msg": "borf! (thank for pats h00man, have a doggocoin)",
            "channel": [],
            "cooldown": 3600,
            "credits": [100, 500],
            "hello_msg": "Hi! Can someone pet me?",
            "last_pet": "2019-08-01 00:00:00.000001",
            "toggle": False,
            "delete_after": 10,
        }

        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    @commands.group()
    async def pets(self, ctx):
        """Manage your pet."""
        if ctx.invoked_subcommand is None:
            guild_data = await self.config.guild(ctx.guild).all()
            if not guild_data["channel"]:
                channel_names = ["No channels set."]
            else:
                channel_names = []
                for channel_id in guild_data["channel"]:
                    channel_obj = self.bot.get_channel(channel_id)
                    channel_names.append(channel_obj.name)

            space = "\N{EN SPACE}"
            toggle = "Active" if guild_data["toggle"] else "Inactive"
            delete_after = "No deletion" if not guild_data["delete_after"] else guild_data["delete_after"]

            msg = f"[Channels]:       {humanize_list(channel_names)}\n"
            msg += f"[Cooldown]:       {guild_data['cooldown']} seconds\n"
            msg += f"[Credit range]:   {guild_data['credits'][0]} - {guild_data['credits'][1]} credits\n"
            msg += f"[Delete after]:   {delete_after}\n"
            msg += f"[Toggle]:         {toggle}\n"
            msg += f"{space}\n"
            msg += f"[Hello message]:  {guild_data['hello_msg']}\n"
            msg += f"[Thanks message]: {guild_data['borf_msg']}\n"

            for page in pagify(msg, delims=["\n"]):
                await ctx.send(box(page, lang="ini"))

    @pets.command()
    async def toggle(self, ctx):
        """Toggle pets on the server."""
        toggle = await self.config.guild(ctx.guild).toggle()
        await self.config.guild(ctx.guild).toggle.set(not toggle)
        await ctx.send(f"The pet is now {'' if not toggle else 'in'}active.")

    @pets.command()
    async def delete(self, ctx, amount: int = 0):
        """
        Set how long to wait before deleting the thanks message.
        To leave the thanks message with no deletion, use 0 as the amount.
        10 is the default.
        Max is 5 minutes (300).
		"""
        if amount < 0:
            return await ctx.send("Use a positive number.")
        if 1 <= amount <= 5:
            return await ctx.send("Use a slightly larger number, greater than 5.")
        if amount > 300:
            return await ctx.send("Use a smaller number, less than or equal to 300.")

        set_amount = None if amount == 0 else amount
        await self.config.guild(ctx.guild).delete_after.set(set_amount)
        msg = f"Timer set to {amount}." if set_amount else "Delete timer has been turned off."
        await ctx.send(msg)

    @pets.command()
    async def cooldown(self, ctx, seconds: int = None):
        """Set the pet appearance cooldown in seconds. 

        300s/5 minute minimum. Default is 3600s/1 hour."""

        if not seconds:
            seconds = 3600
        if seconds < 300:
            seconds = 300
        await self.config.guild(ctx.guild).cooldown.set(seconds)
        await ctx.send(f"Pet appearance cooldown set to {seconds}.")

    @pets.command()
    async def credits(self, ctx, min_amt: int, max_amt: int):
        """Set the pet credits range on successful petting."""
        if min_amt > max_amt:
            return await ctx.send("Min must be less than max.")
        if min_amt < 1 or max_amt < 1:
            return await ctx.send("Min and max amounts must be greater than 1.")
        await self.config.guild(ctx.guild).credits.set([min_amt, max_amt])
        await ctx.send(f"Pet credit range set to {min_amt} - {max_amt}.")

    @pets.command()
    async def hello(self, ctx, *, message: str = None):
        """Set the pet greeting message."""
        if not message:
            hello = await self.config.guild(ctx.guild).hello_msg()
            return await ctx.send(
                f"Current greeting message: `{hello}`\nUse this command with the message you would like to set."
            )
        if len(message) > 1000:
            return await ctx.send("That dog sure likes to talk a lot. Try a shorter message.")
        await self.config.guild(ctx.guild).hello_msg.set(message)
        await ctx.send(f"Pet hello message set to: `{message}`.")

    @pets.command()
    async def thanks(self, ctx, *, message: str = None):
        """Set the pet thanks message."""
        if not message:
            bye = await self.config.guild(ctx.guild).borf_msg()
            return await ctx.send(
                f"Current thanks message: `{bye}`\nUse this command with the message you would like to set."
            )
        if len(message) > 1000:
            return await ctx.send("That dog sure likes to talk a lot. Try a shorter message.")
        await self.config.guild(ctx.guild).borf_msg.set(message)
        await ctx.send(f"Pet thanks message set to: `{message}`.")

    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    @pets.group(invoke_without_command=True)
    async def channel(self, ctx):
        """Channel management for pet appearance."""
        await ctx.send_help()
        channel_list = await self.config.guild(ctx.guild).channel()
        channel_msg = "[Petting Channels]:\n"
        if not channel_list:
            channel_msg += "None."
        for chan in channel_list:
            channel_obj = self.bot.get_channel(chan)
            channel_msg += f"{channel_obj.name}\n"
        await ctx.send(box(channel_msg, lang="ini"))

    @channel.command()
    async def add(self, ctx, channel: discord.TextChannel):
        """Add a text channel for pets."""
        channel_list = await self.config.guild(ctx.guild).channel()
        if channel.id not in channel_list:
            channel_list.append(channel.id)
            await self.config.guild(ctx.guild).channel.set(channel_list)
            await ctx.send(f"{channel.mention} added to the valid petting channels.")
        else:
            await ctx.send(f"{channel.mention} is already in the list of petting channels.")

    @channel.command()
    async def addall(self, ctx):
        """Add all valid channels for the guild that the bot can speak in."""
        bot_text_channels = [
            c for c in ctx.guild.text_channels if c.permissions_for(ctx.guild.me).send_messages is True
        ]
        channel_list = await self.config.guild(ctx.guild).channel()
        channels_appended = []
        channels_in_list = []

        for text_channel in bot_text_channels:
            if text_channel.id not in channel_list:
                channel_list.append(text_channel.id)
                channels_appended.append(text_channel.mention)
            else:
                channels_in_list.append(text_channel.mention)
                pass

        first_msg = ""
        second_msg = ""
        await self.config.guild(ctx.guild).channel.set(channel_list)
        if len(channels_appended) > 0:
            first_msg = f"{humanize_list(channels_appended)} added to the valid petting channels.\n"
        if len(channels_in_list) > 0:
            second_msg = f"{humanize_list(channels_in_list)}: already in the list of petting channels."
        await ctx.send(f"{first_msg}{second_msg}")

    @channel.command()
    async def remove(self, ctx, channel: discord.TextChannel):
        """Remove a text channel from petting."""
        channel_list = await self.config.guild(ctx.guild).channel()
        if channel.id in channel_list:
            channel_list.remove(channel.id)
        else:
            return await ctx.send(f"{channel.mention} not in the active channel list.")
        await self.config.guild(ctx.guild).channel.set(channel_list)
        await ctx.send(f"{channel.mention} removed from the list of petting channels.")

    @channel.command()
    async def removeall(self, ctx):
        """Remove all petting channels from the list."""
        await self.config.guild(ctx.guild).channel.set([])
        await ctx.send("All channels have been removed from the list of petting channels.")

    def _pet_lock(self, guild_id, tf):
        if tf:
            self.pets[guild_id] = True
        else:
            self.pets[guild_id] = False

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if isinstance(message.channel, discord.abc.PrivateChannel):
                return
            if message.author.bot:
                return
            guild_data = await self.config.guild(message.guild).all()
            if not guild_data["toggle"]:
                return
            if not guild_data["channel"]:
                return
            self.pets.setdefault(message.guild.id, False)
            if self.pets[message.guild.id]:
                return

            last_time = datetime.datetime.strptime(str(guild_data["last_pet"]), "%Y-%m-%d %H:%M:%S.%f")
            now = datetime.datetime.now(datetime.timezone.utc)
            now = now.replace(tzinfo=None)
            if int((now - last_time).total_seconds()) > await self.config.guild(message.guild).cooldown():
                self._pet_lock(message.guild.id, True)
                rando_channel = random.choice(guild_data["channel"])
                await asyncio.sleep(random.randint(60, 480))
                rando_channel_obj = self.bot.get_channel(rando_channel)
                borf_msg = await rando_channel_obj.send(guild_data["hello_msg"])
                pets = "👋"
                pets_action = {"veryfastpats": "👋"}

                def check(r, u):
                    return r.message.id == borf_msg.id and any(e in str(r.emoji) for e in pets)

                try:
                    r, u = await self.bot.wait_for("reaction_add", check=check, timeout=300.0)
                except asyncio.TimeoutError:
                    return await borf_msg.delete()

                reacts = {v: k for k, v in pets_action.items()}
                react = reacts[r.emoji]
                if react == "veryfastpats":
                    await borf_msg.delete()
                    deposit = random.randint(guild_data["credits"][0], guild_data["credits"][1])
                    try:
                        large_bank = False
                        await bank.deposit_credits(u, deposit)
                    except BalanceTooHigh as e:
                        large_bank = True
                        await bank.set_balance(u, e.max_balance)
                    credits_name = await bank.get_currency_name(message.guild)
                    msg = (
                        f"{guild_data['borf_msg']} (`+{deposit}` {credits_name})"
                        if not large_bank
                        else guild_data["borf_msg"]
                    )
                    await rando_channel_obj.send(content=msg, delete_after=guild_data["delete_after"])
                else:
                    pass
                self._pet_lock(message.guild.id, False)
                await self.config.guild(message.guild).last_pet.set(str(now))
        except Exception:
            log.error("Error in pupper loop.", exc_info=True)
