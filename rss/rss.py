import asyncio
import aiohttp
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import copy
import datetime
import discord
import feedparser
import filetype
import io
import itertools
import logging
import re
import time
import warnings
from typing import Optional, Union
from types import MappingProxyType, SimpleNamespace
from urllib.parse import urlparse

from redbot.core import checks, commands, Config
from redbot.core.utils import can_user_send_messages_in
from redbot.core.utils.chat_formatting import bold, box, escape, humanize_list, pagify

from .color import Color
from .quiet_template import QuietTemplate
from .rss_feed import RssFeed
from .tag_type import INTERNAL_TAGS, VALID_IMAGES, TagType

log = logging.getLogger("red.aikaterna.rss")


IPV4_RE = re.compile("\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}")
IPV6_RE = re.compile("([a-f0-9:]+:+)+[a-f0-9]+")
GuildMessageable = Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread]


__version__ = "2.1.6"

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    # Ignore the warning in feedparser module *and* our module to account for the unreleased fix of this warning:
    # https://github.com/kurtmckee/feedparser/pull/278
    module=r"^(feedparser|rss)(\..+)?$",
    message=(
        "To avoid breaking existing software while fixing issue 310, a temporary mapping has been created from"
        " `updated_parsed` to `published_parsed` if `updated_parsed` doesn't exist"
    ),
)
warnings.filterwarnings("ignore", module="rss", category=MarkupResemblesLocatorWarning)


