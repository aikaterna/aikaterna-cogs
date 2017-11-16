from __main__ import send_cmd_help
from .utils.dataIO import dataIO
from discord.ext import commands
from .utils import checks
import datetime
import asyncio
import discord
import random
import time
import os

# TODO
# Show error when timing intervals are the same


class Hunting:
    def __init__(self, bot):
        self.bot = bot
        self.scores = dataIO.load_json('data/hunting/scores.json')
        self.subscriptions = dataIO.load_json('data/hunting/subscriptions.json')
        self.settings = dataIO.load_json('data/hunting/settings.json')
        self.animals = {'duck': ':duck: **_Quack!_**', 'penguin': ':penguin: **_Noot!_**', 'chicken': ':rooster: **_Bah-gawk!_**', 'pigeon': ':dove: **_Coo!_**'}
        self.in_game = []
        self.paused_games = []
        self._latest_message_check_message_limit = 5
        self._latest_message_check_wait_limit = self.settings['hunt_interval_maximum'] * 2
        self.next = None

    async def _save_scores(self):
        dataIO.save_json('data/hunting/scores.json', self.scores)

    async def _save_subscriptions(self):
        dataIO.save_json('data/hunting/subscriptions.json', self.subscriptions)

    async def _save_settings(self):
        dataIO.save_json('data/hunting/settings.json', self.settings)

    @commands.group(pass_context=True, no_pm=True, name='hunting')
    async def _hunting(self, context):
        """Hunting, it hunts birds... and things that fly"""
        if context.invoked_subcommand is None:
            await send_cmd_help(context)

    @_hunting.command(pass_context=True, no_pm=True, name='start')
    async def _start(self, context):
        """Start the hunt"""
        server = context.message.server
        channel = context.message.channel
        if server.id in self.subscriptions:
            message = '**We\'re already hunting!**'
        else:
            self.subscriptions[server.id] = channel.id
            message = '**The hunt has started. Good luck to all.**'
            await self._save_subscriptions()
        await self.bot.say(message)

    @_hunting.command(pass_context=True, no_pm=True, name='stop')
    async def _stop(self, context):
        """Stop the hunt"""
        server = context.message.server
        if server.id not in self.subscriptions:
            message = '**We\'re not hunting!**'
        else:
            del self.subscriptions[server.id]
            message = '**The hunt has stopped.**'
            await self._save_subscriptions()
        await self.bot.say(message)

    @_hunting.command(no_pm=True, name='timing')
    @checks.is_owner()
    async def _timing(self, interval_min: int, interval_max: int, bang_timeout: int):
        """Change the timing"""
        if interval_min > interval_max:
            message = '**`interval_min` needs to be lower than `interval_max`**'
        elif interval_min < 0 and interval_max < 0 and bang_timeout < 0:
            message = '**Please no negative numbers!**'
        elif interval_min == interval_max:
            message = '**`interval_min` and `interval_max` cannot be the same**'
        else:
            self.settings['hunt_interval_minimum'] = interval_min
            self.settings['hunt_interval_maximum'] = interval_max
            self.settings['wait_for_bang_timeout'] = bang_timeout
            await self._save_settings()
            message = '**Timing has been set.**'
        await self.bot.say(message)

    @_hunting.command(pass_context=True, no_pm=True, name='next')
    @checks.is_owner()
    async def _next(self, context):
        """When will the next occurance happen?"""
        if self.next:
            time = abs(datetime.datetime.utcnow() - self.next)
            total_seconds = int(time.total_seconds())
            hours, remainder = divmod(total_seconds, 60*60)
            minutes, seconds = divmod(remainder, 60)
            message = '**The next occurance will be in {} hours and {} minutes.**'.format(hours, minutes)
        else:
            message = '**There is currently no hunt.**'
        await self.bot.say(message)

    @_hunting.command(pass_context=True, no_pm=True, name='score')
    async def _score(self, context, member: discord.Member):
        """This will show the score of a hunter"""
        server = context.message.server
        if server.id in self.scores:
            if member.id in self.scores[server.id]:
                message = '**{} shot a total of {} animals ({})**'.format(member.mention, self.scores[server.id][member.id]['total'], ', '.join([str(self.scores[server.id][member.id]['score'][x]) + ' ' + x.capitalize() + 's' for x in self.scores[server.id][member.id]['score']]))  # (', '.join([str(self.scores[server.id][member.id]['score'][x]) + ' ' + x.capitalize() + 's' for x in self.scores[server.id][member.id]['score']]))
            else:
                message = '**Please shoot something before you can brag about it.**'
        else:
            message = '**Please shoot something before you can brag about it.**'
        await self.bot.say(message)

    @_hunting.command(pass_context=True, no_pm=True, name='clearscore')
    @checks.serverowner()
    async def _clearscore(self, context):
        """Clear the leaderboard"""
        server = context.message.server
        if server.id in self.scores:
            self.scores[server.id] = {}
            await self._save_scores()
            message = 'Leaderboard is cleared'
        else:
            message = 'There\'s nothing to clear'
        await self.bot.say(message)

    @_hunting.command(pass_context=True, no_pm=True, name='leaderboard', aliases=['scores'])
    async def _huntingboard(self, context):
        """This will show the top hunters on this server"""
        server = context.message.server
        if server.id in self.scores:
            p = self.scores[server.id]
            scores = sorted(p, key=lambda x: (p[x]['total']), reverse=True)
            message = '```\n{:<4}{:<8}{}\n\n'.format('#', 'TOTAL', 'USERNAME')
            for i, hunter in enumerate(scores, 1):
                if i > 10:
                    break
                message += '{:<4}{:<8}{} ({})\n'.format(i, p[hunter]['total'], p[hunter]['author_name'], ', '.join([str(p[hunter]['score'][x]) + ' ' + x.capitalize() + 's' for x in p[hunter]['score']]))
            message += '```'
        else:
            message = '**Please shoot something before you can brag about it.**'
        await self.bot.say(message)

    async def add_score(self, server, author, avian):
        if server.id not in self.scores:
            self.scores[server.id] = {}
        if author.id not in self.scores[server.id]:
            self.scores[server.id][author.id] = {}
            self.scores[server.id][author.id]['score'] = {}
            self.scores[server.id][author.id]['total'] = 0
            self.scores[server.id][author.id]['author_name'] = ''
            for a in list(self.animals.keys()):
                self.scores[server.id][author.id]['score'][a] = 0
        if avian not in self.scores[server.id][author.id]['score']:
            self.scores[server.id][author.id]['score'][avian] = 0
        self.scores[server.id][author.id]['author_name'] = author.display_name
        self.scores[server.id][author.id]['score'][avian] += 1
        self.scores[server.id][author.id]['total'] += 1
        await self._save_scores()

    async def _wait_for_bang(self, server, channel):
        def check(message):
            return message.content.lower().split(' ')[0] == 'bang' or message.content.lower() == 'b' if message.content else False

        animal = random.choice(list(self.animals.keys()))
        await self.bot.send_message(channel, self.animals[animal])
        message = await self.bot.wait_for_message(channel=channel, timeout=self.settings['wait_for_bang_timeout'], check=check)
        if message:
            author = message.author
            if random.randrange(0, 17) > 1:
                await self.add_score(server, author, animal)
                msg = '**{} shot a {}!**'.format(author.mention, animal)
            else:
                msg = '**{} missed the shot and the {} got away!**'.format(author.mention, animal)
        else:
            msg = '**The {} got away!** :confused:'.format(animal)
        self.in_game.remove(channel.id)
        await self.bot.send_message(channel, msg)

    async def _latest_message_check(self, channel):
        async for message in self.bot.logs_from(channel, limit=self._latest_message_check_message_limit, reverse=True):
            delta = datetime.datetime.utcnow() - message.timestamp
            if delta.total_seconds() < self._latest_message_check_wait_limit and message.author.id != self.bot.user.id:
                if channel.id in self.paused_games:
                    self.paused_games.remove(channel.id)
                return True
        if channel.id not in self.paused_games:
            self.paused_games.append(channel.id)
            await self.bot.send_message(channel, '**It seems there are no hunters here. The hunt will be resumed when someone treads here again.**')
        return False

    async def _hunting_loop(self):
        while self == self.bot.get_cog('Hunting'):
            wait_time = random.randrange(self.settings['hunt_interval_minimum'], self.settings['hunt_interval_maximum'])
            self.next = datetime.datetime.fromtimestamp(int(time.mktime(datetime.datetime.utcnow().timetuple())) + wait_time)
            await asyncio.sleep(wait_time)
            for server in self.subscriptions:
                if self.subscriptions[server] not in self.in_game:
                    channel = self.bot.get_channel(self.subscriptions[server])
                    server = self.bot.get_server(server)
                    if await self._latest_message_check(channel):
                        self.in_game.append(self.subscriptions[server.id])
                        self.bot.loop = asyncio.get_event_loop()
                        self.bot.loop.create_task(self._wait_for_bang(server, channel))


def check_folder():
    if not os.path.exists('data/hunting'):
        print('Creating data/hunting folder...')
        os.makedirs('data/hunting')


def check_files():
    f = 'data/hunting/settings.json'
    if not dataIO.is_valid_json(f):
        print('Creating empty settings.json...')
        data = {}
        data['hunt_interval_minimum'] = 300
        data['hunt_interval_maximum'] = 600
        data['wait_for_bang_timeout'] = 30
        dataIO.save_json(f, data)

    f = 'data/hunting/subscriptions.json'
    if not dataIO.is_valid_json(f):
        print('Creating empty subscriptions.json...')
        dataIO.save_json(f, {})

    f = 'data/hunting/scores.json'
    if not dataIO.is_valid_json(f):
        print('Creating empty scores.json...')
        dataIO.save_json(f, {})


def setup(bot):
    check_folder()
    check_files()
    cog = Hunting(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(cog._hunting_loop())
    bot.add_cog(cog)
