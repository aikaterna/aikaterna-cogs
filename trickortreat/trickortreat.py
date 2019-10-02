import asyncio
import datetime
import discord
import random
from redbot.core import commands, checks, Config, bank
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

__version__ = "0.0.5"
BaseCog = getattr(commands, "Cog", object)

listener = getattr(commands.Cog, "listener", None)  # Trusty + Sinbad
if listener is None:

    def listener(name=None):
        return lambda x: x

class TrickOrTreat(BaseCog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2710311393, force_registration=True)

        default_guild = {"cooldown": 300, "channel": [], "pick": 50, "toggle": False}

        default_user = {
            "candies": 0,
            "eaten": 0,
            "last_tot": "2018-01-01 00:00:00.000001",
            "lollipops": 0,
            "sickness": 0,
            "stars": 0,
        }

        self.config.register_user(**default_user)
        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @commands.command()
    async def eat(self, ctx, number: int = 1, candy_type=None):
        """Eat some candy.
        
        Valid types: candies, lollipops, stars"""
        userdata = await self.config.user(ctx.author).all()
        pick = await self.config.guild(ctx.guild).pick()
        if not candy_type:
            candy_type = "candies"
        if number <= 0:
            number == 1
        if candy_type in ["candies", "candy"]:
            candy_type = "candies"
        if candy_type in ["lollipops", "lollipop"]:
            candy_type = "lollipops"
        if candy_type in ["stars", "star"]:
            candy_type = "stars"
        candy_list = ["candies", "lollipops", "stars"]
        if candy_type not in candy_list:
            return await ctx.send(
                "That's not a candy type! Use the inventory command to see what you have."
            )
        if userdata[candy_type] < number:
            return await ctx.send(f"You don't have that many {candy_type}.")
        if userdata[candy_type] == 0:
            return await ctx.send(f"You contemplate the idea of eating {candy_type}.")

        eat_phrase = [
            "You leisurely enjoy",
            "You take the time to savor",
            "You eat",
            "You scarf down",
            "You sigh in contentment after eating",
            "You gobble up",
            "You make a meal of",
            "You devour",
        ]
        if candy_type in ["candies", "candy"]:
            if (userdata["sickness"] + number * 2) in range(70, 95):
                await ctx.send("After all that candy, sugar doesn't sound so good.")
                yuck = random.randint(1, 10)
                if yuck == 10:
                    await self.config.user(ctx.author).sickness.set(userdata["sickness"] + 25)
                if yuck in range(1, 9):
                    await self.config.user(ctx.author).sickness.set(
                        userdata["sickness"] + (yuck * 2)
                    )

                if userdata["candies"] > 3 + number:
                    lost_candy = userdata["candies"] - random.randint(1, 3) - number
                else:
                    lost_candy = userdata["candies"]

                pick_now = await self.config.guild(ctx.guild).pick()
                if lost_candy < 0:
                    await self.config.user(ctx.author).candies.set(0)
                    await self.config.guild(ctx.guild).pick.set(pick_now + lost_candy)
                else:
                    await self.config.user(ctx.author).candies.set(
                        userdata["candies"] - lost_candy
                    )
                    await self.config.guild(ctx.guild).pick.set(pick_now + lost_candy)

                await self.config.user(ctx.author).eaten.set(
                    userdata["eaten"] + (userdata["candies"] - lost_candy)
                )

                return await ctx.send(
                    f"You begin to think you don't need all this candy, maybe...\n*{lost_candy} candies are left behind*"
                )

            if (userdata["sickness"] + number) > 96:
                await self.config.user(ctx.author).sickness.set(userdata["sickness"] + 30)
                lost_candy = userdata["candies"] - random.randint(1, 5)
                if lost_candy <= 0:
                    await self.config.user(ctx.author).candies.set(0)
                    message = await ctx.send("...")
                    await asyncio.sleep(2)
                    await message.edit(content="..........")
                    await asyncio.sleep(2)
                    return await message.edit(
                        content="You feel absolutely disgusted. At least you don't have any candies left."
                    )
                await self.config.guild(ctx.guild).pick.set(pick + lost_candy)
                await self.config.user(ctx.author).candies.set(0)
                await self.config.user(ctx.author).eaten.set(
                    userdata["eaten"] + (userdata["candies"] - lost_candy)
                )
                message = await ctx.send("...")
                await asyncio.sleep(2)
                await message.edit(content="..........")
                await asyncio.sleep(2)
                return await message.edit(
                    content=f"You toss your candies on the ground in disgust.\n*{lost_candy} candies are left behind*"
                )

            pluralcandy = "candy" if number == 1 else "candies"
            await ctx.send(f"{random.choice(eat_phrase)} {number} {pluralcandy}.")
            await self.config.user(ctx.author).sickness.set(userdata["sickness"] + (number * 2))
            await self.config.user(ctx.author).candies.set(userdata["candies"] - number)
            await self.config.user(ctx.author).eaten.set(userdata["eaten"] + number)
        if candy_type in ["lollipops", "lollipop"]:
            pluralpop = "lollipop" if number == 1 else "lollipops"
            await ctx.send(
                f"{random.choice(eat_phrase)} {number} {pluralpop}. You feel slightly better!\n*Sickness has gone down by {number * 20}*"
            )
            new_sickness = userdata["sickness"] - (number * 20)
            if new_sickness < 0:
                new_sickness = 0
            await self.config.user(ctx.author).sickness.set(new_sickness)
            await self.config.user(ctx.author).lollipops.set(userdata["lollipops"] - number)
            await self.config.user(ctx.author).eaten.set(userdata["eaten"] + number)
        if candy_type in ["stars", "star"]:
            pluralstar = "star" if number == 1 else "stars"
            await ctx.send(
                f"{random.choice(eat_phrase)} {number} {pluralstar}. You feel great!\n*Sickness has been reset*"
            )
            await self.config.user(ctx.author).sickness.set(0)
            await self.config.user(ctx.author).stars.set(userdata["stars"] - number)
            await self.config.user(ctx.author).eaten.set(userdata["eaten"] + number)

    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def balance(self, ctx):
        """Check how many candies are 'on the ground' in the guild."""
        pick = await self.config.guild(ctx.guild).pick()
        await ctx.send(f"The guild is currently holding: {pick} \N{CANDY}")

    @commands.guild_only()
    @commands.command()
    async def buy(self, ctx, pieces: int):
        """Buy some candy. Prices could vary at any time."""
        candy_now = await self.config.user(ctx.author).candies()
        credits_name = await bank.get_currency_name(ctx.guild)
        if pieces <= 0:
            return await ctx.send("Not in this reality.")
        candy_price = int(round(await bank.get_balance(ctx.author)) * 0.04) * pieces
        if candy_price in range(0, 10):
            candy_price = pieces * 10
        try:
            await bank.withdraw_credits(ctx.author, candy_price)
        except ValueError:
            return await ctx.send(f"Not enough {credits_name} ({candy_price} required).")
        await self.config.user(ctx.author).candies.set(candy_now + pieces)
        await ctx.send(f"Bought {pieces} candies with {candy_price} {credits_name}.")

    @commands.guild_only()
    @commands.command()
    async def cboard(self, ctx):
        """Show the candy eating leaderboard."""
        userinfo = await self.config._all_from_scope(scope="USER")
        if not userinfo:
            return await ctx.send("No one has any candy.")
        message = await ctx.send("Populating leaderboard...")
        sorted_acc = sorted(userinfo.items(), key=lambda x: x[1]["eaten"], reverse=True)
        msg = "{name:33}{score:19}\n".format(name="Name", score="Candies Eaten")
        for i, account in enumerate(sorted_acc):
            if account[1]["eaten"] == 0:
                continue
            user_idx = i + 1
            user_obj = await self.bot.fetch_user(account[0])
            user_name = f"{user_obj.name}#{user_obj.discriminator}"
            if len(user_name) > 28:
                user_name = f"{user_obj.name[:19]}...#{user_obj.discriminator}"
            if user_obj == ctx.author:
                name = f"{user_idx}. <<{user_name}>>"
            else:
                name = f"{user_idx}. {user_name}"
            msg += f"{name:33}{account[1]['eaten']}\N{CANDY}\n"

        page_list = []
        for page in pagify(msg, delims=["\n"], page_length=1000):
            embed = discord.Embed(
                colour=await ctx.embed_colour(), description=(box(page, lang="md"))
            )
            page_list.append(embed)
        await message.edit(content=box(f"\N{CANDY} Global Leaderboard \N{CANDY}", lang="prolog"))
        await menu(ctx, page_list, DEFAULT_CONTROLS)

    @commands.guild_only()
    @commands.command()
    async def cinventory(self, ctx):
        """Check your inventory."""
        userdata = await self.config.user(ctx.author).all()
        msg = f"{ctx.author.mention}'s Candy Bag:\n{userdata['candies']} \N{CANDY}"
        if userdata["lollipops"]:
            msg += f"\n{userdata['lollipops']} \N{LOLLIPOP}"
        if userdata["stars"]:
            msg += f"\n{userdata['stars']} \N{WHITE MEDIUM STAR}"
        if userdata["sickness"] in range(41, 56):
            msg += "\n\n**Sickness is over 40/100**\n*You don't feel so good...*"
        elif userdata["sickness"] in range(56, 71):
            msg += "\n\n**Sickness is over 55/100**\n*You don't feel so good...*"
        elif userdata["sickness"] in range(71, 86):
            msg += "\n\n**Sickness is over 70/100**\n*You really don't feel so good...*"
        elif userdata["sickness"] in range(86, 101):
            msg += "\n\n**Sickness is over 85/100**\n*The thought of more sugar makes you feel awful...*"
        elif userdata["sickness"] > 100:
            msg += "\n\n**Sickness is over 100/100**\n*Better wait a while for more candy...*"
        await ctx.send(msg)

    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def cooldown(self, ctx, cooldown_time: int = 0):
        """Set the cooldown time for trick or treating on the server."""
        cooldown = await self.config.guild(ctx.guild).cooldown()
        if not cooldown_time:
            await self.config.guild(ctx.guild).cooldown.set(300)
            await ctx.send("Trick or treating cooldown time reset to 5m.")
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
        message = await ctx.send("You start searching the area for candy...")
        await asyncio.sleep(3)
        await message.edit(content=f"You found {found} \N{CANDY}!")

    @commands.guild_only()
    @commands.cooldown(1, 600, discord.ext.commands.BucketType.user)
    @commands.command()
    async def steal(self, ctx, user: discord.Member = None):
        """Steal some candy."""
        guild_users = [m.id for m in ctx.guild.members if m is not m.bot and not m == ctx.author]
        candy_users = await self.config._all_from_scope(scope="USER")
        valid_user = list(set(guild_users) & set(candy_users))
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
                        message = await ctx.send("You see an unsuspecting guildmate...")
                        await asyncio.sleep(random.randint(3, 6))
                        return await message.edit(
                            content=f"There was nothing in {picked_user.name}#{picked_user.discriminator}'s pockets, so you picked {new_picked_user.name}#{new_picked_user.discriminator}'s pockets but they had no candy either!"
                        )
                else:
                    message = await ctx.send("You see an unsuspecting guildmate...")
                    await asyncio.sleep(random.randint(3, 6))
                    return await message.edit(
                        content=f"There was nothing in {picked_user.name}#{picked_user.discriminator}'s pockets, so you looked around again... you saw {new_picked_user.name}#{new_picked_user.discriminator} in the distance, but you didn't think you could catch up..."
                    )
            if chance in range(10, 20):
                message = await ctx.send("You start sneaking around in the shadows...")
                await asyncio.sleep(random.randint(3, 6))
                return await message.edit(
                    content=f"You snuck up on {picked_user.name}#{picked_user.discriminator} and tried picking their pockets but there was nothing there!"
                )
            else:
                message = await ctx.send("You start looking around for a target...")
                await asyncio.sleep(random.randint(3, 6))
                return await message.edit(
                    content="You snuck around for a while but didn't find anything."
                )
        user_candy_now = await self.config.user(ctx.author).candies()
        multip = random.randint(1, 100) / 100
        if multip > 0.7:
            multip = 0.7
        pieces = round(picked_candy_now * multip)
        if pieces <= 0:
            message = await ctx.send("You stealthily move over to an unsuspecting person...")
            await asyncio.sleep(4)
            return await message.edit(
                content="You found someone to pickpocket, but they had nothing but pocket lint."
            )
        chance = random.randint(1, 25)
        sneak_phrases = [
            "You look around furtively...",
            "You glance around slowly, looking for your target...",
            "You see someone with a full candy bag...",
        ]
        if chance <= 10:
            message = await ctx.send("You creep closer to the target...")
            await asyncio.sleep(random.randint(3, 5))
            return await message.edit(
                content="You snuck around for a while but didn't find anything."
            )
        if chance > 18:
            await self.config.user(picked_user).candies.set(picked_candy_now - pieces)
            await self.config.user(ctx.author).candies.set(user_candy_now + pieces)
            message = await ctx.send(random.choice(sneak_phrases))
            await asyncio.sleep(4)
            await message.edit(content="There seems to be an unsuspecting victim in the corner...")
            await asyncio.sleep(4)
            return await message.edit(
                content=f"You stole {pieces} \N{CANDY} from {picked_user.name}#{picked_user.discriminator}!"
            )
        if chance in range(11, 17):
            await self.config.user(picked_user).candies.set(picked_candy_now - round(pieces / 2))
            await self.config.user(ctx.author).candies.set(user_candy_now + round(pieces / 2))
            message = await ctx.send(random.choice(sneak_phrases))
            await asyncio.sleep(4)
            await message.edit(content="There seems to be an unsuspecting victim in the corner...")
            await asyncio.sleep(4)
            return await message.edit(
                content=f"You stole {round(pieces/2)} \N{CANDY} from {picked_user.name}#{picked_user.discriminator}!"
            )
        else:
            message = await ctx.send(random.choice(sneak_phrases))
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
        if ctx.invoked_subcommand is not None or isinstance(
            ctx.invoked_subcommand, commands.Group
        ):
            return
        channel_list = await self.config.guild(ctx.guild).channel()
        channel_msg = "Trick or Treat Channels:\n"
        for chan in channel_list:
            channel_obj = self.bot.get_channel(chan)
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
    @commands.command()
    async def totversion(self, ctx):
        """Trick or Treat version."""
        await ctx.send(
            f"Trick or Treat, version {__version__}\n\n*0.0.5 updates:*\n**Save values before waiting on messages:\nQuick commands will not overwrite other values**\n\n*0.0.4 updates:*\n**+2% star chance on trick or treat (6% total)\n+5% lollipop chance on trick or treat (25% total)\nMore RP messages\nFix for steal mechanic freezing\n**"
        )

    @listener()
    async def on_message(self, message):
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return
        if message.author.bot:
            return
        content = (message.content).lower()

        chance = random.randint(1, 12)
        if chance % 4 == 0:
            sickness_now = await self.config.user(message.author).sickness()
            sick_chance = random.randint(1, 12)
            if sick_chance % 3 == 0:
                new_sickness = sickness_now - sick_chance
                if new_sickness < 0:
                    new_sickness = 0
                await self.config.user(message.author).sickness.set(new_sickness)

        if "trick or treat" not in content:
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
        if (
            int((now - last_time).total_seconds())
            < await self.config.guild(message.guild).cooldown()
        ):
            await self.config.user(message.author).last_tot.set(str(now))
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
            return await message.channel.send(random.choice(messages))

        candy = random.randint(1, 25)
        lollipop = random.randint(0, 100)
        star = random.randint(0, 100)

        await self.config.user(message.author).candies.set(userdata["candies"] + candy)
        if lollipop > 75:
            await self.config.user(message.author).lollipops.set(userdata["lollipops"] + 1)
        if star > 94:
            await self.config.user(message.author).stars.set(userdata["stars"] + 1)

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
        bot_talking = await message.channel.send(random.choice(walking_messages))
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
        win_message = f"{message.author.mention}\nYou received:\n{candy}\N{CANDY}"
        if lollipop > 75:
            win_message += "\n**BONUS**: 1 \N{LOLLIPOP}"
        if star > 94:
            win_message += "\n**BONUS**: 1 \N{WHITE MEDIUM STAR}"

        await message.channel.send(win_message)
