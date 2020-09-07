import asyncio
import logging
from random import randint
from redbot.core import commands
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.predicates import MessagePredicate


log = logging.getLogger("red.aikaterna.luigipoker")


class Card:
    def __init__(self, card_number=None):
        self._number = card_number if card_number else randint(1, 6)
        self._suit = self._suit()

    def _suit(self):
        if self._number == 1:
            suit = "\N{CLOUD}\N{VARIATION SELECTOR-16}"
        elif self._number == 2:
            suit = "\N{MUSHROOM}"
        elif self._number == 3:
            suit = "\N{SUNFLOWER}"
        elif self._number == 4:
            suit = "\N{LARGE GREEN SQUARE}"
        elif self._number == 5:
            suit = "\N{LARGE RED SQUARE}"
        elif self._number == 6:
            suit = "\N{WHITE MEDIUM STAR}"
        else:
            suit = "Error!"

        return suit

    def __repr__(self):
        return f"{self._suit}"

    def num(self):
        return self._number

    def suit(self):
        return self._suit


class Deck:
    def __init__(self):
        self._length = 5
        self._deck = self._create_deck()
        self.first_pair = 0
        self.second_pair = 0
        self.new_deck()

    def _create_deck(self):
        temp = [Card() for x in range(0, self._length)]
        return temp

    def _new_card(self, i):
        self._deck[i] = Card()

    def _sort_deck(self):
        self._deck.sort(key=lambda x: x.num(), reverse=True)

    def new_deck(self):
        self._deck = self._create_deck()
        self._sort_deck()

    def deck(self):
        return self._deck

    def num(self, i):
        return self._deck[i].num()

    def swap(self, i):
        for x in i:
            self._new_card(int(x) - 1)
        self._sort_deck()

    def suit(self, i):
        return self._deck[i].suit()

    def len(self):
        return self._length


