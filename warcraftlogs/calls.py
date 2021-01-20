# Most of the source of this file can be found at: https://github.com/Kowlin/GraphQL-WoWLogs/blob/master/wowlogs/calls.py

class Queries:

    get_last_encounter = """
    query ($char_realm: String!, $char_name: String!, $char_server: String!) {
  rateLimitData {
    limitPerHour
    pointsSpentThisHour
    pointsResetIn
  }
  characterData {
    character(name: $char_name, serverSlug: $char_realm, serverRegion: $char_server) {
      name
      id
      classID
      recentReports(limit: 1) {
        data {
          fights(killType: Kills) {
            encounterID
            name
            endTime
          }
        }
      }
    }
  }
}
"""

    get_overview = """
    query ($char_realm: String!, $char_name: String!, $char_server: String!, $zone_id: Int!) {
  rateLimitData {
    limitPerHour
    pointsSpentThisHour
    pointsResetIn
  }
  characterData {
    character(name: $char_name, serverSlug: $char_realm, serverRegion: $char_server) {
      name
      id
      zoneRankings(zoneID: $zone_id)
      }
    }
  }
"""

    get_gear = """
    query($char_realm: String!, $char_name: String!, $char_server: String!, $encounter: Int!) {
  rateLimitData {
    limitPerHour
    pointsSpentThisHour
    pointsResetIn
  }
  characterData {
    character(name: $char_name, serverSlug: $char_realm, serverRegion: $char_server) {
      name
      id
      classID
      encounterRankings(includeCombatantInfo: true, byBracket: true, encounterID: $encounter)
    }
  }
}
"""

    check_bearer = """
    query {
  rateLimitData {
    limitPerHour
    pointsSpentThisHour
    pointsResetIn
  }
}
"""
