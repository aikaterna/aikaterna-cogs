# Most of this code is copied from https://github.com/Kowlin/Sentinel/blob/master/githubcards/http.py
# Most of the source of this file can be found at: https://github.com/Kowlin/GraphQL-WoWLogs/blob/master/wowlogs/http.py

from enum import unique
import aiohttp
import logging

from redbot.core.bot import Red
from redbot.core.config import Config

from datetime import datetime

from .calls import Queries

log = logging.getLogger("red.aikaterna.warcraftlogs.http")
baseurl = "https://classic.warcraftlogs.com"
graphql_url = baseurl + "/api/v2/client"


async def generate_bearer(bot: Red, config: Config) -> str:
    """Generate the Bearer token used in GraphQL queries

    Bot and Config are imported here from the main class,
    due the need to save data to both of them."""
    tokens = await bot.get_shared_api_tokens("warcraftlogs")

    client_id = tokens.get("client_id", "")
    client_secret = tokens.get("client_secret", "")
    if not client_id:
        log.error("Generate bearer: No valid client ID set")
        return None
    elif not client_secret:
        log.error("Generate bearer: No valid client secret set")
        return None
    else:
        headers = {"User-Agent": "Red-DiscordBot/WarcraftLogsCog"}
        async with aiohttp.ClientSession(
            headers=headers, auth=aiohttp.BasicAuth(login=client_id, password=client_secret)
        ) as session:
            form = aiohttp.FormData()
            form.add_field("grant_type", "client_credentials")
            request = await session.post(f"{baseurl}/oauth/token", data=form)
            json = await request.json()
            if json.get("error", ""):
                log.error("There is an error generating the bearer key, probably a misconfigured client id and secret.")
                log.error(f"{json['error']}: {json['error_description']}")
                return None

            timestamp_now = int(datetime.utcnow().timestamp())  # Round the timestamp down to a full number
            bearer_timestamp = (
                timestamp_now + json["expires_in"] - 120
            )  # Reduce the timestamp by 2 min to be on the safe side of possible errors
            await config.bearer_timestamp.set(bearer_timestamp)

            log.info("Bearer token created")
            await bot.set_shared_api_tokens("warcraftlogs", bearer=json["access_token"])
            return json["access_token"]


class WoWLogsClient:
    """This is where the magic happens."""

    def __init__(self, bearer: str) -> None:
        self.session: aiohttp.ClientSession
        self._bearer: str
        self._create_session(bearer)

    def _create_session(self, bearer: str) -> None:
        headers = {
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            # Not strictly required to set an user agent, yet still respectful.
            "User-Agent": "Red-DiscordBot/WarcraftLogsCog",
        }
        self._bearer = bearer
        self.session = aiohttp.ClientSession(headers=headers)

    async def recreate_session(self, bearer: str) -> None:
        await self.session.close()
        self._create_session(bearer)

    async def check_bearer(self):
        async with self.session.post(graphql_url, json={"query": Queries.check_bearer}) as call:
            try:
                await call.json()
            except aiohttp.ContentTypeError:
                log.error("Bearer token has been invalidated")
                return False
            return True

    async def get_overview(self, char_name: str, char_realm: str, char_server: str, zone_id: int):
        async with self.session.post(
            graphql_url,
            json={
                "query": Queries.get_overview,
                "variables": {
                    "char_name": char_name,
                    "char_realm": char_realm,
                    "char_server": char_server,
                    "zone_id": zone_id,
                },
            },
        ) as call:
            try:
                json = await call.json()
            except aiohttp.ContentTypeError:
                log.error("Bearer token has been invalidated")
                return None

            error = json.get("error", None)
            if error:
                log.error(f"Error: {error}")

            return json

    async def get_last_encounter(self, char_name: str, char_realm: str, char_server: str):
        async with self.session.post(
            graphql_url,
            json={
                "query": Queries.get_last_encounter,
                "variables": {"char_name": char_name, "char_realm": char_realm, "char_server": char_server},
            },
        ) as call:
            try:
                json = await call.json()
            except aiohttp.ContentTypeError:
                log.error("Bearer token has been invalidated")
                return None

            error = json.get("error", None)
            if error:
                log.error(f"Error: {error}")
                return json

            if json["data"]["characterData"]["character"] is None:
                return False

            data = json["data"]["characterData"]["character"]["recentReports"]["data"]
            unique_encouters = {"ids": [], "latest": 0, "latest_time": 0}
            for fight in data[0]["fights"]:
                if fight["encounterID"] not in unique_encouters["ids"]:
                    unique_encouters["ids"].append(int(fight["encounterID"]))
                if fight["endTime"] > unique_encouters["latest_time"]:
                    unique_encouters["latest"] = fight["encounterID"]
                    unique_encouters["latest_time"] = fight["endTime"]
            return unique_encouters

    async def get_gear(self, char_name: str, char_realm: str, char_server: str, encounter_id: int):
        async with self.session.post(
            graphql_url,
            json={
                "query": Queries.get_gear,
                "variables": {
                    "char_name": char_name,
                    "char_realm": char_realm,
                    "char_server": char_server,
                    "encounter": encounter_id,
                },
            },
        ) as call:
            try:
                json = await call.json()
            except aiohttp.ContentTypeError:
                log.error("Bearer token has been invalidated")
                return None

            error = json.get("error", None)
            if error:
                log.error(f"Error: {error}")
                return json

            if json["data"]["characterData"]["character"] is None:
                return False

            data = json["data"]["characterData"]["character"]
            return data
