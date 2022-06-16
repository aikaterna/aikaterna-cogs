import aiohttp
import base64
import discord
from discord.http import Route
import io
import json
from typing import List

from redbot.core import commands


class DallE(commands.Cog):
    """Dall-E mini image generation"""

    def __init__(self, bot):
        self.bot = bot

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.max_concurrency(3, commands.BucketType.default)
    @commands.command()
    @commands.guild_only()
    async def generate(self, ctx: commands.Context, *, prompt: str):
        """
        Generate images through Dall-E mini.

        https://huggingface.co/spaces/dalle-mini/dalle-mini
        """
        embed_links = ctx.channel.permissions_for(ctx.guild.me).embed_links
        if not embed_links:
            return await ctx.send("I need the `Embed Links` permission here before you can use this command.")

        status_msg = await ctx.send("Image generator starting up, please be patient. This will take a very long time.")
        images = None
        attempt = 0
        async with ctx.typing():
            while not images:
                if attempt < 100:
                    attempt += 1
                    if attempt < 10:
                        divisor = 2
                    else:
                        divisor = 5
                    if attempt % divisor == 0:
                        status = f"This will take a very long time. Once a response is acquired, this counter will pause while processing.\n[attempt `{attempt}/100`]"
                        try:
                            await status_msg.edit(content=status)
                        except discord.NotFound:
                            status_msg = await ctx.send(status)

                images = await self.generate_images(prompt)

        file_images = [discord.File(images[i], filename=f"{i}.png") for i in range(len(images))]
        if len(file_images) == 0:
            return await ctx.send(f"I didn't find anything for `{prompt}`.")
        file_images = file_images[:4]

        embed = discord.Embed(
            colour=await ctx.embed_color(),
            title="Dall-E Mini results",
            url="https://huggingface.co/spaces/dalle-mini/dalle-mini",
        )
        embeds = []
        for i, image in enumerate(file_images):
            em = embed.copy()
            em.set_image(url=f"attachment://{i}.png")
            em.set_footer(text=f"Results for: {prompt}, requested by {ctx.author}\nView this output on a desktop client for best results.")
            embeds.append(em)

        form = []
        payload = {"embeds": [e.to_dict() for e in embeds]}
        form.append({"name": "payload_json", "value": discord.utils.to_json(payload)})
        if len(file_images) == 1:
            file = file_images[0]
            form.append(
                {
                    "name": "file",
                    "value": file.fp,
                    "filename": file.filename,
                    "content_type": "application/octet-stream",
                }
            )
        else:
            for index, file in enumerate(file_images):
                form.append(
                    {
                        "name": f"file{index}",
                        "value": file.fp,
                        "filename": file.filename,
                        "content_type": "application/octet-stream",
                    }
                )

        try:
            await status_msg.delete()
        except discord.NotFound:
            pass

        r = Route("POST", "/channels/{channel_id}/messages", channel_id=ctx.channel.id)
        await ctx.guild._state.http.request(r, form=form, files=file_images)

    @staticmethod
    async def generate_images(prompt: str) -> List[io.BytesIO]:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://bf.dallemini.ai/generate", json={"prompt": prompt}) as response:
                if response.status == 200:
                    response_data = await response.json()
                    images = [io.BytesIO(base64.decodebytes(bytes(image, "utf-8"))) for image in response_data["images"]]
                    return images
                else:
                    return None
