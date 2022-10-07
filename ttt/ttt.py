# Ported from https://github.com/hizkifw/discord-tictactoe
# This cog is licensed under Apache-2.0, which is bundled with the cog file under LICENSE.

import discord
import logging
from redbot.core import commands


log = logging.getLogger("red.aikaterna.ttt")


class TTT(commands.Cog):
    """
    Tic Tac Toe
    """

    def __init__(self, bot):
        self.bot = bot
        self.ttt_games = {}

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    @commands.guild_only()
    @commands.bot_has_permissions(add_reactions=True)
    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.command()
    async def ttt(self, ctx, move=""):
        """ Tic Tac Toe """
        await self.ttt_new(ctx.author, ctx.channel)

    async def ttt_new(self, user, channel):
        self.ttt_games[user.id] = [" "] * 9
        response = self._make_board(user)
        response += "Your move:"
        msg = await channel.send(response)
        await self._make_buttons(msg)

    async def ttt_move(self, user, message, move):
        log.debug(f"ttt_move:{user.id}")
        # Check user currently playing
        if user.id not in self.ttt_games:
            log.debug("New ttt game")
            return await self.ttt_new(user, message.channel)

        # Check spot is empty
        if self.ttt_games[user.id][move] == " ":
            self.ttt_games[user.id][move] = "x"
            log.debug(f"Moved to {move}")
        else:
            log.debug(f"Invalid move: {move}")
            return None

        # Check winner
        check = self._do_checks(self.ttt_games[user.id])
        if check is not None:
            msg = "It's a draw!" if check == "draw" else f"{check[-1]} wins!"
            log.debug(msg)
            await message.edit(content=f"{self._make_board(user)}{msg}")
            return None
        log.debug("Check passed")

        # AI move
        mv = self._ai_think(self._matrix(self.ttt_games[user.id]))
        self.ttt_games[user.id][self._coords_to_index(mv)] = "o"
        log.debug("AI moved")

        # Update board
        await message.edit(content=self._make_board(user))
        log.debug("Board updated")

        # Check winner again
        check = self._do_checks(self.ttt_games[user.id])
        if check is not None:
            msg = "It's a draw!" if check == "draw" else f"{check[-1]} wins!"
            log.debug(msg)
            await message.edit(content=f"{self._make_board(user)}{msg}")
        log.debug("Check passed")

    def _make_board(self, author):
        return f"{author.mention}\n{self._table(self.ttt_games[author.id])}\n"

    async def _make_buttons(self, msg):
        await msg.add_reaction("\u2196")  # 0 tl
        await msg.add_reaction("\u2B06")  # 1 t
        await msg.add_reaction("\u2197")  # 2 tr
        await msg.add_reaction("\u2B05")  # 3 l
        await msg.add_reaction("\u23FA")  # 4 mid
        await msg.add_reaction("\u27A1")  # 5 r
        await msg.add_reaction("\u2199")  # 6 bl
        await msg.add_reaction("\u2B07")  # 7 b
        await msg.add_reaction("\u2198")  # 8 br

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if reaction.message.guild is None:
            return
        if reaction.message.author != self.bot.user:
            return
        game_session = self.ttt_games.get(user.id, None)
        if game_session is None:
            return
        move = self._decode_move(str(reaction.emoji))
        if move is None:
            return
        await self.ttt_move(user, reaction.message, move)

    @staticmethod
    def _decode_move(emoji):
        dict = {
            "\u2196": 0,
            "\u2B06": 1,
            "\u2197": 2,
            "\u2B05": 3,
            "\u23FA": 4,
            "\u27A1": 5,
            "\u2199": 6,
            "\u2B07": 7,
            "\u2198": 8,
        }
        return dict[emoji] if emoji in dict else None

    @staticmethod
    def _table(xo):
        return (
            (("%s%s%s\n" * 3) % tuple(xo))
            .replace("o", ":o2:")
            .replace("x", ":regional_indicator_x:")
            .replace(" ", ":white_large_square:")
        )

    @staticmethod
    def _matrix(b):
        return [[b[0], b[1], b[2]], [b[3], b[4], b[5]], [b[6], b[7], b[8]]]

    @staticmethod
    def _coords_to_index(coords):
        map = {(0, 0): 0, (0, 1): 1, (0, 2): 2, (1, 0): 3, (1, 1): 4, (1, 2): 5, (2, 0): 6, (2, 1): 7, (2, 2): 8}
        return map[coords]

    def _do_checks(self, b):
        m = self._matrix(b)
        if self._check_win(m, "x"):
            return "win X"
        if self._check_win(m, "o"):
            return "win O"
        if self._check_draw(b):
            return "draw"
        return None

    # The following comes from an old project
    # https://gist.github.com/HizkiFW/0aadefb73e71794fb4a2802708db5bcf
    @staticmethod
    def _find_streaks(m, xo):
        row = [0, 0, 0]
        col = [0, 0, 0]
        dia = [0, 0]

        # Check rows and columns for X streaks
        for y in range(3):
            for x in range(3):
                if m[y][x] == xo:
                    row[y] += 1
                    col[x] += 1

        # Check diagonals
        if m[0][0] == xo:
            dia[0] += 1
        if m[1][1] == xo:
            dia[0] += 1
            dia[1] += 1
        if m[2][2] == xo:
            dia[0] += 1
        if m[2][0] == xo:
            dia[1] += 1
        if m[0][2] == xo:
            dia[1] += 1

        return (row, col, dia)

    @staticmethod
    def _find_empty(matrix, rcd, n):
        # Rows
        if rcd == "r":
            for x in range(3):
                if matrix[n][x] == " ":
                    return x
        # Columns
        if rcd == "c":
            for x in range(3):
                if matrix[x][n] == " ":
                    return x
        # Diagonals
        if rcd == "d":
            if n == 0:
                for x in range(3):
                    if matrix[x][x] == " ":
                        return x
            else:
                for x in range(3):
                    if matrix[x][2 - x] == " ":
                        return x

        return False

    def _check_win(self, m, xo):
        row, col, dia = self._find_streaks(m, xo)
        dia.append(0)

        for i in range(3):
            if row[i] == 3 or col[i] == 3 or dia[i] == 3:
                return True

        return False

    @staticmethod
    def _check_draw(board):
        return not " " in board

    def _ai_think(self, m):
        rx, cx, dx = self._find_streaks(m, "x")
        ro, co, do = self._find_streaks(m, "o")

        mv = self._ai_move(2, m, ro, co, do)
        if mv is not False:
            return mv
        mv = self._ai_move(2, m, rx, cx, dx)
        if mv is not False:
            return mv
        mv = self._ai_move(1, m, ro, co, do)
        if mv is not False:
            return mv
        return self._ai_move(1, m, rx, cx, dx)

    def _ai_move(self, n, m, row, col, dia):
        for r in range(3):
            if row[r] == n:
                x = self._find_empty(m, "r", r)
                if x is not False:
                    return (r, x)
            if col[r] == n:
                y = self._find_empty(m, "c", r)
                if y is not False:
                    return (y, r)

        if dia[0] == n:
            y = self._find_empty(m, "d", 0)
            if y is not False:
                return (y, y)
        if dia[1] == n:
            y = self._find_empty(m, "d", 1)
            if y is not False:
                return (y, 2 - y)

        return False
