import discord
from redbot.core import commands, checks, Config


BaseCog = getattr(commands, "Cog", object)

class Otherbot(BaseCog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2730321001, force_registration=True)

        default_guild = {"ping": None, "reporting": None, "watching": []}

        self.config.register_guild(**default_guild)

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def otherbot(self, ctx):
        """Otherbot configuration options."""
        pass

    @otherbot.command()
    async def channel(self, ctx, channel: discord.TextChannel = None):
        """Sets the channel to report in."""
        await self.config.guild(ctx.guild).reporting.set(channel.id)
        await ctx.send(f"Reporting channel set to: {channel.mention}.")

    @otherbot.command()
    async def pingrole(self, ctx, role_name: discord.Role = None):
        """Sets the role to use for pinging. Leave blank to reset it."""
        if not role_name:
            await self.config.guild(ctx.guild).ping.set(None)
            return await ctx.send("Ping role cleared.")
        await self.config.guild(ctx.guild).ping.set(role_name.id)
        pingrole_id = await self.config.guild(ctx.guild).ping()
        pingrole_obj = discord.utils.get(ctx.guild.roles, id=pingrole_id)
        await ctx.send(f"Ping role set to: {pingrole_obj.name}.")

    @otherbot.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def watching(self, ctx, bot_user: discord.Member = None):
        """Add a bot to watch. Leave blank to list existing bots on the list."""
        data = await self.config.guild(ctx.guild).all()
        msg = "```Watching these bots:\n"
        if not data["watching"]:
            msg += "None.```"
        if not bot_user:
            for saved_bot_id in data["watching"]:
                bot_user = await self.bot.get_user_info(saved_bot_id)
                if len(bot_user.name) > 16:
                    bot_name = f"{bot_user.name:16}...#{bot_user.discriminator}"
                else:
                    bot_name = f"{bot_user.name}#{bot_user.discriminator}"
                msg += f"{bot_name:24} ({bot_user.id})\n"
            msg += "```"
            return await ctx.send(msg)
        if not bot_user.bot:
            return await ctx.send("User is not a bot.")
        async with self.config.guild(ctx.guild).watching() as watch_list:
            watch_list.append(bot_user.id)
        await ctx.send(f"Now watching: {bot_user.mention}.")
        if not data["reporting"]:
            await self.config.guild(ctx.guild).reporting.set(ctx.message.channel.id)
            await ctx.send(
                f"Reporting channel set to: {ctx.message.channel.mention}. Use `{ctx.prefix}otherbot channel` to change this."
            )

    async def on_member_update(self, before, after):
        data = await self.config.guild(after.guild).all()
        if after.status == discord.Status.offline and (after.id in data["watching"]):
            channel_object = self.bot.get_channel(data["reporting"])
            if not data["ping"]:
                await channel_object.send(f'{after.mention} is offline.')
            else:
                await channel_object.send(f'<@&{data["ping"]}>, {after.mention} is offline.')
        else:
            pass