class RSS(commands.Cog):
    """RSS feeds for your server."""

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, 2761331001, force_registration=True)
        self.config.register_channel(feeds={})
        self.config.register_global(use_published=["www.youtube.com"])

        self._post_queue = asyncio.PriorityQueue()
        self._post_queue_size = None

        self._read_feeds_loop = None

        self._headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"}

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

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

    async def _add_feed(self, ctx, feed_name: str, channel: GuildMessageable, url: str):
        """Helper for rss add."""
        rss_exists = await self._check_feed_existing(ctx, feed_name, channel)
        if not rss_exists:
            feedparser_obj = await self._fetch_feedparser_object(url)
            if not feedparser_obj:
                await ctx.send("Couldn't fetch that feed: there were no feed objects found.")
                return

            # sort everything by time if a time value is present
            if feedparser_obj.entries:
                # this feed has posts
                sorted_feed_by_post_time = await self._sort_by_post_time(feedparser_obj.entries)
            else:
                # this feed does not have posts, but it has a header with channel information
                sorted_feed_by_post_time = [feedparser_obj.feed]

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
        tags_list = []

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

                if soup:
                    rss_object[f"{tag_name}_plaintext"] = self._add_generic_html_plaintext(soup)

            if tag_content_check == TagType.LIST:
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
                        enclosure_content_counter = 0
                        enclosure_url_counter = 0

                        # common "authors" tag format
                        try:
                            authors_content_counter += 1
                            name = f"{tag_name}_plaintext{str(authors_content_counter).zfill(2)}"
                            tag_content = BeautifulSoup(list_item["name"], "html.parser")
                            rss_object[name] = tag_content.get_text()
                            rss_object["is_special"].append(name)
                        except KeyError:
                            pass

                        # common "enclosure" tag image format
                        # note: this is not adhering to RSS feed specifications
                        # proper enclosure tags should have `length`, `type`, `url`
                        # and not `href`, `type`, `rel`
                        # but, this is written for the first feed I have seen with an "enclosure" tag
                        try:
                            image_url = list_item["href"]
                            image_type = list_item["type"]
                            image_rel = list_item["rel"]
                            enclosure_content_counter += 1
                            name = f"media_plaintext{str(enclosure_content_counter).zfill(2)}"
                            rss_object[name] = image_url
                            rss_object["is_special"].append(name)
                        except KeyError:
                            pass

                        # special tag for enclosure["url"] so that users can differentiate them
                        # from image urls found in enclosure["href"]
                        try:
                            image_url = list_item["url"]
                            enclosure_url_counter += 1
                            name = f"media_url{str(enclosure_url_counter).zfill(2)}"
                            rss_object[name] = image_url
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
                            tags_list.append(tag) if tag not in tags_list else tags_list
                        except KeyError:
                            pass

                if len(tags_list) > 0:
                    rss_object["tags_list"] = tags_list
                    rss_object["tags_plaintext_list"] = humanize_list(tags_list)
                    rss_object["is_special"].append("tags_list")
                    rss_object["is_special"].append("tags_plaintext_list")

        # if image dict tag exists, check for an image
        try:
            rss_object["image_plaintext"] = rss_object["image"]["href"]
            rss_object["is_special"].append("image_plaintext")
        except KeyError:
            pass

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

        # change published_parsed and updated_parsed into a datetime object for embed footers
        for time_tag in ["updated_parsed", "published_parsed"]:
            try:
                if isinstance(rss_object[time_tag], time.struct_time):
                    rss_object[f"{time_tag}_datetime"] = datetime.datetime(*rss_object[time_tag][:6])
            except KeyError:
                pass

        if soup:
            rss_object = self._add_content_images(soup, rss_object)

        # add special tag/special site formatter here if needed in the future

        return rss_object

    async def _check_channel_permissions(self, ctx, channel: GuildMessageable, addl_send_messages_check=True):
        """Helper for rss functions."""
        if not channel.permissions_for(ctx.me).read_messages:
            await ctx.send("I don't have permissions to read that channel.")
            return False
        author_perms = channel.permissions_for(ctx.author)
        if not author_perms.read_messages:
            await ctx.send("You don't have permissions to read that channel.")
            return False
        # bot can only see threads that it has permissions to read messages in so no special handling needed
        # if author has read messages perm, they can read all public threads *but also* private threads they are in
        if isinstance(channel, discord.Thread) and channel.is_private() and not author_perms.manage_threads:
            try:
                await channel.fetch_member(ctx.author.id)
            except discord.NotFound:
                # author is not in a private thread
                return False
        if addl_send_messages_check:
            # check for send messages perm if needed, like on an rss add
            # not needed on something like rss delete
            if not can_user_send_messages_in(ctx.me, channel):
                await ctx.send("I don't have permissions to send messages in that channel.")
                return False
            else:
                return True
        else:
            return True

    async def _check_feed_existing(self, ctx, feed_name: str, channel: GuildMessageable):
        """Helper for rss functions."""
        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)
        if not rss_feed:
            return False
        return True

    async def _delete_feed(self, ctx, feed_name: str, channel: GuildMessageable):
        """Helper for rss delete."""
        rss_exists = await self._check_feed_existing(ctx, feed_name, channel)

        if rss_exists:
            async with self.config.channel(channel).feeds() as rss_data:
                rss_data.pop(feed_name, None)
                return True
        return False

    async def _edit_template(self, ctx, feed_name: str, channel: GuildMessageable, template: str):
        """Helper for rss template."""
        rss_exists = await self._check_feed_existing(ctx, feed_name, channel)

        if rss_exists:
            async with self.config.channel(channel).feeds.all() as feed_data:
                if feed_name not in feed_data:
                    feed_data[feed_name] = {}
                feed_data[feed_name]["template"] = template
                return True
        return False

    @staticmethod
    def _find_website(website_url: str):
        """Helper for rss parse."""
        result = urlparse(website_url)
        if result.scheme:
            # https://www.website.com/...
            if result.netloc:
                website = result.netloc
            else:
                return None
        else:
            # www.website.com/...
            if result.path:
                website = result.path.split("/")[0]
            else:
                return None

        return website

    async def _get_channel_object(self, channel_id: int):
        """Helper for rss feed loop."""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.errors.Forbidden, discord.errors.NotFound):
                return None
        if channel and can_user_send_messages_in(channel.guild.me, channel):
            return channel
        return None

    async def _get_feed_names(self, channel: GuildMessageable):
        """Helper for rss list/listall."""
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
            # force github.com to serve us xml instead of json
            headers = self._headers
            if "github.com" in url:
                headers["Accept"] = "application/vnd.github+xml"

            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 404:
                        friendly_msg = "The server returned 404 Not Found. Check your url and try again."
                        return None, friendly_msg
                    html = await resp.read()
            return html, None
        except aiohttp.client_exceptions.ClientConnectorError:
            friendly_msg = "There was an OSError or the connection failed."
            msg = f"aiohttp failure accessing feed at url:\n\t{url}"
            log.error(msg, exc_info=True)
            return None, friendly_msg
        except aiohttp.client_exceptions.ClientPayloadError as e:
            friendly_msg = "The website closed the connection prematurely or the response was malformed.\n"
            friendly_msg += f"The error returned was: `{str(e)}`\n"
            friendly_msg += "For more technical information, check your bot's console or logs."
            msg = f"content error while reading feed at url:\n\t{url}"
            log.error(msg, exc_info=True)
            return None, friendly_msg
        except asyncio.exceptions.TimeoutError:
            friendly_msg = "The bot timed out while trying to access that content."
            msg = f"asyncio timeout while accessing feed at url:\n\t{url}"
            log.error(msg, exc_info=True)
            return None, friendly_msg
        except aiohttp.client_exceptions.ServerDisconnectedError:
            friendly_msg = "The target server disconnected early without a response."
            msg = f"server disconnected while accessing feed at url:\n\t{url}"
            log.error(msg, exc_info=True)
            return None, friendly_msg
        except Exception:
            friendly_msg = "There was an unexpected error. Check your console for more information."
            msg = f"General failure accessing feed at url:\n\t{url}"
            log.error(msg, exc_info=True)
            return None, friendly_msg

    async def _fetch_feedparser_object(self, url: str):
        """Get a full feedparser object from a url: channel header + items."""
        html, error_msg = await self._get_url_content(url)
        if not html:
            return SimpleNamespace(entries=None, error=error_msg, url=url)

        feedparser_obj = feedparser.parse(html)
        if feedparser_obj.bozo:
            error_msg = f"Bozo feed: feedparser is unable to parse the response from {url}.\n"
            error_msg += f"Feedparser error message: `{feedparser_obj.bozo_exception}`"
            return SimpleNamespace(entries=None, error=error_msg, url=url)

        return feedparser_obj

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

        # sometimes there's no title or no link attribute and feedparser doesn't really play nice with that
        try:
            feedparser_plus_obj_title = feedparser_plus_obj["title"]
        except KeyError:
            feedparser_plus_obj_title = ""
        try:
            feedparser_plus_obj_link = feedparser_plus_obj["link"]
        except KeyError:
            feedparser_plus_obj_link = ""

        rss_object = RssFeed(
            name=feed_name.lower(),
            last_title=feedparser_plus_obj_title,
            last_link=feedparser_plus_obj_link,
            last_time=entry_time,
            template="$title\n$link",
            url=url,
            template_tags=feedparser_plus_obj["template_tags"],
            is_special=feedparser_plus_obj["is_special"],
            embed=True,
        )

        return rss_object

    async def _sort_by_post_time(self, feedparser_obj: feedparser.util.FeedParserDict):
        base_url = urlparse(feedparser_obj[0].get("link")).netloc
        use_published_parsed_override = await self.config.use_published()

        if base_url in use_published_parsed_override:
            time_tag = ["published_parsed"]
        else:
            time_tag = ["updated_parsed", "published_parsed"]

        for tag in time_tag:
            try:
                baseline_time = time.struct_time((2021, 1, 1, 12, 0, 0, 4, 1, -1))
                sorted_feed_by_post_time = sorted(feedparser_obj, key=lambda x: x.get(tag, baseline_time), reverse=True)
                break
            except TypeError:
                sorted_feed_by_post_time = feedparser_obj

        return sorted_feed_by_post_time

    async def _time_tag_validation(self, entry: feedparser.util.FeedParserDict):
        """Gets a unix timestamp if it's available from a single feedparser post entry."""
        feed_link = entry.get("link", None)
        if feed_link:
            base_url = urlparse(feed_link).netloc
        else:
            return None

        # check for a feed time override, if a feed is being problematic regarding updated_parsed
        # usage (i.e. a feed entry keeps reposting with no perceived change in content)
        use_published_parsed_override = await self.config.use_published()
        if base_url in use_published_parsed_override:
            entry_time = entry.get("published_parsed", None)
        else:
            entry_time = entry.get("updated_parsed", None)
            if not entry_time:
                entry_time = entry.get("published_parsed", None)

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
        channel: GuildMessageable,
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
                text, error_msg = await self._get_url_content(url)
                if not text:
                    raise NoFeedContent(error_msg)
                    return False

                rss = feedparser.parse(text)
                if rss.bozo:
                    error_message = rss.feed.get("summary", str(rss))[:1500]
                    error_message = re.sub(IPV4_RE, "[REDACTED IP ADDRESS]", error_message)
                    error_message = re.sub(IPV6_RE, "[REDACTED IP ADDRESS]", error_message)
                    msg = f"Bozo feed: feedparser is unable to parse the response from {url}.\n\n"
                    msg += "Received content preview:\n"
                    msg += box(error_message)
                    raise NoFeedContent(msg)
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
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(headers=self._headers, timeout=timeout) as session:
                async with session.get(url) as resp:
                    image = await resp.content.read(261)
            img = io.BytesIO(image)
            file_type = filetype.guess(img)
            if not file_type:
                return None
            return file_type.extension
        except aiohttp.client_exceptions.InvalidURL:
            return None
        except asyncio.exceptions.TimeoutError:
            log.error(f"asyncio timeout while accessing image at url:\n\t{url}", exc_info=True)
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
    async def _rss_add(self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None, *, url: str):
        """
        Add an RSS feed to a channel.

        Defaults to the current channel if no channel is specified.
        """
        if feed_name.startswith("<#"):
            # someone typed a channel name but not a feed name
            msg = "Try again with a feed name included in the right spot so that you can refer to the feed later.\n"
            msg += f"Example: `{ctx.prefix}rss add feed_name channel_name feed_url`"
            await ctx.send(msg)
            return
        channel = channel or ctx.channel
        channel_permission_check = await self._check_channel_permissions(ctx, channel)
        if not channel_permission_check:
            return

        async with ctx.typing():
            try:
                valid_url = await self._valid_url(url)
            except NoFeedContent as e:
                await ctx.send(str(e))
                return

            if valid_url:
                await self._add_feed(ctx, feed_name.lower(), channel, url)
            else:
                await ctx.send("Invalid or unavailable URL.")

    @rss.group(name="embed")
    async def _rss_embed(self, ctx):
        """Embed feed settings."""
        pass

    @_rss_embed.command(name="color", aliases=["colour"])
    async def _rss_embed_color(
        self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None, *, color: str = None
    ):
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
    async def _rss_embed_image(
        self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None, image_tag_name: str = None
    ):
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
            else:
                msg = "You must use a feed tag for this setting. "
                msg += f"Feed tags start with `$` and can be found by using `{ctx.prefix}rss listtags` "
                msg += "with the saved feed name.\nImages that are scraped from feed content are usually "
                msg += "stored under the tags styled similar to `$content_image01`: subsequent scraped images "
                msg += "will be in tags named `$content_image02`, `$content_image03`, etc. Not every feed entry "
                msg += "will have the same amount of scraped image tags. Images can also be found under tags named "
                msg += "`$media_content_plaintext`, if present.\nExperiment with tags by setting them as your "
                msg += (
                    f"template with `{ctx.prefix}rss template` and using `{ctx.prefix}rss force` to view the content."
                )
                await ctx.send(msg)
                return

        async with self.config.channel(channel).feeds() as feed_data:
            feed_data[feed_name]["embed_image"] = image_tag_name

        if image_tag_name:
            await ctx.send(f"{embed_state_message}Embed image set to the ${image_tag_name} tag.")
        else:
            await ctx.send(
                "Embed image has been cleared. Use this command with a tag name if you intended to set an image tag."
            )

    @_rss_embed.command(name="thumbnail")
    async def _rss_embed_thumbnail(
        self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None, thumbnail_tag_name: str = None
    ):
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
            else:
                msg = "You must use a feed tag for this setting. "
                msg += f"Feed tags start with `$` and can be found by using `{ctx.prefix}rss listtags` "
                msg += "with the saved feed name.\nImages that are scraped from feed content are usually "
                msg += "stored under the tags styled similar to `$content_image01`: subsequent scraped images "
                msg += "will be in tags named `$content_image02`, `$content_image03`, etc. Not every feed entry "
                msg += "will have the same amount of scraped image tags. Images can also be found under tags named "
                msg += "`$media_content_plaintext`, if present.\nExperiment with tags by setting them as your "
                msg += (
                    f"template with `{ctx.prefix}rss template` and using `{ctx.prefix}rss force` to view the content."
                )
                await ctx.send(msg)
                return

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
    async def _rss_embed_toggle(self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None):
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
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(headers=self._headers, timeout=timeout) as session:
                try:
                    async with session.get(website_url) as response:
                        soup = BeautifulSoup(await response.text(errors="replace"), "html.parser")
                except (aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ClientPayloadError):
                    await ctx.send("I can't reach that website.")
                    return
                except aiohttp.client_exceptions.InvalidURL:
                    await ctx.send(
                        "That seems to be an invalid URL. Use a full website URL like `https://www.site.com/`."
                    )
                    return
                except aiohttp.client_exceptions.ServerDisconnectedError:
                    await ctx.send("The server disconnected early without a response.")
                    return
                except asyncio.exceptions.TimeoutError:
                    await ctx.send("The site didn't respond in time or there was no response.")
                    return
                except Exception as e:
                    msg = "There was an issue trying to find a feed in that site. "
                    msg += "Please check your console for more information."
                    log.exception(e, exc_info=e)
                    await ctx.send(msg)
                    return

        if "403 Forbidden" in soup.get_text():
            await ctx.send("I received a '403 Forbidden' message while trying to reach that site.")
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
            possible_feeds = soup.find_all("link", rel="alternate", type=feed_type, href=True)
            for feed in possible_feeds:
                feed_url = feed.get("href", None)
                ls_feed_url = feed_url.lstrip("/")
                if not feed_url:
                    continue
                if feed_url.startswith("//"):
                    final_url = f"{url_scheme}:{feed_url}"
                elif (not ls_feed_url.startswith(url_scheme)) and (not ls_feed_url.startswith(base_url)):
                    final_url = f"{url_scheme}://{base_url}/{ls_feed_url}"
                elif ls_feed_url.startswith(base_url):
                    final_url = f"{url_scheme}://{base_url}"
                else:
                    final_url = feed_url
                msg += f"[Feed Title]: {feed.get('title', None)}\n"
                msg += f"[Feed URL]: {final_url}\n\n"
        if msg:
            await ctx.send(box(msg, lang="ini"))
        else:
            await ctx.send("No RSS feeds found in the link provided.")

    @rss.command(name="force")
    async def _rss_force(self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None):
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
    async def _rss_limit(
        self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None, character_limit: int = None
    ):
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
    async def _rss_list(self, ctx, channel: GuildMessageable = None):
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

    @rss.command(name="listall")
    async def _rss_listall(self, ctx):
        """List all saved feeds for this server."""
        all_channels = await self.config.all_channels()
        all_guild_channels = [x.id for x in itertools.chain(ctx.guild.channels, ctx.guild.threads)]
        msg = ""
        for channel_id, data in all_channels.items():
            if channel_id in all_guild_channels:
                channel_obj = ctx.guild.get_channel_or_thread(channel_id)
                feeds = await self._get_feed_names(channel_obj)
                if not feeds:
                    continue
                if feeds == ["None."]:
                    continue
                msg += f"[ Available Feeds for #{channel_obj.name} ]\n\n\t"
                msg += "\n\t".join(sorted(feeds))
                msg += "\n\n"

        for page in pagify(msg, delims=["\n\n", "\n"], page_length=1800):
            await ctx.send(box(page, lang="ini"))

    @rss.command(name="listtags")
    async def _rss_list_tags(self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None):
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
        msg = f"[ Available Template Tags for {feed_name} ]\n\n\t"
        feedparser_obj = await self._fetch_feedparser_object(rss_feed["url"])

        if not feedparser_obj:
            await ctx.send("Couldn't fetch that feed.")
            return
        if feedparser_obj.entries:
            # this feed has posts
            feedparser_plus_obj = await self._add_to_feedparser_object(feedparser_obj.entries[0], rss_feed["url"])
        else:
            # this feed does not have posts, but it has a header with channel information
            feedparser_plus_obj = await self._add_to_feedparser_object(feedparser_obj.feed, rss_feed["url"])

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

        for msg_part in pagify(msg, delims=["\n\t", "\n\n"]):
            await ctx.send(box(msg_part, lang="ini"))

    @checks.is_owner()
    @rss.group(name="parse")
    async def _rss_parse(self, ctx):
        """
        Change feed parsing for a specfic domain.

        This is a global change per website.
        The default is to use the feed's updated_parsed tag, and adding a website to this list will change the check to published_parsed.

        Some feeds may spam feed entries as they are updating the updated_parsed slot on their feed, but not updating feed content.
        In this case we can force specific sites to use the published_parsed slot instead by adding the website to this override list.
        """
        pass

    @_rss_parse.command(name="add")
    async def _rss_parse_add(self, ctx, website_url: str):
        """
        Add a website to the list for a time parsing override.

        Use a website link formatted like `www.website.com` or `https://www.website.com`.
        For more information, use `[p]help rss parse`.
        """
        website = self._find_website(website_url)
        if not website:
            msg = f"I can't seem to find a website in `{website_url}`. "
            msg += "Use something like `https://www.website.com/` or `www.website.com`."
            await ctx.send(msg)
            return

        override_list = await self.config.use_published()
        if website in override_list:
            await ctx.send(f"`{website}` is already in the parsing override list.")
        else:
            override_list.append(website)
            await self.config.use_published.set(override_list)
            await ctx.send(f"`{website}` was added to the parsing override list.")

    @_rss_parse.command(name="list")
    async def _rss_parse_list(self, ctx):
        """
        Show the list for time parsing overrides.

        For more information, use `[p]help rss parse`.
        """
        override_list = await self.config.use_published()
        if not override_list:
            msg = "No site overrides saved."
        else:
            msg = "Active for:\n" + "\n".join(override_list)
        await ctx.send(box(msg))

    @_rss_parse.command(name="remove", aliases=["delete", "del"])
    async def _rss_parse_remove(self, ctx, website_url: str = None):
        """
        Remove a website from the list for a time parsing override.

        Use a website link formatted like `www.website.com` or `https://www.website.com`.
        For more information, use `[p]help rss parse`.
        """
        website = self._find_website(website_url)
        override_list = await self.config.use_published()
        if website in override_list:
            override_list.remove(website)
            await self.config.use_published.set(override_list)
            await ctx.send(f"`{website}` was removed from the parsing override list.")
        else:
            await ctx.send(f"`{website}` isn't in the parsing override list.")

    @rss.command(name="remove", aliases=["delete", "del"])
    async def _rss_remove(self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None):
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
    async def _rss_show_template(self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None):
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
    async def _rss_tag_allow(self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None, *, tag: str = None):
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
                return await ctx.send(
                    f"{bold(await self._title_case(tag))} is already in the allowed list for {bold(feed_name)}."
                )
            allowed_tags.append(tag.lower())
            feed_data[feed_name]["allowed_tags"] = allowed_tags

        await ctx.send(
            f"{bold(await self._title_case(tag))} was added to the list of allowed tags for {bold(feed_name)}. "
            "If a feed post's `$tags` does not include this value, the feed will not post."
        )

    @_rss_tag.command(name="allowlist")
    async def _rss_tag_allowlist(self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None):
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
    async def _rss_tag_remove(
        self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None, *, tag: str = None
    ):
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
                await ctx.send(
                    f"{bold(await self._title_case(tag))} was removed from the list of allowed tags for {bold(feed_name)}."
                )
            except ValueError:
                await ctx.send(
                    f"{bold(await self._title_case(tag))} was not found in the allow list for {bold(feed_name)}."
                )

    @rss.command(name="template")
    async def _rss_template(
        self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None, *, template: str = None
    ):
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

    @rss.command(name="viewtags")
    async def _rss_view_tags(self, ctx, feed_name: str, channel: Optional[GuildMessageable] = None):
        """View a preview of template tag content available from a specific feed."""
        channel = channel or ctx.channel
        channel_permission_check = await self._check_channel_permissions(ctx, channel)
        if not channel_permission_check:
            return

        rss_feed = await self.config.channel(channel).feeds.get_raw(feed_name, default=None)

        if not rss_feed:
            await ctx.send("No feed with that name in this channel.")
            return

        async with ctx.typing():
            await self._rss_view_tags_helper(ctx, rss_feed, feed_name)

    async def _rss_view_tags_helper(self, ctx, rss_feed: dict, feed_name: str):
        """Helper function for rss viewtags."""
        blue_ansi_prefix = "\u001b[1;40;34m"
        reset_ansi_prefix = "\u001b[0m"
        msg = f"{blue_ansi_prefix}[ Template Tag Content Preview for {feed_name} ]{reset_ansi_prefix}\n\n\t"
        feedparser_obj = await self._fetch_feedparser_object(rss_feed["url"])

        if not feedparser_obj:
            await ctx.send("Couldn't fetch that feed.")
            return
        if feedparser_obj.entries:
            # this feed has posts
            feedparser_plus_obj = await self._add_to_feedparser_object(feedparser_obj.entries[0], rss_feed["url"])
        else:
            # this feed does not have posts, but it has a header with channel information
            feedparser_plus_obj = await self._add_to_feedparser_object(feedparser_obj.feed, rss_feed["url"])

        longest_key = max(feedparser_plus_obj, key=len)
        longest_key_len = len(longest_key)
        for tag_name, tag_content in sorted(feedparser_plus_obj.items()):
            if tag_name in INTERNAL_TAGS:
                # these tags attached to the rss feed object are for internal handling options
                continue

            tag_content = str(tag_content).replace("[", "").replace("]", "").replace("\n", " ").replace('"', "")
            tag_content = tag_content.lstrip(" ")

            space = "\N{SPACE}"
            tag_name_padded = (
                f"{blue_ansi_prefix}${tag_name}{reset_ansi_prefix}{space*(longest_key_len - len(tag_name))}"
            )
            if len(tag_content) > 50:
                tag_content = tag_content[:50] + "..."
            msg += f"{tag_name_padded}  {tag_content}\n\t"

        for msg_part in pagify(msg, delims=["\n\t", "\n\n"], page_length=1900):
            await ctx.send(box(msg_part.rstrip("\n\t"), lang="ansi"))

    @rss.command(name="version", hidden=True)
    async def _rss_version(self, ctx):
        """Show the RSS version."""
        await ctx.send(f"RSS version {__version__}")

    async def get_current_feed(self, channel: GuildMessageable, name: str, rss_feed: dict, *, force: bool = False):
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
        try:
            log.debug(f"{feedparser_obj.error} Channel: {channel.id}")
            return
        except AttributeError:
            pass

        # sorting the entire feedparser object by updated_parsed time if it exists, if not then published_parsed
        # certain feeds can be rearranged by a user, causing all posts to be out of sequential post order
        # or some feeds are out of time order by default
        if feedparser_obj.entries:
            # this feed has posts
            sorted_feed_by_post_time = await self._sort_by_post_time(feedparser_obj.entries)
        else:
            # this feed does not have posts, but it has a header with channel information
            sorted_feed_by_post_time = [feedparser_obj.feed]

        if not force:
            entry_time = await self._time_tag_validation(sorted_feed_by_post_time[0])
            if (last_time and entry_time) is not None:
                if last_time > entry_time:
                    log.debug("Not posting because new entry is older than last saved entry.")
                    return
            try:
                title = sorted_feed_by_post_time[0].title
            except AttributeError:
                title = ""
            try:
                link = sorted_feed_by_post_time[0].link
            except AttributeError:
                link = ""
            await self._update_last_scraped(channel, name, title, link, entry_time)

        feedparser_plus_objects = []
        for entry in sorted_feed_by_post_time:
            # sometimes there's no title or no link attribute and feedparser doesn't really play nice with that
            try:
                entry_title = entry.title
            except AttributeError:
                entry_title = ""
            try:
                entry_link = entry.link
            except AttributeError:
                entry_link = ""

            # find the updated_parsed (checked first) or an published_parsed tag if they are present
            entry_time = await self._time_tag_validation(entry)

            # we only need one feed entry if this is from rss force
            if force:
                feedparser_plus_obj = await self._add_to_feedparser_object(entry, url)
                feedparser_plus_objects.append(feedparser_plus_obj)
                break

            # TODO: spammy debug logs to vvv

            # there's a post time to compare
            elif (entry_time and last_time) is not None:
                # this is a post with an updated time with the same link and title, maybe an edited post.
                # if a feed is spamming updated times with no content update, consider adding the full website
                # (www.website.com) to the rss parse command
                if (last_title == entry_title) and (last_link == entry_link) and (last_time < entry_time):
                    log.debug(f"New update found for an existing post in {name} on cid {channel.id}")
                    feedparser_plus_obj = await self._add_to_feedparser_object(entry, url)
                    feedparser_plus_objects.append(feedparser_plus_obj)
                else:
                    # a post from the future, or we are caught up
                    if last_time >= entry_time:
                        log.debug(f"Up to date on {name} on cid {channel.id}")
                        break

                    # a new post
                    if last_link != entry_link:
                        log.debug(f"New entry found via time and link validation for feed {name} on cid {channel.id}")
                        feedparser_plus_obj = await self._add_to_feedparser_object(entry, url)
                        feedparser_plus_objects.append(feedparser_plus_obj)

                    else:
                        # I don't belive this ever should be hit but this is a catch to debug
                        # a feed in case one ever appears that does this
                        log.debug(
                            f"*** This post qualified via timestamp check but has the same link as last: {entry_title[:25]} | {entry_link}"
                        )

            # this is a post that has no time comparison information because one or both timestamps are None.
            # compare the title and link to see if it's the same post as previous.
            # this may need more definition in the future if there is a feed that provides new titles but not new links etc
            elif entry_time is None or last_time is None:
                if last_title == entry_title and last_link == entry_link:
                    log.debug(f"Up to date on {name} on {channel.id} via link match, no time to compare")
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

        #  TODO: just going to keep this here for now in case something explodes later

        #  if len(feedparser_plus_objects) == len(sorted_feed_by_post_time):
        #      msg = (f"Couldn't match anything for feed {name} on cid {channel.id}, or switching between feed header and feed entry, only posting 1 post")
        #      log.debug(msg)
        #      feedparser_plus_objects = [feedparser_plus_objects[0]]

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
            except AttributeError:
                curr_title = ""
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
                    log.debug(
                        f"{name} feed post in {channel.name} ({channel.id}) was denied because of an allowed tag mismatch."
                    )
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
            red_embed_settings = await self.bot.embed_requested(channel)

            rss_limit = rss_feed.get("limit", 0)
            if rss_limit > 0:
                # rss_limit needs + 8 characters for pagify counting codeblock characters
                message = list(pagify(message, delims=["\n", " "], priority=True, page_length=(rss_limit + 8)))[0]

            if embed_toggle and red_embed_settings:
                await self._get_current_feed_embed(channel, rss_feed, feedparser_plus_obj, message)
            else:
                for page in pagify(message, delims=["\n"]):
                    await channel.send(page)

            # This event can be used in 3rd-party using listeners.
            # This may (and most likely will) get changes in the future
            # so I suggest accepting **kwargs in the listeners using this event.
            #
            # channel: Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread]
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
        # channel: Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread]
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
        channel: GuildMessageable,
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

        if len(embed_list) == 0:
            return

        # Add published timestamp to the last footer if it exists
        time_tags = ["updated_parsed_datetime", "published_parsed_datetime"]
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

        # TODO: very large queues with a lot of RSS feeds (1000+) cause this to fall behind
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
                    except aiohttp.client_exceptions.InvalidURL as e:
                        log.debug(f"Feed at {e.url} is bad or took too long to respond.")
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
                log.error("An error has occurred in the RSS cog. Please report it.", exc_info=e)
                continue

    async def _put_feeds_in_queue(self):
        log.debug("Putting feeds in queue")
        try:
            config_data = await self.config.all_channels()
            total_index = 0
            for channel_id, channel_feed_list in config_data.items():
                channel = await self._get_channel_object(channel_id)
                if not channel:
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


class NoFeedContent(Exception):
    def __init__(self, m):
        self.message = m

    def __str__(self):
        return self.message
