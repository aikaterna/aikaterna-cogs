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

    def create_chart(self, top, others):
        plt.clf()
        sizes = [x[1] for x in top]
        labels = ["{} {:g}%".format(x[0], x[1]) for x in top]
        if len(top) >= 10:
            sizes = sizes + [others]
            labels = labels + ["Others {:g}%".format(others)]

        title = plt.title('User activity in the last 5000 messages')
        title.set_va("top")
        title.set_ha("left")
        plt.gca().axis("equal")
        colors = ['r', 'darkorange', 'gold', 'y', 'olivedrab', 'green', 'darkcyan', 'mediumblue', 'darkblue', 'blueviolet', 'indigo']
        pie = plt.pie(sizes, colors=colors, startangle=0)
        plt.legend(pie[0], labels, bbox_to_anchor=(0.7, 0.5), loc="center", fontsize=10,
                   bbox_transform=plt.gcf().transFigure)
        plt.subplots_adjust(left=0.0, bottom=0.1, right=0.45)
        image_object = BytesIO()
        plt.savefig(image_object, format='PNG')
        image_object.seek(0)
        return image_object

    @commands.command(pass_context=True)
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def chatchart(self, ctx):
        """
        Generates a pie chart, representing the last 5000 messages in this channel.
        """
        channel = ctx.message.channel
        e = discord.Embed(description="Loading...", colour=0x00ccff)
        e.set_thumbnail(url="https://i.imgur.com/vSp4xRk.gif")
        em = await self.bot.say(embed=e)

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

        top_ten = heapq.nlargest(10, [(x, msg_data['users'][x][y])
                                      for x in msg_data['users']
                                      for y in msg_data['users'][x]
                                      if y == 'percent'], key=lambda x: x[1])
        others = 100 - sum(x[1] for x in top_ten)
        img = self.create_chart(top_ten, others)
        await self.bot.delete_message(em)
        await self.bot.send_file(channel, img, filename="chart.png")


def check_folders():
    if not os.path.exists("data/chatchart"):
        print("Creating data/chatchart folder...")
        os.makedirs("data/chatchart")


def setup(bot):
    check_folders()
    bot.add_cog(ChatChart(bot))
