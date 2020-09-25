from typing import Literal

import aiohttp
import datetime
import discord
import itertools
import json
from operator import itemgetter
from redbot.core import Config, commands, checks
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


class WarcraftLogs(commands.Cog):
    """Access Warcraftlogs stats."""

    async def red_delete_data_for_user(
        self, *, requester: Literal["discord", "owner", "user", "user_strict"], user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2713931001, force_registration=True)
        self.session = aiohttp.ClientSession()
        self.zones = [1005, 1004, 1003, 1002] # Ony and MC removed as we are now in ph 5
        self.partitions = [3, 2] # No partition 1 needed here now - ZG, AQ, BWL were not present in ph 1 & 2

        default_user = {
            "charname": None,
            "realm": None,
            "region": None,
        }

        default_global = {
            "apikey": None,
        }

        self.config.register_user(**default_user)
        self.config.register_global(**default_global)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.command()
    async def wclregion(self, ctx, region: str):
        """Set your region."""
        valid_regions = ["EU", "US"]
        if region.upper() not in valid_regions:
            return await ctx.send("Valid regions are: {humanize_list(valid_regions)}")
        await self.config.user(ctx.author).region.set(region)
        await ctx.send(f"Your server's region was set to {region.upper()}.")

    @commands.command()
    async def wclcharname(self, ctx, charname: str):
        """Set your character's name."""
        await self.config.user(ctx.author).charname.set(charname)
        await ctx.send(f"Your character name was set to {charname.title()}.")

    @commands.command()
    async def wclrealm(self, ctx, *, realm: str):
        """Set your realm."""
        realmname = realm.replace(" ", "-")
        await self.config.user(ctx.author).realm.set(realmname)
        await ctx.send(f"Your realm was set to {realm.title()}.")

    @commands.command()
    async def wclsettings(self, ctx, user: discord.User = None):
        """Show your current settings."""
        if not user:
            user = ctx.author
        userinfo = await self.config.user(user).all()
        msg = f"[Settings for {user.display_name}]\n"
        charname = userinfo["charname"].title() if userinfo["charname"] else "None"
        realmname = userinfo["realm"].title().replace("-", " ") if userinfo["realm"] else "None"
        regionname = userinfo["region"].upper() if userinfo["region"] else "None"
        msg += f"Character: {charname}\nRealm: {realmname}\nRegion: {regionname}\n"
        await ctx.send(box(msg, lang="ini"))

    @commands.command()
    @checks.is_owner()
    async def wclapikey(self, ctx, apikey: str):
        """Set the api key."""
        await self.config.apikey.set(apikey)
        try:
            await ctx.message.delete()
        except discord.errors.Forbidden:
            pass
        await ctx.send(f"The WarcraftLogs API key has been set.")

    @commands.command()
    @commands.guild_only()
    async def wclrank(self, ctx, username=None, realmname=None, region=None):
        """Fetch ranking info about a player."""
        userdata = await self.config.user(ctx.author).all()
        apikey = await self.config.apikey()
        if not apikey:
            return await ctx.send("The bot owner needs to set a WarcraftLogs API key before this can be used.")
        if not username:
            username = userdata["charname"]
            if not username:
                return await ctx.send("Please specify a character name with this command.")
        if not realmname:
            realmname = userdata["realm"]
            if not realmname:
                return await ctx.send("Please specify a realm name with this command.")
        if not region:
            region = userdata["region"]
            if not region:
                return await ctx.send("Please specify a region name with this command.")

        final_embed_list = []
        kill_data = []
        log_data = []

        async with ctx.channel.typing():
            for zone in self.zones:
                for phase in self.partitions:
                    url = f"https://classic.warcraftlogs.com/v1/parses/character/{username}/{realmname}/{region}?zone={zone}&partition={phase}&api_key={apikey}"
                    try:
                        async with self.session.request("GET", url) as page:
                            data = await page.text()
                            data = json.loads(data)
                    except Exception as e:
                        return await ctx.send(
                            f"Oops, there was a problem fetching something (Zone {zone}/Phase {phase}): {e}"
                        )
                    if "error" in data:
                        return await ctx.send(
                            f"{username.title()} - {realmname.title()} ({region.upper()}) doesn't have any valid logs that I can see.\nError {data['status']}: {data['error']}"
                        )
                    # Logged Kills
                    zone_name = self.get_zone(zone)
                    zone_and_phase = f"{zone_name}_{phase}"
                    area_data = self.get_kills(data, zone_and_phase)
                    kill_data.append(area_data)
                    # Log IDs for parses
                    log_info = self.get_log_id(data, zone_and_phase)
                    log_data.append(log_info)

        # Logged Kill sorting
        embed1 = discord.Embed(title=f"{username.title()} - {realmname.title()} ({region.upper()})\nLogged Kills")
        for item in kill_data:
            zone_kills = ""
            for boss_info in list(item.values()):
                zone_name, phase_num = self.clean_name(list(item))
                for boss_name, boss_kills in boss_info.items():
                    zone_kills += f"{boss_name}: {boss_kills}\n"
            if zone_kills:
                embed1.add_field(name=f"{zone_name}\n{phase_num}", value=zone_kills)
        embed1.set_footer(text="Molten Core and Onyxia are not currently displayed as we are now in Phase 5.")
        final_embed_list.append(embed1)

        # Log ID sorting
        wcl_url = "https://classic.warcraftlogs.com/reports/{}#fight={}"
        log_embed_list = []

        for item in log_data:
            log_page = ""
            for id_data in list(item.values()):
                sorted_item = {k: v for k, v in sorted(id_data.items(), key=lambda item: item[1], reverse=True)}
                short_list = dict(itertools.islice(sorted_item.items(), 5))
                zone_name, phase_num = self.clean_name(list(item))
                for log_id, info_list in short_list.items():
                    # info_list: [timestamp:int, percentile:int, spec:str, fightid:int, rank:int, outOf:int]
                    # log_id: encounterid-encountername
                    log_url = log_id.split("-")[0]
                    log_name = log_id.split("-")[1]
                    log_page += f"{wcl_url.format(log_url, info_list[3])}\n{self.time_convert(info_list[0])} UTC\nEncounter: {log_name}\nDPS Percentile: {info_list[1]} [{info_list[4]} of {info_list[5]}] ({info_list[2]})\n\n"

            if id_data:
                embed = discord.Embed(
                    title=f"{username.title()} - {realmname.title()} ({region.upper()})\nWarcraft Log IDs"
                )
                embed.add_field(name=f"{zone_name}\n{phase_num}", value=log_page, inline=False)
                embed.set_footer(text="Up to the last 5 logs shown per encounter/phase.")
                log_embed_list.append(embed)

        for log_embed in log_embed_list:
            final_embed_list.append(log_embed)

        await menu(ctx, final_embed_list, DEFAULT_CONTROLS)

    # @commands.command()
    # @commands.guild_only()
    # async def wclgear(self, ctx, username=None, realmname=None, region=None):
        # """Fetch gear info about a player."""
        # userdata = await self.config.user(ctx.author).all()
        # apikey = await self.config.apikey()
        # if not apikey:
            # return await ctx.send("The bot owner needs to set a WarcraftLogs API key before this can be used.")
        # if not username:
            # username = userdata["charname"]
            # if not username:
                # return await ctx.send("Please specify a character name with this command.")
        # if not realmname:
            # realmname = userdata["realm"]
            # if not realmname:
                # return await ctx.send("Please specify a realm name with this command.")
        # if not region:
            # region = userdata["region"]
            # if not region:
                # return await ctx.send("Please specify a region name with this command.")

        # all_encounters = []
        # for zone, phase in [(x, y) for x in self.zones for y in self.partitions]:
            # url = f"https://classic.warcraftlogs.com/v1/parses/character/{username}/{realmname}/{region}?zone={zone}&partition={phase}&api_key={apikey}"

            # async with self.session.request("GET", url) as page:
                # data = await page.text()
                # data = json.loads(data)
                # if "error" in data:
                    # return await ctx.send(
                        # f"{username.title()} - {realmname.title()} ({region.upper()}) doesn't have any valid logs that I can see.\nError {data['status']}: {data['error']}"
                    # )
                # if data:
                    # encounter = self.get_recent_gear(data)
                    # if encounter:
                        # all_encounters.append(encounter)
        # final = self.get_recent_gear(all_encounters)

        # wowhead_url = "https://classic.wowhead.com/item={}"
        # wcl_url = "https://classic.warcraftlogs.com/reports/{}"
        # itempage = ""

        # for item in final["gear"]:
            # if item["id"] == 0:
                # continue
            # rarity = self.get_rarity(item)
            # itempage += f"{rarity} [{item['name']}]({wowhead_url.format(item['id'])})\n"
        # itempage += f"\nAverage ilvl: {final['ilvlKeyOrPatch']}"

        # embed = discord.Embed(
            # title=f"{final['characterName']} - {final['server']} ({region.upper()})\n{final['class']} ({final['spec']})",
            # description=itempage,
        # )
        # embed.set_footer(
            # text=f"Gear data pulled from {wcl_url.format(final['reportID'])}\nEncounter: {final['encounterName']}\nLog Date/Time: {self.time_convert(final['startTime'])} UTC"
        # )
        # await ctx.send(embed=embed)

    @staticmethod
    def get_rarity(item):
        rarity = item["quality"]
        if rarity == "common":
            return "⬜"
        elif rarity == "uncommon":
            return "🟩"
        elif rarity == "rare":
            return "🟦"
        elif rarity == "epic":
            return "🟪"
        else:
            return "🔳"

    @staticmethod
    def time_convert(time):
        time = str(time)[0:10]
        value = datetime.datetime.fromtimestamp(int(time)).strftime("%Y-%m-%d %H:%M:%S")
        return value

    @staticmethod
    def get_kills(data, zone_and_phase):
        # data is json data
        # zone_and_phase: Name_Phasenum
        boss_kills = {}
        for encounter in data:
            if encounter["encounterName"] not in boss_kills.keys():
                boss_kills[encounter["encounterName"]] = 0
            boss_kills[encounter["encounterName"]] += 1
        complete_info = {}
        complete_info[zone_and_phase] = boss_kills
        return complete_info

    @staticmethod
    def get_zone(zone):
        # Zone ID and name is available from the API, but why make another
        # call to a url when it's simple for now... maybe revisit in phase 5+
        if zone == 1000:
            zone_name = "MoltenCore"
        elif zone == 1001:
            zone_name = "Onyxia"
        elif zone == 1002:
            zone_name = "BWL"
        elif zone == 1003:
            zone_name = "ZG"
        elif zone == 1004:
            zone_name = "AQ20"
        elif zone == 1005:
            zone_name = "AQ40"
        else:
            zone_name = None
        return zone_name

    @staticmethod
    def clean_name(zone_and_phase):
        zone_and_phase = zone_and_phase[0]
        zone_name = zone_and_phase.split("_")[0]
        phase_num = zone_and_phase[-1]

        if zone_name == "MoltenCore":
            zone_name = "Molten Core"
        elif zone_name == "BWL":
            zone_name = "Blackwing Lair"
        elif zone_name == "ZG":
            zone_name = "Zul'Gurub"
        elif zone_name == "AQ20":
            zone_name = "Ahn'Qiraj Ruins"
        elif zone_name == "AQ40":
            zone_name = "Ahn'Qiraj Temple"
        else:
            zone_name = zone_name

        if phase_num == "1":
            phase_num = "Phase 1 & 2"
        elif phase_num == "2":
            phase_num = "Phase 3 & 4"
        else:
            phase_num = "Phase 5"
        return zone_name, phase_num

    @staticmethod
    def get_log_id(data, zone_and_phase):
        report_ids = {}
        for encounter in data:
            keyname = f"{encounter['reportID']}-{encounter['encounterName']}"
            report_ids[keyname] = [
                encounter["startTime"],
                encounter["percentile"],
                encounter["spec"],
                encounter["fightID"],
                encounter["rank"],
                encounter["outOf"],
            ]
        complete_info = {}
        complete_info[zone_and_phase] = report_ids
        return complete_info

    @staticmethod
    def get_recent_gear(data):
        date_sorted_data = sorted(data, key=itemgetter("startTime"), reverse=True)
        for encounter in date_sorted_data:
            try:
                item_name = encounter["gear"][0]["name"]
                if item_name == "Unknown Item":
                    continue
                else:
                    return encounter
            except KeyError:
                return None
