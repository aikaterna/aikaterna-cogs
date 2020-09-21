import asyncio
import aiohttp
from bs4 import BeautifulSoup
import copy
import datetime
import discord
import feedparser
from fuzzywuzzy import fuzz
import imghdr
import io
import logging
import re
import time
from types import MappingProxyType, SimpleNamespace
from urllib.parse import urlparse

from redbot.core import checks, commands, Config
from redbot.core.utils.chat_formatting import bold, box, escape, pagify

from .quiet_template import QuietTemplate
from .rss_feed import RssFeed
from .tag_type import INTERNAL_TAGS, VALID_IMAGES, TagType

log = logging.getLogger("red.aikaterna.rss")


__version__ = "1.0.1"


class RSS(commands.Cog):
    """RSS feeds for your server."""

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, 2761331001, force_registration=True)
        self.config.register_channel(feeds={})

        self._post_queue = asyncio.PriorityQueue()
        self._post_queue_size = None

        self._read_feeds_loop = None

    def initialize(self):
        self._read_feeds_loop = self.bot.loop.create_task(self.read_feeds())

    def cog_unload(self):
        if self._read_feeds_loop:
            self._read_feeds_loop.cancel()

    def _add_content_images(self, bs4_soup: BeautifulSoup, rss_object: feedparser.util.FeedParserDict):
        """
        $content_images should always be marked as a special tag as the tags will
        be dynamically generated based on the content included in the latest post.
        """
        content_images = bs4_soup.find_all("img")
        if content_images:
            for i, image in enumerate(content_images):
                tag_name = f"content_image{str(i + 1).zfill(2)}"
                rss_object[tag_name] = image["src"]
                rss_object["is_special"].append(tag_name)
        return rss_object

    async def _add_feed(self, ctx, feed_name: str, url: str):
        """Helper for rss add."""
        rss_exists = await self._check_feed_existing(ctx, feed_name)
        if not rss_exists:
            feedparser_obj = await self._fetch_feedparser_object(url)
            if not feedparser_obj:
                await ctx.send("Couldn't fetch that feed for some reason.")
                return
            feedparser_plus_obj = await self._add_to_feedparser_object(feedparser_obj[0], url)
            rss_object = await self._convert_feedparser_to_rssfeed(feed_name, feedparser_plus_obj, url)

            async with self.config.channel(ctx.channel).feeds() as feed_data:
                feed_data[feed_name] = rss_object.to_json()
            msg = (
                f'Feed "{feed_name}" added. List the template tags with `{ctx.prefix}rss listtags` '
                f"and modify the template using `{ctx.prefix}rss template`."
            )
            await ctx.send(msg)
        else:
            await ctx.send(f"There is already an existing feed named {bold(feed_name)}.")
            return

    def _add_generic_html_plaintext(self, bs4_soup: BeautifulSoup):
        """
        Bs4's .text attribute on a soup strips newlines and spaces
        This provides newlines and more readable content.
        """
        text = ""
        for element in bs4_soup.descendants:
            if isinstance(element, str):
                text += element
            elif element.name == "br" or element.name == "p" or element.name == "li":
                text += "\n"
        text = re.sub("\\n+", "\n", text)
        text = text.replace("*", "\\*")

        return escape(text)

    async def _append_bs4_tags(self, rss_object: feedparser.util.FeedParserDict, url: str):
        """Append bs4-discovered tags to an rss_feed/feedparser object."""
        rss_object["is_special"] = []
        soup = None

        temp_rss_obect = copy.deepcopy(rss_object)
        for tag_name, tag_content in temp_rss_obect.items():
            if tag_name in INTERNAL_TAGS:
                continue

            tag_content_check = await self._get_tag_content_type(tag_content)

            if tag_content_check == TagType.HTML:

                # this is a tag that is only html content
                try:
                    soup = BeautifulSoup(tag_content, "html.parser")
                except TypeError:
                    pass

                # this is a standard html format summary_detail tag
                # the tag was determined to be html through the type attrib that
                # was attached from the feed publisher but it's really a dict.
                try:
                    soup = BeautifulSoup(tag_content["value"], "html.parser")
                except (KeyError, TypeError):
                    pass

                # this is a standard html format content or summary tag
                try:
                    soup = BeautifulSoup(tag_content[0]["value"], "html.parser")
                except (KeyError, TypeError):
                    pass

                rss_object[f"{tag_name}_plaintext"] = self._add_generic_html_plaintext(soup)

        # if media_thumbnail or media_content exists, return the first friendly url
        try:
            rss_object["media_content_plaintext"] = rss_object["media_content"][0]["url"]
        except KeyError:
            pass
        try:
            rss_object["media_thumbnail_plaintext"] = rss_object["media_thumbnail"][0]["url"]
        except KeyError:
            pass

        # change published_parsed into a datetime object for embed footers
        try:
            if isinstance(rss_object["published_parsed"], time.struct_time):
                rss_object["published_parsed"] = datetime.datetime(*rss_object["published_parsed"][:6])
        except KeyError:
            pass

        if soup:
            rss_object = self._add_content_images(soup, rss_object)

        # add special tag/special site formatter here if needed in the future

        return rss_object

    async def _check_feed_existing(self, ctx, feed_name: str):
        """Helper for rss functions."""
        rss_feed = await self.config.channel(ctx.channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            return False
        return True

    async def _delete_feed(self, ctx, feed_name: str):
        """Helper for rss delete."""
        rss_exists = await self._check_feed_existing(ctx, feed_name)

        if rss_exists:
            async with self.config.channel(ctx.channel).feeds() as rss_data:
                rss_data.pop(feed_name, None)
                return True
        return False

    async def _edit_template(self, ctx, feed_name: str, template: str):
        """Helper for rss template."""
        rss_exists = await self._check_feed_existing(ctx, feed_name)

        if rss_exists:
            async with self.config.channel(ctx.channel).feeds.all() as feed_data:
                if feed_name not in feed_data:
                    feed_data[feed_name] = {}
                feed_data[feed_name]["template"] = template
                return True
        return False

    def _get_channel_object(self, channel_id: int):
        """Helper for rss feed loop."""
        channel = self.bot.get_channel(channel_id)
        if channel and channel.permissions_for(channel.guild.me).send_messages:
            return channel
        return None

    async def _get_feed_names(self, channel: discord.TextChannel):
        """Helper for rss list."""
        feed_list = []
        space = "\N{SPACE}"
        all_feeds = await self.config.channel(channel).feeds.all()
        if not all_feeds:
            return ["None."]
        longest_name_len = len(max(list(all_feeds.keys()), key=len))
        for name, data in all_feeds.items():
            extra_spacing = longest_name_len - len(name)
            feed_list.append(f"{name}{space * extra_spacing}  {data['url']}")
        return feed_list

    async def _get_tag_content_type(self, tag_content):
        """
        Tag content type can be:
            str, list, dict (FeedParserDict), bool, datetime.datetime object or time.struct_time
        """
        try:
            if tag_content["type"] == "text/html":
                return TagType(2)
        except (KeyError, TypeError):
            html_tags = ["<a>", "<a href", "<img", "<p>", "<b>", "</li>", "</ul>"]
            if any(word in str(tag_content) for word in html_tags):
                return TagType(2)

        if isinstance(tag_content, dict):
            return TagType(3)
        elif isinstance(tag_content, list):
            return TagType(4)
        else:
            return TagType(1)

    async def _get_url_content(self, url):
        """Helper for rss add/_valid_url."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    html = await resp.read()
            return html
        except Exception:
            log.error(f"Failure accessing feed at url:\n\t{url}", exc_info=True)
            return None

    async def _fetch_feedparser_object(self, url: str):
        """Get all feedparser entries from a url."""
        html = await self._get_url_content(url)
        feedparser_obj = feedparser.parse(html)

        if feedparser_obj.bozo:
            log.debug(f"Feed at {url} is bad or took too long to respond.")
            return None

        return feedparser_obj.entries

    async def _add_to_feedparser_object(self, feedparser_obj: feedparser.util.FeedParserDict, url: str):
        """
        Input: A feedparser object
        Process: Append custom tags to the object from the custom formatters
        Output: A feedparser object with additional attributes
        """
        feedparser_plus_obj = await self._append_bs4_tags(feedparser_obj, url)
        feedparser_plus_obj["template_tags"] = sorted(feedparser_plus_obj.keys())

        return feedparser_plus_obj

    async def _convert_feedparser_to_rssfeed(
        self, feed_name: str, feedparser_plus_obj: feedparser.util.FeedParserDict, url: str
    ):
        """Converts any feedparser/feedparser_plus object to an RssFeed object."""
        rss_object = RssFeed(
            name=feed_name.lower(),
            last_title=feedparser_plus_obj["title"],
            template="$title\n$link",
            url=url,
            template_tags=feedparser_plus_obj["template_tags"],
            is_special=feedparser_plus_obj["is_special"],
            embed=True,
        )

        return rss_object

    async def _update_last_scraped(self, channel: discord.TextChannel, feed_name: str, current_feed_title: str):
        """Updates last title seen for comparison on next feed pull."""
        async with self.config.channel(channel).feeds() as feed_data:
            feed_data[feed_name]["last_title"] = current_feed_title

    async def _valid_url(self, url: str):
        """Helper for rss add."""
        try:
            result = urlparse(url)
        except:
            log.debug(f"failed to resolve {url}")
            return False

        if all([result.scheme, result.netloc, result.path]):
            text = await self._get_url_content(url)
            if not text:
                log.debug(f"no text from _get_url_content: {url}")
                return False

            rss = feedparser.parse(text)
            if rss.bozo:
                log.debug(f"bozo feed at {url}")
                return False
            else:
                return True
        else:
            log.debug(f"failed to urlparse {url}")
            return False

    async def _validate_image(self, url: str):
        """Helper for _get_current_feed_embed."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    image = await resp.read()
            img = io.BytesIO(image)
            image_test = imghdr.what(img)
            return image_test
        except aiohttp.client_exceptions.InvalidURL:
            return None
        except Exception:
            log.error(f"Failure accessing image in embed feed at url:\n\t{url}", exc_info=True)
            return None

    @commands.guild_only()
    @commands.group()
    @checks.mod_or_permissions(manage_channels=True)
    async def rss(self, ctx):
        """RSS feed stuff."""
        pass

    @rss.command(name="add")
    async def _rss_add(self, ctx, feed_name: str, url: str):
        """Add an RSS feed to the current channel."""
        valid_url = await self._valid_url(url)
        if valid_url:
            await self._add_feed(ctx, feed_name.lower(), url)
        else:
            await ctx.send("Invalid or unavailable URL.")

    @rss.group(name="embed")
    async def _rss_embed(self, ctx):
        """Embed feed settings."""
        pass

    @_rss_embed.command(name="color", aliases=["colour"])
    async def _rss_embed_color(self, ctx, feed_name: str, *, color: discord.Color = None):
        """
        Set an embed color for a feed.

        Use this command with no color to reset to the default.
        `color` must be a hex code like #990000 or a [Discord color name](https://discordpy.readthedocs.io/en/latest/api.html#colour)
        """
        rss_feed = await self.config.channel(ctx.channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("That feed name doesn't exist in this channel.")
            return

        embed_toggle = rss_feed["embed"]
        embed_state_message = ""
        if not embed_toggle:
            embed_state_message += (
                f"{bold(feed_name)} is not currently set to be in an embed. "
                f"Toggle it on with `{ctx.prefix}rss embed toggle`.\n"
            )

        if not color:
            async with self.config.channel(ctx.channel).feeds() as feed_data:
                feed_data[feed_name]["embed_color"] = None
            await ctx.send(
                f"{embed_state_message}The color for {bold(feed_name)} has been reset. "
                "Use this command with a color argument to set a color for this feed."
            )

            return

        async with self.config.channel(ctx.channel).feeds() as feed_data:
            feed_data[feed_name]["embed_color"] = f"0x{str(color).lstrip('#')}"

        await ctx.send(f"Embed color for {bold(feed_name)} set to {str(color)}.")

    @_rss_embed.command(name="image")
    async def _rss_embed_image(self, ctx, feed_name: str, image_tag_name: str = None):
        """
        Set a tag to be a large embed image.

        This image will be applied to the last embed in the paginated list.
        Use this command with no image_tag_name to clear the embed image.
        """
        rss_feed = await self.config.channel(ctx.channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("That feed name doesn't exist in this channel.")
            return

        embed_toggle = rss_feed["embed"]
        embed_state_message = ""
        if not embed_toggle:
            embed_state_message += (
                f"{bold(feed_name)} is not currently set to be in an embed. "
                f"Toggle it on with `{ctx.prefix}rss embed toggle`.\n"
            )

        if image_tag_name is not None:
            if image_tag_name.startswith("$"):
                image_tag_name = image_tag_name.strip("$")

        async with self.config.channel(ctx.channel).feeds() as feed_data:
            feed_data[feed_name]["embed_image"] = image_tag_name

        if image_tag_name:
            await ctx.send(f"{embed_state_message}Embed image set to the ${image_tag_name} tag.")
        else:
            await ctx.send(
                "Embed image has been cleared. Use this command with a tag name if you intended to set an image tag."
            )

    @_rss_embed.command(name="thumbnail")
    async def _rss_embed_thumbnail(self, ctx, feed_name: str, thumbnail_tag_name: str = None):
        """
        Set a tag to be a thumbnail image.

        This thumbnail will be applied to the first embed in the paginated list.
        Use this command with no thumbnail_tag_name to clear the embed thumbnail.
        """
        rss_feed = await self.config.channel(ctx.channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("That feed name doesn't exist in this channel.")
            return

        embed_toggle = rss_feed["embed"]
        embed_state_message = ""
        if not embed_toggle:
            embed_state_message += (
                f"{bold(feed_name)} is not currently set to be in an embed. "
                f"Toggle it on with `{ctx.prefix}rss embed toggle`.\n"
            )

        if thumbnail_tag_name is not None:
            if thumbnail_tag_name.startswith("$"):
                thumbnail_tag_name = thumbnail_tag_name.strip("$")

        async with self.config.channel(ctx.channel).feeds() as feed_data:
            feed_data[feed_name]["embed_thumbnail"] = thumbnail_tag_name

        if thumbnail_tag_name:
            await ctx.send(f"{embed_state_message}Embed thumbnail set to the ${thumbnail_tag_name} tag.")
        else:
            await ctx.send(
                "Embed thumbnail has been cleared. "
                "Use this command with a tag name if you intended to set a thumbnail tag."
            )

    @_rss_embed.command(name="toggle")
    async def _rss_embed_toggle(self, ctx, feed_name: str):
        """
        Toggle whether a feed is sent in an embed or not.
        
        If the bot doesn't have permissions to post embeds,
        the feed will always be plain text, even if the embed
        toggle is set.
        """
        rss_feed = await self.config.channel(ctx.channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("That feed name doesn't exist in this channel.")
            return

        embed_toggle = rss_feed["embed"]
        toggle_text = "disabled" if embed_toggle else "enabled"

        async with self.config.channel(ctx.channel).feeds() as feed_data:
            feed_data[feed_name]["embed"] = not embed_toggle

        await ctx.send(f"Embeds for {bold(feed_name)} are {toggle_text}.")

    @rss.command(name="force")
    async def _rss_force(self, ctx, feed_name: str):
        """Forces a feed alert."""
        feeds = await self.config.all_channels()
        try:
            feeds[ctx.channel.id]
        except KeyError:
            await ctx.send("There are no feeds in this channel.")
            return

        if feed_name not in feeds[ctx.channel.id]["feeds"]:
            await ctx.send("That feed name doesn't exist in this channel.")
            return

        rss_feed = feeds[ctx.channel.id]["feeds"][feed_name]
        await self.get_current_feed(ctx.channel, feed_name, rss_feed, force=True)

    @rss.command(name="list")
    async def _rss_list(self, ctx, channel: discord.TextChannel = None):
        """List currently available feeds for this channel, or a specific channel."""
        if not channel:
            channel = ctx.channel
        feeds = await self._get_feed_names(channel)
        msg = f"[ Available Feeds for #{channel.name} ]\n\n\t"
        if feeds:
            msg += "\n\t".join(sorted(feeds))
        else:
            msg += "\n\tNone."
        for page in pagify(msg, delims=["\n"], page_length=1800):
            await ctx.send(box(page, lang="ini"))

    @rss.command(name="listtags")
    async def _rss_list_tags(self, ctx, feed_name: str):
        """List the tags available from a specific feed."""
        rss_feed = await self.config.channel(ctx.channel).feeds.get_raw(feed_name, default=None)

        if not rss_feed:
            await ctx.send("No feed with that name in this channel.")
            return

        async with ctx.typing():
            await self._rss_list_tags_helper(ctx, rss_feed, feed_name)

    async def _rss_list_tags_helper(self, ctx, rss_feed: dict, feed_name: str):
        """Helper function for rss listtags."""
        msg = f"[ Available Tags for {feed_name} ]\n\n\t"
        feedparser_obj = await self._fetch_feedparser_object(rss_feed["url"])
        if not feedparser_obj:
            await ctx.send("Couldn't fetch that feed for some reason.")
            return
        feedparser_plus_obj = await self._add_to_feedparser_object(feedparser_obj[0], rss_feed["url"])

        for tag_name, tag_content in sorted(feedparser_plus_obj.items()):
            if tag_name in INTERNAL_TAGS:
                # these tags attached to the rss feed object are for internal handling options
                continue

            tag_content_check = await self._get_tag_content_type(tag_content)
            if tag_content_check == TagType.HTML:
                msg += f"[X] ${tag_name}\n\t"
            elif tag_content_check == TagType.DICT:
                msg += f"[\\] ${tag_name}  \n\t"
            elif tag_content_check == TagType.LIST:
                msg += f"[-] ${tag_name}  \n\t"
            elif tag_name in feedparser_plus_obj["is_special"]:
                msg += f"[*] ${tag_name}  \n\t"
            else:
                msg += f"[ ] ${tag_name}  \n\t"
        msg += "\n\n\t[X] = html | [\\] = dictionary | [-] = list | [ ] = plain text"
        msg += "\n\t[*] = specially-generated tag, may not be present in every post"

        await ctx.send(box(msg, lang="ini"))

    @rss.command(name="remove", aliases=["delete", "del"])
    async def _rss_remove(self, ctx, name: str):
        """Removes a feed from this channel."""
        success = await self._delete_feed(ctx, name)
        if success:
            await ctx.send("Feed deleted.")
        else:
            await ctx.send("Feed not found!")

    @rss.command(name="showtemplate")
    async def _rss_show_template(self, ctx, feed_name: str):
        """Show the template in use for a specific feed."""
        rss_feed = await self.config.channel(ctx.channel).feeds.get_raw(feed_name, default=None)

        if not rss_feed:
            await ctx.send("No feed with that name in this channel.")
            return

        space = "\N{SPACE}"
        embed_toggle = "[ ] Embed off" if not rss_feed["embed"] else "[X] Embed on"
        embed_image = (
            "[ ] Embed image off"
            if not rss_feed["embed_image"]
            else f"[X] Embed image tag:{space*6}${rss_feed['embed_image']}"
        )
        embed_thumbnail = (
            "[ ] Embed thumbnail off"
            if not rss_feed["embed_thumbnail"]
            else f"[X] Embed thumbnail tag:{space*2}${rss_feed['embed_thumbnail']}"
        )

        template_info = f"{embed_toggle}\n{embed_image}\n{embed_thumbnail}"
        rss_template = rss_feed["template"].replace("\n", "\\n").replace("\t", "\\t")
        await ctx.send(f"Template for {bold(feed_name)}:\n\n`{rss_template}`\n{box(template_info, lang='ini')}")

    @rss.command(name="template")
    async def _rss_template(self, ctx, feed_name: str, *, template: str):
        """
        Set a template for the feed alert.

        Each variable must start with $, valid variables can be found with `[p]rss listtags`.
        """
        template = template.replace("\\t", "\t")
        template = template.replace("\\n", "\n")
        success = await self._edit_template(ctx, feed_name, template)
        if success:
            await ctx.send("Template added successfully.")
        else:
            await ctx.send("Feed not found!")

    @rss.command(name="version", hidden=True)
    async def _rss_version(self, ctx):
        """Show the RSS version."""
        await ctx.send(f"RSS version {__version__}")

    async def get_current_feed(self, channel: discord.TextChannel, name: str, rss_feed: dict, *, force: bool = False):
        """Takes an RSS feed and builds an object with all extra tags"""
        log.debug(f"getting feed {name} on cid {channel.id}")
        url = rss_feed["url"]
        last_title = rss_feed["last_title"]
        if force:
            # clear out the last_title attrib because the feed fetcher
            # compares titles to know whether the next feed is valid
            # and that it can be posted - this is a force so we want it
            # to post no matter what
            last_title = ""
        template = rss_feed["template"]
        message = None

        feedparser_obj = await self._fetch_feedparser_object(url)
        if not feedparser_obj:
            return
        await self._update_last_scraped(channel, name, feedparser_obj[0].title)

        feedparser_plus_objects = []
        for entry in feedparser_obj:
            fuzzy_title_compare = fuzz.ratio(last_title, entry.title)

            # we only need one feed entry if this is from rss force or if this is a brand new feed
            if last_title == "":
                feedparser_plus_obj = await self._add_to_feedparser_object(entry, url)
                feedparser_plus_objects.append(feedparser_plus_obj)
                break

            # we want all the feeds we missed since the last title was recorded
            elif fuzzy_title_compare < 98:
                log.debug(f"New entry found for feed {name} on cid {channel.id}")
                feedparser_plus_obj = await self._add_to_feedparser_object(entry, url)
                feedparser_plus_objects.append(feedparser_plus_obj)

            # we found a match for a previous feed post
            else:
                log.debug(
                    f"Breaking rss entry loop for {name} on {channel.id}, we found where we are supposed to be caught up to"
                )
                break

        # post oldest first
        feedparser_plus_objects.reverse()

        for feedparser_plus_obj in feedparser_plus_objects:
            try:
                curr_title = feedparser_plus_obj.title
            except IndexError:
                log.debug(f"No entries found for feed {name} on cid {channel.id}")
                return

            to_fill = QuietTemplate(template)
            message = to_fill.quiet_safe_substitute(name=bold(name), **feedparser_plus_obj)

            if not message:
                log.debug(f"{name} feed in {channel.name} ({channel.id}) has no valid tags, not posting anything.")
                return

            embed_toggle = rss_feed["embed"]
            red_embed_settings = await self.bot.embed_requested(channel, None)
            embed_permissions = channel.permissions_for(channel.guild.me).embed_links

            if embed_toggle and red_embed_settings and embed_permissions:
                await self._get_current_feed_embed(channel, rss_feed, feedparser_plus_obj, message)
            else:
                for page in pagify(message, delims=["\n"]):
                    await channel.send(page)

            # This event can be used in 3rd-party using listeners.
            # This may (and most likely will) get changes in the future
            # so I suggest accepting **kwargs in the listeners using this event.
            #
            # channel: discord.TextChannel
            #     The channel feed alert went to.
            # feed_data: Mapping[str, Any]
            #     Read-only mapping with feed's data.
            #     The available data depends on what this cog needs
            #     and there most likely will be changes here in future.
            #     Available keys include: `name`, `template`, `url`, `embed`, etc.
            # feedparser_dict: Mapping[str, Any]
            #     Read-only mapping with parsed data from the feed.
            #     See documentation of feedparser.FeedParserDict for more information.
            # force: bool
            #     True if the update was forced (through `[p]rss force`), False otherwise.
            self.bot.dispatch(
                "aikaternacogs_rss_message",
                channel=channel,
                feed_data=MappingProxyType(rss_feed),
                feedparser_dict=MappingProxyType(feedparser_plus_obj),
                force=force,
            )

    async def _get_current_feed_embed(
        self,
        channel: discord.TextChannel,
        rss_feed: dict,
        feedparser_plus_obj: feedparser.util.FeedParserDict,
        message: str,
    ):
        embed_list = []
        for page in pagify(message, delims=["\n"]):
            embed = discord.Embed(description=page)
            if rss_feed["embed_color"]:
                color = int(rss_feed["embed_color"], 16)
                embed.color = discord.Color(color)
            embed_list.append(embed)

        # Add published timestamp to the last footer if it exists
        try:
            published_time = feedparser_plus_obj["published_parsed"]
            embed = embed_list[-1]
            embed.timestamp = published_time
        except KeyError:
            pass

        # Add embed image to last embed if it's set
        try:
            embed_image_tag = rss_feed["embed_image"]
            embed_image_url = feedparser_plus_obj[embed_image_tag]
            img_type = await self._validate_image(embed_image_url)
            if img_type in VALID_IMAGES:
                embed = embed_list[-1]
                embed.set_image(url=embed_image_url)
        except KeyError:
            pass

        # Add embed thumbnail to first embed if it's set
        try:
            embed_thumbnail_tag = rss_feed["embed_thumbnail"]
            embed_thumbnail_url = feedparser_plus_obj[embed_thumbnail_tag]
            img_type = await self._validate_image(embed_thumbnail_url)
            if img_type in VALID_IMAGES:
                embed = embed_list[0]
                embed.set_thumbnail(url=embed_thumbnail_url)
        except KeyError:
            pass

        for embed in embed_list:
            await channel.send(embed=embed)

    async def read_feeds(self):
        """Feed poster loop."""
        await self.bot.wait_until_red_ready()
        await self._put_feeds_in_queue()
        self._post_queue_size = self._post_queue.qsize()
        while True:
            try:
                queue_item = await self._get_next_in_queue()
                if not queue_item:
                    # the queue is empty
                    config_data = await self.config.all_channels()
                    if not config_data:
                        # nothing to check
                        log.debug(f"Sleeping, nothing to do")
                        await asyncio.sleep(30)
                        continue
                    if self._post_queue_size < 300:
                        # less than 300 entries to check means 1/sec check times
                        # the wait is (5 min - entry count) before posting again
                        wait = 300 - self._post_queue_size
                    else:
                        # more than 300 entries means we used the whole 5 min
                        # to check and post feeds so don't wait any longer to start again
                        wait = 0

                    log.debug(f"Waiting {wait}s before starting...")
                    await asyncio.sleep(wait)
                    await self._put_feeds_in_queue()
                    continue
                else:
                    try:
                        # queue_item is a List of channel_priority: int, total_priority: int, queue_item: SimpleNamespace
                        await self.get_current_feed(
                            queue_item[2].channel, queue_item[2].feed_name, queue_item[2].feed_data
                        )
                    except aiohttp.client_exceptions.InvalidURL:
                        log.debug(f"Feed at {url} is bad or took too long to respond.")
                        continue

                    if self._post_queue_size < 300:
                        wait = 1
                    else:
                        wait = (300 - 10) / self._post_queue_size
                    log.debug(f"sleeping for {wait}...")
                    await asyncio.sleep(wait)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.exception(e, exc_info=e)
                break

    async def _put_feeds_in_queue(self):
        log.debug("Putting feeds in queue")
        try:
            config_data = await self.config.all_channels()
            total_index = 0
            for channel_id, channel_feed_list in config_data.items():
                channel = self._get_channel_object(channel_id)
                if not channel:
                    log.info(
                        f"Response channel {channel_id} not found or no perms to send messages, removing channel from config"
                    )
                    await self.config.channel_from_id(int(channel_id)).clear()  # Remove entries from dead channel
                    continue

                for feed_key, feed in channel_feed_list.items():
                    for feed_name, feed_data in feed.items():
                        rss_feed = SimpleNamespace(channel=channel, feed_name=feed_name, feed_data=feed_data)
                        keys = list(feed.keys())
                        channel_index = keys.index(feed_name)
                        total_index += 1
                        queue_entry = [channel_index, total_index, rss_feed]
                        log.debug(f"Putting {channel_index}-{total_index}-{channel}-{feed_name} in queue")
                        await self._post_queue.put(queue_entry)

        except Exception as e:
            log.exception(e, exc_info=e)

    async def _get_next_in_queue(self):
        try:
            to_check = self._post_queue.get_nowait()
        except asyncio.queues.QueueEmpty:
            return None
        return to_check
