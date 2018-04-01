#  picwelcomeset_upload is based on code in orels' drawing.py
#  https://github.com/orels1/ORELS-Cogs

import asyncio
import aiohttp
import datetime
import discord
import os
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from copy import deepcopy
from discord.ext import commands
from PIL import Image


default_settings = {"ANNOUNCE": False,
                    "PICTURE": "data/picwelcome/default.png",
                    "CHANNEL": None,
                    }


class PicWelcome:
    """Welcome new users with a static image."""

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json('data/picwelcome/settings.json')
        self.version = "0.0.1"

    async def save_settings(self):
        dataIO.save_json('data/picwelcome/settings.json', self.settings)

    async def _data_check(self, ctx):
        server = ctx.message.server
        if server.id not in self.settings:
            self.settings[server.id] = deepcopy(default_settings)
            self.settings[server.id]["CHANNEL"] = ctx.message.channel.id
            await self.save_settings()

    @checks.admin_or_permissions(manage_server=True)
    @commands.group(pass_context=True)
    async def picwelcome(self, ctx):
        """Configuration options for a welcome picture."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @picwelcome.command(pass_context=True, name="channel", no_pm=True)
    async def picwelcome_channel(self, ctx, channel: discord.Channel):
        """Set the announcement channel."""
        server = ctx.message.server
        if not server.me.permissions_in(channel).send_messages:
            await self.bot.say("No permissions to speak in that channel.")
            return
        await self._data_check(ctx)
        self.settings[server.id]["CHANNEL"] = channel.id
        await self.save_settings()
        await self.bot.send_message(channel, "This channel will be used for welcome pictures.")

    @picwelcome.command(name='reset', pass_context=True, no_pm=True)
    async def picwelcome_reset(self, ctx):
        """Set the welcome picture back to the default."""
        server = ctx.message.server
        await self._data_check(ctx)
        self.settings[server.id]['PICTURE'] = 'data/picwelcome/default.png'
        await self.save_settings()
        await self.bot.say('Welcome picture reset to default.')

    @picwelcome.command(name="preview", pass_context=True, no_pm=True)
    async def picwelcome_preview(self, ctx, member: discord.Member=None, number: int=None):
        """Show a the welcome picture with the current settings."""
        server = ctx.message.server
        channel = ctx.message.channel
        if member is None:
            member = ctx.message.author
        await self._data_check(ctx)
        channel_object = self.bot.get_channel(channel.id)
        await self.bot.send_typing(channel_object)
        serverpicture = self.settings[server.id]["PICTURE"]
        await self.bot.send_file(channel_object, serverpicture)

    @picwelcome.command(pass_context=True, name="toggle", no_pm=True)
    async def picwelcome_toggle(self, ctx):
        """Toggle welcome pictures on the server."""
        server = ctx.message.server
        await self._data_check(ctx)
        self.settings[server.id]["ANNOUNCE"] = not self.settings[server.id]["ANNOUNCE"]
        if self.settings[server.id]["ANNOUNCE"]:
            await self.bot.say("Now welcoming new users with a picture.")
        else:
            await self.bot.say("No longer welcoming new users with a picture.")
        await self.save_settings()

    @picwelcome.command(name='upload', pass_context=True, no_pm=True)
    async def picwelcome_upload(self, ctx, default=None):
        """Upload a picture through Discord.
        This must be an image file and not a url."""
        server = ctx.message.server
        await self._data_check(ctx)
        await self.bot.say("Please send the file to use as a welcome picture.")
        answer = await self.bot.wait_for_message(timeout=30, author=ctx.message.author)

        try:
            bg_url = answer.attachments[0]["url"]
            success = True
        except Exception as e:
            success = False
            print(e)

        serverimage = Image
        if success:
            try:
                async with aiohttp.get(bg_url) as r:
                    image = await r.content.read()
                    if not os.path.exists('data/picwelcome/{}'.format(server.id)):
                        os.makedirs('data/picwelcome/{}'.format(server.id))
                file_suffix = bg_url.rsplit('.', 1)[1]
                serverbg = 'data/picwelcome/{}/serverpic.{}'.format(server.id, file_suffix)
                with open(serverbg, 'wb') as f:
                    f.write(image)
                    serverimage = Image.open(serverbg).convert('RGBA')
                    success = True
            except Exception as e:
                success = False
                print(e)

            if success:
                self.settings[server.id]['PICTURE'] = "data/picwelcome/{}/serverpic.{}".format(ctx.message.server.id, file_suffix)
                await self.save_settings()
                await self.bot.say('Welcome image for this server set to uploaded file.')
            else:
                await self.bot.say("Couldn't get the image from Discord.")
        else:
            await self.bot.say("Couldn't get the image.")

    @picwelcome.command(name="version", pass_context=True, hidden=True)
    async def picwelcome_version(self):
        """Displays the picwelcome version."""
        await self.bot.say("picwelcome version {}.".format(self.version))

    async def on_member_join(self, member):
        server = member.server
        if server.id not in self.settings:
            self.settings[server.id] = deepcopy(default_settings)
            await self.save_settings()
        if not self.settings[server.id]["ANNOUNCE"]:
            return
        channelid = self.settings[server.id]["CHANNEL"]
        channel_object = self.bot.get_channel(channelid)
        await self.bot.send_typing(channel_object)
        serverpicture = self.settings[server.id]["PICTURE"]
        await self.bot.send_file(channel_object, serverpicture)

def check_folders():
    if not os.path.exists('data/picwelcome/'):
        os.mkdir('data/picwelcome/')

def check_files():
    if not dataIO.is_valid_json('data/picwelcome/settings.json'):
        defaults = {}
        dataIO.save_json('data/picwelcome/settings.json', defaults)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(PicWelcome(bot))
