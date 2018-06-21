import os
import aiohttp
from .utils import checks
from discord.ext import commands
import xml.etree.ElementTree as ET
from cogs.utils.dataIO import dataIO
from PIL import Image


class Wolfram:
    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json('data/wolfram/settings.json')
        self.session = aiohttp.ClientSession()

    def __unload(self):
        self.session.close()

    @commands.command(pass_context=True, name='wolfram', aliases=['ask'])
    async def _wolfram(self, context, *arguments: str):
        """
        Ask Wolfram Alpha any question
        """
        api_key = self.settings['WOLFRAM_API_KEY']
        if api_key:
            url = 'http://api.wolframalpha.com/v2/query?'
            query = ' '.join(arguments)
            payload = {'input': query, 'appid': api_key}
            headers = {'user-agent': 'Red-cog/1.0.0'}
            conn = aiohttp.TCPConnector(verify_ssl=False)
            session = aiohttp.ClientSession(connector=conn)
            async with session.get(url, params=payload, headers=headers) as r:
                result = await r.text()
            session.close()
            root = ET.fromstring(result)
            a = []
            for pt in root.findall('.//plaintext'):
                if pt.text:
                    a.append(pt.text.capitalize())
            if len(a) < 1:
                message = 'There is as yet insufficient data for a meaningful answer.'
            else:
                message = '\n'.join(a[0:3])
        else:
            message = 'No API key set for Wolfram Alpha. Get one at http://products.wolframalpha.com/api/'
        await self.bot.say('```{0}```'.format(message))

    @commands.command(pass_context=True, name='wolframs', aliases=['asks'])
    async def _wolframsimple(self, ctx, *arguments : str):
        """
            Ask Wolfram Alpha any question (using SIMPLE API)
        """
        user = ctx.message.author
        channel = ctx.message.channel
        api_key = self.settings['WOLFRAM_API_KEY']
        width = 800
        max_height = 2000
        font_size = 30
        layout = 'labelbar'
        background = '193555'
        foreground = 'white'
        units = 'metric'

        if api_key:
            query = '+'.join(arguments)
            url = 'http://api.wolframalpha.com/v1/simple?appid={}&i={}%3F&width={}&fontsize={}&layout={}&background={}&foreground={}&units={}'.format(
                api_key, query, width, font_size, layout, background, foreground, units)

            #try:
            filename = 'data/wolfram/{}.png'.format(user.id)
            async with self.session.get(url) as r:
                image = await r.content.read()
            with open(filename,'wb') as f:
                f.write(image)

            # crop image
            image = Image.open(filename)
            width = image.size[0]
            height = image.size[1]

            # if too big
            if height > max_height:
                offset = 100
                size_det_img = image.crop((width-offset, 0, width - offset + 1, height))
                # print('DIMENSIONS: ', size_det_img.size)
                size_det_img = size_det_img.convert('RGB')
                current_color = size_det_img.getpixel((0, 0))
                change_height = 0
                for i in range(height):
                    new_pixel_color = size_det_img.getpixel((0, i))
                    # print(current_color, new_pixel_color)
                    if current_color != new_pixel_color:
                        if i > max_height:
                            break
                        change_height = i

                # print('CHANGE HEIGHT: ', change_height)

                img2 = image.crop((0, 0, width, change_height))
                image = img2

            image.save(filename)

            await self.bot.send_file(channel, content="{}".format(user.mention), fp=filename)
            os.remove(filename)
            #except:
                #await self.bot.say('Error')
                #return
        else:
            await self.bot.say('No API key set for Wolfram Alpha. Get one at http://products.wolframalpha.com/api/')
            return

    @commands.command(pass_context=True, name='setwolframapi', aliases=['setwolfram'])
    @checks.is_owner()
    async def _setwolframapi(self, context, key: str):
        """
        Set the api-key
        """
        if key:
            self.settings['WOLFRAM_API_KEY'] = key
            dataIO.save_json('data/wolfram/settings.json', self.settings)


def check_folder():
    if not os.path.exists('data/wolfram'):
        print('Creating data/wolfram folder...')
        os.makedirs('data/wolfram')


def check_file():
    data = {}
    data['WOLFRAM_API_KEY'] = False
    f = 'data/wolfram/settings.json'
    if not dataIO.is_valid_json(f):
        print('Creating default settings.json...')
        dataIO.save_json(f, data)


def setup(bot):
    check_folder()
    check_file()
    n = Wolfram(bot)
    bot.add_cog(n)
