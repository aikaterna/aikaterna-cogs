#  _is_hex, _hex_to_rgb, _rgb_to_hex are from Stevy's leveler.py
#  Also thanks to Stevy for nice, smooth circles.
#  https://github.com/AznStevy/Maybe-Useful-Cogs
#  imgwelcomeset_upload is based on code in orels' drawing.py
#  https://github.com/orels1/ORELS-Cogs
#  Parts of _create_welcome and on_member_join are from the Welcomer bot:
#  https://discordbots.org/bot/330416853971107840
#  Font switcher, font outline, and bonus text announcement toggles
#  thanks to Sitryk.
#  Font listing from FlapJack + aikaterna's yet unpublished wordcloud cog.
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
                    "BONUSES": {"ACCOUNT_WARNINGS": True,
                                "SPECIAL_USERS": True
                                },
                    "BORDER": [255, 255, 255, 230],
                    "CHANNEL": None,
                    "OUTLINE": [0, 0, 0, 255],
                    "SERVERTEXT": [255, 255, 255, 230],
                    "TEXT": [255, 255, 255, 230],
                    "FONT": {"WELCOME_FONT": {"PATH": "data/imgwelcome/fonts/UniSansHeavy.otf",
                                               "SIZE": 50},
                             "SERVER_FONT": {"PATH": "data/imgwelcome/fonts/UniSansHeavy.otf",
                                              "SIZE": 20},
                             "NAME_FONT": {"PATH": "data/imgwelcome/fonts/UniSansHeavy.otf",
                                            "SIZE": {"NORMAL": 30,
                                                      "MEDIUM": 22,
                                                      "SMALL": 18,
                                                      "SMALLEST": 12
                                                    }
                                            }
                            }
                    }


