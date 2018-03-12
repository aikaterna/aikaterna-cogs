#  Lines 54 through 68 are influenced heavily by cacobot's stats module:
#  https://github.com/Orangestar12/cacobot/blob/master/cacobot/stats.py
#  Big thanks to Redjumpman for changing the beta version from 
#  Imagemagick/cairosvg to matplotlib.
#  Thanks to violetnyte for suggesting this cog.
import discord
import heapq
import os
from io import BytesIO
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
plt.switch_backend('agg')
from discord.ext import commands


class ChatChart:
    """Show activity."""

    def __init__(self, bot):
        self.bot = bot
    def create_chart(self, top, others, channel):
        plt.clf()
        sizes = [x[1] for x in top]
        labels = ["{} {:g}%".format(x[0], x[1]) for x in top]
        if len(top) >= 20:
            sizes = sizes + [others]
            labels = labels + ["Others {:g}%".format(others)]
        title = plt.title("Stats in #{}".format(channel.name), color="white")
        title.set_va("top")
        title.set_ha("right")
        plt.gca().axis("equal")
        colors = ['#7e1e9c', '#15b01a','#0343df','#ff81c0','#653700','#e50000','#95d0fc','#029386','#f97306','#96f97b','#c20078','#ffff14','#75bbfd','#929591','#89fe05','#bf77f6','#9a0eea','#033500','#06c2ac','#c79fef','#00035b','#d1b26f','#00ffff','#13eac9']
        pie = plt.pie(sizes, colors=colors, startangle=0)
        plt.legend(pie[0], labels, bbox_to_anchor=(0.7, 0.5), loc="center", fontsize=10,
                   bbox_transform=plt.gcf().transFigure, facecolor='#ffffff')
        plt.subplots_adjust(left=0.0, bottom=0.1, right=0.45)
        image_object = BytesIO()
        plt.savefig(image_object, format='PNG', facecolor='#36393E')
        image_object.seek(0)
        return image_object

    @commands.command(pass_context=True)
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def chatchart(self, ctx, channel: discord.Channel=None):
        """
        Generates a pie chart, representing the last 5000 messages in the specified channel.
        """
        e = discord.Embed(description="Loading...", colour=0x00ccff)
        e.set_thumbnail(url="https://i.imgur.com/vSp4xRk.gif")
        em = await self.bot.say(embed=e)
		
        if channel is None:
            channel = ctx.message.channel
        history = []
        async for msg in self.bot.logs_from(channel, 5000):
            history.append(msg)
        msg_data = {'total count': 0, 'users': {}}

        for msg in history:
            if msg.author.bot:
                pass
            elif msg.author.name in msg_data['users']:
                msg_data['users'][msg.author.name]['msgcount'] += 1
                msg_data['total count'] += 1
            else:
                msg_data['users'][msg.author.name] = {}
                msg_data['users'][msg.author.name]['msgcount'] = 1
                msg_data['total count'] += 1

        for usr in msg_data['users']:
            pd = float(msg_data['users'][usr]['msgcount']) / float(msg_data['total count'])
            msg_data['users'][usr]['percent'] = round(pd * 100, 1)

        top_ten = heapq.nlargest(20, [(x, msg_data['users'][x][y])
                                      for x in msg_data['users']
                                      for y in msg_data['users'][x]
                                      if y == 'percent'], key=lambda x: x[1])
        others = 100 - sum(x[1] for x in top_ten)
        img = self.create_chart(top_ten, others, channel)
        await self.bot.delete_message(em)
        await self.bot.send_file(ctx.message.channel, img, filename="chart.png")


def check_folders():
    if not os.path.exists("data/chatchart"):
        print("Creating data/chatchart folder...")
        os.makedirs("data/chatchart")


def setup(bot):
    check_folders()
    bot.add_cog(ChatChart(bot))