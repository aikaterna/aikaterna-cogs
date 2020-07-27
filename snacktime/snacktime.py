import asyncio
import discord
import logging
from random import randint
from random import choice as randchoice

from redbot.core import bank, checks, commands, Config
from redbot.core.errors import BalanceTooHigh
from redbot.core.utils.chat_formatting import box, humanize_list, pagify

from .phrases import FRIENDS, SNACKBURR_PHRASES


log = logging.getLogger("red.aikaterna.snacktime")


class Snacktime(commands.Cog):
    """Snackburr's passing out pb jars!"""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2712291001, force_registration=True)

        self.snackSchedule = {}
        self.snacktimePrediction = {}
        self.previousSpeaker = {}
        self.snackInProgress = {}
        self.acceptInput = {}
        self.alreadySnacked = {}
        self.msgsPassed = {}
        self.startLock = {}
        self.snacktimeCheckLock = {}
        self.lockRequests = {}
        self.channel_persona = {}

        default_guild = {
            "DELIVER_CHANNELS": [],
            "FRIENDS": False,
            "EVENT_START_DELAY": 1800,
            "EVENT_START_DELAY_VARIANCE": 900,
            "SNACK_DURATION": 240,
            "SNACK_DURATION_VARIANCE": 120,
            "MSGS_BEFORE_EVENT": 8,
            "SNACK_AMOUNT": 200,
        }

        default_channel = {"repeatMissedSnacktimes": 0}

        self.config.register_guild(**default_guild)
        self.config.register_channel(**default_channel)

    async def persona_choice(self, ctx: None, message: None):
        if ctx:
            invite_friends = await self.config.guild(ctx.guild).FRIENDS()
        else:
            invite_friends = await self.config.guild(message.guild).FRIENDS()
        personas = FRIENDS
        if not invite_friends:
            return "Snackburr" if message else "ʕ •ᴥ•ʔ <"
        elif invite_friends is True:
            try:
                del personas["Snackburr"]
            except KeyError:
                pass
        if message:
            return randchoice(list(personas.keys()))
        else:
            return randchoice(list(personas.values()))

    async def get_response(self, msg, phrase_type):
        scid = f"{msg.guild.id}-{msg.channel.id}"
        persona = self.channel_persona[scid]
        persona_phrase = FRIENDS.get(persona)
        phrase = randchoice(SNACKBURR_PHRASES[phrase_type])
        return f"`{persona_phrase} {phrase}`"

    @commands.cooldown(1, 1, commands.BucketType.channel)
    @commands.guild_only()
    @commands.command()
    async def eat(self, ctx, amount: int):
        """
        all this talk about pb is makin me hungry.

        how bout you guys?
        """
        persona = await self.persona_choice(ctx=ctx, message=None)
        if amount < 0:
            return await ctx.send(f"`{persona} Woah slow down!`")
        if amount > await bank.get_balance(ctx.author):
            return await ctx.send(f"`{persona} You don't got that much pb!.. don't look at me..`")

        await bank.withdraw_credits(ctx.author, amount)

        first_phrase = randchoice(SNACKBURR_PHRASES["EAT_BEFORE"])
        second_phrase = randchoice(SNACKBURR_PHRASES["EAT_AFTER"])
        await ctx.send(f"`{persona} {ctx.author.display_name} {first_phrase} {second_phrase} {amount} whole pb jars!`")

    @commands.guild_only()
    @commands.group()
    @checks.mod_or_permissions(manage_guild=True)
    async def snackset(self, ctx):
        """snack stuff"""
        if ctx.invoked_subcommand is None:
            guild_data = await self.config.guild(ctx.guild).all()
            if not guild_data["DELIVER_CHANNELS"]:
                channel_names = ["No channels set."]
            else:
                channel_names = []
                for channel_id in guild_data["DELIVER_CHANNELS"]:
                    channel_obj = self.bot.get_channel(channel_id)
                    channel_names.append(channel_obj.name)

            if guild_data["FRIENDS"] is True:
                invite_friends = "Friends only"
            elif guild_data["FRIENDS"] is False:
                invite_friends = "Snackburr only"
            else:
                invite_friends = "Everyone's invited!"

            msg = f"[Delivering in]:           {humanize_list(channel_names)}\n"
            msg += f"[Event start delay]:       {guild_data['EVENT_START_DELAY']} seconds\n"
            msg += f"[Event start variance]:    {guild_data['EVENT_START_DELAY_VARIANCE']} seconds\n"
            msg += f"[Friends status]:          {invite_friends}\n"
            msg += f"[Messages before event]:   {guild_data['MSGS_BEFORE_EVENT']}\n"
            msg += f"[Snack amount limit]:      {guild_data['SNACK_AMOUNT']} pb\n"
            msg += f"[Snack duration]:          {guild_data['SNACK_DURATION']} seconds\n"
            msg += f"[Snack duration variance]: {guild_data['SNACK_DURATION_VARIANCE']} seconds\n"

            for page in pagify(msg, delims=["\n"]):
                await ctx.send(box(page, lang="ini"))

    @snackset.command()
    async def errandtime(self, ctx, seconds: int):
        """How long snackburr needs to be out doin errands.. more or less."""
        event_start_delay_variance = await self.config.guild(ctx.guild).EVENT_START_DELAY_VARIANCE()
        if seconds <= event_start_delay_variance:
            await ctx.send("errandtime must be greater than errandvariance!")
        elif seconds <= 0:
            await ctx.send("errandtime must be greater than 0")
        else:
            await self.config.guild(ctx.guild).EVENT_START_DELAY.set(seconds)
            await ctx.send(f"snackburr's errands will now take around {round(seconds/60, 2)} minutes!")

    @snackset.command()
    async def errandvariance(self, ctx, seconds: int):
        """How early or late snackburr might be to snacktime"""
        event_start_delay = await self.config.guild(ctx.guild).EVENT_START_DELAY()
        if seconds >= event_start_delay:
            await ctx.send("errandvariance must be less than errandtime!")
        elif seconds < 0:
            await ctx.send("errandvariance must be 0 or greater!")
        else:
            await self.config.guild(ctx.guild).EVENT_START_DELAY_VARIANCE.set(seconds)
            await ctx.send(f"snackburr now might be {round(seconds/60, 2)} minutes early or late to snacktime")

    @snackset.command(name="snacktime")
    async def snacktimetime(self, ctx, seconds: int):
        """How long snackburr will hang out giving out snacks!.. more or less."""
        snack_duration_variance = await self.config.guild(ctx.guild).SNACK_DURATION_VARIANCE()
        if seconds <= snack_duration_variance:
            await ctx.send("snacktime must be greater than snackvariance!")
        elif seconds <= 0:
            await ctx.send("snacktime must be greater than 0")
        else:
            await self.config.guild(ctx.guild).SNACK_DURATION.set(seconds)
            await ctx.send(f"snacktimes will now last around {round(seconds/60, 2)} minutes!")

    @snackset.command(name="snackvariance")
    async def snacktimevariance(self, ctx, seconds: int):
        """How early or late snackburr might have to leave for errands"""
        snack_duration = await self.config.guild(ctx.guild).SNACK_DURATION()
        if seconds >= snack_duration:
            await ctx.send("snackvariance must be less than snacktime!")
        elif seconds < 0:
            await ctx.send("snackvariance must be 0 or greater!")
        else:
            await self.config.guild(ctx.guild).SNACK_DURATION_VARIANCE.set(seconds)
            await ctx.send(f"snackburr now may have to leave snacktime {round(seconds/60, 2)} minutes early or late")

    @snackset.command()
    async def msgsneeded(self, ctx, amt: int):
        """How many messages must pass in a conversation before a snacktime can start"""
        if amt <= 0:
            await ctx.send("msgsneeded must be greater than 0")
        else:
            await self.config.guild(ctx.guild).MSGS_BEFORE_EVENT.set(amt)
            await ctx.send(f"snackburr will now wait until {amt} messages pass until he comes with snacks")

    @snackset.command()
    async def amount(self, ctx, amt: int):
        """How much pb max snackburr should give out to each person per snacktime"""

        if amt <= 0:
            await ctx.send("amount must be greater than 0")
        else:
            await self.config.guild(ctx.guild).SNACK_AMOUNT.set(amt)
            await ctx.send(f"snackburr will now give out {amt} pb max per person per snacktime.")

    @snackset.command(name="friends")
    async def snackset_friends(self, ctx, choice: int):
        """snackburr's friends wanna know what all the hub-bub's about!

        Do you want to
        1: invite them to the party,
        2: only allow snackburr to chillax with you guys, or
        3: kick snackburr out on the curb in favor of his obviously cooler friends?
        """

        if choice not in (1, 2, 3):
            return await ctx.send_help()

        choices = {
            1: ("both", "Everybody's invited!"),
            2: (False, "You chose to not invite snackburr's friends."),
            3: (True, "You kick snackburr out in favor of his friends! Ouch. Harsh..."),
        }
        choice = choices[choice]

        await self.config.guild(ctx.guild).FRIENDS.set(choice[0])
        await ctx.send(choice[1])

    @snackset.command()
    async def deliver(self, ctx):
        """Asks snackburr to start delivering to this channel"""
        deliver_channels = await self.config.guild(ctx.guild).DELIVER_CHANNELS()
        if not deliver_channels:
            deliver_channels = []
        if ctx.channel.id not in deliver_channels:
            deliver_channels.append(ctx.channel.id)
            await self.config.guild(ctx.guild).DELIVER_CHANNELS.set(deliver_channels)
            await ctx.send("snackburr will start delivering here!")
        else:
            deliver_channels.remove(ctx.channel.id)
            await self.config.guild(ctx.guild).DELIVER_CHANNELS.set(deliver_channels)
            await ctx.send("snackburr will stop delivering here!")

    @commands.guild_only()
    @commands.command()
    async def snacktime(self, ctx):
        """Man i'm hungry! When's snackburr gonna get back with more snacks?"""
        scid = f"{ctx.message.guild.id}-{ctx.message.channel.id}"
        if self.snacktimePrediction.get(scid, None) == None:
            if self.acceptInput.get(scid, False):
                return
            else:
                phrases = [
                    r"Don't look at me. I donno where snackburr's at ¯\_(ツ)_/¯",
                    "I hear snackburr likes parties. *wink wink",
                    "I hear snackburr is attracted to channels with active conversations",
                    "If you party, snackburr will come! 〈( ^o^)ノ",
                ]
                await ctx.send(randchoice(phrases))
            return
        seconds = self.snacktimePrediction[scid] - self.bot.loop.time()
        if self.snacktimeCheckLock.get(scid, False):
            if randint(1, 4) == 4:
                await ctx.send("Hey, snackburr's on errands. I ain't his keeper Kappa")
            return
        self.snacktimeCheckLock[scid] = True
        if seconds < 0:
            await ctx.send(f"I'm not sure where snackburr is.. He's already {round(abs(seconds/60), 2)} minutes late!")
        else:
            await ctx.send(f"snackburr's out on errands! I think he'll be back in {round(seconds/60, 2)} minutes")
        await asyncio.sleep(40)
        self.snacktimeCheckLock[scid] = False

    async def startSnack(self, message):
        scid = f"{message.guild.id}-{message.channel.id}"
        if self.acceptInput.get(scid, False):
            return
        self.channel_persona[scid] = await self.persona_choice(ctx=None, message=message)
        await message.channel.send(await self.get_response(message, "SNACKTIME"))

        self.acceptInput[scid] = True
        self.alreadySnacked[scid] = []

        guild_data = await self.config.guild(message.guild).all()

        duration = guild_data["SNACK_DURATION"] + randint(
            -guild_data["SNACK_DURATION_VARIANCE"], guild_data["SNACK_DURATION_VARIANCE"]
        )
        await asyncio.sleep(duration)
        # sometimes fails sending messages and stops all future snacktimes. Hopefully this fixes it.
        try:
            # list isn't empty
            if self.alreadySnacked.get(scid, False):
                await message.channel.send(await self.get_response(message, "OUT"))
                await self.config.channel(message.channel).repeatMissedSnacktimes.set(0)
            else:
                await message.channel.send(await self.get_response(message, "NO_TAKERS"))
                repeat_missed_snacktimes = await self.config.channel(message.channel).repeatMissedSnacktimes()
                await self.config.channel(message.channel).repeatMissedSnacktimes.set(repeat_missed_snacktimes + 1)
                await asyncio.sleep(2)
                if (repeat_missed_snacktimes + 1) > 9:  # move to a setting
                    await message.channel.send(await self.get_response(message, "LONELY"))
                    deliver_channels = await self.config.guild(message.guild).DELIVER_CHANNELS()
                    new_deliver_channels = deliver_channels.remove(message.channel.id)
                    await self.config.guild(message.guild).DELIVER_CHANNELS.set(new_deliver_channels)
                    await self.config.channel(message.channel).repeatMissedSnacktimes.set(0)
        except:
            log.error("Snacktime: Failed to send message in startSnack")
        self.acceptInput[scid] = False
        self.snackInProgress[scid] = False

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if message.author.bot:
            return
        if not message.channel.permissions_for(message.guild.me).send_messages:
            return

        deliver_channels = await self.config.guild(message.guild).DELIVER_CHANNELS()
        if not deliver_channels:
            return
        if message.channel.id not in deliver_channels:
            return
        scid = f"{message.guild.id}-{message.channel.id}"
        if message.author.id != self.bot.user.id:
            # if nobody has said anything since start
            if self.previousSpeaker.get(scid, None) == None:
                self.previousSpeaker[scid] = message.author.id
            # if new speaker
            elif self.previousSpeaker[scid] != message.author.id:
                self.previousSpeaker[scid] = message.author.id
                msgTime = self.bot.loop.time()
                # if there's a scheduled snack
                if self.snackSchedule.get(scid, None) != None:
                    # if it's time for a snack
                    if msgTime > self.snackSchedule[scid]:
                        # 1 schedule at a time, so remove schedule
                        self.snackSchedule[scid] = None
                        self.snackInProgress[scid] = True

                        # wait to make it more natural
                        naturalWait = randint(30, 240)
                        log.debug(f"Snacktime: snack trigger msg: {message.content}")
                        log.debug(f"Snacktime: Waiting {str(naturalWait)} seconds")
                        await asyncio.sleep(naturalWait)
                        # start snacktime
                        await self.startSnack(message)
                # if no snack coming, schedule one
                elif self.snackInProgress.get(scid, False) == False and not self.startLock.get(scid, False):
                    self.msgsPassed[scid] = self.msgsPassed.get(scid, 0) + 1
                    # check for collisions
                    msgs_before_event = await self.config.guild(message.guild).MSGS_BEFORE_EVENT()
                    if self.msgsPassed[scid] > msgs_before_event:
                        self.startLock[scid] = True
                        if self.lockRequests.get(scid, None) == None:
                            self.lockRequests[scid] = []
                        self.lockRequests[scid].append(message)
                        await asyncio.sleep(1)
                        log.debug(
                            f"Snacktime: :-+-|||||-+-: Lock request: {str(self.lockRequests[scid][0] == message)}"
                        )
                        if self.lockRequests[scid][0] == message:
                            await asyncio.sleep(5)
                            log.debug(f"Snacktime: {message.author.name} - I got the Lock")
                            self.lockRequests[scid] = []
                            # someone got through already
                            if self.msgsPassed[scid] < msgs_before_event or self.snackInProgress.get(scid, False):
                                log.debug("Snacktime: Lock: someone got through already.")
                                return
                            else:
                                log.debug(
                                    "Snacktime: Lock: looks like i'm in the clear. lifting lock. If someone comes now, they should get the lock"
                                )
                                self.msgsPassed[scid] = msgs_before_event
                                self.startLock[scid] = False
                        else:
                            log.debug(f"Snacktime: {message.author.name} Failed lock")
                            return
                    if self.msgsPassed[scid] == msgs_before_event:
                        # schedule a snack
                        log.debug(f"Snacktime: activity: {message.content}")
                        guild_data = await self.config.guild(message.guild).all()
                        timeTillSnack = guild_data["EVENT_START_DELAY"] + randint(
                            -guild_data["EVENT_START_DELAY_VARIANCE"], guild_data["EVENT_START_DELAY_VARIANCE"],
                        )
                        log.debug(f"Snacktime: {str(timeTillSnack)} seconds till snacktime")
                        self.snacktimePrediction[scid] = msgTime + guild_data["EVENT_START_DELAY"]
                        self.snackSchedule[scid] = msgTime + timeTillSnack
                        self.msgsPassed[scid] = 0

            # it's snacktime! who want's snacks?
            if self.acceptInput.get(scid, False):
                if message.author.id not in self.alreadySnacked.get(scid, []):
                    agree_phrases = [
                        "holds out hand",
                        "im ready",
                        "i'm ready",
                        "hit me up",
                        "hand over",
                        "hand me",
                        "kindly",
                        "i want",
                        "i'll have",
                        "ill have",
                        "yes",
                        "pls",
                        "plz",
                        "please",
                        "por favor",
                        "can i",
                        "i'd like",
                        "i would",
                        "may i",
                        "in my mouth",
                        "in my belly",
                        "snack me",
                        "gimme",
                        "give me",
                        "i'll take",
                        "ill take",
                        "i am",
                        "about me",
                        "me too",
                        "of course",
                    ]
                    userWants = False
                    for agreePhrase in agree_phrases:
                        # no one word answers
                        if agreePhrase in message.content.lower() and len(message.content.split()) > 1:
                            userWants = True
                            break
                    if userWants:
                        if self.alreadySnacked.get(scid, None) == None:
                            self.alreadySnacked[scid] = []
                        self.alreadySnacked[scid].append(message.author.id)
                        await asyncio.sleep(randint(1, 6))
                        snack_amount = await self.config.guild(message.guild).SNACK_AMOUNT()
                        snackAmt = randint(1, snack_amount)
                        try:
                            if self.acceptInput.get(scid, False):
                                resp = await self.get_response(message, "GIVE")
                                resp = resp.format(message.author.name, snackAmt)
                                await message.channel.send(resp)
                            else:
                                resp = await self.get_response(message, "LAST_SECOND")
                                resp = resp.format(message.author.name, snackAmt)
                                await message.channel.send(resp)
                            try:
                                await bank.deposit_credits(message.author, snackAmt)
                            except BalanceTooHigh as b:
                                await bank.set_balance(message.author, b.max_balance)
                        except Exception as e:
                            log.info(
                                f"Failed to send pb message. {message.author.name} didn't get pb\n", exc_info=True,
                            )

                else:
                    more_phrases = [
                        "more pl",
                        "i have some more",
                        "i want more",
                        "i have another",
                        "i have more",
                        "more snack",
                    ]
                    userWants = False
                    for morePhrase in more_phrases:
                        if morePhrase in message.content.lower():
                            userWants = True
                            break
                    if userWants:
                        await asyncio.sleep(randint(1, 6))
                        if self.acceptInput.get(scid, False):
                            resp = await self.get_response(message, "GREEDY")
                            await message.channel.send(resp.format(message.author.name))
