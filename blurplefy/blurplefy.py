#  Ported for Red v3 from: https://github.com/Rocked03/Blurplefied

import aiohttp
import asyncio
import datetime
from io import BytesIO
import logging
import math
from PIL import Image, ImageEnhance, ImageSequence, UnidentifiedImageError
import random
import sys
from resizeimage import resizeimage
from types import SimpleNamespace

import discord

from redbot.core import Config, commands, checks
from redbot.core.utils.predicates import MessagePredicate


log = logging.getLogger("red.aikaterna.blurplefy")


# LEGACY_BLURPLE = (114, 137, 218)
# LEGACY_DARK_BLURPLE = (78, 93, 148)
BLURPLE = (88, 101, 242)
DARK_BLURPLE = (69, 79, 191)
WHITE = (255, 255, 255)


class Blurplefy(commands.Cog):
    """Blurplefy images and check blurple content of images."""

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    def __init__(self, bot):
        """Blurplefy images and check blurple content of images."""
        self.bot = bot
        self.config = Config.get_conf(self, 2778931480, force_registration=True)

        default_guild = {"role_enabled": False, "blurple_role": None}

        self.config.register_guild(**default_guild)
        self.session = aiohttp.ClientSession()

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def blurplerole(self, ctx):
        """Toggle a role award for having a blurple profile picture.

        A user's profile picture will be checked when they use [p]blurple.
        """
        blurple_role_id = await self.config.guild(ctx.guild).blurple_role()
        if blurple_role_id is None:
            msg = "Enter the role name to award: it needs to be a valid, already existing role, "
            msg += "and the name must match exactly (don't use a role mention)."
            await ctx.send(msg)
            pred = MessagePredicate.same_context(ctx)
            try:
                blurple_role = await ctx.bot.wait_for("message", timeout=15.0, check=pred)
                blurple_role_obj = discord.utils.get(ctx.guild.roles, name=blurple_role.content)
                if blurple_role_obj is None:
                    return await ctx.send("No role with that name.")
                return await ctx.invoke(self.blurpleroleset, role_name=blurple_role_obj)
            except asyncio.TimeoutError:
                return await ctx.send("No role entered, try again later.")

        role_enabled = await self.config.guild(ctx.guild).role_enabled()
        await self.config.guild(ctx.guild).role_enabled.set(not role_enabled)
        await ctx.send(f"Blurple role awarding {'enabled' if not role_enabled else 'disabled'}.")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def blurpleroleset(self, ctx, *, role_name: discord.Role):
        """Sets the role to award if blurplerole is on."""
        await self.config.guild(ctx.guild).blurple_role.set(role_name.id)
        blurple_role_id = await self.config.guild(ctx.guild).blurple_role()
        blurple_role_obj = discord.utils.get(ctx.guild.roles, id=blurple_role_id)
        await ctx.send(f"Blurple award role set to: {blurple_role_obj.name}.")
        blurple_role_enabled = await self.config.guild(ctx.guild).role_enabled()
        if not blurple_role_enabled:
            await ctx.invoke(self.blurplerole)

    async def blurplefy(self, ctx, user: discord.Member = None):
        """Blurplefy a user or image."""
        picture = None
        link = ctx.message.attachments
        if user is None and not link:
            picture = ctx.author.avatar_url
        else:
            if not user:
                if len(link) != 0:
                    for image in link:
                        picture = image.url
            else:
                picture = user.avatar_url
        try:
            async with self.session.get(str(picture)) as r:
                response = await r.read()
        except ValueError:
            await ctx.send(f"{ctx.author.display_name}, please link a valid image URL.")
            return

    @commands.guild_only()
    @commands.command()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
    async def blurple(self, ctx, user: discord.Member = None):
        """Check a user or an attached uploaded image for blurple content."""
        await ctx.trigger_typing()
        picture = None
        link = ctx.message.attachments
        if user is None and not link:
            picture = ctx.author.avatar_url
            role_check = True
        elif not user:
            if len(link) != 0:
                for image in link:
                    picture = image.url
                    role_check = False
        else:
            picture = user.avatar_url
            role_check = False

        try:
            async with self.session.get(str(picture)) as r:
                response = await r.read()
        except ValueError:
            await ctx.send(f"{ctx.author.display_name}, please link a valid image URL.")
            return
        try:
            im = Image.open(BytesIO(response))
        except UnidentifiedImageError:
            await ctx.send(f"{ctx.author.display_name}, this doesn't look like an image.")
            return
        except Exception as exc:
            log.exception("Blurplefy encountered an error:\n ", exc_info=exc)
            await ctx.send(f"{ctx.author.display_name}, please link a valid image URL.")
            return

        im = im.convert("RGBA")
        imsize = list(im.size)
        impixels = imsize[0] * imsize[1]
        # 1250x1250 = 1562500
        maxpixelcount = 1562500

        if impixels > maxpixelcount:
            downsizefraction = math.sqrt(maxpixelcount / impixels)
            im = resizeimage.resize_width(im, (imsize[0] * downsizefraction))
            imsize = list(im.size)
            impixels = imsize[0] * imsize[1]

            msg = f"{ctx.author.display_name}, image resized smaller for easier processing."
            await ctx.send(msg)

        image_object = await self.blurple_imager(im, imsize)
        image = discord.File(fp=image_object.file, filename=f"{random.randint(1,10000)}_image.png")

        blurpleness_percentage = round(((image_object.nooftotalpixels / image_object.noofpixels) * 100), 2)
        percent_blurple = round(((image_object.noofblurplepixels / image_object.noofpixels) * 100), 2)
        percent_dblurple = round(((image_object.noofdarkblurplepixels / image_object.noofpixels) * 100), 2)
        percent_white = round(((image_object.noofwhitepixels / image_object.noofpixels) * 100), 2)

        embed = discord.Embed(title="", colour=0x7289DA)
        embed.add_field(name=f"Total amount of Blurple", value=f"{blurpleness_percentage}%", inline=False)
        embed.add_field(name=f"Blurple (rgb(88, 101, 242))", value=f"{percent_blurple}%", inline=True)
        embed.add_field(name=f"White (rgb(255, 255, 255))", value=f"{percent_white}%", inline=True)
        embed.add_field(name=f"Dark Blurple (rgb(69, 79, 191))", value=f"{percent_dblurple}%", inline=True)
        embed.add_field(
            name="Guide",
            value="Blurple, White, Dark Blurple =  \nBlurple, White, and Dark Blurple (respectively) \nBlack = Not Blurple, White, or Dark Blurple",
            inline=False,
        )
        embed.set_footer(
            text=f"Please note: Discord slightly reduces quality of the images, therefore the percentages may be slightly inaccurate.\nContent requested by {str(ctx.author)}"
        )
        embed.set_image(url="attachment://image.png")
        embed.set_thumbnail(url=picture)
        await ctx.send(embed=embed, file=image)

        blurple_role_enabled = await self.config.guild(ctx.guild).role_enabled()
        if role_check and blurple_role_enabled:
            blurple_role_id = await self.config.guild(ctx.guild).blurple_role()
            blurple_role_obj = discord.utils.get(ctx.guild.roles, id=blurple_role_id)
            if not blurple_role_obj:
                msg = "The role that is set for the blurple role doesn't exist, so I can't award the role to any qualifying users."
                return await ctx.send(msg)
            if not ctx.channel.permissions_for(ctx.me).manage_roles:
                msg = "I need the Manage Roles permission here to be able to add the set blurple role to users that have a qualifying profile picture set."
                return await ctx.send(msg)
            if (
                blurpleness_percentage > 75
                and picture == ctx.author.avatar_url
                and blurple_role_obj not in ctx.author.roles
                and percent_blurple > 5
            ):
                msg = f"{ctx.author.display_name}, as your profile pic has enough blurple (over 75% in total and over 5% blurple), "
                msg += f"you have recieved the role **{blurple_role_obj.name}**!"
                await ctx.send(msg)
                await ctx.author.add_roles(blurple_role_obj)
            elif picture == ctx.author.avatar_url and blurple_role_obj not in ctx.author.roles:
                msg = f"{ctx.author.display_name}, your profile pic does not have enough blurple (over 75% in total and over 5% blurple), "
                msg += f"therefore you are not eligible for the role {blurple_role_obj.name}."
                await ctx.send(msg)

    @commands.guild_only()
    @commands.command()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
    async def blurplefy(self, ctx, user: discord.Member = None):
        """Blurplefy a user or an uploaded image attached to the command."""
        await ctx.trigger_typing()
        picture = None
        link = ctx.message.attachments
        if user is None and not link:
            picture = ctx.author.avatar_url
        else:
            if not user:
                if len(link) != 0:
                    for image in link:
                        picture = image.url
            else:
                picture = user.avatar_url
        try:
            async with self.session.get(str(picture)) as r:
                response = await r.read()
        except ValueError:
            await ctx.send(f"{ctx.author.display_name}, please link a valid image URL.")
            return
        try:
            im = Image.open(BytesIO(response))
        except UnidentifiedImageError:
            await ctx.send(f"{ctx.author.display_name}, this doesn't look like an image.")
            return
        except Exception as exc:
            log.exception("Blurplefy encountered an error:\n ", exc_info=exc)
            await ctx.send(f"{ctx.author.display_name}, please link a valid image URL.")
            return

        imsize = list(im.size)
        impixels = imsize[0] * imsize[1]
        # 1250x1250 = 1562500
        maxpixelcount = 1562500

        try:
            i = im.info["version"]
            isgif = True
            gifloop = int(im.info["loop"])
        except KeyError:
            # no version key
            isgif = False
        except Exception as exc:
            log.exception("Blurplefy encountered an error:\n ", exc_info=exc)

        if impixels > maxpixelcount:
            downsizefraction = math.sqrt(maxpixelcount / impixels)
            im = resizeimage.resize_width(im, (imsize[0] * downsizefraction))
            imsize = list(im.size)
            impixels = imsize[0] * imsize[1]
            await ctx.send(f"{ctx.author.display_name}, image resized smaller for easier processing.")

        if isgif is False:
            image = await self.imager(im, imsize)
        else:
            image = await self.gifimager(im, gifloop, imsize)

        max_size = 8 * 1024 * 1024
        size = sys.getsizeof(image)
        if size > max_size:
            await ctx.send(
                f"{ctx.author.display_name}, whoops! It looks like this image is too big to upload. Try a smaller image (less than 8mb)."
            )
            return

        if isgif is False:
            image = discord.File(fp=image, filename="image.png")
        else:
            image = discord.File(fp=image, filename="image.gif")

        embed = discord.Embed(title="", colour=0x7289DA)
        embed.set_author(name="Blurplefier - makes your image blurple!")
        if isgif is False:
            embed.set_image(url="attachment://image.png")
        else:
            embed.set_image(url="attachment://image.gif")
        embed.set_footer(
            text=f"Please note - This blurplefier is automated and therefore may not always give you the best result.\nContent requested by {str(ctx.author)}"
        )
        embed.set_thumbnail(url=picture)
        await ctx.send(embed=embed, file=image)

    @staticmethod
    async def blurple_imager(im, imsize):
        colourbuffer = 20
        noofblurplepixels = 0
        noofwhitepixels = 0
        noofdarkblurplepixels = 0
        nooftotalpixels = 0
        noofpixels = 0

        img = im.load()
        for x in range(imsize[0]):
            i = 1
            for y in range(imsize[1]):
                pixel = img[x, y]
                check = 1
                checkblurple = 1
                checkwhite = 1
                checkdarkblurple = 1
                for i in range(3):
                    if not (BLURPLE[i] + colourbuffer > pixel[i] > BLURPLE[i] - colourbuffer):
                        checkblurple = 0
                    if not (DARK_BLURPLE[i] + colourbuffer > pixel[i] > DARK_BLURPLE[i] - colourbuffer):
                        checkdarkblurple = 0
                    if not (WHITE[i] + colourbuffer > pixel[i] > WHITE[i] - colourbuffer):
                        checkwhite = 0
                    if checkblurple == 0 and checkdarkblurple == 0 and checkwhite == 0:
                        check = 0
                if check == 0:
                    img[x, y] = (0, 0, 0, 255)
                if check == 1:
                    nooftotalpixels += 1
                if checkblurple == 1:
                    noofblurplepixels += 1
                if checkdarkblurple == 1:
                    noofdarkblurplepixels += 1
                if checkwhite == 1:
                    noofwhitepixels += 1
                noofpixels += 1

        image_file_object = BytesIO()
        im.save(image_file_object, format="png")
        image_file_object.seek(0)
        return SimpleNamespace(
            file=image_file_object,
            noofblurplepixels=noofblurplepixels,
            noofwhitepixels=noofwhitepixels,
            noofdarkblurplepixels=noofdarkblurplepixels,
            nooftotalpixels=nooftotalpixels,
            noofpixels=noofpixels,
        )

    @staticmethod
    async def imager(im, imsize):
        im = im.convert(mode="L")
        im = ImageEnhance.Contrast(im).enhance(1000)
        im = im.convert(mode="RGB")

        img = im.load()

        for x in range(imsize[0] - 1):
            i = 1
            for y in range(imsize[1] - 1):
                pixel = img[x, y]

                if pixel != (255, 255, 255):
                    img[x, y] = BLURPLE

        image_file_object = BytesIO()
        im.save(image_file_object, format="png")
        image_file_object.seek(0)
        return image_file_object

    @staticmethod
    async def gifimager(im, gifloop, imsize):
        frames = [frame.copy() for frame in ImageSequence.Iterator(im)]
        newgif = []

        for frame in frames:
            frame = frame.convert(mode="L")
            frame = ImageEnhance.Contrast(frame).enhance(1000)
            frame = frame.convert(mode="RGB")
            img = frame.load()

            for x in range(imsize[0]):
                i = 1
                for y in range(imsize[1]):
                    pixel = img[x, y]
                    if pixel != (255, 255, 255):
                        img[x, y] = BLURPLE
            newgif.append(frame)

        image_file_object = BytesIO()
        gif = newgif[0]
        gif.save(image_file_object, format="gif", save_all=True, append_images=newgif[1:], loop=0)
        image_file_object.seek(0)
        return image_file_object

    @commands.command()
    async def countdown(self, ctx):
        """Countdown to Discord's next anniversary."""
        embed = discord.Embed(name="\N{ZERO WIDTH SPACE}", colour=0x7289DA)
        now = datetime.datetime.utcnow()

        timeleft = datetime.datetime(now.year, 5, 13) + datetime.timedelta(hours=7) - datetime.datetime.utcnow()
        discord_years = now.year - 2015
        if timeleft.total_seconds() < 0:
            timeleft = (
                datetime.datetime((now.year + 1), 5, 13) + datetime.timedelta(hours=7) - datetime.datetime.utcnow()
            )
            discord_years = (now.year + 1) - 2015

        discord_years_suffix = self._get_suffix(discord_years)
        embed.set_author(name=f"Time left until Discord's {discord_years}{discord_years_suffix} Anniversary")
        time = self._dynamic_time(int(timeleft.total_seconds()))
        embed.add_field(name="Countdown to midnight, May 13, California time (UTC-7):", value=f"{time}")
        await ctx.send(embed=embed)

    @staticmethod
    def _dynamic_time(time):
        m, s = divmod(time, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        if d > 0:
            msg = "{0}d {1}h"
        elif d == 0 and h > 0:
            msg = "{1}h {2}m"
        elif d == 0 and h == 0 and m > 0:
            msg = "{2}m {3}s"
        elif d == 0 and h == 0 and m == 0 and s > 0:
            msg = "{3}s"
        else:
            msg = ""
        return msg.format(d, h, m, s)

    @staticmethod
    def _get_suffix(num):
        suffixes = {1: "st", 2: "nd", 3: "rd"}
        if 10 <= num % 100 <= 20:
            suffix = "th"
        else:
            suffix = suffixes.get(num % 10, "th")
        return suffix

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
