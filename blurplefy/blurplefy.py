#  Ported for Red v3 from: https://github.com/Rocked03/Blurplefied
#  pip install python-resize-image
#  pip install pillow

import discord
from PIL import Image, ImageEnhance, ImageSequence
from io import BytesIO
import aiohttp
import asyncio
import datetime
import io
import math
from resizeimage import resizeimage
from redbot.core import Config, commands, checks

blurple = (114, 137, 218)
blurplehex = 0x7289DA
darkblurple = (78, 93, 148)
white = (255, 255, 255)


class Blurplefy(commands.Cog):
    """Blurplefy images and check blurple content of images."""

    async def red_delete_data_for_user(self, **kwargs):
        """ Nothing to delete """
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
        """Toggle a role award for having a blurple profile picture."""
        blurple_role_id = await self.config.guild(ctx.guild).blurple_role()
        if blurple_role_id is None:
            await ctx.send("Enter the role name to award: it needs to be a valid, already existing role.")

            def check(m):
                return m.author == ctx.author

            try:
                blurple_role = await ctx.bot.wait_for("message", timeout=15.0, check=check)
                blurple_role_obj = discord.utils.get(ctx.guild.roles, name=blurple_role.content)
                if blurple_role_obj is None:
                    return await ctx.send("No role with that name.")
                return await ctx.invoke(self.blurpleroleset, role_name=blurple_role_obj)
            except asyncio.TimeoutError:
                return await ctx.send("No role entered, try again later.")

        role_enabled = await self.config.guild(ctx.guild).role_enabled()
        await self.config.guild(ctx.guild).role_enabled.set(not role_enabled)

        if not role_enabled:
            word = "enabled"
        else:
            word = "disabled"
        await ctx.send("Blurple role awarding {}.".format(word))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def blurpleroleset(self, ctx, *, role_name: discord.Role):
        """Sets the role to award if blurplerole is on."""
        await self.config.guild(ctx.guild).blurple_role.set(role_name.id)
        blurple_role_id = await self.config.guild(ctx.guild).blurple_role()
        blurple_role_obj = discord.utils.get(ctx.guild.roles, id=blurple_role_id)
        await ctx.send("Blurple award role set to: {}.".format(blurple_role_obj.name))
        blurple_role_enabled = await self.config.guild(ctx.guild).role_enabled()
        if not blurple_role_enabled:
            await ctx.invoke(self.blurplerole)

    async def blurplefy(self, ctx, user: discord.Member = None):
        """Blurplefy a user or image."""
        picture = None
        await ctx.send("{}, starting blurple image analysis.".format(ctx.message.author.mention))
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
            async with self.session.request("GET", str(picture)) as r:
                response = await r.read()
        except ValueError:
            await ctx.send("{}, please link a valid image URL.".format(ctx.author.display_name))
            return

    @commands.guild_only()
    @commands.command()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
    async def blurple(self, ctx, user: discord.Member = None):
        """Check a user or uploaded image for blurple content."""
        picture = None
        await ctx.send("{}, starting blurple image analysis.".format(ctx.message.author.mention))
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
            async with self.session.request("GET", str(picture)) as r:
                response = await r.read()
        except ValueError:
            await ctx.send("{}, please link a valid image URL.".format(ctx.author.display_name))
            return
        try:
            im = Image.open(BytesIO(response))
        except Exception:
            await ctx.send("{}, please link a valid image URL.".format(ctx.author.display_name))
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
            await ctx.send("{}, image resized smaller for easier processing.".format(ctx.message.author.display_name))

        image = self.blurple_imager(im, imsize)
        image = discord.File(fp=image, filename="image.png")

        blurplenesspercentage = round(((nooftotalpixels / noofpixels) * 100), 2)
        percentblurple = round(((noofblurplepixels / noofpixels) * 100), 2)
        percentdblurple = round(((noofdarkblurplepixels / noofpixels) * 100), 2)
        percentwhite = round(((noofwhitepixels / noofpixels) * 100), 2)

        embed = discord.Embed(title="", colour=0x7289DA)
        embed.add_field(name="Total amount of Blurple", value="{}%".format(blurplenesspercentage), inline=False)
        embed.add_field(name="Blurple (rgb(114, 137, 218))", value="{}%".format(percentblurple), inline=True)
        embed.add_field(name="White (rgb(255, 255, 255))", value="{}\%".format(percentwhite), inline=True)
        embed.add_field(
            name="Dark Blurple (rgb(78, 93, 148))", value="{}\%".format(percentdblurple), inline=True,
        )
        embed.add_field(
            name="Guide",
            value="Blurple, White, Dark Blurple =  \nBlurple, White, and Dark Blurple (respectively) \nBlack = Not Blurple, White, or Dark Blurple",
            inline=False,
        )
        embed.set_footer(
            text="Please note: Discord slightly reduces quality of the images, therefore the percentages may be slightly inaccurate. | Content requested by {}".format(
                ctx.author
            )
        )
        embed.set_image(url="attachment://image.png")
        embed.set_thumbnail(url=picture)
        await ctx.send(embed=embed, file=image)

        blurple_role_enabled = await self.config.guild(ctx.guild).role_enabled()
        if role_check and blurple_role_enabled:
            blurple_role_id = await self.config.guild(ctx.guild).blurple_role()
            blurple_role_obj = discord.utils.get(ctx.guild.roles, id=blurple_role_id)
            if (
                blurplenesspercentage > 75
                and picture == ctx.author.avatar_url
                and blurple_role_obj not in ctx.author.roles
                and percentblurple > 5
            ):
                await ctx.send(
                    "{}, as your profile pic has enough blurple (over 75% in total and over 5% blurple), you have recieved the role **{}**!".format(
                        ctx.message.author.display_name, blurple_role_obj.name
                    )
                )
                await ctx.author.add_roles(blurple_role_obj)
            elif picture == ctx.author.avatar_url and blurple_role_obj not in ctx.author.roles:
                await ctx.send(
                    "{}, your profile pic does not have enough blurple (over 75% in total and over 5% blurple), therefore you are not eligible for the role {}.".format(
                        ctx.message.author.display_name, blurple_role_obj.name
                    )
                )

    @commands.guild_only()
    @commands.command()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
    async def blurplefy(self, ctx, user: discord.Member = None):
        """Blurplefy a user or uploaded image."""
        picture = None
        await ctx.send("{}, starting blurple image analysis.".format(ctx.message.author.mention))
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
            async with self.session.request("GET", str(picture)) as r:
                response = await r.read()
        except ValueError:
            await ctx.send("{}, please link a valid image URL.".format(ctx.author.display_name))
            return
        try:
            im = Image.open(BytesIO(response))
        except Exception:
            await ctx.send("{}, please link a valid image URL.".format(ctx.author.display_name))
            return

        imsize = list(im.size)
        impixels = imsize[0] * imsize[1]
        # 1250x1250 = 1562500
        maxpixelcount = 1562500

        try:
            i = im.info["version"]
            isgif = True
            gifloop = int(im.info["loop"])
        except Exception:
            isgif = False

        await ctx.send("{}, image fetched, analyzing image...".format(ctx.message.author.display_name))

        if impixels > maxpixelcount:
            downsizefraction = math.sqrt(maxpixelcount / impixels)
            im = resizeimage.resize_width(im, (imsize[0] * downsizefraction))
            imsize = list(im.size)
            impixels = imsize[0] * imsize[1]
            await ctx.send("{}, image resized smaller for easier processing".format(ctx.message.author.display_name))

        if isgif is False:
            image = self.imager(im, imsize)
        else:
            image = self.gifimager(im, gifloop, imsize)
        await ctx.send("{}, image data extracted.".format(ctx.author.display_name))
        if isgif is False:
            image = discord.File(fp=image, filename="image.png")
        else:
            image = discord.File(fp=image, filename="image.gif")

        try:
            embed = discord.Embed(title="", colour=0x7289DA)
            embed.set_author(name="Blurplefier - makes your image blurple!")
            if isgif is False:
                embed.set_image(url="attachment://image.png")
            else:
                embed.set_image(url="attachment://image.gif")
            embed.set_footer(
                text="Please note - This blurplefier is automated and therefore may not always give you the best result. | Content requested by {}".format(
                    ctx.author
                )
            )
            embed.set_thumbnail(url=picture)
            await ctx.send(embed=embed, file=image)
        except Exception:
            await ctx.send(
                "{}, whoops! It looks like this gif is too big to upload. Try a smaller image (less than 8mb).".format(
                    ctx.author.name
                )
            )

    @staticmethod
    def blurple_imager(im, imsize):
        colourbuffer = 20
        global noofblurplepixels
        noofblurplepixels = 0
        global noofwhitepixels
        noofwhitepixels = 0
        global noofdarkblurplepixels
        noofdarkblurplepixels = 0
        global nooftotalpixels
        nooftotalpixels = 0
        global noofpixels
        noofpixels = 0

        blurple = (114, 137, 218)
        darkblurple = (78, 93, 148)
        white = (255, 255, 255)

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
                    if not (blurple[i] + colourbuffer > pixel[i] > blurple[i] - colourbuffer):
                        checkblurple = 0
                    if not (darkblurple[i] + colourbuffer > pixel[i] > darkblurple[i] - colourbuffer):
                        checkdarkblurple = 0
                    if not (white[i] + colourbuffer > pixel[i] > white[i] - colourbuffer):
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

        image_file_object = io.BytesIO()
        im.save(image_file_object, format="png")
        image_file_object.seek(0)
        return image_file_object

    @staticmethod
    def imager(im, imsize):
        im = im.convert(mode="L")
        im = ImageEnhance.Contrast(im).enhance(1000)
        im = im.convert(mode="RGB")

        img = im.load()

        for x in range(imsize[0] - 1):
            i = 1
            for y in range(imsize[1] - 1):
                pixel = img[x, y]

                if pixel != (255, 255, 255):
                    img[x, y] = (114, 137, 218)

        image_file_object = io.BytesIO()
        im.save(image_file_object, format="png")
        image_file_object.seek(0)
        return image_file_object

    @staticmethod
    def gifimager(im, gifloop, imsize):
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
                        img[x, y] = (114, 137, 218)
            newgif.append(frame)

        image_file_object = io.BytesIO()
        gif = newgif[0]
        gif.save(image_file_object, format="gif", save_all=True, append_images=newgif[1:], loop=0)
        image_file_object.seek(0)
        return image_file_object

    @commands.command()
    async def countdown(self, ctx):
        """Countdown to Discord's 6th Anniversary."""
        embed = discord.Embed(name="", colour=0x7289DA)
        timeleft = datetime.datetime(2020, 5, 13) + datetime.timedelta(hours=7) - datetime.datetime.utcnow()
        embed.set_author(name="Time left until Discord's 6th Anniversary")
        if int(timeleft.total_seconds()) < 0:
            timeleft = datetime.datetime(2021, 5, 13) + datetime.timedelta(hours=7) - datetime.datetime.utcnow()
            embed.set_author(name="Time left until Discord's 6th Anniversary")
        embed.add_field(
            name="Countdown to midnight, May 13, California time (UTC-7):",
            value=("{}".format(self._dynamic_time(int(timeleft.total_seconds())))),
        )
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

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
