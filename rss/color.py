from math import sqrt
import discord
import re
import webcolors


_DISCORD_COLOURS = {
    discord.Color.teal().to_rgb(): 'teal',
    discord.Color.dark_teal().to_rgb(): 'dark_teal',
    discord.Color.green().to_rgb(): 'green',
    discord.Color.dark_green().to_rgb(): 'dark_green',
    discord.Color.blue().to_rgb(): 'blue',
    discord.Color.dark_blue().to_rgb(): 'dark_blue',
    discord.Color.purple().to_rgb(): 'purple',
    discord.Color.dark_purple().to_rgb(): 'dark_purple',
    discord.Color.magenta().to_rgb(): 'magenta',
    discord.Color.dark_magenta().to_rgb(): 'dark_magenta',
    discord.Color.gold().to_rgb(): 'gold',
    discord.Color.dark_gold().to_rgb(): 'dark_gold',
    discord.Color.orange().to_rgb(): 'orange',
    discord.Color.dark_orange().to_rgb(): 'dark_orange',
    discord.Color.red().to_rgb(): 'red',
    discord.Color.dark_red().to_rgb(): 'dark_red',
    discord.Color.lighter_grey().to_rgb(): 'lighter_grey',
    discord.Color.light_grey().to_rgb(): 'light_grey',
    discord.Color.dark_grey().to_rgb(): 'dark_grey',
    discord.Color.darker_grey().to_rgb(): 'darker_grey',
    discord.Color.blurple().to_rgb(): 'old_blurple',
    discord.Color(0x4a90e2).to_rgb(): 'new_blurple',
    discord.Color.greyple().to_rgb(): 'greyple',
    discord.Color.dark_theme().to_rgb(): 'discord_dark_theme'
}

_RGB_NAME_MAP = {webcolors.hex_to_rgb(hexcode): name for hexcode, name in webcolors.css3_hex_to_names.items()}
_RGB_NAME_MAP.update(_DISCORD_COLOURS)


def _distance(point_a: tuple, point_b: tuple):
    """
    Euclidean distance between two points using rgb values as the metric space.
    """
    # rgb values
    x1, y1, z1 = point_a
    x2, y2, z2 = point_b

    # distances
    dx = x1 - x2
    dy = y1 - y2
    dz = z1 - z2

    # final distance
    return sqrt(dx**2 + dy**2 + dz**2)

def _linear_nearest_neighbour(all_points: list, pivot: tuple):
    """
    Check distance against all points from the pivot and return the distance and nearest point.
    """
    best_dist = None
    nearest = None
    for point in all_points:
        dist = _distance(point, pivot)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            nearest = point
    return best_dist, nearest


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

        positions = list(_RGB_NAME_MAP.keys())
        dist, nearest = _linear_nearest_neighbour(positions, rgb_tuple)

        return _RGB_NAME_MAP[nearest]

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