class LuigiPoker(commands.Cog):
    """The Luigi Poker minigame from New Super Mario Brothers."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
        return

    __version__ = "0.1.2"

    def __init__(self, bot):
        self.bot = bot
        self._in_game = {}
        self._hit = {}
        self.player_deck = Deck()
        self.dealer_deck = Deck()

    @commands.group()
    async def poker(self, ctx):
        """The Luigi Poker minigame from New Super Mario Brothers."""
        if ctx.invoked_subcommand is None:
            space = "\N{EN SPACE}"
            msg = (
                f"I'm Luigi, Number 1!\n"
                f"This game plays the same as Luigi's "
                f"Poker in Super Mario 64 DS Minigames.\n"
                f"The card's worth is based on the suit.\n"
                f"Starman > Mario > Luigi > Fire Flower > Mushroom > Cloud.\n"
                f"{space*3}{Card(6)}{space*4}>{space*3}{Card(5)}{space*3}>{space*3}{Card(4)}{space*3}"
                f">{space*6}{Card(3)}{space*6}>{space*4}{Card(2)}{space*5}>{space*4}{Card(1)}\n"
                f"---------------------------------------------------------\n"
                f"The following table represents the winning matches.\n"
                f"For example, a Full House is greater than Three of a Kind, but "
                f"less than a Four of a Kind.\n"
                f"---------------------------------------------------------\n"
                f"Flush:           {Card(6)}{Card(6)}{Card(6)}{Card(6)}{Card(6)}\n"
                f"Four of a Kind:  {Card(6)}{Card(6)}{Card(6)}{Card(6)}\n"
                f"Full House:      {Card(6)}{Card(6)}{Card(6)}{Card(3)}{Card(3)}\n"
                f"Three of a Kind: {Card(6)}{Card(6)}{Card(6)}\n"
                f"Two Pairs:       {Card(6)}{Card(6)}{Card(2)}{Card(2)}\n"
                f"Pair:            {Card(6)}{Card(6)}\n"
            )
            await ctx.send(box(msg))
            return await ctx.send(
                f"Are you ready to play my game?! What are you waiting for? Start the game using `{ctx.prefix}poker play`!"
            )

    @poker.command()
    async def play(self, ctx):
        """Starts the Game!"""
        if not self._in_game.get(ctx.guild.id, False):
            self._in_game[ctx.guild.id] = True
            self.player_deck.new_deck()
            self.dealer_deck.new_deck()
        else:
            return await ctx.send("You're already in a game...")

        square = "\N{WHITE MEDIUM SMALL SQUARE}"
        msg = (
            f"Dealer's Deck: {square*5}\n"
            f"Your Deck:     {self.player_deck.suit(0)}{self.player_deck.suit(1)}"
            f"{self.player_deck.suit(2)}{self.player_deck.suit(3)}{self.player_deck.suit(4)}"
        )

        await ctx.send(box(msg))

        if self._hit.get(ctx.guild.id, False):
            await ctx.send("`Stay` or `fold`?")
            answers = ["stay", "fold"]
        else:
            await ctx.send("`Stay`, `hit`, or `fold`?")
            answers = ["stay", "hit", "fold"]
        await self._play_response(ctx, answers)

    async def _play_response(self, ctx, answers):
        pred = MessagePredicate.lower_contained_in(answers, ctx=ctx)
        try:
            user_resp = await ctx.bot.wait_for("message", timeout=120, check=pred)
        except asyncio.TimeoutError:
            await ctx.send("No response.")
            return await self.fold(ctx)
        if "stay" in user_resp.content.lower():
            return await self.stay(ctx)
        elif "hit" in user_resp.content.lower():
            return await self.hit(ctx)
        elif "fold" in user_resp.content.lower():
            return await self.fold(ctx)
        else:
            log.error(
                "LuigiPoker: Something broke unexpectedly in _play_response. Please report it.", exc_info=True,
            )

    async def hit(self, ctx):
        card_question = await ctx.send(
            "What cards do you want to swap out?\n"
            "Use numbers 1 through 5 to specify, with commas in between.\n"
            "Examples: `1,3,5` or `4, 5`"
        )
        try:
            user_resp = await ctx.bot.wait_for("message", timeout=60, check=MessagePredicate.same_context(ctx))
        except asyncio.TimeoutError:
            await ctx.send("No response.")
            return await self.fold(ctx)

        user_answers = user_resp.content.strip().split(",")
        user_answers_valid = list(set(user_answers) & set(["1", "2", "3", "4", "5"]))
        if len(user_answers_valid) == 0:
            return await self.hit(ctx)

        await ctx.send("Swapping Cards...")
        self.player_deck.swap(user_answers_valid)
        square = "\N{WHITE MEDIUM SMALL SQUARE}"
        msg = (
            f"Dealer's Deck: {square*5}\n"
            f"Your Deck:     {self.player_deck.suit(0)}{self.player_deck.suit(1)}"
            f"{self.player_deck.suit(2)}{self.player_deck.suit(3)}{self.player_deck.suit(4)}"
        )
        await ctx.send(box(msg))
        await ctx.send("`Stay` or `fold`?")
        self._hit[ctx.guild.id] = True
        answers = ["stay", "fold"]
        await self._play_response(ctx, answers)

    async def fold(self, ctx):
        msg = "You have folded.\n"
        msg += box(
            f"Dealer's Deck: {self.dealer_deck.suit(0)}{self.dealer_deck.suit(1)}"
            f"{self.dealer_deck.suit(2)}{self.dealer_deck.suit(3)}{self.dealer_deck.suit(4)}\n"
            f"Your Deck:     {self.player_deck.suit(0)}{self.player_deck.suit(1)}"
            f"{self.player_deck.suit(2)}{self.player_deck.suit(3)}{self.player_deck.suit(4)}"
        )

        self._in_game[ctx.guild.id] = False
        self._hit[ctx.guild.id] = False
        await ctx.send(msg)

    async def stay(self, ctx):
        say = ""
        win = False
        same_move = False
        tied = False

        # Flush
        if self.flush(self.player_deck) != self.flush(self.dealer_deck):
            say = "a Flush"
            if self.flush(self.player_deck):
                win = True
        elif self.flush(self.player_deck) and self.flush(self.dealer_deck):
            say = "Flush"
            same_move = True
            if self.player_deck.first_pair > self.dealer_deck.first_pair:
                win = True
            elif self.player_deck.first_pair == self.dealer_deck.first_pair:
                tied = True

        # Four of a Kind
        elif self.four_of_a_kind(self.player_deck) != self.four_of_a_kind(self.dealer_deck):
            say = "a Four of a Kind"
            if self.four_of_a_kind(self.player_deck):
                win = True
        elif self.four_of_a_kind(self.player_deck) and self.four_of_a_kind(self.dealer_deck):
            say = "Four of a Kind"
            same_move = True
            if self.player_deck.first_pair > self.dealer_deck.first_pair:
                win = True
            elif self.player_deck.first_pair == self.dealer_deck.first_pair:
                tied = True

        # Full House
        elif self.full_house(self.player_deck) != self.full_house(self.dealer_deck):
            say = "a Full House"
            if self.full_house(self.player_deck):
                win = True
        elif self.full_house(self.player_deck) and self.full_house(self.dealer_deck):
            say = "Full House"
            same_move = True
            if self.player_deck.first_pair > self.dealer_deck.first_pair:
                win = True
            elif self.player_deck.second_pair > self.dealer_deck.second_pair:
                win = True
            elif (
                self.player_deck.first_pair == self.dealer_deck.first_pair
                and self.player_deck.second_pair == self.dealer_deck.second_pair
            ):
                tied = True

        # Full House
        elif self.three_of_a_kind(self.player_deck) != self.three_of_a_kind(self.dealer_deck):
            say = "a Three of a Kind"
            if self.three_of_a_kind(self.player_deck):
                win = True
        elif self.three_of_a_kind(self.player_deck) and self.three_of_a_kind(self.dealer_deck):
            say = "Three of a Kind"
            same_move = True
            if self.player_deck.first_pair > self.dealer_deck.first_pair:
                win = True
            elif self.player_deck.first_pair == self.dealer_deck.first_pair:
                tied = True

        # Two Pairs
        elif self.two_pair(self.player_deck) != self.two_pair(self.dealer_deck):
            say = "Two Pairs"
            if self.two_pair(self.player_deck):
                win = True
        elif self.two_pair(self.player_deck) and self.two_pair(self.dealer_deck):
            say = "Two Pairs"
            same_move = True
            if self.player_deck.first_pair > self.dealer_deck.first_pair:
                win = True
            elif self.player_deck.second_pair > self.dealer_deck.second_pair:
                win = True
            elif (
                self.player_deck.first_pair == self.dealer_deck.first_pair
                and self.player_deck.second_pair == self.dealer_deck.second_pair
            ):
                tied = True

        # One Pair
        elif self.one_pair(self.player_deck) != self.one_pair(self.dealer_deck):
            say = "a Pair"
            if self.one_pair(self.player_deck):
                win = True
        elif self.one_pair(self.player_deck) and self.one_pair(self.dealer_deck):
            say = "Pair"
            same_move = True
            if self.player_deck.first_pair > self.dealer_deck.first_pair:
                win = True
            elif self.player_deck.first_pair == self.dealer_deck.first_pair:
                tied = True
        else:
            tied = True

        msg = "You've stayed.\n"

        if same_move:
            if win:
                msg += f"You won! Your {say} is greater than Dealer's {say}!"
            else:
                msg += f"You lost! The Dealer's {say} is greater than your {say}!"
        elif win:
            msg += f"You won! You got {say}!"
        elif tied:
            msg += "Both the Dealer and the Player have tied."
        else:
            msg += f"You lost! The Dealer got {say}."

        msg += box(
            f"Dealer's Deck: {self.dealer_deck.suit(0)}{self.dealer_deck.suit(1)}"
            f"{self.dealer_deck.suit(2)}{self.dealer_deck.suit(3)}{self.dealer_deck.suit(4)}\n"
            f"Your Deck:     {self.player_deck.suit(0)}{self.player_deck.suit(1)}"
            f"{self.player_deck.suit(2)}{self.player_deck.suit(3)}{self.player_deck.suit(4)}"
        )
        self._in_game[ctx.guild.id] = False
        self._hit[ctx.guild.id] = False
        await ctx.send(msg)

    @staticmethod
    def one_pair(deck):
        answer = False
        for x in range(0, deck.len() - 1):
            if deck.num(x) == deck.num(x + 1):
                deck.first_pair = deck.num(x)
                answer = True

        return answer

    @staticmethod
    def two_pair(deck):
        answer = False
        first_pair = 0
        second_pair = 0

        for x in range(0, deck.len() - 1):
            if deck.num(x) == deck.num(x + 1):
                if first_pair == 0:
                    first_pair = deck.num(x)
                elif first_pair != deck.num(x) and second_pair == 0:
                    second_pair = deck.num(x)

        if first_pair != 0 and second_pair != 0:
            deck.first_pair = first_pair
            deck.second_pair = second_pair
            answer = True

        return answer

    @staticmethod
    def three_of_a_kind(deck):
        answer = False
        for x in range(0, deck.len() - 2):
            if deck.num(x) == deck.num(x + 1) and deck.num(x + 1) == deck.num(x + 2):
                deck.first_pair = deck.num(x)
                answer = True

        return answer

    @staticmethod
    def full_house(deck):
        answer = False
        first_pair = 0
        second_pair = 0
        for x in range(0, deck.len() - 2):
            if deck.num(x) == deck.num(x + 1) and deck.num(x + 1) == deck.num(x + 2):
                if first_pair == 0:
                    first_pair = deck.num(x)
        for x in range(0, deck.len() - 1):
            if deck.num(x) == deck.num(x + 1):
                if first_pair != deck.num(x) and second_pair == 0:
                    second_pair = deck.num(x)

        if first_pair != 0 and second_pair != 0:
            deck.first_pair = first_pair
            deck.second_pair = second_pair
            answer = True

        return answer

    @staticmethod
    def four_of_a_kind(deck):
        answer = False
        for x in range(0, deck.len() - 3):
            if (
                deck.num(x) == deck.num(x + 1)
                and deck.num(x + 1) == deck.num(x + 2)
                and deck.num(x + 2) == deck.num(x + 3)
            ):
                deck.first_pair = deck.num(x)
                answer = True

        return answer

    @staticmethod
    def flush(deck):
        answer = False
        x = 0
        if (
            deck.num(x) == deck.num(x + 1)
            and deck.num(x + 1) == deck.num(x + 2)
            and deck.num(x + 2) == deck.num(x + 3)
            and deck.num(x + 3) == deck.num(x + 4)
        ):
            deck.first_pair = deck.num(x)
            answer = True

        return answer
