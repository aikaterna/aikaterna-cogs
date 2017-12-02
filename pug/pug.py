import json
import os
import requests
from .utils.dataIO import dataIO
from __main__ import send_cmd_help
from discord.ext import commands
from .utils import checks


class Pug:

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json("data/pug/config.json")
        self.fp = "data/pug/config.json"
        API_KEY = self.settings["blizzard_api_key"]
        default_region = self.settings["default_region"]

    LEG_WITH_SOCKET = [
        132369, 132410, 137044, 132444, 132449, 132452, 132460, 133973, 133974, 137037, 137038, 137039, 137040, 137041,
        137042, 137043, 132378, 137045, 137046, 137047, 137048, 137049, 137050, 137051, 137052, 137054, 137055, 137220,
        137223, 137276, 137382, 138854
    ]

    ENCHANTABLE_SLOTS = ["neck", "back", "finger1", "finger2"]

    region_locale = {
        'us': ['us', 'en_US', 'en'],
        'eu': ['eu', 'en_GB', 'en']
    #    'kr': ['kr', 'ko_KR', 'ko'],
    #    'tw': ['tw', 'zh_TW', 'zh'],
    #    'es': ['es', 'es_MX', 'es'],	es lookup is broken until the armory site is migrated to the new format
    }

    def get_sockets(self, player_dictionary):
        """
        Return dict with total sockets and count of equipped gems and slots that are missing

        :param player_dictionary: Retrieved player dict from API
        :return: dict()
        """
        sockets = 0
        equipped_gems = 0

        for item in player_dictionary["items"]:
            if item in "averageItemLevel" or item in "averageItemLevelEquipped":
                continue

            if int(player_dictionary["items"][item]["id"]) in self.LEG_WITH_SOCKET:
                sockets += 1

            for bonus in player_dictionary["items"][item]["bonusLists"]:
                if bonus == 1808:  # 1808 is Legion prismatic socket bonus
                    sockets += 1

            if item in ["neck", "finger1", "finger2"]:
                if player_dictionary["items"][item]["context"] == "trade-skill":
                    sockets += 1

            for ttip in player_dictionary["items"][item]["tooltipParams"]:
                if item in "mainHand" or item in "offHand":  # Ignore Relic
                    continue
                if "gem" in ttip:  # Equipped gems are listed as gem0, gem1, etc...
                    equipped_gems += 1

        return {"total_sockets": sockets,
                "equipped_gems": equipped_gems}

    def get_enchants(self, player_dictionary):
        """
        Get count of enchants missing and slots that are missing
        :param player_dictionary:
        :return: dict()
        """
        self.missing_enchant_slots = []
        for slot in self.ENCHANTABLE_SLOTS:
            if "enchant" not in player_dictionary["items"][slot]["tooltipParams"]:
                self.missing_enchant_slots.append(slot)

        return {
            "enchantable_slots": len(self.ENCHANTABLE_SLOTS),
            "missing_slots": self.missing_enchant_slots,
            "total_missing": len(self.missing_enchant_slots)
        }

    def get_raid_progression(self, player_dictionary, raid):
        r = [x for x in player_dictionary["progression"]
        ["raids"] if x["name"] in raid][0]
        normal = 0
        heroic = 0
        mythic = 0

        for boss in r["bosses"]:
            if boss["normalKills"] > 0:
                normal += 1
            if boss["heroicKills"] > 0:
                heroic += 1
            if boss["mythicKills"] > 0:
                mythic += 1

        return {"normal": normal,
                "heroic": heroic,
                "mythic": mythic,
                "total_bosses": len(r["bosses"])}

    def get_mythic_progression(self, player_dictionary):
        achievements = player_dictionary["achievements"]
        plus_two = 0
        plus_five = 0
        plus_ten = 0

        if 33096 in achievements["criteria"]:
            index = achievements["criteria"].index(33096)
            plus_two = achievements["criteriaQuantity"][index]

        if 33097 in achievements["criteria"]:
            index = achievements["criteria"].index(33097)
            plus_five = achievements["criteriaQuantity"][index]

        if 33098 in achievements["criteria"]:
            index = achievements["criteria"].index(33098)
            plus_ten = achievements["criteriaQuantity"][index]

        return {
            "plus_two": plus_two,
            "plus_five": plus_five,
            "plus_ten": plus_ten
        }

    def get_char(self, name, server, target_region):
        self.settings = dataIO.load_json("data/pug/config.json")  # Load Configs
        API_KEY = self.settings["blizzard_api_key"]
        r = requests.get("https://%s.api.battle.net/wow/character/%s/%s?fields=items+progression+achievements&locale=%s&apikey=%s" % (
                self.region_locale[target_region][0], server, name, self.region_locale[target_region][1], API_KEY))

        if r.status_code != 200:
            raise Exception("Could not find character (No 200 from API).")

        player_dict = json.loads(r.text)

        r = requests.get(
            "https://%s.api.battle.net/wow/data/character/classes?locale=%s&apikey=%s" % (
                self.region_locale[target_region][0], self.region_locale[target_region][1], API_KEY))
        if r.status_code != 200:
            raise Exception("Could Not Find Character Classes (No 200 From API)")
        class_dict = json.loads(r.text)
        class_dict = {c['id']: c['name'] for c in class_dict["classes"]}
		
        r = requests.get("https://%s.api.battle.net/wow/character/%s/%s?fields=stats&locale=%s&apikey=%s" % (
                self.region_locale[target_region][0], server, name, self.region_locale[target_region][1], API_KEY))
        if r.status_code != 200:
            raise Exception("Could not find character stats (No 200 From API).")
        stats_dict = json.loads(r.text)

        health = stats_dict["stats"]["health"]
        power = stats_dict["stats"]["power"]
        powertype = stats_dict["stats"]["powerType"]
        powertypeproper = powertype.title()
        strength = stats_dict["stats"]["str"]
        agi = stats_dict["stats"]["agi"]
        int = stats_dict["stats"]["int"]
        sta = stats_dict["stats"]["sta"]
        crit = stats_dict["stats"]["critRating"]
        critrating = stats_dict["stats"]["crit"]
        haste = stats_dict["stats"]["hasteRating"]
        hasterating = stats_dict["stats"]["haste"]
        mastery = stats_dict["stats"]["masteryRating"]
        masteryrating = stats_dict["stats"]["mastery"]
        vers = stats_dict["stats"]["versatility"]
        versrating = stats_dict["stats"]["versatilityDamageDoneBonus"]
        equipped_ivl = player_dict["items"]["averageItemLevelEquipped"]
        sockets = self.get_sockets(player_dict)
        enchants = self.get_enchants(player_dict)
        tov_progress = self.get_raid_progression(player_dict, "Trial of Valor")
        en_progress = self.get_raid_progression(player_dict, "The Emerald Nightmare")
        nh_progress = self.get_raid_progression(player_dict, "The Nighthold")
        tos_progress = self.get_raid_progression(player_dict, "Tomb of Sargeras")
        ant_progress = self.get_raid_progression(player_dict, "Antorus, the Burning Throne")
        mythic_progress = self.get_mythic_progression(player_dict)

        armory_url = 'http://{}.battle.net/wow/{}/character/{}/{}/advanced'.format(
            self.region_locale[target_region][0], self.region_locale[target_region][2], server, name)

        return_string = ''
        return_string += "**%s** - **%s** - **%s %s**\n" % (
            name.title(), server.title(), player_dict['level'], class_dict[player_dict['class']])
        return_string += '<{}>\n'.format(armory_url)
        return_string += '```ini\n'  # start Markdown

        # iLvL
        return_string += "[Equipped Item Level]: %s\n" % equipped_ivl

        # Mythic Progression
        return_string += "[Mythics]: +2: %s, +5: %s, +10: %s\n" % (mythic_progress["plus_two"],
                                                                 mythic_progress["plus_five"],
                                                                 mythic_progress["plus_ten"])

        # Raid Progression
        return_string += "[EN]: {1}/{0} (N), {2}/{0} (H), {3}/{0} (M)\n".format(en_progress["total_bosses"],
                                                                              en_progress["normal"],
                                                                              en_progress["heroic"],
                                                                              en_progress["mythic"])
        return_string += "[TOV]: {1}/{0} (N), {2}/{0} (H), {3}/{0} (M)\n".format(tov_progress["total_bosses"],
                                                                               tov_progress["normal"],
                                                                               tov_progress["heroic"],
                                                                               tov_progress["mythic"])
        return_string += "[NH]: {1}/{0} (N), {2}/{0} (H), {3}/{0} (M)\n".format(nh_progress["total_bosses"],
                                                                               nh_progress["normal"],
                                                                               nh_progress["heroic"],
                                                                               nh_progress["mythic"])
        return_string += "[TOS]: {1}/{0} (N), {2}/{0} (H), {3}/{0} (M)\n".format(tos_progress["total_bosses"],
                                                                               tos_progress["normal"],
                                                                               tos_progress["heroic"],
                                                                               tos_progress["mythic"])
        return_string += "[ANT]: {1}/{0} (N), {2}/{0} (H), {3}/{0} (M)\n".format(ant_progress["total_bosses"],
                                                                               ant_progress["normal"],
                                                                               ant_progress["heroic"],
                                                                               ant_progress["mythic"])
        # Gems
        return_string += "[Gems Equipped]: %s/%s\n" % (
            sockets["equipped_gems"], sockets["total_sockets"])

        # Enchants
        return_string += "[Enchants]: %s/%s\n" % (enchants["enchantable_slots"] - enchants["total_missing"],
                                                enchants["enchantable_slots"])
        if enchants["total_missing"] > 0:
            return_string += "[Missing Enchants]: {0}".format(
                ", ".join(enchants["missing_slots"]))

        # Stats
        return_string += "\n"
        return_string += "[Health]: {}   [{}]: {}\n".format(health, powertypeproper, power)
        return_string += "[Str]: {}  [Agi]: {}\n".format(strength, agi, int, sta)
        return_string += "[Int]: {}  [Sta]: {}\n".format(int, sta)
        return_string += "[Crit]:    {}, {}%   [Haste]: {}, {}%\n".format(crit, critrating, haste, hasterating,)
        return_string += "[Mastery]: {}, {}%   [Vers]:  {}, {}% bonus damage\n".format(mastery, masteryrating, vers, versrating)

        return_string += '```'  # end Markdown
        return return_string

    @commands.command(name="pug", pass_context=True, no_pm=True)
    async def _pug(self, ctx, *, message):
        """A Warcraft Armory character lookup tool.
        Use: !pug <name> <server> <region>
        Hyphenate two-word servers (Ex: Twisting-Nether)."""
        self.settings = dataIO.load_json("data/pug/config.json")  # Load Configs
        default_region = self.settings["default_region"]
        target_region = default_region
        channel = ctx.message.channel
        try:
            i = str(ctx.message.content).split(' ')
            name = i[1]
            server = i[2]
            if len(i) == 4 and i[3].lower() in self.region_locale.keys():
                target_region = i[3].lower()
            character_info = self.get_char(name, server, target_region)
            await self.bot.send_message(ctx.message.channel, character_info)
        except Exception as e:
            print(e)
            await self.bot.send_message(ctx.message.channel, "Error with character name or server.")

    @commands.command(pass_context=True, name='pugtoken')
    @checks.is_owner()
    async def _pugtoken(self, context, key: str):
        """Sets the token for the Blizzard API.
        You can use this command in a private message to the bot.

        Get an API token at: https://dev.battle.net/member/register"""
        settings = dataIO.load_json(self.fp)
        settings['blizzard_api_key'] = key
        dataIO.save_json(self.fp, settings)
        await self.bot.say("API key set.")

    @commands.command(pass_context=True, name='pugregion')
    @checks.is_owner()
    async def _pugregion(self, context, key: str):
        """Sets the default region."""
        settings = dataIO.load_json(self.fp)
        settings['default_region'] = key
        dataIO.save_json(self.fp, settings)
        await self.bot.say("Default region set.")

    @commands.command()
    async def pugcredits(self):
        """Code credits."""
        message = await self._credit()
        await self.bot.say(message)

    async def _credit(self):
        message = "```This cog is made possible by Pugbot.\n"
        message+= "Please visit https://github.com/reznok/PugBot for more information.\n"
        message+= "```"
        return message


def check_folders():
    if not os.path.exists("data/pug"):
        print("Creating data/pug folder...")
        os.mkdir("data/pug")


def check_files():
    fp = "data/pug/config.json"
    if not dataIO.is_valid_json(fp):
        print("Creating config.json...")
        dataIO.save_json(fp, {"blizzard_api_key": "", "default_region": "us"})


def setup(bot):
    check_folders()
    check_files()
    n = Pug(bot)
    bot.add_cog(n)
