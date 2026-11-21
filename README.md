# Rebel Gaming Republic announcement relay

Run one copy on your PC or an always-on host. It polls about every 12 seconds, reads one Discord inbox, and posts to one Fluxer channel. A single Fluxer operator controls subscriptions in that channel. Requires Python 3.11 or newer. No Python packages to install.

## Connect Discord

1. Create a text channel such as #announcement-inbox in a Discord server you manage.
2. In each source community, open its megaphone announcement channel, choose **Follow**, and select your inbox. You need Manage Webhooks in the destination to set up the follow. You can point multiple channels and communities at the same inbox.
3. At https://discord.com/developers/applications create an application. In **Bot**, enable **Message Content Intent** and obtain the bot token. In **Installation** or the OAuth2 URL Generator, make a guild install link with the **bot** scope. Install the bot in your inbox server and give it **View Channel** and **Read Message History** in the inbox. The bot only needs read access there.
4. Enable Developer Mode in Discord settings and copy the inbox channel ID. Also copy a channel link from each **original source community** you want to select. A regular invite link does not identify the source for the relay.

## Connect Fluxer

1. In Fluxer **User Settings → Applications**, create an application and obtain its bot token. Use the application's bot authorization link to install it in your Fluxer community. Grant **View Channel**, **Read Message History**, and **Send Messages** in the destination text channel, e.g. #game-news.
2. Copy the destination channel ID and your own Fluxer user ID (enable Developer Mode if needed). The operator ID is the person authorized to change subscriptions.
3. Extract this ZIP. On Windows, open PowerShell in the extracted folder and run:
   
   ~~~powershell
   .\start.ps1
   ~~~
   
   On first run it opens config.json. Replace all three placeholders with the IDs, keep the quotes, save, and close the editor. Enter each bot token at its hidden prompt. If your Python installation has only a python command, use the manual steps below.
4. Wait until the console says both services connected. In the configured Fluxer channel, type the following, replacing the example link with a channel link from the source community:
   
   ~~~text
   !relay follow https://discord.com/channels/123456789012345678/234567890123456789 Phigros
   !relay list
   ~~~
   
   The final name is an optional display label. A selection covers every channel from that Discord server that you followed into the inbox. Select more communities with additional follow commands. Remove one with `!relay unfollow 123456789012345678`. Type `!relay` for help.

## Manual startup

Copy config.example.json to config.json and fill in the IDs. Supply DISCORD_BOT_TOKEN and FLUXER_BOT_TOKEN as environment variables in the hosting environment, then run `python relay.py` (or `python3 relay.py`). Tokens are the raw bot credentials without a "Bot " prefix. Keep the process running. On Windows the launcher prompts again in a fresh terminal unless those variables are already set.

## What to expect

The first launch starts at the current tip of each channel. Selecting a community enables future published announcements. Typing into the inbox by hand will not trigger the relay. To test on demand, follow an announcement channel you control, select its community, then **publish** a new Discord announcement. Expect its text, community label and original Discord link to appear in Fluxer. Someone opening the link needs Discord access to that post.

The relay includes embed text and attachment links when available and shortens oversized posts with a link to the full announcement. Discord attachment links may expire. Mentions do not ping Fluxer members. Source edits and deletions are not mirrored. Ordinary Discord text channels have no Follow feed.

Keep relay.sqlite3 beside the program between runs. It stores subscriptions and read positions. Run only one instance per folder. After downtime the relay catches up from those positions as far as both platforms' accessible history allows. A crash or connection loss immediately after Fluxer accepts a post can repeat that post on retry.

For no output, check both connection messages, use !relay list, verify the selected server ID matches the original community, and look for a newly published copy in the Discord inbox. A 401 points to credentials, and a 403 generally points to channel access. If only the Discord link comes through on text posts, check Message Content Intent. A failing post stays pending and is retried.

Platform references: [Discord Channel Following](https://support.discord.com/hc/en-us/articles/360028384531-Channel-Following-FAQ) · [Fluxer bots](https://fluxer.com/help/bots) · [Fluxer message API](https://docs.fluxer.com/http-api/messages/)
