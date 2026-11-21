"""One Discord announcement inbox feeding one Fluxer channel. Python 3.11+."""
import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
HELP = ("!relay follow <Discord channel link or server ID> [display name]\n"
        "!relay unfollow <Discord channel link or server ID>\n!relay list")
ID = re.compile(r"[1-9][0-9]{0,19}")
LINK = re.compile(r"https://(?:(?:ptb|canary)\.)?discord\.com/channels/(\d+)/\d+(?:/\d+)?/?")


class API:
    def __init__(self, base, token):
        self.base = base
        self.token = token

    def call(self, path, body=None):
        req = Request(self.base + path, headers={
            "Authorization": "Bot " + self.token, "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://discord.com/developers/docs, 1.0) RGR-Relay"})
        data = json.dumps(body).encode() if body is not None else None
        try:
            with urlopen(req, data=data, timeout=25) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 429:
                delay = json.load(exc).get("retry_after", 5)
                time.sleep(max(1, float(delay)))
            raise


def new_messages(api, path, cursor):
    # Walk backwards on a full page so even a long outage cannot skip a page.
    params = f"?limit=100&after={cursor}"
    messages = {}
    while True:
        page = api.call(path + params)
        if not page:
            break
        oldest = min(int(m["id"]) for m in page)
        messages.update((int(m["id"]), m) for m in page if int(m["id"]) > cursor)
        if len(page) < 100 or oldest <= cursor:
            break
        params = f"?limit=100&before={oldest}"
    return [messages[k] for k in sorted(messages)]


def command(db, message):
    parts = message["content"].strip().split(maxsplit=3)
    action = parts[1].lower() if len(parts) >= 2 else ""
    if action == "list":
        rows = list(db.execute("SELECT name,id FROM feeds ORDER BY name"))
        return ("Following\n" + "\n".join(f"{name} ({i})" for name, i in rows)
                if rows else "No communities selected yet.\n" + HELP)
    if action not in ("follow", "unfollow") or len(parts) < 3:
        return HELP
    value = parts[2].strip("<>")
    match = LINK.fullmatch(value)
    guild = match[1] if match else value
    if not ID.fullmatch(guild):
        return "Use a Discord server ID or a discord.com/channels link from that community."
    if action == "unfollow":
        db.execute("DELETE FROM feeds WHERE id=?", (guild,))
        return f"Community {guild} is off."
    name = parts[3][:80] if len(parts) == 4 else guild
    db.execute("INSERT INTO feeds VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name",
               (guild, name, message["timestamp"]))
    return f"Following {name} ({guild}) for published posts arriving in the Discord inbox."


def announcement(db, msg):
    if not msg.get("flags", 0) & 2 or msg["flags"] & 8:
        return
    ref = msg.get("message_reference") or {}
    guild, channel, original = (str(ref.get(k, "")) for k in ("guild_id", "channel_id", "message_id"))
    if not all(ID.fullmatch(i) for i in (guild, channel, original)):
        return
    feed = db.execute("SELECT name,since FROM feeds WHERE id=?", (guild,)).fetchone()
    if not feed or datetime.fromisoformat(msg["timestamp"]) < datetime.fromisoformat(feed[1]):
        return
    label = msg.get("author", {}).get("username", guild) if feed[0] == guild else feed[0]
    lines = [msg.get("content", "")]
    for embed in msg.get("embeds", []):
        lines.extend(embed.get(k) or "" for k in ("title", "description", "url"))
        for field in embed.get("fields", []):
            lines.append(f"{field['name']} — {field['value']}")
        for key in ("image", "thumbnail", "video"):
            lines.append((embed.get(key) or {}).get("url", ""))
    lines.extend(a["url"] for a in msg.get("attachments", []))
    body = "\n".join(dict.fromkeys(s for s in lines if s))
    link = f"https://discord.com/channels/{guild}/{channel}/{original}"
    heading = f"**{label}**\n"
    # Budget UTF-16 units for services that count emoji as two.
    budget = 1980 - len((heading + link).encode("utf-16-le")) // 2
    raw = body.encode("utf-16-le")
    if len(raw) > budget * 2:
        body = raw[:budget * 2].decode("utf-16-le", "ignore").rstrip() + "…"
    return heading + body + "\n" + link


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    inbox, destination, owner = (str(cfg[k]) for k in
                                ("discord_inbox", "fluxer_channel", "fluxer_operator"))
    if not all(ID.fullmatch(i) for i in (inbox, destination, owner)):
        raise SystemExit("Enter the three numeric IDs in config.json.")
    discord = API("https://discord.com/api/v10", os.environ["DISCORD_BOT_TOKEN"])
    fluxer = API("https://api.fluxer.app/v1", os.environ["FLUXER_BOT_TOKEN"])
    db = sqlite3.connect(ROOT / "relay.sqlite3")
    db.execute("CREATE TABLE IF NOT EXISTS feeds(id TEXT PRIMARY KEY,name TEXT,since TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS cursors(stream TEXT PRIMARY KEY,last TEXT)")
    target = f"/channels/{destination}/messages"
    streams = [(fluxer, destination), (discord, inbox)]
    ready = set()
    while True:
        for api, channel in streams:
            side = "Fluxer" if api is fluxer else "Discord"
            stream = f"{side}:{channel}"
            path = f"/channels/{channel}/messages"
            try:
                row = db.execute("SELECT last FROM cursors WHERE stream=?", (stream,)).fetchone()
                if row is None:
                    latest = api.call(path + "?limit=1")
                    with db:
                        db.execute("INSERT INTO cursors VALUES(?,?)",
                                   (stream, latest[0]["id"] if latest else "0"))
                else:
                    for msg in new_messages(api, path, int(row[0])):
                        with db:
                            reply = None
                            if api is discord:
                                reply = announcement(db, msg)
                            elif (msg.get("author", {}).get("id") == owner and
                                  not msg.get("webhook_id") and
                                  (msg.get("content") or "").split()[:1] == ["!relay"]):
                                reply = command(db, msg)
                            if reply:
                                # Long command output splits on lines. Announcements fit one post.
                                chunks = [""]
                                for line in reply.split("\n"):
                                    candidate = chunks[-1] + "\n" + line if chunks[-1] else line
                                    if len(candidate.encode("utf-16-le")) > 4000:
                                        chunks.append(line)
                                    else:
                                        chunks[-1] = candidate
                                for chunk in chunks:
                                    fluxer.call(target, {"content": chunk, "allowed_mentions":{"parse":[]}})
                            db.execute("UPDATE cursors SET last=? WHERE stream=?", (msg["id"], stream))
                if side not in ready:
                    print(f"{side} connected.", flush=True)
                    ready.add(side)
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                print(f"{side} processing paused ({error}). Retrying.", flush=True)
                # Commands must be current before applying subscriptions to Discord posts.
                if api is fluxer:
                    break
        time.sleep(12)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
