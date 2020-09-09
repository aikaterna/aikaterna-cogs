import asyncio
from random import uniform as randfloat
import re
from redbot.core import commands, checks, Config
from redbot.core.utils.chat_formatting import box


class NoFlippedTables(commands.Cog):
    """For the table sympathizers"""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2712290002, force_registration=True)

        default_guild = {
            "ALL_TABLES": True,
            "BOT_EXEMPT": False,
            "SNACKBEAR": False,
            "TOGGLE": False,
        }

        self.config.register_guild(**default_guild)

        self.flippedTables = {}

    @checks.mod_or_permissions(manage_guild=True)
    @commands.group()
    async def tableset(self, ctx):
        """Got some nice settings for my UNflipped tables"""
        if ctx.invoked_subcommand is None:
            settings = await self.config.guild(ctx.guild).all()
            msg = "[Current Settings]\n"
            for k, v in settings.items():
                msg += str(k) + ": " + str(v) + "\n"
            await ctx.send(box(msg, lang="ini"))

    @tableset.command()
    async def flipall(self, ctx):
        """Enables/disables right all unflipped tables in a message"""
        settings = await self.config.guild(ctx.guild).ALL_TABLES()
        await self.config.guild(ctx.guild).ALL_TABLES.set(not settings)
        if not settings:
            await ctx.send("All tables will now be unflipped.")
        else:
            await ctx.send("Now only one table unflipped per message.")

    @tableset.command()
    async def flipbot(self, ctx):
        """Enables/disables allowing bot to flip tables"""
        settings = await self.config.guild(ctx.guild).BOT_EXEMPT()
        await self.config.guild(ctx.guild).BOT_EXEMPT.set(not settings)
        if not settings:
            await ctx.send("Bot is now allowed to leave its own tables flipped.")
        else:
            await ctx.send("Bot must now unflip tables that itself flips.")

    @tableset.command()
    async def snackbear(self, ctx):
        """Snackburr is unflipping tables!"""
        settings = await self.config.guild(ctx.guild).SNACKBEAR()
        await self.config.guild(ctx.guild).SNACKBEAR.set(not settings)
        if not settings:
            await ctx.send("Snackburr will now unflip tables.")
        else:
            await ctx.send("Snackburr is heading off for his errands!")

    @tableset.command()
    async def toggle(self, ctx):
        """Toggle the unflipping on or off."""
        settings = await self.config.guild(ctx.guild).TOGGLE()
        await self.config.guild(ctx.guild).TOGGLE.set(not settings)
        if not settings:
            await ctx.send("No table shall be left unflipped in this server.")
        else:
            await ctx.send("No more unflipping here.")

    @commands.Cog.listener()
    # so much fluff just for this OpieOP
    async def on_message(self, message):
        channel = message.channel
        user = message.author
        if not message.guild:
            return
        if not channel.permissions_for(message.guild.me).send_messages:
            return
        if hasattr(user, "bot") and user.bot is True:
            return
        toggle = await self.config.guild(message.guild).TOGGLE()
        if not toggle:
            return
        if channel.id not in self.flippedTables:
            self.flippedTables[channel.id] = {}
        # ┬─┬ ┬┬ ┻┻ ┻━┻ ┬───┬ ┻━┻ will leave 3 tables left flipped
        # count flipped tables
        for m in re.finditer("┻━*┻|┬─*┬", message.content):
            t = m.group()
            bot_exempt = await self.config.guild(message.guild).BOT_EXEMPT()
            if "┻" in t and not (message.author.id == self.bot.user.id and bot_exempt):
                if t in self.flippedTables[channel.id]:
                    self.flippedTables[channel.id][t] += 1
                else:
                    self.flippedTables[channel.id][t] = 1
                    all_tables = await self.config.guild(message.guild).ALL_TABLES()
                    if not all_tables:
                        break
            else:
                f = t.replace("┬", "┻").replace("─", "━")
                if f in self.flippedTables[channel.id]:
                    if self.flippedTables[channel.id][f] <= 0:
                        del self.flippedTables[channel.id][f]
                    else:
                        self.flippedTables[channel.id][f] -= 1
        # wait random time. some tables may be unflipped by now.
        await asyncio.sleep(randfloat(0, 1.5))
        tables = ""

        deleteTables = []
        # unflip tables in self.flippedTables[channel.id]
        for t, n in self.flippedTables[channel.id].items():
            snackburr = await self.config.guild(message.guild).SNACKBEAR()
            if snackburr:
                unflipped = t.replace("┻", "┬").replace("━", "─") + " ノʕ •ᴥ•ノʔ" + "\n"
            else:
                unflipped = t.replace("┻", "┬").replace("━", "─") + " ノ( ゜-゜ノ)" + "\n"
            for i in range(0, n):
                tables += unflipped
                # in case being processed in parallel
                self.flippedTables[channel.id][t] -= 1
            deleteTables.append(t)
        for t in deleteTables:
            del self.flippedTables[channel.id][t]
        if tables != "":
            await channel.send(tables)
