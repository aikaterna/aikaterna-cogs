from discord.ext import commands
from cogs.utils.dataIO import dataIO
import discord
import os
import asyncio
from datetime import datetime


DB_VERSION = 2


class Seen:
    '''Check when someone was last seen.'''
    def __init__(self, bot):
        self.bot = bot
        self.seen = dataIO.load_json('data/seen/seen.json')
        self.new_data = False

    async def data_writer(self):
        while self == self.bot.get_cog('Seen'):
            if self.new_data:
                dataIO.save_json('data/seen/seen.json', self.seen)
                self.new_data = False
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(30)

    @commands.command(pass_context=True, no_pm=True, name='seen')
    async def _seen(self, context, username: discord.Member):
        '''seen <@username>'''
        server = context.message.server
        author = username
        timestamp_now = context.message.timestamp
        if server.id in self.seen:
            if author.id in self.seen[server.id]:
                data = self.seen[server.id][author.id]
                timestamp_then = datetime.fromtimestamp(data['TIMESTAMP'])
                timestamp = timestamp_now - timestamp_then
                days = timestamp.days
                seconds = timestamp.seconds
                hours = seconds // 3600
                seconds = seconds - (hours * 3600)
                minutes = seconds // 60
                if sum([days, hours, minutes]) < 1:
                    ts = 'just now'
                else:
                    ts = ''
                    if days == 1:
                        ts += '{} day, '.format(days)
                    elif days > 1:
                        ts += '{} days, '.format(days)
                    if hours == 1:
                        ts += '{} hour, '.format(hours)
                    elif hours > 1:
                        ts += '{} hours, '.format(hours)
                    if minutes == 1:
                        ts += '{} minute ago'.format(minutes)
                    elif minutes > 1:
                        ts += '{} minutes ago'.format(minutes)
                em = discord.Embed(color=discord.Color.green())
                avatar = author.avatar_url if author.avatar else author.default_avatar_url
                em.set_author(name='{} was seen {}'.format(author.display_name, ts), icon_url=avatar)
                await self.bot.say(embed=em)
            else:
                message = 'I haven\'t seen {} yet.'.format(author.display_name)
                await self.bot.say('{}'.format(message))
        else:
            message = 'I haven\'t seen {} yet.'.format(author.display_name)
            await self.bot.say('{}'.format(message))

    async def on_message(self, message):
        if not message.channel.is_private and self.bot.user.id != message.author.id:
            if not any(message.content.startswith(n) for n in self.bot.settings.prefixes):
                server = message.server
                author = message.author
                ts = message.timestamp.timestamp()
                data = {}
                data['TIMESTAMP'] = ts
                if server.id not in self.seen:
                    self.seen[server.id] = {}
                self.seen[server.id][author.id] = data
                self.new_data = True


def check_folder():
    if not os.path.exists('data/seen'):
        print('Creating data/seen folder...')
        os.makedirs('data/seen')


def check_file():
    data = {}
    data['db_version'] = DB_VERSION
    f = 'data/seen/seen.json'
    if not dataIO.is_valid_json(f):
        print('Creating seen.json...')
        dataIO.save_json(f, data)
    else:
        check = dataIO.load_json(f)
        if 'db_version' in check:
            if check['db_version'] < DB_VERSION:
                data = {}
                data['db_version'] = DB_VERSION
                dataIO.save_json(f, data)
                print('SEEN: Database version too old, resetting!')
        else:
            data = {}
            data['db_version'] = DB_VERSION
            dataIO.save_json(f, data)
            print('SEEN: Database version too old, resetting!')


def setup(bot):
    check_folder()
    check_file()
    n = Seen(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(n.data_writer())
    bot.add_cog(n)
