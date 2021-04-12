import aiohttp
import asyncio
import datetime
import discord
import html
import logging
import math
import random
import time

from redbot.core import bank, checks, commands, Config
from redbot.core.errors import BalanceTooHigh
from redbot.core.utils.chat_formatting import box


log = logging.getLogger("red.aikaterna.quiz")


def check_global_setting_admin():
    """
    Command decorator. If the bank is not global, it checks if the author is
    either a bot admin or has the manage_guild permission.
    """

    async def pred(ctx: commands.Context):
        author = ctx.author
        if not await bank.is_global():
            if not isinstance(ctx.channel, discord.abc.GuildChannel):
                return False
            if await ctx.bot.is_owner(author):
                return True
            if author == ctx.guild.owner:
                return True
            if ctx.channel.permissions_for(author).manage_guild:
                return True
            admin_role_ids = await ctx.bot.get_admin_role_ids(ctx.guild.id)
            for role in author.roles:
                if role.id in admin_role_ids:
                    return True
        else:
            return await ctx.bot.is_owner(author)

    return commands.check(pred)


class Quiz(commands.Cog):
    """
    Play a kahoot-like trivia game with questions from Open Trivia Database.
    Originally by Keane for Red v2
    """

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    def __init__(self, bot):
        self.bot = bot

        self.game_tasks = []
        self.playing_channels = {}
        self.session = aiohttp.ClientSession()
        self.starter_task = self.bot.loop.create_task(self.start_loop())

        self.config = Config.get_conf(self, 2782511001, force_registration=True)
        default_guild = {
            "afk": 3,
            "multiplier": 100,
            "questions": 20,
            "show_answer": True,
            "token": None,
        }
        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @commands.group()
    async def quiz(self, ctx):
        """Play a kahoot-like trivia game.
        Questions from the Open Trivia Database.

        In this game, you will compete with other players to correctly answer each
        question as quickly as you can. You have 10 seconds to type the answer
        choice before time runs out. The longer you take to say the right answer,
        the fewer points you get. If you get it wrong, you get no points. Only the
        first valid answer (A, B, C, or D) will be recorded - be sure of the
        answer before replying!

        To end the game, stop responding to the questions and the game will time out.
        """
        pass

    @quiz.command(name="play")
    async def quiz_play(self, ctx, *, category_name_or_id=None):
        """
        Create or join a quiz game.
        Specify a category name or ID number, otherwise it will be random.
        Use [p]quiz categories to list category names or id numbers.
        """
        channel = ctx.message.channel
        player = ctx.message.author

        if not category_name_or_id:
            # random
            category_id = await self.category_selector()
            category_name = await self.category_name_from_id(category_id)

        elif category_name_or_id.isdigit():
            # cat id specified
            if 9 <= int(category_name_or_id) >= 32:
                return await ctx.send(f"Invalid category number. Use `{ctx.prefix}quiz categories` to see a list.")
            category_id = category_name_or_id
            try:
                category_name = await self.category_name_from_id(int(category_name_or_id))
            except RuntimeError:
                return await ctx.send(f"Invalid category ID. Use `{ctx.prefix}quiz categories` to see a list.")
        else:
            # cat name specified
            try:
                category_name = await self.category_name_match(category_name_or_id)
            except RuntimeError:
                return await ctx.send(f"Invalid category name. Use `{ctx.prefix}quiz categories` to see a list.")
            category_id = await self.category_id_from_name(category_name)

        if channel.id not in self.playing_channels:
            self.playing_channels[channel.id] = {
                "Start": datetime.datetime.utcnow(),
                "Started": False,
                "Players": {player.id: 0},
                "Answers": {},
                "Category": str(category_name),
                "CategoryID": int(category_id),
            }
            return await ctx.send(
                f"{player.display_name} is starting a quiz game!\n"
                f"Category: `{category_name}`\n"
                f"It will start in 30 seconds. Use `{ctx.prefix}quiz play` to join."
            )

        channelinfo = self.playing_channels[channel.id]
        if player.id in channelinfo["Players"]:
            await ctx.send("You are already in the game.")
        elif channelinfo["Started"]:
            await ctx.send("A quiz game is already underway.")
        else:
            channelinfo["Players"][player.id] = 0
            await ctx.send(f"{player.display_name} joined the game.")

    @quiz.command(name="categories")
    async def quiz_cat(self, ctx):
        """List quiz categories."""
        async with self.session.get("https://opentdb.com/api_category.php") as response:
            response_json = await response.json()
            msg = f"[Category Name]{' ' * 24}[ID]\n"
            for cat_dict in response_json["trivia_categories"]:
                padding = 40 - len(cat_dict["name"])
                msg += f"{cat_dict['name']}{' ' * padding}{cat_dict['id']}\n"
        embed = discord.Embed(description=box(msg, lang="ini"))
        await ctx.send(embed=embed)

    @commands.guild_only()
    @commands.group()
    @checks.mod_or_permissions(manage_guild=True)
    async def quizset(self, ctx):
        """Quiz settings."""
        if ctx.invoked_subcommand is None:
            guild_data = await self.config.guild(ctx.guild).all()
            msg = (
                f"[Quiz Settings for {ctx.guild.name}]\n"
                f"AFK questions before end: {guild_data['afk']}\n"
                f"Credit multiplier:        {guild_data['multiplier']}x\n"
                f"Number of questions:      {guild_data['questions']}\n"
                f"Reveal correct answer:    {guild_data['show_answer']}\n"
            )
            await ctx.send(box(msg, lang="ini"))

    @quizset.command(name="afk")
    async def quizset_afk(self, ctx, questions: int):
        """Set number of questions before the game ends due to non-answers."""
        if 1 <= questions <= 10:
            await self.config.guild(ctx.guild).afk.set(questions)
            plural = "" if int(questions) == 1 else "s"
            return await ctx.send(
                f"{questions} question{plural} will be asked before the game times out. "
                "A question will be counted in this afk count if 0 or 1 person answers. "
                "2 or more answers on a question will not trigger this counter."
            )
        await ctx.send("Please use a number between 1 and 10. The default is 3.")

    @quizset.command(name="show")
    async def quizset_show(self, ctx):
        """Toggle revealing the answers."""
        show = await self.config.guild(ctx.guild).show_answer()
        await self.config.guild(ctx.guild).show_answer.set(not show)
        await ctx.send(f"Question answers will be revealed during the game: {not show}")

    @quizset.command(name="questions")
    async def quizset_questions(self, ctx, questions: int):
        """Set number of questions per game."""
        if 5 <= questions <= 50:
            await self.config.guild(ctx.guild).questions.set(questions)
            return await ctx.send(f"Number of questions per game: {questions}")
        await ctx.send("Please use a number between 5 and 50. The default is 20.")

    @check_global_setting_admin()
    @quizset.command(name="multiplier")
    async def quizset_multiplier(self, ctx, multiplier: int):
        """
        Set the credit multiplier.
        The accepted range is 0 - 10000.
        0 will turn credit gain off.
        Credit gain will be based on the number of questions set and user speed.
        1x = A small amount of credits like 1-10.
        100x = A handful of credits: 100-500.
        10000x = Quite a lot of credits, around 10k to 50k.
		"""
        if 0 <= multiplier <= 10000:
            await self.config.guild(ctx.guild).multiplier.set(multiplier)
            credits_name = await bank.get_currency_name(ctx.guild)
            return await ctx.send(f"Credit multipilier: `{multiplier}x`")
        await ctx.send("Please use a number between 0 and 10000. The default is 100.")

    async def start_loop(self):
        """Starts quiz games when the timeout period ends."""
        try:
            while True:
                for channelid in list(self.playing_channels):
                    channelinfo = self.playing_channels[channelid]
                    since_start = (datetime.datetime.utcnow() - channelinfo["Start"]).total_seconds()

                    if since_start > 30 and not channelinfo["Started"]:
                        channel = self.bot.get_channel(channelid)
                        if len(channelinfo["Players"]) > 1:
                            channelinfo["Started"] = True
                            task = self.bot.loop.create_task(self.game(channel))
                            self.game_tasks.append(task)
                        else:
                            await channel.send("Nobody else joined the quiz game.")
                            self.playing_channels.pop(channelid)
                await asyncio.sleep(2)
        except Exception:
            log.error("Error in Quiz start loop.", exc_info=True)

    async def game(self, channel):
        """Runs a quiz game on a channel."""
        channelinfo = self.playing_channels[channel.id]
        category = channelinfo["CategoryID"]
        category_name = channelinfo["Category"]

        try:
            response = await self.get_questions(channel.guild, category=channelinfo["CategoryID"])
        except RuntimeError:
            await channel.send("An error occurred in retrieving questions. Please try again.")
            self.playing_channels.pop(channel.id)
            raise

        # Introduction
        intro = (
            f"Welcome to the quiz game! Your category is `{category_name}`.\n"
            "Remember to answer correctly as quickly as you can for more points.\n"
            "You have 10 seconds per question: the timer is shown in reactions on each question.\n"
            "The game will begin shortly."
        )
        await channel.send(intro)
        await asyncio.sleep(4)

        # Question and Answer
        afk_questions = 0
        for index, dictionary in enumerate(response["results"]):
            answers = [dictionary["correct_answer"]] + dictionary["incorrect_answers"]

            # Display question and countdown
            if len(answers) == 2:  # true/false question
                answers = ["True", "False", "", ""]
            else:
                answers = [html.unescape(answer) for answer in answers]
                random.shuffle(answers)

            message = ""
            message += html.unescape(dictionary["question"]) + "\n"
            message += f"A. {answers[0]}\n"
            message += f"B. {answers[1]}\n"
            message += f"C. {answers[2]}\n"
            message += f"D. {answers[3]}\n"

            message_obj = await channel.send(box(message))
            await message_obj.add_reaction("0⃣")
            channelinfo["Answers"].clear()  # clear the previous question's answers
            start_time = time.perf_counter()

            numbers = ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣", "🔟"]
            for i in range(10):
                if len(channelinfo["Answers"]) == len(channelinfo["Players"]):
                    break
                await asyncio.sleep(1)
                await message_obj.add_reaction(numbers[i])

            # Organize answers
            user_answers = channelinfo["Answers"]
            # snapshot channelinfo["Answers"] at this point in time
            # to ignore new answers that are added to it
            answerdict = {["a", "b", "c", "d"][num]: answers[num] for num in range(4)}

            # Check for AFK
            if len(user_answers) < 2:
                afk_questions += 1
                afk_count = await self.config.guild(channel.guild).afk()
                if afk_questions == int(afk_count):
                    await channel.send("The game has been cancelled due to lack of participation.")
                    self.playing_channels.pop(channel.id)
                    return
            else:
                afk_questions = 0

            # Find and display correct answer
            correct_letter = ""
            for letter, answer in answerdict.items():
                if answer == html.unescape(dictionary["correct_answer"]):
                    correct_letter = letter
                    break
            assert answerdict[correct_letter] == html.unescape(dictionary["correct_answer"])

            if await self.config.guild(channel.guild).show_answer():
                message = f"Correct answer:```{correct_letter.upper()}. {answerdict[correct_letter]}```"
                await channel.send(message)

            # Assign scores
            for playerid in user_answers:
                if user_answers[playerid]["Choice"] == correct_letter:
                    time_taken = user_answers[playerid]["Time"] - start_time
                    assert time_taken > 0
                    if time_taken < 1:
                        channelinfo["Players"][playerid] += 1000
                    else:
                        # the 20 in the formula below is 2 * 10s (max answer time)
                        channelinfo["Players"][playerid] += round(1000 * (1 - (time_taken / 20)))

            # Display top 5 players and their points
            message = self.scoreboard(channel)
            await channel.send("Scoreboard:\n" + message)
            await asyncio.sleep(4)

            questions = await self.config.guild(channel.guild).questions()
            if index < (int(questions) - 1):
                await channel.send("Next question...")
                await asyncio.sleep(1)

        await self.end_game(channel)

    async def end_game(self, channel):
        """Ends a quiz game."""
        # non-linear credit earning .0002x^{2.9} where x is score/100
        channelinfo = self.playing_channels[channel.id]
        idlist = sorted(list(channelinfo["Players"]), key=(lambda idnum: channelinfo["Players"][idnum]), reverse=True,)

        winner = channel.guild.get_member(idlist[0])
        await channel.send(f"Game over! {winner.mention} won!")

        multiplier = await self.config.guild(channel.guild).multiplier()
        if multiplier == 0:
            self.playing_channels.pop(channel.id)
            return

        leaderboard = "\n"
        max_credits = self.calculate_credits(channelinfo["Players"][idlist[0]])
        end_len = len(str(max_credits)) + 1
        rank_len = len(str(len(channelinfo["Players"])))
        rank = 1

        for playerid in idlist:
            player = channel.guild.get_member(playerid)

            if len(player.display_name) > 25 - rank_len - end_len:
                name = player.display_name[: 22 - rank_len - end_len] + "..."
            else:
                name = player.display_name

            leaderboard += str(rank)
            leaderboard += " " * (1 + rank_len - len(str(rank)))
            leaderboard += name
            creds = self.calculate_credits(channelinfo["Players"][playerid]) * int(multiplier)
            creds_str = str(creds)
            leaderboard += " " * (26 - rank_len - 1 - len(name) - len(creds_str))
            leaderboard += creds_str + "\n"

            try:
                await bank.deposit_credits(player, creds)
            except BalanceTooHigh as e:
                await bank.set_balance(player, e.max_balance)

            rank += 1

        await channel.send("Credits earned:\n" + box(leaderboard, lang="py"))
        self.playing_channels.pop(channel.id)

    def scoreboard(self, channel):
        """Returns a scoreboard string to be sent to the text channel."""
        channelinfo = self.playing_channels[channel.id]
        scoreboard = "\n"
        idlist = sorted(list(channelinfo["Players"]), key=(lambda idnum: channelinfo["Players"][idnum]), reverse=True,)
        max_score = channelinfo["Players"][idlist[0]]
        end_len = len(str(max_score)) + 1
        rank = 1
        for playerid in idlist[:5]:
            player = channel.guild.get_member(playerid)
            if len(player.display_name) > 24 - end_len:
                name = player.display_name[: 21 - end_len] + "..."
            else:
                name = player.display_name
            scoreboard += str(rank) + " " + name
            score_str = str(channelinfo["Players"][playerid])
            scoreboard += " " * (24 - len(name) - len(score_str))
            scoreboard += score_str + "\n"
            rank += 1
        return box(scoreboard, lang="py")

    def calculate_credits(self, score):
        """Calculates credits earned from a score."""
        adjusted = score / 100
        if adjusted < 156.591:
            result = 0.0002 * (adjusted ** 2.9)
        else:
            result = (0.6625 * math.exp(0.0411 * adjusted)) + 50
        return round(result)

    @commands.Cog.listener()
    async def on_message_without_command(self, message):
        if not message.guild:
            return
        authorid = message.author.id
        channelid = message.channel.id
        choice = message.content.lower()
        if channelid in self.playing_channels:
            channelinfo = self.playing_channels[channelid]
            if (
                authorid in channelinfo["Players"]
                and authorid not in channelinfo["Answers"]
                and choice in {"a", "b", "c", "d"}
            ):
                channelinfo["Answers"][authorid] = {"Choice": choice, "Time": time.perf_counter()}

    # OpenTriviaDB API functions
    async def get_questions(self, server, category=None, difficulty=None):
        """Gets questions, resetting a token or getting a new one if necessary."""
        questions = await self.config.guild(server).questions()
        parameters = {"amount": questions}
        if category:
            parameters["category"] = category
        if difficulty:
            parameters["difficulty"] = difficulty
        for _ in range(3):
            parameters["token"] = await self.get_token(server)
            async with self.session.get("https://opentdb.com/api.php", params=parameters) as response:
                response_json = await response.json()
                response_code = response_json["response_code"]
                if response_code == 0:
                    return response_json
                elif response_code == 1:
                    raise RuntimeError("Question retrieval unsuccessful. Response code from OTDB: 1")
                elif response_code == 2:
                    raise RuntimeError("Question retrieval unsuccessful. Response code from OTDB: 2")
                elif response_code == 3:
                    # Token expired. Obtain new one.
                    log.debug("Quiz: Response code from OTDB: 3")
                    await self.config.guild(server).token.set(None)
                elif response_code == 4:
                    # Token empty. Reset it.
                    log.debug("Quiz: Response code from OTDB: 4")
                    await self.reset_token(server)
        raise RuntimeError("Failed to retrieve questions.")

    async def get_token(self, server):
        """Gets the provided server's token, or generates
        and saves one if one doesn't exist."""
        token = await self.config.guild(server).token()
        if not token:
            async with self.session.get("https://opentdb.com/api_token.php", params={"command": "request"}) as response:
                response_json = await response.json()
                token = response_json["token"]
                await self.config.guild(server).token.set(token)
        return token

    async def reset_token(self, server):
        """Resets the provided server's token."""
        token = await self.config.guild(server).token()
        async with self.session.get(
            "https://opentdb.com/api_token.php", params={"command": "reset", "token": token}
        ) as response:
            response_code = (await response.json())["response_code"]
            if response_code != 0:
                raise RuntimeError(f"Token reset was unsuccessful. Response code from OTDB: {response_code}")

    async def category_selector(self):
        """Chooses a random category that has enough questions."""
        for _ in range(10):
            category = random.randint(9, 32)
            async with self.session.get("https://opentdb.com/api_count.php", params={"category": category}) as response:
                response_json = await response.json()
                assert response_json["category_id"] == category
                if response_json["category_question_count"]["total_question_count"] > 39:
                    return category
        raise RuntimeError("Failed to select a category.")

    async def category_name_from_id(self, idnum):
        """Finds a category's name from its number."""
        async with self.session.get("https://opentdb.com/api_category.php") as response:
            response_json = await response.json()
            for cat_dict in response_json["trivia_categories"]:
                if cat_dict["id"] == idnum:
                    return cat_dict["name"]
        raise RuntimeError("Failed to find category's name.")

    async def category_name_match(self, name):
        """Check if a category name exists."""
        async with self.session.get("https://opentdb.com/api_category.php") as response:
            response_json = await response.json()
            for cat_dict in response_json["trivia_categories"]:
                if cat_dict["name"].lower() == name.lower():
                    return cat_dict["name"]
        raise RuntimeError("Failed to find category's name.")

    async def category_id_from_name(self, name):
        """Finds a category's name from its number."""
        async with self.session.get("https://opentdb.com/api_category.php") as response:
            response_json = await response.json()
            for cat_dict in response_json["trivia_categories"]:
                if cat_dict["name"] == name:
                    return cat_dict["id"]
        raise RuntimeError("Failed to find category's id.")

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self.starter_task.cancel()
        for task in self.game_tasks:
            task.cancel()
