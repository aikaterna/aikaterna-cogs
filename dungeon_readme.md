
The dungeon cog was written for a specific type of server setup and may or may not work for your needs. This cog stops text and voice channel raiders by restricting new accounts to a read-only channel on-join when set up appropriately.

The ideal guild setup for this cog would be one set up with an autorole so that new users are given a role on-join that sends them to a “verify” or “agreement” or “welcome” channel - usually to agree to rules and receive a new Member role, removing the initial autorole and granting them access to the rest of the server. The everyone role is generally denied from viewing or speaking in any channels and channel access is generally granted through the Member role or other roles after the normal server verification process.


What this cog can do if the above guild restrictions are in place:

- A new user joins the server.
- The cog determines whether the user is new (under a settable threshold of days)
- If the user is new, the dungeon role would be added to them instead of the autorole, restricting them to the dungeon channel where they can only see and not speak. 
- If autoban is on, they will be banned instead of sent to the dungeon.
- If the setting is on to do so, the bot will blacklist the user from using the bot.
- A message is sent to the announce channel with the dungeoned user’s name, id, account age, and whether they have a default profile pic.
- Admins can verify someone in the dungeon by using a command. This will remove the dungeon role, add the initial autorole, and then un-blacklist the user from using the bot.

If a user is over the new user days threshold:

- A new user joins the server.
- They are given the autorole.
- They proceed as normal through the server’s verification/role awarding/welcome channels.

How to set it up:

Turn off your current autorole system, if you have one. This cog will only interact with roles used in this cog like the dungeon role and the user role (autorole).
Remember to deny the Dungeon role from viewing any channel that’s viewable by @ everyone.

Use [p]dungeon autosetup
    This sets up the dungeon/silenced channel in it’s own category.

Use [p]dungeon announce #channel
    This sets up the channel to announce dungeoned users.

Use [p]dungeon userrole rolename
    This sets up the autorole to award if the new user is not a new account.

Use [p]dungeon blacklist
    This toggles the auto-blacklist on. Dungeoned users will be blacklisted from using the bot.

If a user needs to be verified, use [p]dungeon verify id/username. This will remove the dungeon role from them and apply the initial autorole so they can proceed through the server’s verification or welcome process. If a custom message should be sent to the user when they are verified, use [p]dungeon dm message to set a message. The command with no message will turn the DM feature off.

A user can be stripped of all their roles with [p]banish. This will apply the dungeon role to them and if the blacklist toggle is on, blacklist them from using the bot.

Autobanning can be done instead of sending the user to the dungeon channel. It will use the days and profile picture parameters to choose who to auto-ban. Turn autoban on with [p]dungeon autoban and set a message to DM the user: [p]dungeon banmessage. If [p]dungeon modlog is used, it will create a mod log entry if the bot is set up to report bans with the built-in Mod cog instead of reporting to the announce channel.

Current settings can be seen with [p]dungeon settings.
