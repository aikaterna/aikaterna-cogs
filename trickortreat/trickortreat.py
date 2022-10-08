import asyncio
import datetime
from typing import Literal, Optional

import discord
import random
import math
from redbot.core import commands, checks, Config, bank
from redbot.core.utils.chat_formatting import box, pagify, humanize_number
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

__version__ = "0.1.7"


class TrickOrTreat(commands.Cog):
    """Trick or treating for your server."""

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord", "owner", "user", "user_strict"],
        user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2710311393, force_registration=True)

        default_guild = {"cooldown": 300, "channel": [], "pick": 50, "toggle": False}

        default_user = {
            "candies": 0,
            "chocolate": 0,
            "cookies": 0,
            "eaten": 0,
            "last_tot": "2018-01-01 00:00:00.000001",
            "lollipops": 0,
            "sickness": 0,
            "stars": 0,
        }

        self.config.register_user(**default_user)
        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @commands.cooldown(1, 1, commands.BucketType.user)
    @commands.command()
    async def eatcandy(self, ctx, number: Optional[int] = 1, candy_type=None):
        """Eat some candy.

        Valid types: candy/candie(s), chocolate(s), lollipop(s), cookie(s), star(s)
        Examples:
            `[p]eatcandy 3 lollipops`
            `[p]eatcandy star`

        \N{CANDY}
        The star of this competition. You should try to eat all of these, but don't get too sick.

        \N{CHOCOLATE BAR}
        Reduces sickness by 10.

        \N{LOLLIPOP}
        Reduces sickness by 20.

        \N{FORTUNE COOKIE}
        Sets sickness to a random amount - fortune favours the brave.

        \N{WHITE MEDIUM STAR}
        Resets sickness to 0.
        """
        userdata = await self.config.user(ctx.author).all()
        pick = await self.config.guild(ctx.guild).pick()
        if not candy_type:
            candy_type = "candies"
        if number < 0:
            return await ctx.send(
                "That doesn't sound fun.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
        if number == 0:
            return await ctx.send(
                "You pretend to eat a candy.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
        if candy_type in ["candies", "candy"]:
            candy_type = "candies"
        if candy_type in ["lollipops", "lollipop"]:
            candy_type = "lollipops"
        if candy_type in ["stars", "star"]:
            candy_type = "stars"
        if candy_type in ["chocolate", "chocolates"]:
            candy_type = "chocolate"
        if candy_type in ["cookie", "cookies"]:
            candy_type = "cookies"
        candy_list = ["candies", "chocolate", "lollipops", "cookies", "stars"]
        if candy_type not in candy_list:
            return await ctx.send(
                "That's not a candy type! Use the inventory command to see what you have.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
        if userdata[candy_type] < number:
            return await ctx.send(
                f"You don't have that many {candy_type}.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
        if userdata[candy_type] == 0:
            return await ctx.send(
                f"You contemplate the idea of eating {candy_type}.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )

        eat_phrase = [
            "You leisurely enjoy",
            "You take the time to savor",
            "You eat",
            "You scarf down",
            "You sigh in contentment after eating",
            "You gobble up",
            "You make a meal of",
            "You devour",
            "You monstrously pig out on",
            "You hastily chomp down on",
            "You daintily partake of",
            "You earnestly consume",
        ]
        if candy_type in ["candies", "candy"]:
            if (userdata["sickness"] + number * 2) in range(70, 95):
                await ctx.send(
                    "After all that candy, sugar doesn't sound so good.",
                    reference=ctx.message.to_reference(fail_if_not_exists=False),
                )
                yuck = random.randint(1, 10)
                if yuck == 10:
                    await self.config.user(ctx.author).sickness.set(userdata["sickness"] + 25)
                if yuck in range(1, 9):
                    await self.config.user(ctx.author).sickness.set(userdata["sickness"] + (yuck * 2))

                if userdata["candies"] > 3 + number:
                    lost_candy = userdata["candies"] - random.randint(1, 3) - number
                else:
                    lost_candy = userdata["candies"]

                pick_now = await self.config.guild(ctx.guild).pick()
                if lost_candy < 0:
                    await self.config.user(ctx.author).candies.set(0)
                    await self.config.guild(ctx.guild).pick.set(pick_now + lost_candy)
                else:
                    await self.config.user(ctx.author).candies.set(userdata["candies"] - lost_candy)
                    await self.config.guild(ctx.guild).pick.set(pick_now + lost_candy)

                await self.config.user(ctx.author).eaten.set(userdata["eaten"] + (userdata["candies"] - lost_candy))

                return await ctx.send(
                    f"You begin to think you don't need all this candy, maybe...\n*{lost_candy} candies are left behind*",
                    reference=ctx.message.to_reference(fail_if_not_exists=False),
                )

            if (userdata["sickness"] + number) > 96:
                await self.config.user(ctx.author).sickness.set(userdata["sickness"] + 30)
                lost_candy = userdata["candies"] - random.randint(1, 5)
                if lost_candy <= 0:
                    await self.config.user(ctx.author).candies.set(0)
                    message = await ctx.send(
                        "...",
                        reference=ctx.message.to_reference(fail_if_not_exists=False),
                    )
                    await asyncio.sleep(2)
                    await message.edit(content="..........")
                    await asyncio.sleep(2)
                    return await message.edit(
                        content="You feel absolutely disgusted. At least you don't have any candies left."
                    )
                await self.config.guild(ctx.guild).pick.set(pick + lost_candy)
                await self.config.user(ctx.author).candies.set(0)
                await self.config.user(ctx.author).eaten.set(userdata["eaten"] + (userdata["candies"] - lost_candy))
                message = await ctx.send("...", reference=ctx.message.to_reference(fail_if_not_exists=False))
                await asyncio.sleep(2)
                await message.edit(content="..........")
                await asyncio.sleep(2)
                return await message.edit(
                    content=f"You toss your candies on the ground in disgust.\n*{lost_candy} candies are left behind*"
                )

            pluralcandy = "candy" if number == 1 else "candies"
            await ctx.send(
                f"{random.choice(eat_phrase)} {number} {pluralcandy}. (Total eaten: `{humanize_number(await self.config.user(ctx.author).eaten() + number)}` \N{CANDY})",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
            await self.config.user(ctx.author).sickness.set(userdata["sickness"] + (number * 2))
            await self.config.user(ctx.author).candies.set(userdata["candies"] - number)
            await self.config.user(ctx.author).eaten.set(userdata["eaten"] + number)

        if candy_type in ["chocolates", "chocolate"]:
            pluralchoc = "chocolate" if number == 1 else "chocolates"
            await ctx.send(
                f"{random.choice(eat_phrase)} {number} {pluralchoc}. You feel slightly better!\n*Sickness has gone down by {number * 10}*",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
            new_sickness = userdata["sickness"] - (number * 10)
            if new_sickness < 0:
                new_sickness = 0
            await self.config.user(ctx.author).sickness.set(new_sickness)
            await self.config.user(ctx.author).chocolate.set(userdata["chocolate"] - number)
            await self.config.user(ctx.author).eaten.set(userdata["eaten"] + number)

        if candy_type in ["lollipops", "lollipop"]:
            pluralpop = "lollipop" if number == 1 else "lollipops"
            await ctx.send(
                f"{random.choice(eat_phrase)} {number} {pluralpop}. You feel slightly better!\n*Sickness has gone down by {number * 20}*",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
            new_sickness = userdata["sickness"] - (number * 20)
            if new_sickness < 0:
                new_sickness = 0
            await self.config.user(ctx.author).sickness.set(new_sickness)
            await self.config.user(ctx.author).lollipops.set(userdata["lollipops"] - number)
            await self.config.user(ctx.author).eaten.set(userdata["eaten"] + number)

        if candy_type in ["cookies", "cookie"]:
            pluralcookie = "cookie" if number == 1 else "cookies"
            new_sickness = random.randint(0, 100)
            old_sickness = userdata["sickness"]
            if new_sickness > old_sickness:
                phrase = f"You feel worse!\n*Sickness has gone up by {new_sickness - old_sickness}*"
            else:
                phrase = f"You feel better!\n*Sickness has gone down by {old_sickness - new_sickness}*"
            await ctx.reply(
                f"{random.choice(eat_phrase)} {number} {pluralcookie}. {phrase}"
            )
            await self.config.user(ctx.author).sickness.set(new_sickness)
            await self.config.user(ctx.author).cookies.set(userdata["cookies"] - number)
            await self.config.user(ctx.author).eaten.set(userdata["eaten"] + number)

        if candy_type in ["stars", "star"]:
            pluralstar = "star" if number == 1 else "stars"
            await ctx.send(
                f"{random.choice(eat_phrase)} {number} {pluralstar}. You feel great!\n*Sickness has been reset*",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
            await self.config.user(ctx.author).sickness.set(0)
            await self.config.user(ctx.author).stars.set(userdata["stars"] - number)
            await self.config.user(ctx.author).eaten.set(userdata["eaten"] + number)

    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def totbalance(self, ctx):
        """[Admin] Check how many candies are 'on the ground' in the guild."""
        pick = await self.config.guild(ctx.guild).pick()
        await ctx.send(f"The guild is currently holding: {pick} \N{CANDY}")

    @commands.guild_only()
    @commands.command()
    async def buycandy(self, ctx, pieces: int):
        """Buy some candy. Prices could vary at any time."""
        candy_now = await self.config.user(ctx.author).candies()
        credits_name = await bank.get_currency_name(ctx.guild)
        if pieces <= 0:
            return await ctx.send(
                "Not in this reality.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
        candy_price = int(round(await bank.get_balance(ctx.author)) * 0.04) * pieces
        if candy_price in range(0, 10):
            candy_price = pieces * 10
        try:
            await bank.withdraw_credits(ctx.author, candy_price)
        except ValueError:
            return await ctx.send(
                f"Not enough {credits_name} ({candy_price} required).",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
        await self.config.user(ctx.author).candies.set(candy_now + pieces)
        await ctx.send(
            f"Bought {pieces} candies with {candy_price} {credits_name}.",
            reference=ctx.message.to_reference(fail_if_not_exists=False),
        )

    @commands.guild_only()
    @commands.command()
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    async def cboard(self, ctx):
        """Show the candy eating leaderboard."""
        userinfo = await self.config._all_from_scope(scope="USER")
        if not userinfo:
            return await ctx.send(
                "No one has any candy.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
        async with ctx.typing():
            sorted_acc = sorted(userinfo.items(), key=lambda x: x[1]["eaten"], reverse=True)
        # Leaderboard logic from https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/economy/economy.py#L445
        pound_len = len(str(len(sorted_acc)))
        score_len = 10
        header = "{pound:{pound_len}}{score:{score_len}}{name:2}\n".format(
            pound="#",
            pound_len=pound_len + 3,
            score="Candies Eaten",
            score_len=score_len + 6,
            name="\N{THIN SPACE}" + "Name"
            if not str(ctx.author.mobile_status) in ["online", "idle", "dnd"]
            else "Name",
        )
        temp_msg = header
        for pos, account in enumerate(sorted_acc):
            if account[1]["eaten"] == 0:
                continue
            try:
                if account[0] in [member.id for member in ctx.guild.members]:
                    user_obj = ctx.guild.get_member(account[0])
                else:
                    user_obj = await self.bot.fetch_user(account[0])
            except AttributeError:
                user_obj = await self.bot.fetch_user(account[0])
            
            _user_name = discord.utils.escape_markdown(user_obj.name)
            user_name = f"{_user_name}#{user_obj.discriminator}"
            if len(user_name) > 28:
                user_name = f"{_user_name[:19]}...#{user_obj.discriminator}"
            user_idx = pos + 1
            if user_obj == ctx.author:
                temp_msg += (
                    f"{f'{user_idx}.': <{pound_len + 2}} "
                    f"{humanize_number(account[1]['eaten']) + ' 🍬': <{score_len + 4}} <<{user_name}>>\n"
                )
            else:
                temp_msg += (
                    f"{f'{user_idx}.': <{pound_len + 2}} "
                    f"{humanize_number(account[1]['eaten']) + ' 🍬': <{score_len + 4}} {user_name}\n"
                )

        page_list = []
        pages = 1
        for page in pagify(temp_msg, delims=["\n"], page_length=1000):
            embed = discord.Embed(
                colour=0xF4731C,
                description=box(f"\N{CANDY} Global Leaderboard \N{CANDY}", lang="prolog") + (box(page, lang="md")),
            )
            embed.set_footer(text=f"Page {humanize_number(pages)}/{humanize_number(math.ceil(len(temp_msg) / 1500))}")
            pages += 1
            page_list.append(embed)
        return await menu(ctx, page_list, DEFAULT_CONTROLS)

    @commands.guild_only()
    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def cinventory(self, ctx):
        """Check your inventory."""
        userdata = await self.config.user(ctx.author).all()
        sickness = userdata["sickness"]
        msg = f"{ctx.author.mention}'s Candy Bag:"
        em = discord.Embed(color=await ctx.embed_color())
        em.description = f"{userdata['candies']} \N{CANDY}"
        if userdata["chocolate"]:
            em.description += f"\n{userdata['chocolate']} \N{CHOCOLATE BAR}"
        if userdata["lollipops"]:
            em.description += f"\n{userdata['lollipops']} \N{LOLLIPOP}"
        if userdata["cookies"]:
            em.description += f"\n{userdata['cookies']} \N{FORTUNE COOKIE}"
        if userdata["stars"]:
            em.description += f"\n{userdata['stars']} \N{WHITE MEDIUM STAR}"
        if sickness in range(41, 56):
            em.description += f"\n\n**Sickness is over 40/100**\n*You don't feel so good...*"
        elif sickness in range(56, 71):
            em.description += f"\n\n**Sickness is over 55/100**\n*You don't feel so good...*"
        elif sickness in range(71, 86):
            em.description += f"\n\n**Sickness is over 70/100**\n*You really don't feel so good...*"
        elif sickness in range(86, 101):
            em.description += f"\n\n**Sickness is over 85/100**\n*The thought of more sugar makes you feel awful...*"
        elif sickness > 100:
            em.description += f"\n\n**Sickness is over 100/100**\n*Better wait a while for more candy...*"
        await ctx.send(msg, embed=em)

    @commands.guild_only()
    @checks.is_owner()
    @commands.command()
    async def totclearall(self, ctx, are_you_sure=False):
        """[Owner] Clear all saved game data."""
        if not are_you_sure:
            msg = "This will clear ALL saved data for this cog and reset it to the defaults.\n"
            msg += f"If you are absolutely sure you want to do this, use `{ctx.prefix}totclearall yes`."
            return await ctx.send(msg)
        await self.config.clear_all()
        await ctx.send("All data for this cog has been cleared.")

    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def totcooldown(self, ctx, cooldown_time: int = 0):
        """Set the cooldown time for trick or treating on the server."""
        if cooldown_time < 0:
            return await ctx.send("Nice try.")
        if cooldown_time == 0:
            await self.config.guild(ctx.guild).cooldown.set(300)
            return await ctx.send("Trick or treating cooldown time reset to 5m.")
        elif 1 <= cooldown_time <= 30:
            await self.config.guild(ctx.guild).cooldown.set(30)
            return await ctx.send("Trick or treating cooldown time set to the minimum of 30s.")
        else:
            await self.config.guild(ctx.guild).cooldown.set(cooldown_time)
            await ctx.send(f"Trick or treating cooldown time set to {cooldown_time}s.")

    @commands.guild_only()
    @commands.cooldown(1, 600, discord.ext.commands.BucketType.user)
    @commands.command()
    async def pickup(self, ctx):
        """Pick up some candy, if there is any."""
        candies = await self.config.user(ctx.author).candies()
        to_pick = await self.config.guild(ctx.guild).pick()
        chance = random.randint(1, 100)
        found = round((chance / 100) * to_pick)
        await self.config.user(ctx.author).candies.set(candies + found)
        await self.config.guild(ctx.guild).pick.set(to_pick - found)
        message = await ctx.send(
            "You start searching the area for candy...",
            reference=ctx.message.to_reference(fail_if_not_exists=False),
        )
        await asyncio.sleep(3)
        await message.edit(content=f"You found {found} \N{CANDY}!")

    @commands.guild_only()
    @commands.cooldown(1, 600, discord.ext.commands.BucketType.user)
    @commands.command()
    async def stealcandy(self, ctx, user: discord.Member = None):
        """Steal some candy."""
        guild_users = [m.id for m in ctx.guild.members if m is not m.bot and not m == ctx.author]
        candy_users = await self.config._all_from_scope(scope="USER")
        valid_user = list(set(guild_users) & set(candy_users))
        if not valid_user:
            return await ctx.send(
                "No one has any candy yet!",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
        if not user:
            picked_user = self.bot.get_user(random.choice(valid_user))
        elif user == ctx.author or user == user.bot:
            picked_user = self.bot.get_user(random.choice(valid_user))
        elif user != ctx.author or user != user.bot:
            picked_user = user
        else:
            picked_user = self.bot.get_user(random.choice(valid_user))
        picked_candy_now = await self.config.user(picked_user).candies()
        if picked_candy_now == 0:
            chance = random.randint(1, 25)
            if chance in range(21, 25):
                new_picked_user = self.bot.get_user(random.choice(valid_user))
                new_picked_candy_now = await self.config.user(new_picked_user).candies()
                if chance in range(24, 25):
                    if new_picked_candy_now == 0:
                        message = await ctx.send(
                            "You see an unsuspecting guildmate...",
                            reference=ctx.message.to_reference(fail_if_not_exists=False),
                        )
                        await asyncio.sleep(random.randint(3, 6))
                        return await message.edit(
                            content=f"There was nothing in {picked_user.name}#{picked_user.discriminator}'s pockets, so you picked {new_picked_user.name}#{new_picked_user.discriminator}'s pockets but they had no candy either!"
                        )
                else:
                    message = await ctx.send(
                        "You see an unsuspecting guildmate...",
                        reference=ctx.message.to_reference(fail_if_not_exists=False),
                    )
                    await asyncio.sleep(random.randint(3, 6))
                    return await message.edit(
                        content=f"There was nothing in {picked_user.name}#{picked_user.discriminator}'s pockets, so you looked around again... you saw {new_picked_user.name}#{new_picked_user.discriminator} in the distance, but you didn't think you could catch up..."
                    )
            if chance in range(10, 20):
                message = await ctx.send(
                    "You start sneaking around in the shadows...",
                    reference=ctx.message.to_reference(fail_if_not_exists=False),
                )
                await asyncio.sleep(random.randint(3, 6))
                return await message.edit(
                    content=f"You snuck up on {picked_user.name}#{picked_user.discriminator} and tried picking their pockets but there was nothing there!"
                )
            else:
                message = await ctx.send(
                    "You start looking around for a target...",
                    reference=ctx.message.to_reference(fail_if_not_exists=False),
                )
                await asyncio.sleep(random.randint(3, 6))
                return await message.edit(content="You snuck around for a while but didn't find anything.")
        user_candy_now = await self.config.user(ctx.author).candies()
        multip = random.randint(1, 100) / 100
        if multip > 0.7:
            multip = 0.7
        pieces = round(picked_candy_now * multip)
        if pieces <= 0:
            message = await ctx.send(
                "You stealthily move over to an unsuspecting person...",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
            await asyncio.sleep(4)
            return await message.edit(content="You found someone to pickpocket, but they had nothing but pocket lint.")
        chance = random.randint(1, 25)
        sneak_phrases = [
            "You look around furtively...",
            "You glance around slowly, looking for your target...",
            "You see someone with a full candy bag...",
        ]
        if chance <= 10:
            message = await ctx.send(
                "You creep closer to the target...",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
            await asyncio.sleep(random.randint(3, 5))
            return await message.edit(content="You snuck around for a while but didn't find anything.")
        if chance > 18:
            await self.config.user(picked_user).candies.set(picked_candy_now - pieces)
            await self.config.user(ctx.author).candies.set(user_candy_now + pieces)
            message = await ctx.send(
                random.choice(sneak_phrases),
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
            await asyncio.sleep(4)
            await message.edit(content="There seems to be an unsuspecting victim in the corner...")
            await asyncio.sleep(4)
            return await message.edit(
                content=f"You stole {pieces} \N{CANDY} from {picked_user.name}#{picked_user.discriminator}!"
            )
        if chance in range(11, 17):
            await self.config.user(picked_user).candies.set(picked_candy_now - round(pieces / 2))
            await self.config.user(ctx.author).candies.set(user_candy_now + round(pieces / 2))
            message = await ctx.send(
                random.choice(sneak_phrases),
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
            await asyncio.sleep(4)
            await message.edit(content="There seems to be an unsuspecting victim in the corner...")
            await asyncio.sleep(4)
            return await message.edit(
                content=f"You stole {round(pieces/2)} \N{CANDY} from {picked_user.name}#{picked_user.discriminator}!"
            )
        else:
            message = await ctx.send(
                random.choice(sneak_phrases),
                reference=ctx.message.to_reference(fail_if_not_exists=False),
            )
            await asyncio.sleep(4)
            noise_msg = [
                "You hear a sound behind you! When you turn back, your target is gone.",
                "You look away for a moment and your target has vanished.",
                "Something flashes in your peripheral vision, and as you turn to look, your target gets away...",
            ]
            await message.edit(content=random.choice(noise_msg))

    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    @commands.group()
    async def totchannel(self, ctx):
        """Channel management for Trick or Treat."""
        if ctx.invoked_subcommand is not None or isinstance(ctx.invoked_subcommand, commands.Group):
            return
        channel_list = await self.config.guild(ctx.guild).channel()
        channel_msg = "Trick or Treat Channels:\n"
        for chan in channel_list:
            channel_obj = self.bot.get_channel(chan)
            if channel_obj:
                channel_msg += f"{channel_obj.name}\n"
        await ctx.send(box(channel_msg))

    @commands.guild_only()
    @totchannel.command()
    async def add(self, ctx, channel: discord.TextChannel):
        """Add a text channel for Trick or Treating."""
        channel_list = await self.config.guild(ctx.guild).channel()
        if channel.id not in channel_list:
            channel_list.append(channel.id)
            await self.config.guild(ctx.guild).channel.set(channel_list)
            await ctx.send(f"{channel.mention} added to the valid Trick or Treat channels.")
        else:
            await ctx.send(f"{channel.mention} is already in the list of Trick or Treat channels.")

    @commands.guild_only()
    @totchannel.command()
    async def remove(self, ctx, channel: discord.TextChannel):
        """Remove a text channel from Trick or Treating."""
        channel_list = await self.config.guild(ctx.guild).channel()
        if channel.id in channel_list:
            channel_list.remove(channel.id)
        else:
            return await ctx.send(f"{channel.mention} not in whitelist.")
        await self.config.guild(ctx.guild).channel.set(channel_list)
        await ctx.send(f"{channel.mention} removed from the list of Trick or Treat channels.")

    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def tottoggle(self, ctx):
        """Toggle trick or treating on the whole server."""
        toggle = await self.config.guild(ctx.guild).toggle()
        msg = f"Trick or Treating active: {not toggle}.\n"
        channel_list = await self.config.guild(ctx.guild).channel()
        if not channel_list:
            channel_list.append(ctx.message.channel.id)
            await self.config.guild(ctx.guild).channel.set(channel_list)
            msg += f"Trick or Treating channel added: {ctx.message.channel.mention}"
        await self.config.guild(ctx.guild).toggle.set(not toggle)
        await ctx.send(msg)

    @commands.guild_only()
    @commands.command(hidden=True)
    async def totversion(self, ctx):
        """Trick or Treat version."""
        await ctx.send(f"Trick or Treat version {__version__}")

    async def has_perm(self, user):
        return await self.bot.allowed_by_whitelist_blacklist(user)

    @commands.Cog.listener()
    async def on_message_without_command(self, message):
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return
        if message.author.bot:
            return
        if not await self.has_perm(message.author):
            return

        chance = random.randint(1, 12)
        if chance % 4 == 0:
            sickness_now = await self.config.user(message.author).sickness()
            sick_chance = random.randint(1, 12)
            if sick_chance % 3 == 0:
                new_sickness = sickness_now - sick_chance
                if new_sickness < 0:
                    new_sickness = 0
                await self.config.user(message.author).sickness.set(new_sickness)

        pick_chance = random.randint(1, 12)
        if pick_chance % 4 == 0:
            random_candies = random.randint(1, 3)
            guild_pool = await self.config.guild(message.guild).pick()
            await self.config.guild(message.guild).pick.set(guild_pool + random_candies)

        content = (message.content).lower()
        if not content.startswith("trick or treat"):
            return
        toggle = await self.config.guild(message.guild).toggle()
        if not toggle:
            return
        channel = await self.config.guild(message.guild).channel()
        if message.channel.id not in channel:
            return
        userdata = await self.config.user(message.author).all()

        last_time = datetime.datetime.strptime(str(userdata["last_tot"]), "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc)
        now = now.replace(tzinfo=None)
        if int((now - last_time).total_seconds()) < await self.config.guild(message.guild).cooldown():
            messages = [
                "The thought of candy right now doesn't really sound like a good idea.",
                "All the lights on this street are dark...",
                "It's starting to get late.",
                "The wind howls through the trees. Does it seem darker all of a sudden?",
                "You start to walk the long distance to the next house...",
                "You take a moment to count your candy before moving on.",
                "The house you were approaching just turned the light off.",
                "The wind starts to pick up as you look for the next house...",
            ]
            return await message.channel.send(
                random.choice(messages), reference=message.to_reference(fail_if_not_exists=False)
            )
        await self.config.user(message.author).last_tot.set(str(now))
        candy = random.randint(1, 25)
        lollipop = random.randint(0, 100)
        star = random.randint(0, 100)
        chocolate = random.randint(0, 100)
        cookie = random.randint(0, 100)
        win_message = f"{message.author.mention}\nYou received:\n{candy}\N{CANDY}"
        await self.config.user(message.author).candies.set(userdata["candies"] + candy)

        if chocolate == 100:
            await self.config.user(message.author).chocolate.set(userdata["chocolate"] + 6)
            win_message += "\n**BONUS**: 6 \N{CHOCOLATE BAR}"
        elif 99 >= chocolate >= 95:
            await self.config.user(message.author).chocolate.set(userdata["chocolate"] + 5)
            win_message += "\n**BONUS**: 5 \N{CHOCOLATE BAR}"
        elif 94 >= chocolate >= 90:
            await self.config.user(message.author).chocolate.set(userdata["chocolate"] + 4)
            win_message += "\n**BONUS**: 4 \N{CHOCOLATE BAR}"
        elif 89 >= chocolate >= 80:
            await self.config.user(message.author).chocolate.set(userdata["chocolate"] + 3)
            win_message += "\n**BONUS**: 3 \N{CHOCOLATE BAR}"
        elif 79 >= chocolate >= 75:
            await self.config.user(message.author).chocolate.set(userdata["chocolate"] + 2)
            win_message += "\n**BONUS**: 2 \N{CHOCOLATE BAR}"
        elif 74 >= chocolate >= 70:
            await self.config.user(message.author).chocolate.set(userdata["chocolate"] + 1)
            win_message += "\n**BONUS**: 1 \N{CHOCOLATE BAR}"

        if lollipop == 100:
            await self.config.user(message.author).lollipops.set(userdata["lollipops"] + 4)
            win_message += "\n**BONUS**: 4 \N{LOLLIPOP}"
        elif 99 >= lollipop >= 95:
            await self.config.user(message.author).lollipops.set(userdata["lollipops"] + 3)
            win_message += "\n**BONUS**: 3 \N{LOLLIPOP}"
        elif 94 >= lollipop >= 85:
            await self.config.user(message.author).lollipops.set(userdata["lollipops"] + 2)
            win_message += "\n**BONUS**: 2 \N{LOLLIPOP}"
        elif 84 >= lollipop >= 75:
            await self.config.user(message.author).lollipops.set(userdata["lollipops"] + 1)
            win_message += "\n**BONUS**: 1 \N{LOLLIPOP}"

        if cookie == 100:
            await self.config.user(message.author).cookies.set(userdata["cookies"] + 4)
            win_message += "\n**BONUS**: 4 \N{FORTUNE COOKIE}"
        elif 99 >= cookie >= 97:
            await self.config.user(message.author).cookies.set(userdata["cookies"] + 3)
            win_message += "\n**BONUS**: 3 \N{FORTUNE COOKIE}"
        elif 96 >= cookie >= 85:
            await self.config.user(message.author).cookies.set(userdata["cookies"] + 2)
            win_message += "\n**BONUS**: 2 \N{FORTUNE COOKIE}"
        elif 84 >= cookie >= 75:
            await self.config.user(message.author).cookies.set(userdata["cookies"] + 1)
            win_message += "\n**BONUS**: 1 \N{FORTUNE COOKIE}"

        if star == 100:
            await self.config.user(message.author).stars.set(userdata["stars"] + 4)
            win_message += "\n**BONUS**: 4 \N{WHITE MEDIUM STAR}"
        elif 99 >= star >= 97:
            await self.config.user(message.author).stars.set(userdata["stars"] + 3)
            win_message += "\n**BONUS**: 3 \N{WHITE MEDIUM STAR}"
        elif 96 >= star >= 85:
            await self.config.user(message.author).stars.set(userdata["stars"] + 2)
            win_message += "\n**BONUS**: 2 \N{WHITE MEDIUM STAR}"
        elif 84 >= star >= 75:
            await self.config.user(message.author).stars.set(userdata["stars"] + 1)
            win_message += "\n**BONUS**: 1 \N{WHITE MEDIUM STAR}"

        walking_messages = [
            "*You hear footsteps...*",
            "*You're left alone with your thoughts as you wait for the door to open...*",
            "*The wind howls through the trees...*",
            "*Does it feel colder out here all of a sudden?*",
            "*Somewhere inside the house, you hear wood creaking...*",
            "*You walk up the path to the door and knock...*",
            "*You knock on the door...*",
            "*There's a movement in the shadows by the side of the house...*",
        ]
        bot_talking = await message.channel.send(
            random.choice(walking_messages), reference=message.to_reference(fail_if_not_exists=False)
        )
        await asyncio.sleep(random.randint(5, 8))
        door_messages = [
            "*The door slowly opens...*",
            "*The ancient wooden door starts to open...*",
            "*A light turns on overhead...*",
            "*You hear a scuffling noise...*",
            "*There's someone talking inside...*",
            "*The wind whips around your feet...*",
            "*A crow caws ominously...*",
            "*You hear an owl hooting in the distance...*",
        ]
        await bot_talking.edit(content=random.choice(door_messages))
        await asyncio.sleep(random.randint(5, 8))
        greet_messages = [
            "Oh, hello. What a cute costume. Here, have some candy.",
            "Look at that costume. Here you go.",
            "Out this late at night?",
            "Here's a little something for you.",
            "The peppermint ones are my favorite.",
            "Come back again later if you see the light on still.",
            "Go ahead, take a few.",
            "Here you go.",
            "Aww, look at you. Here, take this.",
            "Don't eat all those at once!",
            "Well, I think this is the last of it. Go ahead and take it.",
            "*I hear the next door neighbors have some pretty good candy too, this year.*",
        ]
        await bot_talking.edit(content=random.choice(greet_messages))
        await asyncio.sleep(2)
        await message.channel.send(win_message)
