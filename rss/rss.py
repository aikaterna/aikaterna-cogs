import asyncio
import aiohttp
from bs4 import BeautifulSoup
import copy
import datetime
import discord
import feedparser
import imghdr
import io
import logging
import re
import time
from typing import Optional
from types import MappingProxyType, SimpleNamespace
from urllib.parse import urlparse

from redbot.core import checks, commands, Config
from redbot.core.utils.chat_formatting import bold, box, escape, humanize_list, pagify

from .color import Color
from .quiet_template import QuietTemplate
from .rss_feed import RssFeed
from .tag_type import INTERNAL_TAGS, VALID_IMAGES, TagType

log = logging.getLogger("red.aikaterna.rss")


__version__ = "1.3.4"


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
                try:
                    rss_object[tag_name] = image["src"]
                    rss_object["is_special"].append(tag_name)
                except KeyError:
                    pass
        return rss_object

    async def _add_feed(self, ctx, feed_name: str, channel: discord.TextChannel, url: str):
        """Helper for rss add."""
        rss_exists = await self._check_feed_existing(ctx, feed_name, channel)
        if not rss_exists:
            feedparser_obj = await self._fetch_feedparser_object(url)
            if not feedparser_obj:
                await ctx.send("Couldn't fetch that feed for some reason.")
                return

            # sort everything by time if a time value is present
            sorted_feed_by_post_time = await self._sort_by_post_time(feedparser_obj)

            # add additional tags/images/clean html
            feedparser_plus_obj = await self._add_to_feedparser_object(sorted_feed_by_post_time[0], url)
            rss_object = await self._convert_feedparser_to_rssfeed(feed_name, feedparser_plus_obj, url)

            async with self.config.channel(channel).feeds() as feed_data:
                feed_data[feed_name] = rss_object.to_json()
            msg = (
                f"Feed `{feed_name}` added in channel: {channel.mention}\n"
                f"List the template tags with `{ctx.prefix}rss listtags` "
                f"and modify the template using `{ctx.prefix}rss template`."
            )
            await ctx.send(msg)
        else:
            await ctx.send(f"There is already an existing feed named {bold(feed_name)} in {channel.mention}.")
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
        text = text.replace("SC_OFF", "").replace("SC_ON", "\n")
        text = text.replace("[link]", "").replace("[comments]", "")

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

            if tag_content_check == TagType.LIST:
                tags_list = []
                tags_content_counter = 0

                for list_item in tag_content:
                    list_item_check = await self._get_tag_content_type(list_item)

                    # for common "links" format or when "content" is a list
                    list_html_content_counter = 0
                    if list_item_check == TagType.HTML:
                        list_tags = ["value", "href"]
                        for tag in list_tags:
                            try:
                                url_check = await self._valid_url(list_item[tag], feed_check=False)
                                if not url_check:
                                    # bs4 will cry if you try to give it a url to parse, so let's only
                                    # parse non-url content
                                    tag_content = BeautifulSoup(list_item[tag], "html.parser")
                                    tag_content = self._add_generic_html_plaintext(tag_content)
                                else:
                                    tag_content = list_item[tag]
                                list_html_content_counter += 1
                                name = f"{tag_name}_plaintext{str(list_html_content_counter).zfill(2)}"
                                rss_object[name] = tag_content
                                rss_object["is_special"].append(name)
                            except (KeyError, TypeError):
                                pass

                    if list_item_check == TagType.DICT:
                        authors_content_counter = 0

                        # common "authors" tag format
                        try:
                            authors_content_counter += 1
                            name = f"{tag_name}_plaintext{str(authors_content_counter).zfill(2)}"
                            rss_object[name] = list_item["name"]
                            rss_object["is_special"].append(name)
                        except KeyError:
                            pass

                        # common "tags" tag format
                        try:
                            tag = list_item["term"]
                            tags_content_counter += 1
                            name = f"{tag_name}_plaintext{str(tags_content_counter).zfill(2)}"
                            rss_object[name] = tag
                            rss_object["is_special"].append(name)
                            tags_list.append(tag)
                        except KeyError:
                            pass

                    if len(tags_list) > 0:
                        rss_object["tags_list"] = tags_list
                        rss_object["tags_plaintext_list"] = humanize_list(tags_list)
                        rss_object["is_special"].append("tags_list")
                        rss_object["is_special"].append("tags_plaintext_list")

        # if media_thumbnail or media_content exists, return the first friendly url
        try:
            rss_object["media_content_plaintext"] = rss_object["media_content"][0]["url"]
            rss_object["is_special"].append("media_content_plaintext")
        except KeyError:
            pass
        try:
            rss_object["media_thumbnail_plaintext"] = rss_object["media_thumbnail"][0]["url"]
            rss_object["is_special"].append("media_thumbnail_plaintext")
        except KeyError:
            pass

        # change published_parsed or updated_parsed into a datetime object for embed footers
        for time_tag in ["published_parsed", "updated_parsed"]:
            try:
                if isinstance(rss_object[time_tag], time.struct_time):
                    rss_object[f"{time_tag}_datetime"] = datetime.datetime(*rss_object[time_tag][:6])
                    break 
            except KeyError:
                pass

        if soup:
            rss_object = self._add_content_images(soup, rss_object)

        # add special tag/special site formatter here if needed in the future

        return rss_object

    async def _check_channel_permissions(self, ctx, channel: discord.TextChannel, addl_send_messages_check=True):
        """Helper for rss functions."""
        if not channel.permissions_for(ctx.me).read_messages:
            await ctx.send("I don't have permissions to read that channel.")
            return False
        elif not channel.permissions_for(ctx.author).read_messages:
            await ctx.send("You don't have permissions to read that channel.")
            return False
        elif addl_send_messages_check:
            # check for send messages perm if needed, like on an rss add
            # not needed on something like rss delete
            if not channel.permissions_for(ctx.me).send_messages:
                await ctx.send("I don't have permissions to send messages in that channel.")
                return False
            else:
                return True
        else:
            return True

    async def _check_feed_existing(self, ctx, feed_name: str, channel: discord.TextChannel):
        """Helper for rss functions."""
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            return False
        return True

    async def _delete_feed(self, ctx, feed_name: str, channel: discord.TextChannel):
        """Helper for rss delete."""
        rss_exists = await self._check_feed_existing(ctx, feed_name, channel)

        if rss_exists:
            async with self.config.channel(channel).feeds() as rss_data:
                rss_data.pop(feed_name, None)
                return True
        return False

    async def _edit_template(self, ctx, feed_name: str, channel: discord.TextChannel, template: str):
        """Helper for rss template."""
        rss_exists = await self._check_feed_existing(ctx, feed_name, channel)

        if rss_exists:
            async with self.config.channel(channel).feeds.all() as feed_data:
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
        except aiohttp.client_exceptions.ClientConnectorError:
            log.error(f"aiohttp failure accessing feed at url:\n\t{url}", exc_info=True)
            return None
        except Exception:
            log.error(f"General failure accessing feed at url:\n\t{url}", exc_info=True)
            return None

    async def _fetch_feedparser_object(self, url: str):
        """Get all feedparser entries from a url."""
        html = await self._get_url_content(url)
        if not html:
            return None

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
        """
        Converts any feedparser/feedparser_plus object to an RssFeed object.
        Used in rss add when saving a new feed.
        """
        entry_time = await self._time_tag_validation(feedparser_plus_obj)

        rss_object = RssFeed(
            name=feed_name.lower(),
            last_title=feedparser_plus_obj["title"],
            last_link=feedparser_plus_obj["link"],
            last_time=entry_time,
            template="$title\n$link",
            url=url,
            template_tags=feedparser_plus_obj["template_tags"],
            is_special=feedparser_plus_obj["is_special"],
            embed=True,
        )

        return rss_object

    async def _sort_by_post_time(self, feedparser_obj: feedparser.util.FeedParserDict):
        for time_tag in ["published_parsed", "updated_parsed"]:
            try:
                sorted_feed_by_post_time = sorted(feedparser_obj, key=lambda x: x.get(time_tag), reverse=True)
                break
            except TypeError:
                sorted_feed_by_post_time = feedparser_obj

        return sorted_feed_by_post_time

    async def _time_tag_validation(self, entry: feedparser.util.FeedParserDict):
        """Gets a unix timestamp if it's available from a single feedparser post entry."""
        entry_time = entry.get("published_parsed", None)
        if not entry_time:
            entry_time = entry.get("updated_parsed", None)
        if isinstance(entry_time, time.struct_time):
            entry_time = time.mktime(entry_time)
        if entry_time:
            return int(entry_time)
        return None

    @staticmethod
    async def _title_case(phrase: str):
        exceptions = ["a", "and", "in", "of", "or", "on", "the"]
        lowercase_words = re.split(" ", phrase.lower())
        final_words = [lowercase_words[0].capitalize()]
        final_words += [word if word in exceptions else word.capitalize() for word in lowercase_words[1:]]
        return " ".join(final_words)

    async def _update_last_scraped(
        self,
        channel: discord.TextChannel,
        feed_name: str,
        current_feed_title: str,
        current_feed_link: str,
        current_feed_time: int,
    ):
        """Updates last title and last link seen for comparison on next feed pull."""
        async with self.config.channel(channel).feeds() as feed_data:
            try:
                feed_data[feed_name]["last_title"] = current_feed_title
                feed_data[feed_name]["last_link"] = current_feed_link
                feed_data[feed_name]["last_time"] = current_feed_time
            except KeyError:
                # the feed was deleted during a _get_current_feed execution
                pass

    async def _valid_url(self, url: str, feed_check=True):
        """Helper for rss add."""
        try:
            result = urlparse(url)
        except Exception as e:
            log.exception(e, exc_info=e)
            return False

        if all([result.scheme, result.netloc, result.path]):
            if feed_check:
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
                return True
        else:
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
    async def _rss_add(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None, *, url: str):
        """
        Add an RSS feed to a channel.

        Defaults to the current channel if no channel is specified.
        """
        channel = channel or ctx.channel
        channel_permission_check = await self._check_channel_permissions(ctx, channel)
        if not channel_permission_check:
            return

        valid_url = await self._valid_url(url)
        if valid_url:
            await self._add_feed(ctx, feed_name.lower(), channel, url)
        else:
            await ctx.send("Invalid or unavailable URL.")

    @rss.group(name="embed")
    async def _rss_embed(self, ctx):
        """Embed feed settings."""
        pass

    @_rss_embed.command(name="color", aliases=["colour"])
    async def _rss_embed_color(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None, *, color: str = None):
        """
        Set an embed color for a feed.

        Use this command with no color to reset to the default.
        `color` must be a hex code like #990000, a [Discord color name](https://discordpy.readthedocs.io/en/latest/api.html#colour),
        or a [CSS3 color name](https://www.w3.org/TR/2018/REC-css-color-3-20180619/#svg-color).
        """
        channel = channel or ctx.channel
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
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
            async with self.config.channel(channel).feeds() as feed_data:
                feed_data[feed_name]["embed_color"] = None
            await ctx.send(
                f"{embed_state_message}The color for {bold(feed_name)} has been reset. "
                "Use this command with a color argument to set a color for this feed."
            )
            return

        color = color.replace(" ", "_")
        hex_code = await Color()._color_converter(color)
        if not hex_code:
            await ctx.send(
                "Not a valid color code. Use a hex code like #990000, a "
                "Discord color name or a CSS3 color name.\n"
                "<https://discordpy.readthedocs.io/en/latest/api.html#colour>\n"
                "<https://www.w3.org/TR/2018/REC-css-color-3-20180619/#svg-color>"
            )
            return
        user_facing_hex = hex_code.replace("0x", "#")
        color_name = await Color()._hex_to_css3_name(hex_code)

        # 0xFFFFFF actually doesn't show up as white in an embed
        # so let's make it close enough to count
        if hex_code == "0xFFFFFF":
            hex_code = "0xFFFFFE"

        async with self.config.channel(channel).feeds() as feed_data:
            # data is always a 0xFFFFFF style value
            feed_data[feed_name]["embed_color"] = hex_code

        await ctx.send(f"Embed color for {bold(feed_name)} set to {user_facing_hex} ({color_name}).")

    @_rss_embed.command(name="image")
    async def _rss_embed_image(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None, image_tag_name: str = None):
        """
        Set a tag to be a large embed image.

        This image will be applied to the last embed in the paginated list.
        Use this command with no image_tag_name to clear the embed image.
        """
        channel = channel or ctx.channel
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
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

        async with self.config.channel(channel).feeds() as feed_data:
            feed_data[feed_name]["embed_image"] = image_tag_name

        if image_tag_name:
            await ctx.send(f"{embed_state_message}Embed image set to the ${image_tag_name} tag.")
        else:
            await ctx.send(
                "Embed image has been cleared. Use this command with a tag name if you intended to set an image tag."
            )

    @_rss_embed.command(name="thumbnail")
    async def _rss_embed_thumbnail(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None, thumbnail_tag_name: str = None):
        """
        Set a tag to be a thumbnail image.

        This thumbnail will be applied to the first embed in the paginated list.
        Use this command with no thumbnail_tag_name to clear the embed thumbnail.
        """
        channel = channel or ctx.channel
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
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

        async with self.config.channel(channel).feeds() as feed_data:
            feed_data[feed_name]["embed_thumbnail"] = thumbnail_tag_name

        if thumbnail_tag_name:
            await ctx.send(f"{embed_state_message}Embed thumbnail set to the ${thumbnail_tag_name} tag.")
        else:
            await ctx.send(
                "Embed thumbnail has been cleared. "
                "Use this command with a tag name if you intended to set a thumbnail tag."
            )

    @_rss_embed.command(name="toggle")
    async def _rss_embed_toggle(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None):
        """
        Toggle whether a feed is sent in an embed or not.

        If the bot doesn't have permissions to post embeds,
        the feed will always be plain text, even if the embed
        toggle is set.
        """
        channel = channel or ctx.channel
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("That feed name doesn't exist in this channel.")
            return

        embed_toggle = rss_feed["embed"]
        toggle_text = "disabled" if embed_toggle else "enabled"

        async with self.config.channel(channel).feeds() as feed_data:
            feed_data[feed_name]["embed"] = not embed_toggle

        await ctx.send(f"Embeds for {bold(feed_name)} are {toggle_text}.")

    @rss.command(name="find")
    async def _rss_find(self, ctx, website_url: str):
        """
        Attempts to find RSS feeds from a URL/website.

        The site must have identified their feed in the html of the page based on RSS feed type standards.
        """
        async with ctx.typing():
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(website_url) as response:
                        soup = BeautifulSoup(await response.text(), "html.parser")
                except (aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ClientPayloadError):
                    await ctx.send("I can't reach that website.")
                    return
                except aiohttp.client_exceptions.InvalidURL:
                    await ctx.send("That seems to be an invalid URL. Use a full website URL like `https://www.site.com/`.")
                    return
        if not soup:
            await ctx.send("I didn't find anything at all on that link.")
            return
        msg = ""
        url_parse = urlparse(website_url)
        base_url = url_parse.netloc
        url_scheme = url_parse.scheme

        feed_url_types = ["application/rss+xml", "application/atom+xml", "text/xml", "application/rdf+xml"]
        for feed_type in feed_url_types:
            possible_feeds = soup.find_all('link', rel='alternate', type=feed_type, href=True)
            for feed in possible_feeds:
                feed_url = feed.get('href', None)
                if not feed_url:
                    continue
                feed_url = feed_url.lstrip("/")
                if ((not feed_url.startswith(url_scheme)) and (not feed_url.startswith(base_url))):
                    feed_url = f"{url_scheme}://{base_url}/{feed_url}"
                if feed_url.startswith(base_url):
                    feed_url = f"{url_scheme}://{base_url}"
                msg += f"[Feed Title]: {feed.get('title', None)}\n"
                msg += f"[Feed URL]: {feed_url}\n\n"
        if msg:
            await ctx.send(box(msg, lang="ini"))
        else:
            await ctx.send("No RSS feeds found in the link provided.")

    @rss.command(name="force")
    async def _rss_force(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None):
        """Forces a feed alert."""
        channel = channel or ctx.channel
        channel_permission_check = await self._check_channel_permissions(ctx, channel)
        if not channel_permission_check:
            return

        feeds = await self.config.all_channels()
        try:
            feeds[channel.id]
        except KeyError:
            await ctx.send("There are no feeds in this channel.")
            return

        if feed_name not in feeds[channel.id]["feeds"]:
            await ctx.send("That feed name doesn't exist in this channel.")
            return

        rss_feed = feeds[channel.id]["feeds"][feed_name]
        await self.get_current_feed(channel, feed_name, rss_feed, force=True)

    @rss.command(name="limit")
    async def _rss_limit(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None, character_limit: int = None):
        """
        Set a character limit for feed posts. Use 0 for unlimited.

        RSS posts are naturally split at around 2000 characters to fit within the Discord character limit per message.
        If you only want the first embed or first message in a post feed to show, use 2000 or less characters for this setting.

        Note that this setting applies the character limit to the entire post, for all template values on the feed together.
        For example, if the template is `$title\\n$content\\n$link`, and title + content + link is longer than the limit, the link will not show.
        """
        extra_msg = ""

        if character_limit is None:
            await ctx.send_help()
            return

        if character_limit < 0:
            await ctx.send("Character limit cannot be less than zero.")
            return

        if character_limit > 20000:
            character_limit = 0

        if 0 < character_limit < 20:
            extra_msg = "Character limit has a 20 character minimum.\n"
            character_limit = 20

        channel = channel or ctx.channel
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("That feed name doesn't exist in this channel.")
            return
        
        async with self.config.channel(channel).feeds() as feed_data:
            feed_data[feed_name]["limit"] = character_limit

        characters = f"approximately {character_limit}" if character_limit > 0 else "an unlimited amount of"
        await ctx.send(f"{extra_msg}Character limit for {bold(feed_name)} is now {characters} characters.")

    @rss.command(name="list")
    async def _rss_list(self, ctx, channel: discord.TextChannel = None):
        """List saved feeds for this channel or a specific channel."""
        channel = channel or ctx.channel
        channel_permission_check = await self._check_channel_permissions(ctx, channel)
        if not channel_permission_check:
            return

        feeds = await self._get_feed_names(channel)
        msg = f"[ Available Feeds for #{channel.name} ]\n\n\t"
        if feeds:
            msg += "\n\t".join(sorted(feeds))
        else:
            msg += "\n\tNone."
        for page in pagify(msg, delims=["\n"], page_length=1800):
            await ctx.send(box(page, lang="ini"))

    @rss.command(name="listtags")
    async def _rss_list_tags(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None):
        """List the tags available from a specific feed."""
        channel = channel or ctx.channel
        channel_permission_check = await self._check_channel_permissions(ctx, channel)
        if not channel_permission_check:
            return

        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)

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
    async def _rss_remove(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None):
        """
        Removes a feed from a channel.

        Defaults to the current channel if no channel is specified.
        """
        channel = channel or ctx.channel
        channel_permission_check = await self._check_channel_permissions(ctx, channel, addl_send_messages_check=False)
        if not channel_permission_check:
            return

        success = await self._delete_feed(ctx, feed_name, channel)
        if success:
            await ctx.send("Feed deleted.")
        else:
            await ctx.send("Feed not found!")

    @rss.command(name="showtemplate")
    async def _rss_show_template(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None):
        """Show the template in use for a specific feed."""
        channel = channel or ctx.channel
        channel_permission_check = await self._check_channel_permissions(ctx, channel)
        if not channel_permission_check:
            return

        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("No feed with that name in this channel.")
            return

        space = "\N{SPACE}"
        embed_toggle = f"[ ] Embed:{space*16}Off" if not rss_feed["embed"] else f"[X] Embed:{space*16}On"
        embed_image = (
            f"[ ] Embed image tag:{space*6}None"
            if not rss_feed["embed_image"]
            else f"[X] Embed image tag:{space*6}${rss_feed['embed_image']}"
        )
        embed_thumbnail = (
            f"[ ] Embed thumbnail tag:{space*2}None"
            if not rss_feed["embed_thumbnail"]
            else f"[X] Embed thumbnail tag:{space*2}${rss_feed['embed_thumbnail']}"
        )
        hex_color = rss_feed.get("embed_color", None)
        if hex_color:
            color_name = await Color()._hex_to_css3_name(hex_color)
            hex_color = hex_color.lstrip("0x")
        embed_color = (
            f"[ ] Embed hex color:{space*6}None"
            if not hex_color
            else f"[X] Embed hex color:{space*6}{hex_color} ({color_name})"
        )

        allowed_tags = rss_feed.get("allowed_tags", [])
        if not allowed_tags:
            tag_msg = "[ ] No restrictions\n\tAll tags are allowed."
        else:
            tag_msg = "[X] Feed is restricted to posts that include:"
            for tag in allowed_tags:
                tag_msg += f"\n\t{await self._title_case(tag)}"

        character_limit = rss_feed.get("limit", 0)
        if character_limit == 0:
            length_msg = "[ ] Feed length is unlimited."
        else:
            length_msg = f"[X] Feed length is capped at {character_limit} characters."

        embed_settings = f"{embed_toggle}\n{embed_color}\n{embed_image}\n{embed_thumbnail}"
        rss_template = rss_feed["template"].replace("\n", "\\n").replace("\t", "\\t")

        msg = f"Template for {bold(feed_name)}:\n\n`{rss_template}`\n\n{box(embed_settings, lang='ini')}\n{box(tag_msg, lang='ini')}\n{box(length_msg, lang='ini')}"

        for page in pagify(msg, delims=["\n"], page_length=1800):
            await ctx.send(page)

    @rss.group(name="tag")
    async def _rss_tag(self, ctx):
        """RSS post tag qualification."""
        pass

    @_rss_tag.command(name="allow")
    async def _rss_tag_allow(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None, *, tag: str = None):
        """
        Set an allowed tag for a feed to be posted. The tag must match exactly (without regard to title casing).
        No regex or placeholder qualification.

        Tags can be found in `[p]rss listtags` under `$tags` or `$tags_list` (if tags are present in the feed - not all feeds have tags).
        """
        channel = channel or ctx.channel
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("That feed name doesn't exist in this channel.")
            return
        
        async with self.config.channel(channel).feeds() as feed_data:
            allowed_tags = feed_data[feed_name].get("allowed_tags", [])
            if tag.lower() in [x.lower() for x in allowed_tags]:
                return await ctx.send(f"{bold(await self._title_case(tag))} is already in the allowed list for {bold(feed_name)}.")
            allowed_tags.append(tag.lower())
            feed_data[feed_name]["allowed_tags"] = allowed_tags

        await ctx.send(f"{bold(await self._title_case(tag))} was added to the list of allowed tags for {bold(feed_name)}. "
                        "If a feed post's `$tags` does not include this value, the feed will not post.")

    @_rss_tag.command(name="allowlist")
    async def _rss_tag_allowlist(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None):
        """
        List allowed tags for feed post qualification.
        """
        channel = channel or ctx.channel
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("That feed name doesn't exist in this channel.")
            return

        msg = f"[ Allowed Tags for {feed_name} ]\n\n\t"
        allowed_tags = rss_feed.get("allowed_tags", [])
        if not allowed_tags:
            msg += "All tags are allowed."
        else:
            for tag in allowed_tags:
                msg += f"{await self._title_case(tag)}\n"

        await ctx.send(box(msg, lang="ini"))

    @_rss_tag.command(name="remove", aliases=["delete"])
    async def _rss_tag_remove(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None, *, tag: str = None):
        """
        Remove a tag from the allow list. The tag must match exactly (without regard to title casing).
        No regex or placeholder qualification.
        """
        channel = channel or ctx.channel
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            await ctx.send("That feed name doesn't exist in this channel.")
            return
        
        async with self.config.channel(channel).feeds() as feed_data:
            allowed_tags = feed_data[feed_name].get("allowed_tags", [])
            try:
                allowed_tags.remove(tag.lower())
                feed_data[feed_name]["allowed_tags"] = allowed_tags
                await ctx.send(f"{bold(await self._title_case(tag))} was removed from the list of allowed tags for {bold(feed_name)}.")
            except ValueError:
                await ctx.send(f"{bold(await self._title_case(tag))} was not found in the allow list for {bold(feed_name)}.")

    @rss.command(name="template")
    async def _rss_template(self, ctx, feed_name: str, channel: Optional[discord.TextChannel] = None, *, template: str = None):
        """
        Set a template for the feed alert.

        Each variable must start with $, valid variables can be found with `[p]rss listtags`.
        """
        channel = channel or ctx.channel
        channel_permission_check = await self._check_channel_permissions(ctx, channel)
        if not channel_permission_check:
            return
        if not template:
            await ctx.send_help()
            return
        template = template.replace("\\t", "\t")
        template = template.replace("\\n", "\n")
        success = await self._edit_template(ctx, feed_name, channel, template)
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
        # last_link is a get for feeds saved before RSS 1.1.5 which won't have this attrib till it's checked once
        last_link = rss_feed.get("last_link", None)
        # last_time is a get for feeds saved before RSS 1.1.7 which won't have this attrib till it's checked once
        last_time = rss_feed.get("last_time", None)
        template = rss_feed["template"]
        message = None

        feedparser_obj = await self._fetch_feedparser_object(url)
        if not feedparser_obj:
            return

        # sorting the entire feedparser object by published_parsed time if it exists, if not then updated_parsed
        # certain feeds can be rearranged by a user, causing all posts to be out of sequential post order
        # or some feeds are out of time order by default
        sorted_feed_by_post_time = await self._sort_by_post_time(feedparser_obj)

        if not force:
            entry_time = await self._time_tag_validation(sorted_feed_by_post_time[0])
            if (last_time and entry_time) is not None:
                if last_time > entry_time:
                    log.debug("Not posting because new entry is older than last saved entry.")
                    return
            await self._update_last_scraped(channel, name, sorted_feed_by_post_time[0].title, sorted_feed_by_post_time[0].link, entry_time)

        feedparser_plus_objects = []
        for entry in sorted_feed_by_post_time:

            # find the published_parsed (checked first) or an updatated_parsed tag if they are present
            entry_time = await self._time_tag_validation(entry)

            # we only need one feed entry if this is from rss force
            if force:
                feedparser_plus_obj = await self._add_to_feedparser_object(entry, url)
                feedparser_plus_objects.append(feedparser_plus_obj)
                break

            # if this feed has a published_parsed or an updatated_parsed tag, it will use
            # that time value present in entry_time to verify that the post is new.
            elif (entry_time and last_time) is not None:
                if (last_title != entry.title) and (last_link != entry.link) and (last_time < entry_time):
                    log.debug(f"New entry found via time validation for feed {name} on cid {channel.id}")
                    feedparser_plus_obj = await self._add_to_feedparser_object(entry, url)
                    feedparser_plus_objects.append(feedparser_plus_obj)
                if (last_title == "" and entry.title == "") and (last_link != entry.link) and (last_time < entry_time):
                    log.debug(f"New entry found via time validation for feed {name} on cid {channel.id} - no title")
                    feedparser_plus_obj = await self._add_to_feedparser_object(entry, url)
                    feedparser_plus_objects.append(feedparser_plus_obj)

            # this is a post that has no time information attached to it and we can only
            # verify that the title and link did not match the previously posted entry
            elif (entry_time or last_time) is None:
                if last_title == entry.title and last_link == entry.link:
                    log.debug(f"Breaking rss entry loop for {name} on {channel.id}, via link match")
                    break
                else:
                    log.debug(f"New entry found for feed {name} on cid {channel.id} via new link or title")
                    feedparser_plus_obj = await self._add_to_feedparser_object(entry, url)
                    feedparser_plus_objects.append(feedparser_plus_obj)

            # we found a match for a previous feed post
            else:
                log.debug(
                    f"Breaking rss entry loop for {name} on {channel.id}, we found where we are supposed to be caught up to"
                )
                break

        # nothing in the whole feed matched to what was saved, so let's only post 1 instead of every single post
        if len(feedparser_plus_objects) == len(sorted_feed_by_post_time):
            log.debug(f"Couldn't match anything for feed {name} on cid {channel.id}, only posting 1 post")
            feedparser_plus_objects = [feedparser_plus_objects[0]]

        if not feedparser_plus_objects:
            # early-exit so that we don't dispatch when there's no updates
            return

        # post oldest first
        feedparser_plus_objects.reverse()

        # list of feedparser_plus_objects wrapped in MappingProxyType
        # filled during the loop below
        proxied_dicts = []

        for feedparser_plus_obj in feedparser_plus_objects:
            try:
                curr_title = feedparser_plus_obj.title
            except IndexError:
                log.debug(f"No entries found for feed {name} on cid {channel.id}")
                return

            # allowed tag verification section
            allowed_tags = rss_feed.get("allowed_tags", [])
            if len(allowed_tags) > 0:
                allowed_post_tags = [x.lower() for x in allowed_tags]
                feed_tag_list = [x.lower() for x in feedparser_plus_obj.get("tags_list", [])]
                intersection = list(set(feed_tag_list).intersection(allowed_post_tags))
                if len(intersection) == 0:
                    log.debug(f"{name} feed post in {channel.name} ({channel.id}) was denied because of an allowed tag mismatch.")
                    continue

            # starting to fill out the template for feeds that passed tag verification (if present)
            to_fill = QuietTemplate(template)
            message = to_fill.quiet_safe_substitute(name=bold(name), **feedparser_plus_obj)

            if len(message.strip(" ")) == 0:
                message = None

            if not message:
                log.debug(f"{name} feed in {channel.name} ({channel.id}) has no valid tags, not posting anything.")
                return

            embed_toggle = rss_feed["embed"]
            red_embed_settings = await self.bot.embed_requested(channel, None)
            embed_permissions = channel.permissions_for(channel.guild.me).embed_links

            rss_limit = rss_feed.get("limit", 0)
            if rss_limit > 0:
                # rss_limit needs + 8 characters for pagify counting codeblock characters
                message = list(pagify(message, delims=["\n", " "], priority=True, page_length=(rss_limit + 8)))[0]

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
            feedparser_dict_proxy = MappingProxyType(feedparser_plus_obj)
            proxied_dicts.append(feedparser_dict_proxy)
            self.bot.dispatch(
                "aikaternacogs_rss_message",
                channel=channel,
                feed_data=MappingProxyType(rss_feed),
                feedparser_dict=feedparser_dict_proxy,
                force=force,
            )

        # This event can be used in 3rd-party using listeners.
        # This may (and most likely will) get changes in the future
        # so I suggest accepting **kwargs in the listeners using this event.
        #
        # channel: discord.TextChannel
        #     The channel feed alerts went to.
        # feed_data: Mapping[str, Any]
        #     Read-only mapping with feed's data.
        #     The available data depends on what this cog needs
        #     and there most likely will be changes here in future.
        #     Available keys include: `name`, `template`, `url`, `embed`, etc.
        # feedparser_dicts: List[Mapping[str, Any]]
        #     List of read-only mappings with parsed data
        #     from each **new** entry in the feed.
        #     See documentation of feedparser.FeedParserDict for more information.
        # force: bool
        #     True if the update was forced (through `[p]rss force`), False otherwise.
        self.bot.dispatch(
            "aikaternacogs_rss_feed_update",
            channel=channel,
            feed_data=MappingProxyType(rss_feed),
            feedparser_dicts=proxied_dicts,
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
        time_tags = ["published_parsed_datetime", "updated_parsed_datetime"]
        for time_tag in time_tags:
            try:
                published_time = feedparser_plus_obj[time_tag]
                embed = embed_list[-1]
                embed.timestamp = published_time
                break
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
                    if self._post_queue.qsize() > self._post_queue_size:
                        # there's been more feeds added so let's update the total size
                        # so feeds have the proper wait time @ > 300 feeds
                        log.debug(f"Updating total queue size to {self._post_queue.qsize()}")
                        self._post_queue_size = self._post_queue.qsize()
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

                if await self.bot.cog_disabled_in_guild(self, channel.guild):
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
