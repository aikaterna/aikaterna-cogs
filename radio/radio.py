import os
import discord
import asyncio
from discord.ext import commands
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO


class Radio:
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.memory_path = 'data/radio/memory.json'
        self.memory = dataIO.load_json(self.memory_path)

    @commands.group(pass_context=True, no_pm=True, name='radio')
    async def _radio(self, ctx):
        """Streaming audio commands."""
        audio_cog = self.bot.get_cog('Audio')
        if audio_cog:
            return await self.bot.say("Please unload the audio cog before using this cog.")
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_radio.command(pass_context=True, no_pm=True, name='stop')
    async def _leave(self, ctx):
        """Stops playback."""
        server = ctx.message.server
        voice_client = await self.voice_client(server)
        await self.stop_playing(server)
        if voice_client:
            await voice_client.disconnect()

    @_radio.command(no_pm=True, pass_context=True, name='play')
    async def _play(self, ctx, url: str):
        """Play a http stream."""
        server = ctx.message.server
        if server.id in self.players:
            await self.stop_playing(server)
        await self.play_stream(ctx, url)
        await self.bot.say("Now playing: <{}>".format(url))

    @_radio.command(no_pm=True, pass_context=True, name='list')
    async def _list(self, ctx):
        """List saved stream URLs."""
        server = ctx.message.server
        message_list = []
        if server.id in self.memory:
            for stream in self.memory[server.id]:
                message = '{:<30}{}\n'.format(stream, self.memory[server.id][stream])
                message_list.append(message)
        sorted_list = sorted(message_list, key=str.lower)
        msg = '```'
        msg += '{:<30}{}\n\n'.format('NAME', 'URL')
        for sorted_msg in sorted_list:
            msg += sorted_msg
        msg += '```'
        await self.bot.say(msg)

    @_radio.command(no_pm=True, pass_context=True, name='add')
    async def _add(self, ctx, name: str, url: str):
        """Add a url to save for radio playback."""
        server = ctx.message.server
        await self.add_to_memory(server, name, url)
        await self.bot.say('Added to memory')

    @_radio.command(no_pm=True, pass_context=True, name='load')
    async def _load(self, ctx, name: str):
        """Load a saved url for radio playback."""
        server = ctx.message.server
        if server.id in self.memory:
            if name.lower() in self.memory[server.id]:
                url = self.memory[server.id][name.lower()]
                if server.id in self.players:
                    await self.stop_playing(server)
                await self.play_stream(ctx, url)
                await self.bot.say("Now playing: <{}>".format(url))
            else:
                await self.bot.say('"{}" is not in memory.'.format(name.lower()))
        else:
            await self.bot.say('Nothing in memory yet')

    @_radio.command(no_pm=True, pass_context=True, name='remove')
    async def _remove(self, ctx, name: str):
        """Remove a saved radio stream."""
        server = ctx.message.server
        await self.remove_from_memory(server, name)
        await self.bot.say('Removed {} from memory.'.format(name))

    async def save_memory(self):
        dataIO.save_json(self.memory_path, self.memory)

    async def add_to_memory(self, server, name, url):
        if server.id not in self.memory:
            self.memory[server.id] = {}
        self.memory[server.id][name.lower()] = url
        await self.save_memory()

    async def remove_from_memory(self, server, name):
        del self.memory[server.id][name.lower()]
        await self.save_memory()

    async def join_voice_channel(self, channel):
        try:
            await self.bot.join_voice_channel(channel)
            return True
        except discord.InvalidArgument:
            await self.bot.say('You need to be in a voice channel yourself.')
        except discord.Forbidden:
            await self.bot.say('I don\'t have permissions to join this channel.')
        return False

    async def leave_voice_channel(self, server):
        voice_client = await self.voice_client(server)
        if server.id in self.players:
            self.players[server.id].stop()
            del self.players[server.id]
            await self.stop_playing(server)
        await voice_client.disconnect()

    async def voice_connected(self, server):
        return self.bot.is_voice_connected(server)

    async def voice_client(self, server):
        return self.bot.voice_client_in(server)

    async def stop_playing(self, server):
        if server.id in self.players:
            self.players[server.id].stop()
            del self.players[server.id]

    async def start_playing(self, server, url):
        if server.id not in self.players:
            voice_client = await self.voice_client(server)
            audio_player = voice_client.create_ffmpeg_player(url)
            self.players[server.id] = audio_player
            self.players[server.id].start()

    async def play_stream(self, ctx, url):
        server = ctx.message.server
        channel = ctx.message.author.voice_channel
        if not ctx.message.channel.is_private:
            check = True
            if not await self.voice_connected(server):
                check = await self.join_voice_channel(channel)
            if check:
                await self.start_playing(server, url)

    async def _playing_check(self):
        while self == self.bot.get_cog('Radio'):
            for player in self.players:
                if not self.players[player].is_playing():
                    server = self.bot.get_server(player)
                    await self.leave_voice_channel(server)
                    break
            await asyncio.sleep(30)


def check_folder():
    if not os.path.exists('data/radio'):
        print('Creating data/radio folder...')
        os.makedirs('data/radio')


def check_file():
    if not dataIO.is_valid_json('data/radio/memory.json'):
        print('Creating memory.json...')
        dataIO.save_json('data/radio/memory.json', {})


def setup(bot):
    check_folder()
    check_file()
    cog = Radio(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(cog._playing_check())
    bot.add_cog(cog)
