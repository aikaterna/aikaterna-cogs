import discord
import re
from scipy.spatial import KDTree
import webcolors


class Color:
    """Helper for color handling."""

    async def _color_converter(self, hex_code_or_color_word: str):
        """
        Used for user input on rss embed color
        Input:    discord.Color name, CSS3 color name, 0xFFFFFF, #FFFFFF, FFFFFF
        Output:   0xFFFFFF
        """
        # #FFFFFF and FFFFFF to 0xFFFFFF
        hex_match = re.match(r"#?[a-f0-9]{6}", hex_code_or_color_word.lower())
        if hex_match:
            hex_code = f"0x{hex_code_or_color_word.lstrip('#')}"
            return hex_code

        # discord.Color checking
        if hasattr(discord.Color, hex_code_or_color_word):
            hex_code = str(getattr(discord.Color, hex_code_or_color_word)())
            hex_code = hex_code.replace("#", "0x")
            return hex_code

        # CSS3 color name checking
        try:
            hex_code = webcolors.name_to_hex(hex_code_or_color_word, spec="css3")
            hex_code = hex_code.replace("#", "0x")
            return hex_code
        except ValueError:
            pass

        return None

    async def _hex_to_css3_name(self, hex_code: str):
        """
        Input:  0xFFFFFF
        Output: CSS3 color name string closest match
        """
        hex_code = await self._hex_validator(hex_code)
        rgb_tuple = await self._hex_to_rgb(hex_code)

        names = []
        positions = []

        for hex, name in webcolors.css3_hex_to_names.items():
            names.append(name)
            positions.append(webcolors.hex_to_rgb(hex))

        spacedb = KDTree(positions)
        dist, index = spacedb.query(rgb_tuple)

        return names[index]

    async def _hex_to_rgb(self, hex_code: str):
        """
        Input:  0xFFFFFF
        Output: (255, 255, 255)
        """
        return webcolors.hex_to_rgb(hex_code)

    async def _hex_validator(self, hex_code: str):
        """
        Input:  0xFFFFFF
        Output: #FFFFFF or None
        """
        if hex_code[:2] == "0x":
            hex_code = hex_code.replace("0x", "#")
        try:
            # just a check to make sure it's a real color hex code
            hex_code = webcolors.normalize_hex(hex_code)
        except ValueError:
            hex_code = None
        return hex_code
