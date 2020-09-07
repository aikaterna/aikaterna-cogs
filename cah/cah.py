import asyncio
import discord
import html
import json
import random
import time
from random import shuffle
from redbot.core import commands
from redbot.core.data_manager import bundled_data_path


class CardsAgainstHumanity(commands.Cog):
    """Play Cards Against Humanity in DMs."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot
        self.games = []
        self.maxBots = 5  # Max number of bots that can be added to a game - don't count toward max players
        self.maxPlayers = 10  # Max players for ranjom joins
        self.maxDeadTime = 3600  # Allow an hour of dead time before killing a game
        self.checkTime = 300  # 5 minutes between dead time checks
        self.winAfter = 10  # 10 wins for the game
        self.botWaitMin = 5  # Minimum number of seconds before the bot makes a decision (default 5)
        self.botWaitMax = 30  # Max number of seconds before a bot makes a decision (default 30)
        self.userTimeout = 500  # 5 minutes to timeout
        self.utCheck = 30  # Check timeout every 30 seconds
        self.utWarn = 60  # Warn the user if they have 60 seconds or less before being kicked
        self.charset = "1234567890"
        self.botName = "Rando Cardrissian"
        self.minMembers = 3

        self.bot.loop.create_task(self.checkDead())
        self.bot.loop.create_task(self.checkUserTimeout())

    def cleanJson(self, json):
        json = html.unescape(json)
        # Clean out html formatting
        json = json.replace("_", "[blank]")
        json = json.replace("<br>", "\n")
        json = json.replace("<br/>", "\n")
        json = json.replace("<i>", "*")
        json = json.replace("</i>", "*")
        return json

    def displayname(self, member: discord.Member):
        # A helper function to return the member's display name
        nick = name = None
        try:
            nick = member.nick
        except AttributeError:
            pass
        try:
            name = member.name
        except AttributeError:
            pass
        if nick:
            return nick
        if name:
            return name
        return None

    def memberforname(self, name, server):
        # Check nick first - then name
        for member in server.members:
            if member.nick:
                if member.nick.lower() == name.lower():
                    return member
        for member in server.members:
            if member.name.lower() == name.lower():
                return member
        # No member yet - try ID
        memID = "".join(list(filter(str.isdigit, name)))
        newMem = self.memberforid(memID, server)
        if newMem:
            return newMem
        return None

    @staticmethod
    def memberforid(checkid, server):
        for member in server.members:
            if str(member.id) == str(checkid):
                return member
        return None

    def getreadabletimebetween(self, first, last):
        # A helper function to make a readable string between two times
        timeBetween = int(last - first)
        weeks = int(timeBetween / 604800)
        days = int((timeBetween - (weeks * 604800)) / 86400)
        hours = int((timeBetween - (days * 86400 + weeks * 604800)) / 3600)
        minutes = int((timeBetween - (hours * 3600 + days * 86400 + weeks * 604800)) / 60)
        seconds = int(timeBetween - (minutes * 60 + hours * 3600 + days * 86400 + weeks * 604800))
        msg = ""

        if weeks > 0:
            if weeks == 1:
                msg = f"{msg}{str(weeks)} week, "
            else:
                msg = f"{msg}{str(weeks)} weeks, "
        if days > 0:
            if days == 1:
                msg = f"{msg}{str(days)} day, "
            else:
                msg = f"{msg}{str(days)} days, "
        if hours > 0:
            if hours == 1:
                msg = f"{msg}{str(hours)} hour, "
            else:
                msg = f"{msg}{str(hours)} hours, "
        if minutes > 0:
            if minutes == 1:
                msg = f"{msg}{str(minutes)} minute, "
            else:
                msg = f"{msg}{str(minutes)} minutes, "
        if seconds > 0:
            if seconds == 1:
                msg = f"{msg}{str(seconds)} second, "
            else:
                msg = f"{msg}{str(seconds)} seconds, "

        if not msg:
            return "0 seconds"
        else:
            return msg[:-2]

    async def checkUserTimeout(self):
        while True:
            # Wait first - then check
            await asyncio.sleep(self.utCheck)
            for game in self.games:
                if not game["Timeout"]:
                    continue
                if len(game["Members"]) >= self.minMembers:
                    # Game is started
                    for member in game["Members"]:
                        if member["IsBot"]:
                            continue
                        if game["Judging"]:
                            if not member == game["Members"][game["Judge"]]:
                                # Not the judge - don't hold against the user
                                member["Time"] = int(time.time())
                                continue
                        else:
                            # Not judging
                            if member == game["Members"][game["Judge"]]:
                                # The judge - don't hold that against them
                                member["Time"] = int(time.time())
                                continue
                        currentTime = int(time.time())
                        userTime = member["Time"]
                        downTime = currentTime - userTime
                        # Check if downTime results in a kick
                        if downTime >= self.userTimeout:
                            # You gettin kicked, son.
                            await self.removeMember(member["User"])
                            self.checkGame(game)
                            continue
                        # Check if downTime is in warning time
                        if downTime >= (self.userTimeout - self.utWarn):
                            # Check if we're at warning phase
                            if self.userTimeout - downTime >= (self.utWarn - self.utCheck):
                                kickTime = self.userTimeout - downTime
                                if kickTime % self.utCheck:
                                    # Kick time isn't exact time - round out to the next loop
                                    kickTime = kickTime - (kickTime % self.utCheck) + self.utCheck
                                # Warning time!
                                timeString = self.getreadabletimebetween(0, kickTime)
                                await self.sendToUser(
                                    member["User"],
                                    f"**WARNING** - You will be kicked from the game if you do not make a move in *{timeString}!*",
                                )
                else:
                    for member in game["Members"]:
                        # Reset timer
                        member["Time"] = int(time.time())

    async def checkDead(self):
        while True:
            # Wait first - then check
            await asyncio.sleep(self.checkTime)
            for game in self.games:
                gameTime = game["Time"]
                currentTime = int(time.time())
                timeRemain = currentTime - gameTime
                if timeRemain > self.maxDeadTime:
                    # Game is dead - quit it and alert members
                    for member in game["Members"]:
                        if member["IsBot"]:
                            # Clear pending tasks and set to None
                            if not member["Task"] == None:
                                task = member["Task"]
                                if not task.done():
                                    task.cancel()
                                member["Task"] = None
                            continue
                        await self.sendToUser(
                            member["User"], f"Game id: *{game['ID']}* has been closed due to inactivity.",
                        )

                    # Set running to false
                    game["Running"] = False
                    self.games.remove(game)

    async def checkPM(self, message):
        # Checks if we're talking in PM, and if not - outputs an error
        if isinstance(message.channel, discord.abc.PrivateChannel):
            # PM
            return True
        else:
            # Not in PM
            await message.channel.send("Cards Against Humanity commands must be run in Direct Messages with the bot.")
            return False

    def randomID(self, length=8):
        # Create a random id that doesn't already exist
        while True:
            # Repeat until found
            newID = "".join(random.choice(self.charset) for i in range(length))
            exists = False
            for game in self.games:
                if game["ID"] == newID:
                    exists = True
                    break
            if not exists:
                break
        return newID

    def randomBotID(self, game, length=4):
        # Returns a random id for a bot that doesn't already exist
        while True:
            # Repeat until found
            newID = "".join(random.choice(self.charset) for i in range(length))
            exists = False
            for member in game["Members"]:
                if member["ID"] == newID:
                    exists = True
                    break
            if not exists:
                break
        return newID

    async def userGame(self, user):
        # Returns the game the user is currently in
        if not len(str(user)) == 4:
            if not type(user) is int:
                # Assume it's a discord.Member/User
                user = user.id

        for game in self.games:
            for member in game["Members"]:
                if member["ID"] == user:
                    # Found our user
                    return game
        return None

    def gameForID(self, id):
        # Returns the game with the passed id
        for game in self.games:
            if game["ID"] == id:
                return game
        return None

    async def removeMember(self, user, game=None):
        if not len(str(user)) == 4:
            if not type(user) is int:
                # Assume it's a discord.Member/User
                user = user.id
        outcome = False
        removed = None
        if not game:
            game = await self.userGame(user)
        if game:
            for member in game["Members"]:
                if member["ID"] == user:
                    removed = member
                    outcome = True
                    judgeChanged = False
                    # Reset judging flag to retrigger actions
                    game["Judging"] = False
                    # Get current Judge - only if game has started
                    if len(game["Members"]) >= self.minMembers:
                        judge = game["Members"][game["Judge"]]
                        game["Members"].remove(member)
                        # Check if we're removing the current judge
                        if judge == member:
                            # Judge will change
                            judgeChanged = True
                            # Find out if our member was the last in line
                            if game["Judge"] >= len(game["Members"]):
                                game["Judge"] = 0
                            # Reset judge var
                            judge = game["Members"][game["Judge"]]
                        else:
                            # Judge didn't change - so let's reset judge index
                            index = game["Members"].index(judge)
                            game["Judge"] = index
                    else:
                        judge = None
                        # Just remove the member
                        game["Members"].remove(member)

                    if member["Creator"]:
                        # We're losing the game creator - pick a new one
                        for newCreator in game["Members"]:
                            if not newCreator["IsBot"]:
                                newCreator["Creator"] = True
                                await self.sendToUser(
                                    newCreator["User"], "The creator of this game left.  **YOU** are now the creator.",
                                )
                                break

                    # Remove submissions
                    for sub in game["Submitted"]:
                        # Remove deleted member and new judge's submissions
                        if sub["By"] == member or sub["By"] == judge:
                            # Found it!
                            game["Submitted"].remove(sub)
                            break
                    if member["IsBot"]:
                        if not member["Task"] == None:
                            task = member["Task"]
                            if not task.done():
                                task.cancel()
                            member["Task"] = None
                    else:
                        await self.sendToUser(
                            member["User"], f"**You were removed from game id:** ***{game['ID']}.***",
                        )
                    # Removed, no need to finish the loop
                    break
        if not outcome:
            return outcome
        # We removed someone - let's tell the world
        for member in game["Members"]:
            if member["IsBot"]:
                continue
            if removed["IsBot"]:
                msg = f"***{self.botName} ({removed['ID']})*** **left the game - reorganizing...**"
            else:
                msg = f"***{self.displayname(removed['User'])}*** **left the game - reorganizing...**"
            # Check if the judge changed
            if judgeChanged:
                # Judge changed
                newJudge = game["Members"][game["Judge"]]
                if newJudge["IsBot"]:
                    msg += f"\n\n***{self.botName} ({newJudge['ID']})*** **is now judging!**"
                    # Schedule judging task
                else:
                    if newJudge == member:
                        msg += "\n\n***YOU*** **are now judging!**"
                    else:
                        msg += f"\n\n***{newJudge['User']}*** **is now judging!**"

            await self.sendToUser(member["User"], msg)
        return game

    def checkGame(self, game):
        for member in game["Members"]:
            if not member["IsBot"]:
                return True
        # If we got here - only bots, or empty game
        # Kill all bots' loops
        for member in game["Members"]:
            if member["IsBot"]:
                # Clear pending tasks and set to None
                if not member["Task"] == None:
                    task = member["Task"]
                    if not task.done():
                        task.cancel()
                    member["Task"] = None
        # Set running to false
        game["Running"] = False
        self.games.remove(game)
        return False

    async def typing(self, game, typeTime=5):
        # Allows us to show the bot typing
        waitTime = random.randint(self.botWaitMin, self.botWaitMax)
        preType = waitTime - typeTime
        if preType > 0:
            await asyncio.sleep(preType)
            for member in game["Members"]:
                if member["IsBot"]:
                    continue
                await asyncio.sleep(0.1)
            await asyncio.sleep(typeTime)
        else:
            for member in game["Members"]:
                if member["IsBot"]:
                    continue
                await asyncio.sleep(0.1)
            await asyncio.sleep(waitTime)

    async def botPick(self, ctx, bot, game):
        # Has the bot pick their card
        blackNum = game["BlackCard"]["Pick"]
        if blackNum == 1:
            cardSpeak = "card"
        else:
            cardSpeak = "cards"
        i = 0
        cards = []
        while i < blackNum:
            randCard = random.randint(0, len(bot["Hand"]) - 1)
            cards.append(bot["Hand"].pop(randCard)["Text"])
            i += 1

        await self.typing(game)

        # Make sure we haven't laid any cards
        if bot["Laid"] == False and game["Judging"] == False:
            newSubmission = {"By": bot, "Cards": cards}
            game["Submitted"].append(newSubmission)
            # Shuffle cards
            shuffle(game["Submitted"])
            bot["Laid"] = True
            game["Time"] = currentTime = int(time.time())
            await self.checkSubmissions(ctx, game, bot)

    async def botPickWin(self, ctx, game):
        totalUsers = len(game["Members"]) - 1
        submitted = len(game["Submitted"])
        if submitted >= totalUsers:
            # Judge is a bot - and all cards are in!
            await self.typing(game)
            # Pick a winner
            winner = random.randint(0, totalUsers - 1)
            await self.winningCard(ctx, game, winner)

    async def checkSubmissions(self, ctx, game, user=None):
        totalUsers = len(game["Members"]) - 1
        submitted = len(game["Submitted"])
        for member in game["Members"]:
            msg = ""
            # Is the game running?
            if len(game["Members"]) < self.minMembers:
                if member["IsBot"]:
                    # Clear pending tasks and set to None
                    if not member["Task"] == None:
                        task = member["Task"]
                        if not task.done():
                            # Task isn't finished - we're on a new hand, cancel it
                            task.cancel()
                        member["Task"] = None
                    continue
                # not enough members - send the embed
                stat_embed = discord.Embed(color=discord.Color.red())
                stat_embed.set_author(
                    name=f"Not enough players to continue! ({len(game['Members'])}/{self.minMembers})"
                )
                prefix = await self.bot.get_valid_prefixes()
                stat_embed.set_footer(text=f"Have other users join with: {prefix[0]}joincah {game['ID']}")
                await self.sendToUser(member["User"], stat_embed, True)
                continue
            if member["IsBot"] == True:
                continue
            # Check if we have a user
            if user:
                blackNum = game["BlackCard"]["Pick"]
                if blackNum == 1:
                    card = "card"
                else:
                    card = "cards"
                if user["IsBot"]:
                    msg = f"*{self.botName} ({user['ID']})* submitted their {card}! "
                else:
                    if not member == user:
                        # Don't say this to the submitting user
                        msg = f"*{self.displayname(user['User'])}* submitted their {card}! "
            if submitted < totalUsers:
                msg += f"{submitted}/{totalUsers} cards submitted..."
            if len(msg):
                # We have something to say
                await self.sendToUser(member["User"], msg)

    async def checkCards(self, ctx, game):
        while True:
            if not game["Running"]:
                break
            # wait for 1 second
            await asyncio.sleep(1)
            # Check for all cards
            if len(game["Members"]) < self.minMembers:
                # Not enough members
                continue
            # Enough members - let's check if we're judging
            if game["Judging"]:
                continue
            # Enough members, and not judging - let's check cards
            totalUsers = len(game["Members"]) - 1
            submitted = len(game["Submitted"])
            if submitted >= totalUsers:
                game["Judging"] = True
                # We have enough cards
                for member in game["Members"]:
                    if member["IsBot"]:
                        continue
                    msg = "All cards have been submitted!"
                    # if
                    await self.sendToUser(member["User"], msg)
                    await self.showOptions(ctx, member["User"])

                # Check if a bot is the judge
                judge = game["Members"][game["Judge"]]
                if not judge["IsBot"]:
                    continue
                # task = self.bot.loop.create_task(self.botPickWin(ctx, game))
                task = asyncio.ensure_future(self.botPickWin(ctx, game))
                judge["Task"] = task

    async def winningCard(self, ctx, game, card):
        # Let's pick our card and alert everyone
        winner = game["Submitted"][card]
        if winner["By"]["IsBot"]:
            winnerName = f"{self.botName} ({winner['By']['ID']})"
            winner["By"]["Points"] += 1
            winner["By"]["Won"].append(game["BlackCard"]["Text"])
        else:
            winnerName = self.displayname(winner["By"]["User"])
        for member in game["Members"]:
            if member["IsBot"]:
                continue
            stat_embed = discord.Embed(color=discord.Color.gold())
            stat_embed.set_footer(text=f"Cards Against Humanity - id: {game['ID']}")
            index = game["Members"].index(member)
            if index == game["Judge"]:
                stat_embed.set_author(name=f"You picked {winnerName}'s card!")
            elif member == winner["By"]:
                stat_embed.set_author(name="YOU WON!!")
                member["Points"] += 1
                member["Won"].append(game["BlackCard"]["Text"])
            else:
                stat_embed.set_author(name=f"{winnerName} won!")
            if len(winner["Cards"]) == 1:
                msg = "The **Winning** card was:\n\n{}".format("{}".format(" - ".join(winner["Cards"])))
            else:
                msg = "The **Winning** cards were:\n\n{}".format("{}".format(" - ".join(winner["Cards"])))
            await self.sendToUser(member["User"], stat_embed, True)
            await self.sendToUser(member["User"], msg)
            await asyncio.sleep(0.1)

            # await self.nextPlay(ctx, game)

        # Start the game loop
        event = game["NextHand"]
        self.bot.loop.call_soon_threadsafe(event.set)
        game["Time"] = currentTime = int(time.time())

    async def gameCheckLoop(self, ctx, game):
        task = game["NextHand"]
        while True:
            if not game["Running"]:
                break
            # Clear the pending task
            task.clear()
            # Queue up the next hand
            await self.nextPlay(ctx, game)
            # Wait until our next clear
            await task.wait()

    async def messagePlayers(self, ctx, message, game, judge=False):
        # Messages all the users on in a game
        for member in game["Members"]:
            if member["IsBot"]:
                continue
            # Not bots
            if member is game["Members"][game["Judge"]]:
                # Is the judge
                if judge:
                    await self.sendToUser(member["User"], message)
            else:
                # Not the judge
                await self.sendToUser(member["User"], message)

    async def sendToUser(self, user, message, embed_bool=False):
        try:
            if embed_bool:
                await user.send(embed=message)
            else:
                await user.send(message)
        except discord.errors.Forbidden:
            pass

    ################################################

    async def showPlay(self, ctx, user):
        # Creates an embed and displays the current game stats
        stat_embed = discord.Embed(color=discord.Color.blue())
        game = await self.userGame(user)
        if not game:
            return
        # Get the judge's name
        if game["Members"][game["Judge"]]["User"] == user:
            judge = "**YOU** are"
        else:
            if game["Members"][game["Judge"]]["IsBot"]:
                # Bot
                judge = f"*{self.botName} ({game['Members'][game['Judge']]['ID']})* is"
            else:
                judge = f"*{self.displayname(game['Members'][game['Judge']]['User'])}* is"

        # Get the Black Card
        try:
            blackCard = game["BlackCard"]["Text"]
            blackNum = game["BlackCard"]["Pick"]
        except Exception:
            blackCard = "None."
            blackNum = 0

        msg = f"{judge} the judge.\n\n"
        msg += f"__Black Card:__\n\n**{blackCard}**\n\n"

        totalUsers = len(game["Members"]) - 1
        submitted = len(game["Submitted"])
        if len(game["Members"]) >= self.minMembers:
            if submitted < totalUsers:
                msg += f"{submitted}/{totalUsers} cards submitted..."
            else:
                msg += "All cards have been submitted!"
                await self.showOptions(ctx, user)
                return
        if not judge == "**YOU** are":
            # Judge doesn't need to lay a card
            prefix = await self.bot.get_valid_prefixes()
            if blackNum == 1:
                # Singular
                msg += f"\n\nLay a card with `{prefix[0]}lay [card number]`"
            elif blackNum > 1:
                # Plural
                msg += f"\n\nLay **{blackNum} cards** with `{prefix[0]}lay [card numbers separated by commas (1,2,3)]`"

        stat_embed.set_author(name="Current Play")
        stat_embed.set_footer(text=f"Cards Against Humanity - id: {game['ID']}")
        await self.sendToUser(user, stat_embed, True)
        await self.sendToUser(user, msg)

    async def showHand(self, ctx, user):
        # Shows the user's hand in an embed
        stat_embed = discord.Embed(color=discord.Color.green())
        game = await self.userGame(user)
        if not game:
            return
        i = 0
        msg = ""
        points = "? points"
        for member in game["Members"]:
            if member["ID"] == user.id:
                # Got our user
                if member["Points"] == 1:
                    points = "1 point"
                else:
                    points = f"{member['Points']} points"
                for card in member["Hand"]:
                    i += 1
                    msg += f"{i}. {card['Text']}\n"

        try:
            blackCard = f"**{game['BlackCard']['Text']}**"
        except Exception:
            blackCard = "**None.**"
        stat_embed.set_author(name=f"Your Hand - {points}")
        stat_embed.set_footer(text=f"Cards Against Humanity - id: {game['ID']}")
        await self.sendToUser(user, stat_embed, True)
        await self.sendToUser(user, msg)

    async def showOptions(self, ctx, user):
        # Shows the judgement options
        stat_embed = discord.Embed(color=discord.Color.orange())
        game = await self.userGame(user)
        if not game:
            return
        # Add title
        stat_embed.set_author(name="JUDGEMENT TIME!!")
        stat_embed.set_footer(text=f"Cards Against Humanity - id: {game['ID']}")
        await self.sendToUser(user, stat_embed, True)

        if game["Members"][game["Judge"]]["User"] == user:
            judge = "**YOU** are"
        else:
            if game["Members"][game["Judge"]]["IsBot"]:
                # Bot
                judge = f"*{self.botName} ({game['Members'][game['Judge']]['ID']})* is"
            else:
                judge = f"*{self.displayname(game['Members'][game['Judge']]['User'])}* is"
        blackCard = game["BlackCard"]["Text"]

        msg = f"{judge} judging.\n\n"
        msg += f"__Black Card:__\n\n**{blackCard}**\n\n"
        msg += "__Submitted White Cards:__\n\n"

        i = 0
        for sub in game["Submitted"]:
            i += 1
            msg += "{}. {}\n".format(i, " - ".join(sub["Cards"]))
        if judge == "**YOU** are":
            prefix = await self.bot.get_valid_prefixes()
            msg += f"\nPick a winner with `{prefix[0]}pick [submission number]`."
        await self.sendToUser(user, msg)

    async def drawCard(self, game):
        with open(str(bundled_data_path(self)) + "/deck.json", "r") as deck_file:
            deck = json.load(deck_file)
        # Draws a random unused card and shuffles the deck if needed
        totalDiscard = len(game["Discard"])
        for member in game["Members"]:
            totalDiscard += len(member["Hand"])
        if totalDiscard >= len(deck["whiteCards"]):
            # Tell everyone the cards were shuffled
            for member in game["Members"]:
                if member["IsBot"]:
                    continue
                user = member["User"]
                await self.sendToUser(user, "Shuffling white cards...")
            # Shuffle the cards
            self.shuffle(game)
        while True:
            # Random grab a unique card
            index = random.randint(0, len(deck["whiteCards"]) - 1)
            if not index in game["Discard"]:
                game["Discard"].append(index)
                text = deck["whiteCards"][index]
                text = self.cleanJson(text)
                card = {"Index": index, "Text": text}
                return card

    def shuffle(self, game):
        # Adds discards back into the deck
        game["Discard"] = []
        for member in game["Members"]:
            for card in member["Hand"]:
                game["Discard"].append(card["Index"])

    async def drawCards(self, user, cards=10):
        if not len(str(user)) == 4:
            if not type(user) is int:
                # Assume it's a discord.Member/User
                user = user.id
        # fills the user's hand up to number of cards
        game = await self.userGame(user)
        for member in game["Members"]:
            if member["ID"] == user:
                # Found our user - let's draw cards
                i = len(member["Hand"])
                while i < cards:
                    # Draw unique cards until we fill our hand
                    newCard = await self.drawCard(game)
                    member["Hand"].append(newCard)
                    i += 1

    async def drawBCard(self, game):
        with open(str(bundled_data_path(self)) + "/deck.json", "r") as deck_file:
            deck = json.load(deck_file)
        # Draws a random black card
        totalDiscard = len(game["BDiscard"])
        if totalDiscard >= len(deck["blackCards"]):
            # Tell everyone the cards were shuffled
            for member in game["Members"]:
                if member["IsBot"]:
                    continue
                user = member["User"]
                await self.sendToUser(user, "Shuffling black cards...")
            # Shuffle the cards
            game["BDiscard"] = []
        while True:
            # Random grab a unique card
            index = random.randint(0, len(deck["blackCards"]) - 1)
            if not index in game["BDiscard"]:
                game["BDiscard"].append(index)
                text = deck["blackCards"][index]["text"]
                text = self.cleanJson(text)
                game["BlackCard"] = {"Text": text, "Pick": deck["blackCards"][index]["pick"]}
                return game["BlackCard"]

    async def nextPlay(self, ctx, game):
        # Advances the game
        if len(game["Members"]) < self.minMembers:
            stat_embed = discord.Embed(color=discord.Color.red())
            stat_embed.set_author(name=f"Not enough players to continue! ({len(game['Members'])}/{self.minMembers})")
            prefix = await self.bot.get_valid_prefixes()
            stat_embed.set_footer(text=f"Have other users join with: {prefix[0]}joincah {game['ID']}")
            for member in game["Members"]:
                if member["IsBot"]:
                    continue
                await self.sendToUser(member["User"], stat_embed, True)
            return

        # Find if we have a winner
        winner = False
        stat_embed = discord.Embed(color=discord.Color.lighter_grey())
        for member in game["Members"]:
            if member["IsBot"]:
                # Clear pending tasks and set to None
                if not member["Task"] == None:
                    task = member["Task"]
                    if not task.done():
                        # Task isn't finished - we're on a new hand, cancel it
                        task.cancel()
                    member["Task"] = None
            if member["Points"] >= self.winAfter:
                # We have a winner!
                winner = True
                if member["IsBot"]:
                    stat_embed.set_author(name=f"{self.botName} ({member['ID']}) is the WINNER!!")
                else:
                    stat_embed.set_author(name=f"{self.displayname(member['User'])} is the WINNER!!")
                stat_embed.set_footer(text="Congratulations!")
                break
        if winner:
            for member in game["Members"]:
                if not member["IsBot"]:
                    await self.sendToUser(member["User"], stat_embed, True)
                # Reset all users
                member["Hand"] = []
                member["Points"] = 0
                member["Won"] = []
                member["Laid"] = False
                member["Refreshed"] = False
                return

        game["Judging"] = False
        # Clear submitted cards
        game["Submitted"] = []
        # We have enough members
        if game["Judge"] == -1:
            # First game - randomize judge
            game["Judge"] = random.randint(0, len(game["Members"]) - 1)
        else:
            game["Judge"] += 1
        # Reset the judge if out of bounds
        if game["Judge"] >= len(game["Members"]):
            game["Judge"] = 0

        # Draw the next black card
        bCard = await self.drawBCard(game)

        # Draw cards
        for member in game["Members"]:
            member["Laid"] = False
            await self.drawCards(member["ID"])

        # Show hands
        for member in game["Members"]:
            if member["IsBot"]:
                continue
            await self.showPlay(ctx, member["User"])
            index = game["Members"].index(member)
            if not index == game["Judge"]:
                await self.showHand(ctx, member["User"])
            await asyncio.sleep(0.1)

        # Have the bots lay their cards
        for member in game["Members"]:
            if not member["IsBot"]:
                continue
            if member["ID"] == game["Members"][game["Judge"]]["ID"]:
                continue
            # Not a human player, and not the judge
            # task = self.bot.loop.create_task(self.botPick(ctx, member, game))\
            task = asyncio.ensure_future(self.botPick(ctx, member, game))
            member["Task"] = task
            # await self.botPick(ctx, member, game)

    @commands.command()
    async def game(self, ctx, *, message=None):
        """Displays the game's current status."""
        if not await self.checkPM(ctx.message):
            return
        userGame = await self.userGame(ctx.author)
        if not userGame:
            prefix = await self.bot.get_valid_prefixes()
            msg = f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`."
            return await self.sendToUser(ctx.author, msg)
        await self.showPlay(ctx, ctx.author)

    @commands.command()
    async def chat(self, ctx, *, message=None):
        """Broadcasts a message to the other players in your game."""
        if not await self.checkPM(ctx.message):
            return
        userGame = await self.userGame(ctx.author)
        if not userGame:
            prefix = await self.bot.get_valid_prefixes()
            msg = f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`."
            return await self.sendToUser(ctx.author, msg)
        userGame["Time"] = int(time.time())
        if message == None:
            msg = "Ooookay, you say *nothing...*"
            return await self.sendToUser(ctx.author, msg)
        msg = f"*{ctx.author.name}* says: {message}"
        for member in userGame["Members"]:
            if member["IsBot"]:
                continue
            # Tell them all!!
            if not member["User"] == ctx.author:
                # Don't tell yourself
                await self.sendToUser(member["User"], msg)
            else:
                # Update member's time
                member["Time"] = int(time.time())
        await self.sendToUser(ctx.author, "Message sent!")

    @commands.command()
    async def lay(self, ctx, *, card=None):
        """Lays a card or cards from your hand.  If multiple cards are needed, separate them by a comma (1,2,3)."""
        if not await self.checkPM(ctx.message):
            return
        userGame = await self.userGame(ctx.author)
        prefix = await self.bot.get_valid_prefixes()
        if not userGame:
            msg = f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`."
            return await self.sendToUser(ctx.author, msg)
        userGame["Time"] = int(time.time())
        for member in userGame["Members"]:
            if member["User"] == ctx.author:
                member["Time"] = int(time.time())
                user = member
                index = userGame["Members"].index(member)
                if index == userGame["Judge"]:
                    await self.sendToUser(ctx.author, "You're the judge.  You don't get to lay cards this round.")
                    return
        for submit in userGame["Submitted"]:
            if submit["By"]["User"] == ctx.author:
                await self.sendToUser(ctx.author, "You already made your submission this round.")
                return
        if card == None:
            await self.sendToUser(ctx.author, "You need you input *something.*")
            return
        card = card.strip()
        card = card.replace(" ", "")
        # Not the judge
        if len(userGame["Members"]) < self.minMembers:
            stat_embed = discord.Embed(color=discord.Color.red())
            stat_embed.set_author(
                name=f"Not enough players to continue! ({len(userGame['Members'])}/{self.minMembers})"
            )
            stat_embed.set_footer(text=f"Have other users join with: {prefix[0]}joincah {userGame['ID']}")
            return await self.sendToUser(ctx.author, stat_embed, True)

        numberCards = userGame["BlackCard"]["Pick"]
        cards = []
        if numberCards > 1:
            cardSpeak = "cards"
            try:
                card = card.split(",")
            except Exception:
                card = []
            if not len(card) == numberCards:
                await self.sendToUser(
                    ctx.author,
                    f"You need to lay **{numberCards} cards** (no duplicates) with `{prefix[0]}lay [card numbers separated by commas (1,2,3)]`",
                )
                return await self.showHand(ctx, ctx.author)
            # Got something
            # Check for duplicates
            if not len(card) == len(set(card)):
                await self.sendToUser(
                    ctx.author,
                    f"You need to lay **{numberCards} cards** (no duplicates) with `{prefix[0]}lay [card numbers separated by commas (1,2,3)]`",
                )
                return await self.showHand(ctx, ctx.author)
            # Works
            for c in card:
                try:
                    c = int(c)
                except Exception:
                    await self.sendToUser(
                        ctx.author,
                        f"You need to lay **{numberCards} cards** (no duplicates) with `{prefix[0]}lay [card numbers separated by commas (1,2,3)]`",
                    )
                    return await self.showHand(ctx, ctx.author)
                if c < 1 or c > len(user["Hand"]):
                    await self.sendToUser(ctx.author, f"Card numbers must be between 1 and {len(user['Hand'])}.")
                    return await self.showHand(ctx, ctx.author)
                cards.append(user["Hand"][c - 1]["Text"])
            # Remove from user's hand
            card = sorted(card, key=lambda card: int(card), reverse=True)
            for c in card:
                user["Hand"].pop(int(c) - 1)
            # Valid cards

            newSubmission = {"By": user, "Cards": cards}
        else:
            cardSpeak = "card"
            try:
                card = int(card)
            except Exception:
                await self.sendToUser(ctx.author, f"You need to lay a valid card with `{prefix[0]}lay [card number]`")
                return await self.showHand(ctx, ctx.author)
            if card < 1 or card > len(user["Hand"]):
                await self.sendToUser(ctx.author, f"Card numbers must be between 1 and {len(user['Hand'])}.")
                return await self.showHand(ctx, ctx.author)
            # Valid card
            newSubmission = {"By": user, "Cards": [user["Hand"].pop(card - 1)["Text"]]}
        userGame["Submitted"].append(newSubmission)

        # Shuffle cards
        shuffle(userGame["Submitted"])

        user["Laid"] = True
        await self.sendToUser(ctx.author, f"You submitted your {cardSpeak}!")
        await self.checkSubmissions(ctx, userGame, user)

    @commands.command()
    async def pick(self, ctx, *, card=None):
        """As the judge - pick the winning card(s)."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        prefix = await self.bot.get_valid_prefixes()
        if not userGame:
            # Not in a game
            msg = f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`."
            return await self.sendToUser(ctx.author, msg)
        userGame["Time"] = int(time.time())
        isJudge = False
        for member in userGame["Members"]:
            if member["User"] == ctx.author:
                member["Time"] = int(time.time())
                user = member
                index = userGame["Members"].index(member)
                if index == userGame["Judge"]:
                    isJudge = True
        if not isJudge:
            msg = "You're not the judge - I guess you'll have to wait your turn."
            return await self.sendToUser(ctx.author, msg)
        # Am judge
        totalUsers = len(userGame["Members"]) - 1
        submitted = len(userGame["Submitted"])
        if submitted < totalUsers:
            if totalUsers - submitted == 1:
                msg = "Still waiting on 1 card..."
            else:
                msg = f"Still waiting on {totalUsers - submitted} cards..."
            await self.sendToUser(ctx.author, msg)
            return
        try:
            card = int(card) - 1
        except Exception:
            card = -1
        if card < 0 or card >= totalUsers:
            return await self.sendToUser(ctx.author, f"Your pick must be between 1 and {totalUsers}.")
        # Pick is good!
        await self.winningCard(ctx, userGame, card)

    @commands.command()
    async def hand(self, ctx):
        """Shows your hand."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if not userGame:
            # Not in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`.",
            )
        await self.showHand(ctx, ctx.author)
        userGame["Time"] = currentTime = int(time.time())

    @commands.command()
    async def newcah(self, ctx):
        """Starts a new Cards Against Humanity game."""
        try:
            embed = discord.Embed(color=discord.Color.green())
            embed.set_author(name="**Setting up the game...**")
            await ctx.author.send(embed=embed)
        except discord.errors.Forbidden:
            return await ctx.send("You must allow Direct Messages from the bot for this game to work.")

        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if userGame:
            # Already in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're already in a game (id: *{userGame['ID']}*)\nType `{prefix[0]}leavecah` to leave that game.",
            )

        # Not in a game - create a new one
        gameID = self.randomID()
        currentTime = int(time.time())
        newGame = {
            "ID": gameID,
            "Members": [],
            "Discard": [],
            "BDiscard": [],
            "Judge": -1,
            "Time": currentTime,
            "BlackCard": None,
            "Submitted": [],
            "NextHand": asyncio.Event(),
            "Judging": False,
            "Timeout": True,
        }
        member = {
            "ID": ctx.author.id,
            "User": ctx.author,
            "Points": 0,
            "Won": [],
            "Hand": [],
            "Laid": False,
            "Refreshed": False,
            "IsBot": False,
            "Creator": True,
            "Task": None,
            "Time": currentTime,
        }
        newGame["Members"].append(member)
        newGame["Running"] = True
        task = self.bot.loop.create_task(self.gameCheckLoop(ctx, newGame))
        task = self.bot.loop.create_task(self.checkCards(ctx, newGame))
        self.games.append(newGame)
        # Tell the user they created a new game and list its ID
        await ctx.send(f"You created game id: *{gameID}*")
        await self.drawCards(ctx.author)
        # await self.showHand(ctx, ctx.author)
        # await self.nextPlay(ctx, newGame)

    @commands.command()
    async def leavecah(self, ctx):
        """Leaves the current game you're in."""
        removeCheck = await self.removeMember(ctx.author)
        if not removeCheck:
            msg = "You are not in a game."
            await ctx.send(msg)
            return
        if self.checkGame(removeCheck):
            # await self.nextPlay(ctx, removeCheck)

            """# Start the game loop
            event = removeCheck['NextHand']
            self.bot.loop.call_soon_threadsafe(event.set)"""
            # Player was removed - try to handle it calmly...
            await self.checkSubmissions(ctx, removeCheck)

    @commands.command()
    async def joincah(self, ctx, *, id=None):
        """Join a Cards Against Humanity game.  If no id or user is passed, joins a random game."""
        try:
            embed = discord.Embed(color=discord.Color.green())
            embed.set_author(name="**Setting up the game...**")
            await ctx.author.send(embed=embed)
        except discord.errors.Forbidden:
            return await ctx.send("You must allow Direct Messages from the bot for this game to work.")

        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        isCreator = False
        if userGame:
            # Already in a game
            prefix = await self.bot.get_valid_prefixes()
            return await ctx.send(
                f"You're already in a game (id: *{userGame['ID']}*)\nType `{prefix[0]}leavecah` to leave that game."
            )
        if len(self.games):
            if id:
                game = self.gameForID(id)
                prefix = await self.bot.get_valid_prefixes()
                if game == None:
                    # That id doesn't exist - or is possibly a user
                    # If user, has to be joined from server chat
                    if not ctx.message.guild:
                        return await ctx.send(
                            f"I couldn't find a game attached to that id. \n"
                            f"If you are trying to join a user - run the `{prefix[0]}joincah [user]` "
                            f"command in a channel in a Discord server you share with that user.\n"
                            f"Make sure to use the proper command prefix for your server - it may or may not be `{prefix[0]}`."
                        )
                    else:
                        # We have a server - let's try for a user
                        member = self.memberforname(id, ctx.message.guild)
                        if not member:
                            # Couldn't find user!
                            return await ctx.send(
                                f"I couldn't find a game attached to that id. \n"
                                f"If you are trying to join a user - run the `{prefix[0]}joincah [user]` "
                                f"command in a channel in a Discord server you share with that user.\n"
                                f"Make sure to use the proper command prefix for your server - it may or may not be `{prefix[0]}`."
                            )
                        # Have a user - check if they're in a game
                        game = await self.userGame(member)
                        if not game:
                            # That user is NOT in a game!
                            return await ctx.send("That user doesn't appear to be playing.")

            else:
                game = random.choice(self.games)
        else:
            # No games - create a new one
            gameID = self.randomID()
            currentTime = int(time.time())
            game = {
                "ID": gameID,
                "Members": [],
                "Discard": [],
                "BDiscard": [],
                "Judge": -1,
                "Time": currentTime,
                "BlackCard": None,
                "Submitted": [],
                "NextHand": asyncio.Event(),
                "Judging": False,
                "Timeout": True,
            }
            game["Running"] = True
            task = self.bot.loop.create_task(self.gameCheckLoop(ctx, game))
            task = self.bot.loop.create_task(self.checkCards(ctx, game))
            self.games.append(game)
            # Tell the user they created a new game and list its ID
            await ctx.send(f"**You created game id:** ***{gameID}***")
            isCreator = True

        # Tell everyone else you joined
        for member in game["Members"]:
            if member["IsBot"]:
                continue
            await self.sendToUser(member["User"], f"***{self.displayname(ctx.author)}*** **joined the game!**")

        # We got a user!
        currentTime = int(time.time())
        member = {
            "ID": ctx.author.id,
            "User": ctx.author,
            "Points": 0,
            "Won": [],
            "Hand": [],
            "Laid": False,
            "Refreshed": False,
            "IsBot": False,
            "Creator": isCreator,
            "Task": None,
            "Time": currentTime,
        }
        game["Members"].append(member)
        await self.drawCards(ctx.author)
        if len(game["Members"]) == 1:
            # Just created the game
            await self.drawCards(ctx.author)
        else:
            await ctx.send(
                f"**You've joined game id:** ***{game['ID']}!***\n\nThere are *{len(game['Members'])} users* in this game."
            )

        # Check if adding put us at minimum members
        if len(game["Members"]) - 1 < self.minMembers:
            # It was - *actually* start a game
            event = game["NextHand"]
            self.bot.loop.call_soon_threadsafe(event.set)
        else:
            # It was not - just incorporate new players
            await self.checkSubmissions(ctx, game)
            # Reset judging flag to retrigger actions
            game["Judging"] = False
            # Show the user the current card and their hand
            await self.showPlay(ctx, member["User"])
            await self.showHand(ctx, member["User"])
        event = game["NextHand"]

        game["Time"] = int(time.time())

    @commands.command()
    async def joinbot(self, ctx):
        """Adds a bot to the game.  Can only be done by the player who created the game."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if not userGame:
            # Not in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`.",
            )
        botCount = 0
        for member in userGame["Members"]:
            if member["IsBot"]:
                botCount += 1
                continue
            if member["User"] == ctx.author:
                if not member["Creator"]:
                    # You didn't make this game
                    msg = "Only the player that created the game can add bots."
                    await self.sendToUser(ctx.author, msg)
                    return
                member["Time"] = int(time.time())
        # We are the creator - let's check the number of bots
        if botCount >= self.maxBots:
            # Too many bots!
            return await self.sendToUser(ctx.author, f"You already have enough bots (max is {self.maxBots}).")
        # We can get another bot!
        botID = self.randomBotID(userGame)
        lobot = {
            "ID": botID,
            "User": None,
            "Points": 0,
            "Won": [],
            "Hand": [],
            "Laid": False,
            "Refreshed": False,
            "IsBot": True,
            "Creator": False,
            "Task": None,
        }
        userGame["Members"].append(lobot)
        await self.drawCards(lobot["ID"])
        for member in userGame["Members"]:
            if member["IsBot"]:
                continue
            await self.sendToUser(member["User"], f"***{self.botName} ({botID})*** **joined the game!**")
        # await self.nextPlay(ctx, userGame)

        # Check if adding put us at minimum members
        if len(userGame["Members"]) - 1 < self.minMembers:
            # It was - *actually* start a game
            event = userGame["NextHand"]
            self.bot.loop.call_soon_threadsafe(event.set)
        else:
            # It was not - just incorporate new players
            await self.checkSubmissions(ctx, userGame)
            # Reset judging flag to retrigger actions
            userGame["Judging"] = False
            # Schedule stuff
            task = asyncio.ensure_future(self.botPick(ctx, lobot, userGame))
            lobot["Task"] = task

    @commands.command()
    async def joinbots(self, ctx, number=None):
        """Adds bots to the game.  Can only be done by the player who created the game."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if not userGame:
            # Not in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`.",
            )
        botCount = 0
        for member in userGame["Members"]:
            if member["IsBot"]:
                botCount += 1
                continue
            if member["User"] == ctx.author:
                if not member["Creator"]:
                    # You didn't make this game
                    return await self.sendToUser(ctx.author, "Only the player that created the game can add bots.")
                member["Time"] = int(time.time())
        if number == None:
            # No number specified - let's add the max number of bots
            number = self.maxBots - botCount

        try:
            number = int(number)
        except ValueError:
            return await self.sendToUser(ctx.author, "Number of bots to add must be an integer.")

        # We are the creator - let's check the number of bots
        if botCount >= self.maxBots:
            # Too many bots!
            return await self.sendToUser(ctx.author, f"You already have enough bots (max is {self.maxBots}).")

        if number > (self.maxBots - botCount):
            number = self.maxBots - botCount

        if number == 1:
            msg = f"**Adding {number} bot:**\n\n"
        else:
            msg = f"**Adding {number} bots:**\n\n"

        newBots = []
        for i in range(0, number):
            # We can get another bot!
            botID = self.randomBotID(userGame)
            lobot = {
                "ID": botID,
                "User": None,
                "Points": 0,
                "Won": [],
                "Hand": [],
                "Laid": False,
                "Refreshed": False,
                "IsBot": True,
                "Creator": False,
                "Task": None,
            }
            userGame["Members"].append(lobot)
            newBots.append(lobot)
            await self.drawCards(lobot["ID"])
            msg += f"***{self.botName} ({botID})*** **joined the game!**\n"
            # await self.nextPlay(ctx, userGame)

        for member in userGame["Members"]:
            if member["IsBot"]:
                continue
            await self.sendToUser(member["User"], msg)

        # Check if adding put us at minimum members
        if len(userGame["Members"]) - number < self.minMembers:
            # It was - *actually* start a game
            event = userGame["NextHand"]
            self.bot.loop.call_soon_threadsafe(event.set)
        else:
            # It was not - just incorporate new players
            await self.checkSubmissions(ctx, userGame)
            # Reset judging flag to retrigger actions
            game["Judging"] = False
            for bot in newBots:
                # Schedule stuff
                task = asyncio.ensure_future(self.botPick(ctx, bot, userGame))
                bot["Task"] = task

    @commands.command()
    async def removebot(self, ctx, *, id=None):
        """Removes a bot from the game.  Can only be done by the player who created the game."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if not userGame:
            # Not in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`.",
            )
        botCount = 0
        for member in userGame["Members"]:
            if member["IsBot"]:
                botCount += 1
                continue
            if member["User"] == ctx.author:
                if not member["Creator"]:
                    # You didn't make this game
                    return await self.sendToUser(ctx.author, "Only the player that created the game can remove bots.")
                member["Time"] = int(time.time())
        # We are the creator - let's check the number of bots
        if id == None:
            # Just remove the first bot we find
            for member in userGame["Members"]:
                if member["IsBot"]:
                    await self.removeMember(member["ID"])
                    """# Start the game loop
                    event = userGame['NextHand']
                    self.bot.loop.call_soon_threadsafe(event.set)"""
                    # Bot was removed - try to handle it calmly...
                    return await self.checkSubmissions(ctx, userGame)
            msg = "No bots to remove!"
            return await self.sendToUser(ctx.author, msg)
        else:
            # Remove a bot by id
            if not await self.removeMember(id):
                # not found
                prefix = await self.bot.get_valid_prefixes()
                return await self.sendToUser(
                    ctx.author,
                    f"I couldn't locate that bot on this game.  If you're trying to remove a player, try the `{prefix[0]}removeplayer [name]` command.",
                )
        # await self.nextPlay(ctx, userGame)

        """# Start the game loop
        event = userGame['NextHand']
        self.bot.loop.call_soon_threadsafe(event.set)"""
        # Bot was removed - let's try to handle it calmly...
        await self.checkSubmissions(ctx, userGame)

    @commands.command()
    async def cahgames(self, ctx):
        """Displays up to 10 CAH games in progress."""
        shuffledGames = list(self.games)
        random.shuffle(shuffledGames)
        if not len(shuffledGames):
            await ctx.send("No games being played currently.")
            return

        max = 10
        if len(shuffledGames) < 10:
            max = len(shuffledGames)
        msg = "__Current CAH Games__:\n\n"

        for i in range(0, max):
            playerCount = 0
            botCount = 0
            gameID = shuffledGames[i]["ID"]
            for j in shuffledGames[i]["Members"]:
                if j["IsBot"]:
                    botCount += 1
                else:
                    playerCount += 1
            botText = f"{botCount} bot"
            if not botCount == 1:
                botText += "s"
            playerText = f"{playerCount} player"
            if not playerCount == 1:
                playerText += "s"

            msg += f"{i + 1}. {gameID} - {playerText} | {botText}\n"

        await ctx.send(msg)

    @commands.command()
    async def score(self, ctx):
        """Display the score of the current game."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if not userGame:
            # Not in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`.",
            )
        stat_embed = discord.Embed(color=discord.Color.purple())
        stat_embed.set_author(name="Current Score")
        stat_embed.set_footer(text=f"Cards Against Humanity - id: {userGame['ID']}")
        await self.sendToUser(ctx.author, stat_embed, True)
        users = sorted(userGame["Members"], key=lambda card: int(card["Points"]), reverse=True)
        msg = ""
        i = 0
        if len(users) > 10:
            msg += f"__10 of {len(users)} Players:__\n\n"
        else:
            msg += "__Players:__\n\n"
        for user in users:
            i += 1
            if i > 10:
                break
            if user["Points"] == 1:
                if user["User"]:
                    # Person
                    msg += f"{i}. *{self.displayname(user['User'])}* - 1 point\n"
                else:
                    # Bot
                    msg += f"{i}. *{self.botName} ({user['ID']})* - 1 point\n"
            else:
                if user["User"]:
                    # Person
                    msg += f"{i}. *{self.displayname(user['User'])}* - {user['Points']} points\n"
                else:
                    # Bot
                    msg += f"{i}. *{self.botName} ({user['ID']})* - {user['Points']} points\n"
        await self.sendToUser(ctx.author, msg)

    @commands.command()
    async def laid(self, ctx):
        """Shows who laid their cards and who hasn't."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if not userGame:
            # Not in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`.",
            )
        stat_embed = discord.Embed(color=discord.Color.purple())
        stat_embed.set_author(name="Card Check")
        stat_embed.set_footer(text=f"Cards Against Humanity - id: {userGame['ID']}")
        await self.sendToUser(ctx.author, stat_embed, True)
        users = sorted(userGame["Members"], key=lambda card: int(card["Laid"]))
        msg = ""
        i = 0
        if len(users) > 10:
            msg += f"__10 of {len(users)} Players:__\n\n"
        else:
            msg += "__Players:__\n\n"
        for user in users:
            if len(userGame["Members"]) >= self.minMembers:
                if user == userGame["Members"][userGame["Judge"]]:
                    continue
            i += 1
            if i > 10:
                break

            if user["Laid"]:
                if user["User"]:
                    # Person
                    msg += f"{i}. *{self.displayname(user['User'])}* - Cards are in.\n"
                else:
                    # Bot
                    msg += f"{i}. *{self.botName} ({user['ID']})* - Cards are in.\n"
            else:
                if user["User"]:
                    # Person
                    msg += f"{i}. *{self.displayname(user['User'])}* - Waiting for cards...\n"
                else:
                    # Bot
                    msg += f"{i}. *{self.botName} ({user['ID']})* - Waiting for cards...\n"
        await self.sendToUser(ctx.author, msg)

    @commands.command()
    async def removeplayer(self, ctx, *, name=None):
        """Removes a player from the game.  Can only be done by the player who created the game."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if not userGame:
            # Not in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`.",
            )
        botCount = 0
        for member in userGame["Members"]:
            if member["IsBot"]:
                botCount += 1
                continue
            if member["User"] == ctx.author:
                if not member["Creator"]:
                    # You didn't make this game
                    return await self.sendToUser(
                        ctx.author, "Only the player that created the game can remove players."
                    )
                member["Time"] = int(time.time())
        # We are the creator - let's check the number of bots
        if name == None:
            # Nobody named!
            return await self.sendToUser(ctx.author, "Okay, I removed... no one from the game...")

        # Let's get the person either by name, or by id
        nameID = "".join(list(filter(str.isdigit, name)))
        for member in userGame["Members"]:
            toRemove = False
            if member["IsBot"]:
                continue
            if name.lower() == self.displayname(member["User"]).lower():
                # Got em!
                toRemove = True
            elif nameID == member["ID"]:
                # Got em!
                toRemove = True
            if toRemove:
                await self.removeMember(member["ID"])
                break
        # await self.nextPlay(ctx, userGame)

        if toRemove:
            """# Start the game loop
            event = userGame['NextHand']
            self.bot.loop.call_soon_threadsafe(event.set)"""
            # Player was removed - try to handle it calmly...
            await self.checkSubmissions(ctx, userGame)
        else:
            prefix = await self.bot.get_valid_prefixes()
            msg = f"I couldn't locate that player on this game.  If you're trying to remove a bot, try the `{prefix[0]}removebot [id]` command."
            await self.sendToUser(ctx.author, msg)

    @commands.command()
    async def flushhand(self, ctx):
        """Flushes the cards in your hand - can only be done once per game."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if not userGame:
            # Not in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`.",
            )
        if userGame["Judge"] == -1:
            msg = "The game hasn't started yet.  Probably not worth it to flush your hand before you get it..."
            return await self.sendToUser(ctx.author, msg)
        for member in userGame["Members"]:
            if member["IsBot"]:
                continue
            if member["User"] == ctx.author:
                member["Time"] = int(time.time())
                # Found us!
                if member["Refreshed"]:
                    # Already flushed their hand
                    msg = "You have already flushed your hand this game."
                    return await self.sendToUser(ctx.author, msg)
                else:
                    member["Hand"] = []
                    await self.drawCards(member["ID"])
                    member["Refreshed"] = True
                    await self.sendToUser(ctx.author, "Flushing your hand!")
                    await self.showHand(ctx, ctx.author)
                    return

    @commands.command()
    async def idlekick(self, ctx, *, setting=None):
        """Sets whether or not to kick members if idle for 5 minutes or more.  Can only be done by the player who created the game."""
        if not await self.checkPM(ctx.message):
            return
        # Check if the user is already in game
        userGame = await self.userGame(ctx.author)
        if not userGame:
            # Not in a game
            prefix = await self.bot.get_valid_prefixes()
            return await self.sendToUser(
                ctx.author,
                f"You're not in a game - you can create one with `{prefix[0]}newcah` or join one with `{prefix[0]}joincah`.",
            )
        botCount = 0
        for member in userGame["Members"]:
            if member["IsBot"]:
                botCount += 1
                continue
            if member["User"] == ctx.author:
                if not member["Creator"]:
                    # You didn't make this game
                    return await self.sendToUser(ctx.author, "Only the player that created the game can remove bots.")
        # We are the creator - let's check the number of bots
        if setting == None:
            # Output idle kick status
            if userGame["Timeout"]:
                await ctx.send("Idle kick is enabled.")
            else:
                await ctx.send("Idle kick is disabled.")
            return
        elif setting.lower() == "yes" or setting.lower() == "on" or setting.lower() == "true":
            setting = True
        elif setting.lower() == "no" or setting.lower() == "off" or setting.lower() == "false":
            setting = False
        else:
            setting = None

        if setting == True:
            if userGame["Timeout"] == True:
                msg = "Idle kick remains enabled."
            else:
                msg = "Idle kick now enabled."
                for member in userGame["Members"]:
                    member["Time"] = int(time.time())
        else:
            if userGame["Timeout"] == False:
                msg = "Idle kick remains disabled."
            else:
                msg = "Idle kick now disabled."
        userGame["Timeout"] = setting

        await ctx.send(msg)

    @commands.command()
    async def cahcredits(self, ctx):
        """Code credits."""
        await ctx.send(
            "```\nThis cog is made possible by CorpBot.\nPlease visit https://github.com/corpnewt/CorpBot.py for more information.\n```"
        )
