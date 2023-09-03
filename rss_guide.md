# RSS Guide

The placeholder for your bot's prefix is `[p]` in this guide.

All commands are under the main command group of `[p]rss`.

### Add a new feed

If you already have a rss feed url to use, great! If you need to find an RSS feed from a website url, use `[p]rss find` with the url.

![rss find](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/9f035b36-72fc-4dc2-a191-02be57b61690)

**Q:** I added my feed but I got something that says "Bozo feed" in response.  
**A:** Make sure the link is a real RSS feed, in an Atom or XML standard RSS feed format. The `feedparser` library that RSS uses can only read and use RSS feeds that conform to standards. Sometimes when adding a new feed, your bot may be blocked by Cloudflare from navigating to the RSS feed and receive a bozo response - there is no handling in the cog to be able to follow or solve Cloudflare captchas or gates.  

**Q:** I used `[p]rss find` on a website link but it told me "No RSS feeds found in the link provided". I think they do have an RSS feed, what's wrong?  
**A:** The rss find command searches the page for any links in the website's HTML where the RSS feed is properly called out, to Atom 1.0 or RSS 2.0 specifications.   If the command can't find the feed, maybe approach the site owners to ask for their feeds to identify the feed as application/rss+xml, application/atom+xml, text/xml, or application/rdf+xml for the `link` tag for the feed.
  
Add the RSS feed, giving it a name you can refer to later. I'm using `test` in this example.  

![rss feed name](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/622dccdc-0d69-4e51-99f2-61f269bd1218)

### Set a feed post template

Use `[p]rss viewtags` with the feed name to view a small content preview of all template tags on the most recent post.

![viewtags](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/c234d354-a060-4119-8bcc-3e838c23faff)

The default template of every feed is a simple embed with the feed entry title, the url if present, and the date of the entry.

![default template](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/5983a227-f4af-4468-8aed-cccc1816d026)

If you wish to have a simple link post with a title where Discord can auto-unfurl the url, if possible, you only need to toggle off the embed display with `[p]rss embed toggle` and the feed name.

![simple link post](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/0112ebe4-700a-46a6-9c06-add79d7db01e)

Preview your changes at any time with `[p]rss force`.

![rss force](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/b7af1f68-d177-4aa5-865f-45d5a4f48aaa)

For the rest of these examples and explaination, I have toggled the test feed back to using an embed, with `[p]rss embed toggle`.  
Now let's explore the feed tags present on the feed, so we can modify the way the feed posts look.  

Use `[p]rss listtags` to display the feed tags.

![rss listtags](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/88793962-7efc-4c0d-947b-996b3d539d44)

Templates can include any of these placeholder values, which are prefixed with `$`. Not all feeds will have all of these placeholder values shown - they can vary from feed to feed and even from post to post on the same feed. Templates can also use the same Markdown formatting that you can use natively in Discord messages, like `\n` for a line return, `**` for bold, etc.  

Any tag with `plaintext` in its name is usually a cleaned or unpacked version of the parent tag it was generated from. For example, in our `test` feed here, there is a `$summary_detail` html-containing tag that also has a `$summary_detail_plaintext` version. If we use the summary detail in our template, we will want to choose the plaintext version.  

But what's in that `$summary_detail_plaintext` tag? Let's see...

![template preview](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/c102bc76-cd1e-4ae5-9365-ab41dfe310e6)

Well, this looks good to me on the information I want on these feed posts - let's add the title and the link back.  

I used `[p]rss template test **$title**\n$link\n\n$summary_detail_plaintext` here, giving a bold title with line returns for the link and the summary.

![template preview 2](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/6d763c71-dc26-4366-abea-f168e330767c)

Unfortunately, there are no images to use in these template tags on this test as there are no `$content_image` tags listed in `[p]rss listtags` nor does `$media_content` or the plaintext version of that tag have any image urls. If the post display needed an image preview, we would need to set this feed to display with the embed off, and with a link included, so that Discord can display it if the site is supported.  

##### Media template tags
The `$media_content` tag, `$media_url` tag, or any other `$media_`-prefixed tag usually holds non-image content. This can include and is not limited to video links and audio links. Rarely, there will be an image url in `$media_content` or `$media_url` tags, but it should not be the case if the feed or site owner is tagging the feed elements or html elements properly.  

##### Image template tags
Image tags are usually named `$content_image01` or similar, where every image url found in the feed post adds 1 to the name value. For example the second image url gathered from the feed post would be named `$content_image02` if it was present in `[p]rss listtags`. Rarely, an image url might be found under the `$links_plaintext` tag, if present.  

Let's make another test feed that has an image to use.  

![test 2 listtags](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/0d2f7e34-58de-4e5f-b6d6-d10b1202ef7b)

There is a `$media_thumbnail_plaintext` and a `$links_plaintext01` here. Let's see what they contain.  

![test 2 exploring tag content](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/42dd4e99-c7c8-4b17-a361-6589d420cad2)

Looks like an image url for the first and a link to the commit on the feed. Let's give it a real template and set the `$media_thumbnail_plaintext` tag as the embed image.  

I used `[p]rss template aikaterna-cogs aikaterna-cogs\nAuthor: $author\n[$content_plaintext01]($link)`. Note the combination of a template tag with a link - you can use `[text](url)` formatting in an embed with text-containing template tags.  

Let's set the embed thumbnail with the `[p]rss embed thumbnail` command. You can also use `[p]rss embed image` to set the large embed image to a tag instead of the embed thumbnail.  

![set embed thumbnail](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/0fd537a5-fcd7-44d6-8432-c065bcf03b48)

You can set different image template tags to be the main embed image and the embed thumbnail.

![set embed images](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/17e3e836-e1cd-4ba4-a28b-1db65a3340c8)

And that's it! You only need to add your feed and customize it with your template and RSS will check the feed every 5 minutes or so. The hardest part is creating a template you like.

### Double feed posts

RSS qualifies a new post based on the published time and updated time of the feed. Some sites update the updated time of the feed without updating content. This makes the RSS cog "double post" or even continuously post the same post. Use `[p]rss parse` to be able to configure the RSS cog to use the published_parsed feed tag, and stop multi-posting.  

![rss parse](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/e0b7b123-428b-4c38-8c3b-997bd40dbebc)

### Post filtering by tag

Sometimes, when a feed is set up to RSS standards and specifications, tags are included per feed post that provide content filtering. You can check if your feed includes these tags by using `[p]rss listtags` and seeing if there are `$tags` or similar.  

![tags list](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/c4a07812-5801-4970-a9dd-170de96ceb01)

This feed has tags! Let's see what some examples of their tags may be. Alternatively, maybe the site lists their RSS post tags elsewhere as a post tag preview may not include all tags in use on the site.  

![tag list](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/ffe335cf-09e5-4f5d-8585-167ebe0845e5)

Tag filtering is only an allow list. These tag names are case insensitive, you cannot have differing tags like `True Crime` vs. `true crime` - they will be processed the same way.

![tag filter added](https://github.com/aikaterna/aikaterna-cogs/assets/20862007/efde1fa9-21c4-4228-a643-0a8d966bb23d)

### Non-essential noteable features

There are other features of RSS to explore like:

`[p]rss embed color` - changing the embed color bar if you have an embedded post template  
`[p]rss limit` - limit the amount of characters used per post, but note that this is for the whole template, all template tags combined  
`[p]rss list` or `[p]rss listall` - list rss feeds in the current channel or all feeds on the Discord server  
`[p]rss showtemplate` - in case you forgot what you used for a feed's template and you would like to use it elsewhere  