class ImgWelcome:
    """Welcomes a user to the server with an image."""

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json('data/imgwelcome/settings.json')
        self.version = "0.1.8"
        self.session = aiohttp.ClientSession()
        
    def __unload(self):
        self.session.close()

    async def save_settings(self):
        dataIO.save_json('data/imgwelcome/settings.json', self.settings)

    async def _create_welcome(self, member, url, test_member_number: int = None):
        server = member.server
        wfont = self.settings[server.id]["FONT"]["WELCOME_FONT"]
        sfont = self.settings[server.id]["FONT"]["SERVER_FONT"]
        nfont = self.settings[server.id]["FONT"]["NAME_FONT"]
        welcome_font = ImageFont.truetype(wfont["PATH"], wfont["SIZE"])
        server_font = ImageFont.truetype(sfont["PATH"], sfont["SIZE"])

        name_font = ImageFont.truetype(nfont["PATH"], nfont["SIZE"]["NORMAL"])
        name_font_medium = ImageFont.truetype(nfont["PATH"], nfont["SIZE"]["MEDIUM"])
        name_font_small = ImageFont.truetype(nfont["PATH"], nfont["SIZE"]["SMALL"])
        name_font_smallest = ImageFont.truetype(nfont["PATH"], nfont["SIZE"]["SMALLEST"])
        background = Image.open(self.settings[server.id]["BACKGROUND"]).convert('RGBA')
        no_profile_picture = Image.open("data/imgwelcome/noimage.png")

        global welcome_picture
        welcome_picture = Image.new("RGBA", (500, 150))
        welcome_picture = ImageOps.fit(background, (500, 150), centering=(0.5, 0.5))
        welcome_picture.paste(background)
        welcome_picture = welcome_picture.resize((500, 150), Image.NEAREST)

        profile_area = Image.new("L", (512, 512), 0)
        draw = ImageDraw.Draw(profile_area)
        draw.ellipse(((0, 0), (512, 512)), fill=255)
        circle_img_size = tuple(self.settings[member.server.id]["CIRCLE"])
        profile_area = profile_area.resize((circle_img_size), Image.ANTIALIAS)
        try:
            url = url.replace('webp?size=1024', 'png')
            url = url.replace('gif?size=1024', 'png')
            await self._get_profile(url)
            profile_picture = Image.open('data/imgwelcome/profilepic.png')
        except:
            profile_picture = no_profile_picture
        profile_area_output = ImageOps.fit(profile_picture, (circle_img_size), centering=(0, 0))
        profile_area_output.putalpha(profile_area)

        bordercolor = tuple(self.settings[member.server.id]["BORDER"])
        fontcolor = tuple(self.settings[member.server.id]["TEXT"])
        servercolor = tuple(self.settings[member.server.id]["SERVERTEXT"])
        textoutline = tuple(self.settings[server.id]["OUTLINE"])

        mask = Image.new('L', (512, 512), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (512, 512), fill=255, outline=0)
        circle = Image.new("RGBA", (512, 512))
        draw_circle = ImageDraw.Draw(circle)
        draw_circle.ellipse([0, 0, 512, 512], fill=(bordercolor[0], bordercolor[1], bordercolor[2], 180), outline=(255, 255, 255, 250))
        circle_border_size = await self._circle_border(circle_img_size)
        circle = circle.resize((circle_border_size), Image.ANTIALIAS)
        circle_mask = mask.resize((circle_border_size), Image.ANTIALIAS)
        circle_pos = (7 + int((136 - circle_border_size[0]) / 2))
        border_pos = (11 + int((136 - circle_border_size[0]) / 2))
        drawtwo = ImageDraw.Draw(welcome_picture)
        welcome_picture.paste(circle, (circle_pos, circle_pos), circle_mask)
        welcome_picture.paste(profile_area_output, (border_pos, border_pos), profile_area_output)

        uname = (str(member.name) + "#" + str(member.discriminator))

        def _outline(original_position: tuple, text: str, pixel_displacement: int, font, textoutline):
            op = original_position
            pd = pixel_displacement

            left = (op[0] - pd, op[1])
            right = (op[0] + pd, op[1])
            up = (op[0], op[1] - pd)
            down = (op[0], op[1] + pd)

            drawtwo.text(left, text, font=font, fill=(textoutline))
            drawtwo.text(right, text, font=font, fill=(textoutline))
            drawtwo.text(up, text, font=font, fill=(textoutline))
            drawtwo.text(down, text, font=font, fill=(textoutline))

            drawtwo.text(op, text, font=font, fill=(textoutline))

        _outline((150, 16), "Welcome", 1, welcome_font, (textoutline))
        drawtwo.text((150, 16), "Welcome", font=welcome_font, fill=(fontcolor))

        if len(uname) <= 17:
            _outline((152, 63), uname, 1, name_font, (textoutline))
            drawtwo.text((152, 63), uname, font=name_font, fill=(fontcolor))

        if len(uname) > 17:
            if len(uname) <= 23:
                _outline((152, 66), uname, 1,  name_font_medium, (textoutline))
                drawtwo.text((152, 66), uname, font=name_font_medium, fill=(fontcolor))

        if len(uname) >= 24:
            if len(uname) <= 32:
                _outline((152, 70), uname, 1,  name_font_small, (textoutline))
                drawtwo.text((152, 70), uname, font=name_font_small, fill=(fontcolor))

        if len(uname) >= 33:
            _outline((152, 73), uname, 1,  name_font_smallest, (textoutline))
            drawtwo.text((152, 73), uname, font=name_font_smallest, fill=(fontcolor))

        if test_member_number is None:
            members = sorted(server.members,
                               key=lambda m: m.joined_at).index(member) + 1
        else:
            members = test_member_number

        member_number = str(members) + self._get_suffix(members)
        sname = str(member.server.name) + '!' if len(str(member.server.name)) <= 28 else str(member.server.name)[:23] + '...'

        _outline((152, 96), "You are the " + str(member_number) + " member", 1, server_font, (textoutline))
        drawtwo.text((152, 96), "You are the " + str(member_number) + " member", font=server_font, fill=(servercolor))
        _outline((152, 116), 'of ' + sname, 1, server_font, (textoutline))
        drawtwo.text((152, 116), 'of ' + sname, font=server_font, fill=(servercolor))

        image_object = BytesIO()
        welcome_picture.save(image_object, format="PNG")
        image_object.seek(0)
        return image_object

    async def _circle_border(self, circle_img_size: tuple):
        border_size = []
        for i in range(len(circle_img_size)):
            border_size.append(circle_img_size[0] + 8)
        return tuple(border_size)

    async def _data_check(self, ctx):
        server = ctx.message.server
        if server.id not in self.settings:
            self.settings[server.id] = deepcopy(default_settings)
            self.settings[server.id]["CHANNEL"] = ctx.message.channel.id
            await self.save_settings()

        if "BONUSES" not in self.settings[server.id].keys():
            self.settings[server.id]["BONUSES"] = {"ACCOUNT_WARNINGS": True,
                                                   "SPECIAL_USERS": True
                                                   }
            await self.save_settings()

        if "CIRCLE" not in self.settings[server.id].keys():
            self.settings[server.id]["CIRCLE"] = [128, 128]
            await self.save_settings()

        if "CHANNEL" not in self.settings[server.id].keys():
            self.settings[server.id]["CHANNEL"] = ctx.message.channel.id
            await self.save_settings()

        if "FONT" not in self.settings[server.id].keys():
            self.settings[server.id]["FONT"] = {"WELCOME_FONT": {"PATH": "data/imgwelcome/fonts/UniSansHeavy.otf",
                                                                  "SIZE": 50},
                                                "SERVER_FONT": {"PATH": "data/imgwelcome/fonts/UniSansHeavy.otf",
                                                                 "SIZE": 20},
                                                "NAME_FONT": {"PATH": "data/imgwelcome/fonts/UniSansHeavy.otf",
                                                               "SIZE": {"NORMAL": 30,
                                                                         "MEDIUM": 22,
                                                                         "SMALL": 18,
                                                                         "SMALLEST": 12
                                                                        }
                                                                }
                                                }

        if "OUTLINE" not in self.settings[server.id].keys():
            self.settings[server.id]["OUTLINE"] = [0, 0, 0, 255]
            await self.save_settings()

    async def _get_profile(self, url):
        async with self.session.get(url) as r:
            image = await r.content.read()
        with open('data/imgwelcome/profilepic.png', 'wb') as f:
            f.write(image)

    def _get_suffix(self, num):
        suffixes = {1: 'st', 2: 'nd', 3: 'rd'}
        if 10 <= num % 100 <= 20:
            suffix = 'th'
        else:
            suffix = suffixes.get(num % 10, 'th')
        return suffix

    def _hex_to_rgb(self, hex_num: str, a: int):
        h = hex_num.lstrip('#')

        # if only 3 characters are given
        if len(str(h)) == 3:
            expand = ''.join([x*2 for x in str(h)])
            h = expand

        colors = [int(h[i:i+2], 16) for i in (0, 2, 4)]
        colors.append(a)
        return tuple(colors)

    def _is_hex(self, color: str):
        if color is not None and len(color) != 4 and len(color) != 7:
            return False

        reg_ex = r'^#(?:[0-9a-fA-F]{3}){1,2}$'
        return re.search(reg_ex, str(color))

    def _rgb_to_hex(self, rgb):
        rgb = tuple(rgb[:3])
        return '#%02x%02x%02x' % rgb

    @checks.admin_or_permissions(manage_server=True)
    @commands.group(pass_context=True)
    async def imgwelcome(self, ctx):
        """Configuration options for the welcome image."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @imgwelcome.command(pass_context=True, name="border", no_pm=True)
    async def imgwelcome_border(self, ctx, bordercolor=None):
        """Set the profile image border color.
        Use hex codes for colors and ‘clear’ for transparent."""
        server = ctx.message.server
        await self._data_check(ctx)
        default_a = 230
        valid = True

        if bordercolor == "clear":
            self.settings[server.id]["BORDER"] = [0, 0, 0, 0]
        elif self._is_hex(bordercolor):
            self.settings[server.id]["BORDER"] = self._hex_to_rgb(bordercolor, default_a)
        else:
            await self.bot.say('Border color is invalid. Use #000000 as a format.')
            valid = False

        if valid:
            await self.bot.say('The profile border color has been set.')
            await self.save_settings()

    @imgwelcome.command(pass_context=True, name="channel", no_pm=True)
    async def imgwelcome_channel(self, ctx, channel: discord.Channel):
        """Set the announcement channel."""
        server = ctx.message.server
        if not server.me.permissions_in(channel).send_messages:
            await self.bot.say("No permissions to speak in that channel.")
            return
        await self._data_check(ctx)
        self.settings[server.id]["CHANNEL"] = channel.id
        await self.save_settings()
        await self.bot.send_message(channel, "This channel will be used for welcome messages.")

    @imgwelcome.command(name='clear', pass_context=True, no_pm=True)
    async def imgwelcome_clear(self, ctx):
        """Set the background to transparent."""
        server = ctx.message.server
        await self._data_check(ctx)
        self.settings[server.id]['BACKGROUND'] = 'data/imgwelcome/transparent.png'
        await self.save_settings()
        await self.bot.say('Welcome image background is now transparent.')

    @imgwelcome.command(pass_context=True, name="outline", no_pm=True)
    async def imgwelcome_outline(self, ctx, outline=None):
        """Set the text outline. White or black."""
        server = ctx.message.server
        await self._data_check(ctx)
        valid = True
        if outline == "white":
            self.settings[server.id]["OUTLINE"] = [255, 255, 255, 255]
            await self.save_settings()
        elif outline == "black":
            self.settings[server.id]["OUTLINE"] = [0, 0, 0, 255]
            await self.save_settings()
        else:
            await self.bot.say('Outline color is invalid. Use white or black.')
            valid = False

        if valid:
            await self.bot.say('The text outline has been set.')

    @imgwelcome.command(name="preview", pass_context=True, no_pm=True)
    async def imagewelcome_preview(self, ctx, member: discord.Member=None, number: int=None):
        """Show a welcome image with the current settings."""
        server = ctx.message.server
        channel = ctx.message.channel
        if member is None:
            member = ctx.message.author
        await self._data_check(ctx)
        channel_object = self.bot.get_channel(channel.id)
        await self.bot.send_typing(channel_object)
        image_object = await self._create_welcome(member, member.avatar_url, number)
        await self.bot.send_file(channel_object, image_object, filename="welcome.png")

    @imgwelcome.command(pass_context=True, name="size", no_pm=True)
    async def imgwelcome_profilesize(self, ctx, profilesize: int):
        """Set the profile size in pixels. Use one number, 128 is recommended."""
        server = ctx.message.server
        await self._data_check(ctx)
        if profilesize is 0:
            await self.bot.say("Profile picture size must be larger than 0.")
            return
        else:
            self.settings[server.id]["CIRCLE"] = [profilesize, profilesize]
            await self.save_settings()
            await self.bot.say('The profile picture size has been set.')

    @imgwelcome.command(pass_context=True, name="text", no_pm=True)
    async def imgwelcome_text(self, ctx, textcolor: str, servercolor: str):
        """Set text colors. Use hex code for colors."""
        server = ctx.message.server
        await self._data_check(ctx)
        default_a = 230
        valid = True

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
            await self.bot.say('The text colors have been set.')
            await self.save_settings()

    @imgwelcome.command(pass_context=True, name="toggle", no_pm=True)
    async def imgwelcome_toggle(self, ctx):
        """Toggle welcome messages on the server."""
        server = ctx.message.server
        await self._data_check(ctx)
        self.settings[server.id]["ANNOUNCE"] = not self.settings[server.id]["ANNOUNCE"]
        if self.settings[server.id]["ANNOUNCE"]:
            await self.bot.say("Now welcoming new users.")
        else:
            await self.bot.say("No longer welcoming new users.")
        await self.save_settings()

    @imgwelcome.command(name='upload', pass_context=True, no_pm=True)
    async def imgwelcome_upload(self, ctx, default=None):
        """Upload a background through Discord. 500px x 150px.
        This must be an image file and not a url."""
        server = ctx.message.server
        await self._data_check(ctx)
        await self.bot.say("Please send the file to use as a background. File must be 500px x 150px.")
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
                async with self.session.get(bg_url) as r:
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
                if serverimage.size == (500, 150):
                    self.settings[server.id]['BACKGROUND'] = "data/imgwelcome/" + ctx.message.server.id + "/serverbg.png"
                    await self.save_settings()
                else:
                    await self.bot.say("Image needs to be 500x150.")
                    return
                background_img = ('data/imgwelcome/{}/serverbg.png'.format(server.id))
                self.settings[server.id]['BACKGROUND'] = (background_img)
                await self.save_settings()
                await self.bot.say('Welcome image for this server set to uploaded file.')
            else:
                await self.bot.say("Couldn't get the image from Discord.")
        else:
            await self.bot.say("Couldn't get the image.")

    @imgwelcome.group(pass_context=True, name='bonus', no_pm=True)
    async def imgwelcome_bonus(self, ctx):
        """Toggle display of additional text welcome messages when a user joins the server."""
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)
            return

    @imgwelcome_bonus.command(pass_context=True, name='user', no_pm=True)
    async def bonus_user(self, ctx):
        """Toggle text announcement when a user is x 100th to join or #1337."""
        server = ctx.message.server
        await self._data_check(ctx)
        self.settings[server.id]["BONUSES"]["SPECIAL_USERS"] = not self.settings[server.id]["BONUSES"]["SPECIAL_USERS"]
        await self.save_settings()
        if self.settings[server.id]["BONUSES"]["SPECIAL_USERS"]:
            msg = "I will now announce when special users join."
        else:
            msg = "I will no longer announce when special users join."
        await self.bot.say(msg)

    @imgwelcome_bonus.command(pass_context=True, name='warn', no_pm=True)
    async def bonus_warn(self, ctx):
        """Toggle text announcement when a new user's account is <7d old."""
        server = ctx.message.server
        await self._data_check(ctx)
        self.settings[server.id]["BONUSES"]["ACCOUNT_WARNINGS"] = not self.settings[server.id]["BONUSES"]["ACCOUNT_WARNINGS"]
        await self.save_settings()
        if self.settings[server.id]["BONUSES"]["ACCOUNT_WARNINGS"]:
            msg = "I will now announce when new accounts join."
        else:
            msg = "I will no longer announce when new accounts join."
        await self.bot.say(msg)

    @imgwelcome.group(pass_context=True, name='font', no_pm=True)
    async def imgwelcome_font(self, ctx):
        """Place your font files in the data/imgwelcome/fonts/ directory.
        Valid font areas to change are: welcome, server and name.
        """
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)
            return

    @imgwelcome_font.command(pass_context=True, name='list', no_pm=True)
    async def fontg_list(self, ctx):
        """List fonts in the directory."""
        channel = ctx.message.channel
        directory = "data/imgwelcome/fonts/"
        fonts = sorted(os.listdir(directory))

        if len(fonts) == 0:
            await self.bot.send_message(channel, "No fonts found. Place "
                                        "fonts in /data/imgwelcome/fonts/.")
            return

        pager = commands.formatter.Paginator(prefix='```', suffix='```', max_size=2000)
        pager.add_line('Current fonts:')
        for font_name in fonts:
            pager.add_line(font_name)
        for page in pager.pages:
            await self.bot.send_message(channel, page)

    @imgwelcome_font.command(pass_context=True, name='name', no_pm=True)
    async def fontg_name(self, ctx, font_name: str, size: int=None):
        """Change the name text font.
        e.g. [p]imgwelcome font name "UniSansHeavy.otf"
        """
        await self._data_check(ctx)
        server = ctx.message.server

        directory = "data/imgwelcome/fonts/"
        if size is None:
            size = self.settings[server.id]["FONT"]["NAME_FONT"]["SIZE"]["NORMAL"]

        try:
            ImageFont.truetype(directory + font_name, size)
        except:
            await self.bot.say("I could not find that font file.")
            return

        self.settings[server.id]["FONT"]["NAME_FONT"]["PATH"] = directory + font_name
        self.settings[server.id]["FONT"]["NAME_FONT"]["SIZE"]["NORMAL"] = size
        self.settings[server.id]["FONT"]["NAME_FONT"]["SIZE"]["MEDIUM"] = size - 8
        self.settings[server.id]["FONT"]["NAME_FONT"]["SIZE"]["SMALL"] = size - 12
        self.settings[server.id]["FONT"]["NAME_FONT"]["SIZE"]["SMALLEST"] = size - 18
        await self.save_settings()
        await self.bot.say("Name font changed to: {}".format(font_name[:-4]))

    @imgwelcome_font.command(pass_context=True, name='server', no_pm=True)
    async def fontg_server(self, ctx, font_name: str, size: int=None):
        """Change the server text font."""
        await self._data_check(ctx)
        server = ctx.message.server

        directory = "data/imgwelcome/fonts/"
        if size is None:
            size = self.settings[server.id]["FONT"]["SERVER_FONT"]["SIZE"]

        try:
            ImageFont.truetype(directory + font_name, size)
        except:
            await self.bot.say("I could not find that font file.")
            return

        self.settings[server.id]["FONT"]["SERVER_FONT"]["PATH"] = directory + font_name
        self.settings[server.id]["FONT"]["SERVER_FONT"]["SIZE"] = size
        await self.save_settings()
        await self.bot.say("Server text font changed to: {}".format(font_name[:-4]))
        pass

    @imgwelcome_font.command(pass_context=True, name='welcome', no_pm=True)
    async def fontg_welcome(self, ctx, font_name: str, size: int=None):
        """Change the welcome text font."""
        # try open file_name, if fail tell user
        # if opens change settings, tell user success
        # if file_name doesn't exist, list available fonts
        await self._data_check(ctx)
        server = ctx.message.server

        directory = "data/imgwelcome/fonts/"
        if size is None:
            size = self.settings[server.id]["FONT"]["WELCOME_FONT"]["SIZE"]

        try:
            ImageFont.truetype(directory + font_name, size)
        except:
            await self.bot.say("I could not find that font file.")
            return

        self.settings[server.id]["FONT"]["WELCOME_FONT"]["PATH"] = directory + font_name
        self.settings[server.id]["FONT"]["WELCOME_FONT"]["SIZE"] = size
        await self.save_settings()
        await self.bot.say("Welcome font changed to: {}".format(font_name[:-4]))
        pass

    @imgwelcome.command(name="version", pass_context=True, hidden=True)
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
        channel_object = self.bot.get_channel(channelid)
        await self.bot.send_typing(channel_object)
        image_object = await self._create_welcome(member, member.avatar_url)
        await self.bot.send_file(channel_object, image_object, filename="welcome.png")
        if ((len(member.server.members) % 100) == 0 or (len(member.server.members) == 1337)) and self.settings[server.id]["BONUSES"]["SPECIAL_USERS"]:
            msg = "\N{PARTY POPPER} Thanks <@" + member.id + ">, you're the ***" + str(len(member.server.members)) + "*** th user on this server! \N{PARTY POPPER}"
            await self.bot.send_message(channel_object, msg)
        date_join = datetime.datetime.strptime(str(member.created_at), "%Y-%m-%d %H:%M:%S.%f")
        date_now = datetime.datetime.now(datetime.timezone.utc)
        date_now = date_now.replace(tzinfo=None)
        since_join = date_now - date_join
        if since_join.days < 7 and self.settings[server.id]["BONUSES"]["ACCOUNT_WARNINGS"]:
            await self.bot.send_message(channel_object, "\N{WARNING SIGN} This account was created less than a week ago (" + str(since_join.days) + " days ago)")


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
