#  _is_hex, _hex_to_rgb, _rgb_to_hex are from Stevy's leveler.py
#  Also thanks to Stevy for nice, smooth circles.
#  https://github.com/AznStevy/Maybe-Useful-Cogs
#  imgwelcomeset_upload is based on code in orels' drawing.py
#  https://github.com/orels1/ORELS-Cogs
#  Parts of createWelcomeImage and on_member_join are from the Welcomer bot:
#  https://discordbots.org/bot/330416853971107840
import asyncio
import aiohttp
import datetime
import discord
import os
import re
import time
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from copy import deepcopy
from discord.ext import commands
from io import BytesIO
from PIL import Image, ImageFont, ImageOps, ImageDraw


default_settings = {"ANNOUNCE": False,
                    "BACKGROUND": "data/imgwelcome/transparent.png",
                    "BORDER": [255,255,255,230], "CHANNEL": None,
                    "SERVERTEXT": [255,255,255,230], "TEXT": [255,255,255,230]}


class ImgWelcome:
    """Welcomes a user to the server with an image."""

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json('data/imgwelcome/settings.json')
        self.version = "0.1.1a"

    async def save_settings(self):
        dataIO.save_json('data/imgwelcome/settings.json', self.settings)

    async def createWelcomeImage(self, member, url):
        server = member.server
        defaultFont = ImageFont.truetype("data/imgwelcome/fonts/UniSansHeavy.otf",50)
        smallFont = ImageFont.truetype("data/imgwelcome/fonts/UniSansHeavy.otf",20)
        italicFont = ImageFont.truetype("data/imgwelcome/fonts/UniSansHeavy.otf",30)
        italicFontsmall = ImageFont.truetype("data/imgwelcome/fonts/UniSansHeavy.otf",22)
        italicFontsupersmall = ImageFont.truetype("data/imgwelcome/fonts/UniSansHeavy.otf",18)
        Background = Image.open(self.settings[server.id]["BACKGROUND"])
        NoProfilePicture = Image.open("data/imgwelcome/noimage.png")

        global WelcomePicture
        WelcomePicture = Image.new("RGBA",(500,150))
        WelcomePicture = ImageOps.fit(Background,(500,150),centering=(0.5,0.5))
        WelcomePicture.paste(Background)
        WelcomePicture = WelcomePicture.resize((500,150), Image.NEAREST)

        # Load profile picture and make template
        ProfileArea = Image.new("L",(512,512),0)
        draw = ImageDraw.Draw(ProfileArea)
        draw.ellipse(((0,0),(512,512)),fill=255)
        ProfileArea = ProfileArea.resize((128,128), Image.ANTIALIAS)
        try:
            url = url.replace('webp?size=1024', 'png')
            url = url.replace('gif?size=1024', 'png')
            await self.getProfile(url)
            ProfilePicture = Image.open('data/imgwelcome/profilepic.png')
        except:
            ProfilePicture = NoProfilePicture
        ProfileAreaOutput = ImageOps.fit(ProfilePicture,(128,128),centering=(0,0))
        ProfileAreaOutput.putalpha(ProfileArea)

        # Create profile picture
        drawtwo = ImageDraw.Draw(WelcomePicture)
        bordercolor = tuple(self.settings[member.server.id]["BORDER"])
        fontcolor = tuple(self.settings[member.server.id]["TEXT"])
        servercolor = tuple(self.settings[member.server.id]["SERVERTEXT"])
        circle = Image.new("RGB", (544, 544))
        draw_circle = ImageDraw.Draw(circle)
        draw_circle.ellipse([0,0,544,544],fill=(bordercolor), outline=0)
        circle = circle.resize((136, 136), Image.ANTIALIAS)
        WelcomePicture.paste(circle, (7, 7))
        WelcomePicture.paste(ProfileAreaOutput,(11,11),ProfileAreaOutput)

        # Draw welcome text
        uname = (str(member.name) + "#" + str(member.discriminator))
        drawtwo.text((150,16),"Welcome",font=defaultFont, fill=(fontcolor))
        if len(uname) <= 17:
            drawtwo.text((152,63),uname,font=italicFont, fill=(fontcolor))
        if len(uname) > 17:
            if len(uname) <= 23:
                drawtwo.text((152,66),uname,font=italicFontsmall, fill=(fontcolor))
        if len(uname) >= 24:
            drawtwo.text((152,70),uname,font=italicFontsupersmall, fill=(fontcolor))

        member_number = len(member.server.members)
        drawtwo.text((152,96),"You are the " + str(member_number) + self.getSuffix(member_number) + " member",font=smallFont, fill=(servercolor))
        drawtwo.text((152,116),"of " + str(member.server.name) + "!",font=smallFont, fill=(servercolor))
        # Export
        ImageObject = BytesIO()
        WelcomePicture.save(ImageObject, format="PNG")
        ImageObject.seek(0)
        return ImageObject

    def _rgb_to_hex(self, rgb):
        rgb = tuple(rgb[:3])
        return '#%02x%02x%02x' % rgb

    def _hex_to_rgb(self, hex_num: str, a:int):
        h = hex_num.lstrip('#')

        # if only 3 characters are given
        if len(str(h)) == 3:
            expand = ''.join([x*2 for x in str(h)])
            h = expand

        colors = [int(h[i:i+2], 16) for i in (0, 2 ,4)]
        colors.append(a)
        return tuple(colors)

    def _is_hex(self, color:str):
        if color is not None and len(color) != 4 and len(color) != 7:
            return False

        reg_ex = r'^#(?:[0-9a-fA-F]{3}){1,2}$'
        return re.search(reg_ex, str(color))

    async def getProfile(self, url):
        async with aiohttp.get(url) as r:
            image = await r.content.read()
        with open('data/imgwelcome/profilepic.png','wb') as f:
            f.write(image)

    def getSuffix(self, num):
        num = str(num)
        last = num[len(num)-1:len(num)]
        if last == "1":
            return "st"
        elif last == "2":
            return "nd"
        elif last == "3":
            return "rd"
        else:
            return "th"

    async def data_check(self, ctx):
        server = ctx.message.server
        if server.id not in self.settings:
            self.settings[server.id] = deepcopy(default_settings)
            self.settings[server.id]["CHANNEL"] = ctx.message.channel.id
            await self.save_settings()
        channel = self.settings[server.id]["CHANNEL"]
        if channel not in self.settings:
            self.settings[server.id]["CHANNEL"] = ctx.message.channel.id
            await self.save_settings()

    @checks.admin_or_permissions(manage_server=True)
    @commands.group(pass_context=True)
    async def imgwelcomeset(self, ctx):
        """Configuration options for the welcome image."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @imgwelcomeset.command(pass_context=True, name="colors", no_pm=True)
    async def imgwelcomeset_colors(self, ctx, bordercolor:str, textcolor:str, servercolor:str):
        """Set image border and text colors. Accepts hex code for colors."""
        user = ctx.message.author
        server = ctx.message.server
        await self.data_check(ctx)
        default_a = 230
        valid = True

        if self._is_hex(bordercolor):
            self.settings[server.id]["BORDER"] = self._hex_to_rgb(bordercolor, default_a)
        else:
            await self.bot.say('Border color is invalid. Use #000000 as a format.')
            valid = False

        if self._is_hex(textcolor):
            self.settings[server.id]["TEXT"] = self._hex_to_rgb(textcolor, default_a)
        else:
            await self.bot.say('Welcome text color is invalid. Use #000000 as a format.')
            valid = False

        if self._is_hex(servercolor):
            self.settings[server.id]["SERVERTEXT"] = self._hex_to_rgb(servercolor, default_a)
        else:
            await self.bot.say('Server text color is invalid. Use #000000 as a format.')
            valid = False

        if valid:
            await self.bot.say('The profile and text colors have been set.')
            await self.save_settings()

    @imgwelcomeset.command(pass_context=True, name="channel", no_pm=True)
    async def imgwelcomeset_channel(self, ctx, channel: discord.Channel):
        """Set the announcement channel."""
        server = ctx.message.server
        if not server.me.permissions_in(channel).send_messages:
            await self.bot.say("No permissions to speak in that channel.")
            return
        await self.data_check(ctx)
        self.settings[server.id]["CHANNEL"] = channel.id
        await self.save_settings()
        await self.bot.send_message(channel, "This channel will be used for welcome messages.")

    @imgwelcomeset.command(name='clear', pass_context=True, no_pm=True)
    async def imgwelcomeset_clear(self, ctx):
        """Set the background to transparent."""
        server = ctx.message.server
        await self.data_check(ctx)
        self.settings[server.id]['BACKGROUND'] = 'data/imgwelcome/transparent.png'
        await self.save_settings()
        await self.bot.say('Welcome image background is now transparent.')

    @imgwelcomeset.command(name='clearborder', pass_context=True, no_pm=True)
    async def imgwelcomeset_clearborder(self, ctx):
        """Set the image border to transparent."""
        server = ctx.message.server
        await self.data_check(ctx)
        self.settings[server.id]['BORDER'] = [0,0,0,0]
        await self.save_settings()
        await self.bot.say('Profile image border is now transparent.')

    @imgwelcomeset.command(name="preview", pass_context=True)
    async def imagewelcomeset_preview(self, ctx, member:discord.Member=None):
        """Show a welcome image with the current settings."""
        server = ctx.message.server
        author = ctx.message.author
        channel = ctx.message.channel
        if member is None:
            member = ctx.message.author
        await self.data_check(ctx)
        channelobj = self.bot.get_channel(channel.id)
        await self.bot.send_typing(channelobj)
        ImageObject = await self.createWelcomeImage(member, member.avatar_url)
        await self.bot.send_file(channelobj,ImageObject,filename="welcome.png")

    @imgwelcomeset.command(pass_context=True, name="toggle", no_pm=True)
    async def imgwelcomeset_toggle(self, ctx):
        """Toggle welcome messages on the server."""
        server = ctx.message.server
        await self.data_check(ctx)
        self.settings[server.id]["ANNOUNCE"] = not self.settings[server.id]["ANNOUNCE"]
        if self.settings[server.id]["ANNOUNCE"]:
            await self.bot.say("Now welcoming new users.")
        else:
            await self.bot.say("No longer welcoming new users.")
        await self.save_settings()

    @imgwelcomeset.command(name='upload', pass_context=True, no_pm=True)
    async def imgwelcomeset_upload(self, ctx, default=None):
        """Upload a background through Discord. 500px x 150px.
        This must be an image file and not a url."""
        # request image from user
        server = ctx.message.server
        await self.data_check(ctx)
        await self.bot.say("Please send the file to use as a background. File must be 500px x 150px.")
        answer = await self.bot.wait_for_message(timeout=30, author=ctx.message.author)

        # get the image from message
        try:
            bg_url = answer.attachments[0]["url"]
            success = True
        except Exception as e:
            success = False
            print(e)

        serverimage = Image

        if success:

            # download the image
            try:
                async with aiohttp.get(bg_url) as r:
                    image = await r.content.read()
                    if not os.path.exists('data/imgwelcome/{}'.format(server.id)):
                        os.makedirs('data/imgwelcome/{}'.format(server.id))
                serverbg = 'data/imgwelcome/{}/serverbg.png'.format(server.id)
                with open(serverbg, 'wb') as f:
                    f.write(image)
                    serverimage = Image.open(serverbg).convert('RGBA')
                    success = True

            except Exception as e:
                success = False
                print(e)

            if success:
                # check dimensions
                if serverimage.size == (500,150):
                    self.settings[server.id]['BACKGROUND'] = "data/imgwelcome/" + ctx.message.server.id + "/serverbg.png"
                    await self.save_settings()
                else:
                    await self.bot.say("Image needs to be 500x150.")
                    return
                backgroundimg = ('data/imgwelcome/{}/serverbg.png'.format(server.id))
                self.settings[server.id]['BACKGROUND'] = (backgroundimg)
                await self.save_settings()
                await self.bot.say('Welcome image for this server set to uploaded file.')
            else:
                await self.bot.say("Couldn't get the image from Discord.")
        else:
            await self.bot.say("Couldn't get the image.")

    @imgwelcomeset.command(name="version", pass_context=True, hidden=True)
    async def imagewelcomeset_version(self):
        """Displays the imgwelcome version."""
        await self.bot.say("imgwelcome version {}.".format(self.version))

    async def on_member_join(self, member):
        server = member.server
        if server.id not in self.settings:
            self.settings[server.id] = deepcopy(default_settings)
            await self.save_settings()
        if not self.settings[server.id]["ANNOUNCE"]:
            return
        channelid = self.settings[server.id]["CHANNEL"]
        channelobj = self.bot.get_channel(channelid)
        await self.bot.send_typing(channelobj)
        ImageObject = await self.createWelcomeImage(member, member.avatar_url)
        await self.bot.send_file(channelobj,ImageObject,filename="welcome.png")
        if (len(member.server.members) % 100) == 0 or (len(member.server.members) == 1337):
            msg = "\N{PARTY POPPER} Thanks <@" + member.id + ">, you're the ***" + str(len(member.server.members)) + "*** th user on this server! \N{PARTY POPPER}"
            await self.bot.send_message(channelobj,msg)
        joinDate = datetime.datetime.strptime(str(member.created_at),"%Y-%m-%d %H:%M:%S.%f")
        currentDate = datetime.datetime.now(datetime.timezone.utc)
        currentDate = currentDate.replace(tzinfo=None)
        timeSinceJoining = currentDate - joinDate
        if timeSinceJoining.days < 7:
            await self.bot.send_message(channelobj,"\N{WARNING SIGN} This account was created less than a week ago (" + str(timeSinceJoining.days) + " days ago)")


def check_folders():
    if not os.path.exists('data/imgwelcome/'):
        os.mkdir('data/imgwelcome/')


def check_files():
    if not dataIO.is_valid_json('data/imgwelcome/settings.json'):
        defaults = {}
        dataIO.save_json('data/imgwelcome/settings.json', defaults)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(ImgWelcome(bot))
