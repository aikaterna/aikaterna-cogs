#  get_default_channel_or_other is from Squid's Admin cog:
#  https://github.com/tekulvw/Squid-Plugins

import discord
import traceback


class ServerLimit:
    def __init__(self, bot):
        self.bot = bot

    async def _message(self, server):
        server_owner = server.owner
        notice_msg = "Hi, I tried to make an announcement in your "\
        + "server, " + server.name + ", but I don't have "\
        + "permissions to send messages in the default "\
        + "channel there!"
        await self.bot.send_message(server_owner, notice_msg)
        await self.bot.leave_server(server)

    async def on_server_join(self, server):
        chan = self.get_default_channel_or_other(server,
                                                 discord.ChannelType.text,
                                                 send_messages=True)
        me = server.me
        server_owner = server.owner
        msg = "I can only join servers which have more than 25 members. "\
        + "Please try again later when the server is larger."
        if len(server.members) <= 25:
            if chan is not None:
                if chan.permissions_for(me).send_messages:
                    await self.bot.send_message(chan, msg)
                    await self.bot.leave_server(server)
                else:
                    await self._message(server)
                    await self.bot.send_message(server_owner, msg)
            else:
                await self._message(server)
                await self.bot.send_message(server_owner, msg)

    def get_default_channel_or_other(self, server,
                                     ctype: discord.ChannelType=None,
                                     **perms_required):

        perms = discord.Permissions.none()
        perms.update(**perms_required)
        if ctype is None:
            types = [discord.ChannelType.text, discord.ChannelType.voice]
        elif ctype == discord.ChannelType.text:
            types = [discord.ChannelType.text]
        else:
            types = [discord.ChannelType.voice]
        try:
            channel = server.default_channel
        except Exception:
            channel = None
        if channel is not None:
            if channel.permissions_for(server.me).is_superset(perms):
                return channel

        chan_list = [c for c in sorted(server.channels,
                                       key=lambda ch: ch.position)
                     if c.type in types]
        for ch in chan_list:
            if ch.permissions_for(server.me).is_superset(perms):
                return ch
        return None


def setup(bot):
    bot.add_cog(ServerLimit(bot))
