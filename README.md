# Discord bots (DraVee's own)

## Index

* [AogoWimsy](#aogowimsy)
  * [As a channel](#as-a-channel)
* [XujiWimsy](#xujiwimsy)
* [Tests](#tests)
* [The Discord applications](#the-discord-applications)

DraVee's personal bots, kept private, each the MCP server a coding session starts, Python 3.12 with its standard
library: AogoWimsy, Aogo (a Claude Code session) on Discord, and XujiWimsy, the same server with a bot of its own, for
Xuji (a Grok Build session). The project's public bots, ReiWimsy and AccordWimsy, are in
[scarletnx/wimsy-core](https://github.com/scarletnx/wimsy-core).

| Bot | What it does | What it reads | What it sends out |
|---|---|---|---|
| `aogo/aogowimsy.py` (AogoWimsy) | Aogo, the Claude Code session, on Discord as a bot user of its own, through five MCP tools: post (only once its owner approves the draft), the same wait on a draft still waiting, read a channel, wait for a reply, save a message's attachments. A Claude Code channel too: while the session runs it stays on Discord's gateway and wakes the session with what is addressed to it | the messages of the channels it lists and their threads, or of every one it sees, and its owner's DMs with it: the owner's, the listed users' and its own reach the session, and a stranger's only once its owner lets it through; the others only counted, and a stranger's DM only by name; its owner's reactions to a draft or to a stranger's message | to Discord, the drafts (to its owner's DMs) and the posts approved; to the session, the messages it may read and the ones addressed to it |
| `xuji/xujiwimsy.py` (XujiWimsy) | Xuji, the Grok Build session, on Discord as a bot user of its own: AogoWimsy's code and five tools, with Xuji's bot and settings. No channel: the session hears by waiting for a reply, and its owner's answers to its drafts and the gateway's news come with its next tool result | as AogoWimsy | as AogoWimsy, but nothing is pushed: the session gets what a tool returns |

No bot keeps a message or logs what was said, and none pings anyone.

## AogoWimsy

A local MCP server: Claude Code starts `aogo/aogowimsy.py` and talks to it on stdin and stdout through the
`initialize` handshake, protocol `2025-11-25` back to `2024-11-05`. It does not speak revision `2026-07-28`: Claude Code
registers no [channel](https://code.claude.com/docs/en/channels-reference) on it, as that revision cannot carry channel
messages ([MCP, Push messages with channels](https://code.claude.com/docs/en/mcp#push-messages-with-channels)), so it
answers a `2026-07-28` client's `server/discover` with method not found, and the client falls back to `initialize`.
Discord's REST API v10 reads and posts; once the client says it is initialized, it also stays on Discord's gateway (a
WebSocket of its own: heartbeats, resume after a drop, a fresh session when Discord ends the old one, backoff up to
60 s), which wakes the session and feeds `discord_wait`. Its tools, as the session sees them:

| Tool | What it does |
|---|---|
| `discord_post(channel, text, reply_to, wait=300, files)` | sends the text as a draft to its owner's DMs with AogoWimsy (the text and its images, `files`: 1 to 4 png, jpg, gif or webp by absolute path, how big each may be Discord's to say; under it a card with the channel's name and id and, for a reply, the message it answers as a link), with a check mark and a cross, then waits up to `wait` s for its owner's reaction, looking every 3 s: the check mark posts the text as it is, with the draft's images fetched from Discord's CDN (without the token), pinging no one, and edits the card to link the post; the cross edits it to say it was not sent; no answer returns the draft's id, still waiting. Another person's reaction counts for nothing |
| `discord_post_status(draft, wait=300)` | the same wait, on a draft that came back still waiting; a draft sent or refused answers that again, and is never posted twice |
| `discord_read(channel, after, limit=50, from)` | the first `limit` messages after an id, or the newest `limit` without one, oldest first: id, author, time, text, the message it answers, attachments by name, and whether it is a stranger's its owner let through |
| `discord_wait(channel, after, wait=600, from)` | the first message after an id from the owner or a listed user, as the gateway brings it; what came before it began listening, from REST |
| `discord_attachments(channel, message)` | saves the attachments of a message `discord_read` gives (the owner's, a listed user's, its own, or a stranger's its owner let through) to `<XDG_CACHE_HOME or ~/.cache>/aogowimsy/<channel>/<message>/`, fetched from Discord's CDN without the token, for the session to open (an image, a log): each one's name, type, size, an image's width and height, and its path, or why it was not saved (over 64 MiB, the CDN's error). A file saved before is not fetched again |

`from` (a list of ids, each the owner or a listed user; anyone else is an error naming the id) narrows read and wait to
those authors: the others join the count of the left out, and wait returns only on one of theirs.

Its owner's check mark is the only way a text gets out, and no setting turns it off. It reads and posts in the listed
channels and their threads, or, with none listed, in every channel and thread Discord lets the bot see (a channel it
cannot see is Discord's 403 or 404, naming it); it reads its owner's DMs with it too. Of what it reads, only the
owner's messages, the listed users' and its own reach the session; a stranger's message reaches it once the owner
lets it through, the others are counted and nothing else of them given. The owner lets a stranger's message through,
that one message:

- with his `:wimsyaogo:` reaction, on a message addressed to AogoWimsy (a mention, or a reply to one of its
  messages); only his reaction counts;
- by replying to it with a message that mentions AogoWimsy, whoever wrote it; a listed user's reply lets nothing
  through.

Nothing is stored but the attachments `discord_attachments` is asked for (folders 700, files 600, kept until someone
removes them): a draft waiting is its message in the owner's DMs, read again at each look, so a restart loses none;
what the owner let through is kept in memory while it runs; stderr says what ran or failed, never what was said nor
who said it. A 429 waits its `retry_after` and tries again; any other failure comes back to the session with Discord's
status and message, as does a value a tool refuses, named with what it takes.

It serves Claude Code alone, so that no other client posts as Aogo: an `initialize` whose `clientInfo` name is not
`claude-code` (Claude Code's) gets an error naming that name and XujiWimsy, the server logs it, and nothing reaches
Discord. XujiWimsy (below) refuses Claude Code the same way.

### As a channel

Started with the development flag (custom channels are not on the research preview's allowlist, so `--channels`
does not take it), from the folder whose `.mcp.json` names it:

    claude --dangerously-load-development-channels server:aogowimsy

Each start shows a warning naming the development channel: answer **I am using this for local development**. The flag
works in an interactive session only (with `-p` Claude Code drops it), and a claude.ai or Console login is needed.
Then, while the session runs, each of these wakes it as a `<channel source="aogowimsy" ...>` event, the text as its
body:

| `kind` | What wakes the session | Its attributes |
|---|---|---|
| `message` | a message addressed to AogoWimsy (a mention, or a reply to one of its messages) from the owner or a listed user, in a channel it may read; any DM the owner or a listed user sends it. When the owner replies to someone while mentioning AogoWimsy, the text ends with the message he replied to, whole | `author`, `author_id`, `channel`, `message_id`, `reply_to`, `attachments`; `quoted_author`, `quoted_author_id`, `quoted_attachments` for the owner's reply |
| `approved` | a stranger's message addressed to AogoWimsy, once the owner puts his `:wimsyaogo:` reaction on it, once | as `message` |
| `dm` | someone neither the owner nor listed wrote to AogoWimsy in DMs: their name and id, never what they wrote; once a person while it runs | `author`, `author_id` |
| `draft` | the owner's check mark or cross on a draft this session made, still waiting: it is posted or refused then, not on a tool's next look (another session's draft waits for that session) | `draft`, `status` (sent, not sent), `channel`; `message_id` once posted |
| `error`, `notice` | the gateway stopped (a close code Discord takes no new try after: a token that is not the bot's, intents not turned on), cannot be reached for three tries in a row, or is back | |

Nothing else wakes it: a message not addressed to AogoWimsy, anything a stranger says before the owner lets it
through, its own messages. Without the flag, the gateway still runs and feeds `discord_wait`, and Claude Code drops
the events. The session answers in Discord with `discord_post` (reply_to the `message_id`), which still waits for the
owner's check mark.

Its settings, a line each of its env file, `~/.config/aogowimsy/aogowimsy.env` unless `--env FILE` names another:

| Key | Default | What it is |
|---|---|---|
| `AOGOWIMSY_TOKEN` | none: needed | the bot's token |
| `AOGOWIMSY_OWNER` | none: needed | the owner's user id: who approves every post and lets a stranger's message through |
| `AOGOWIMSY_USERS` | none: needed | `id,id`: whose messages reach the session (the owner's always do) |
| `AOGOWIMSY_CHANNELS` | every channel and thread the bot can see | `id,id`: where it reads and posts; a thread of one of them counts as it |

A key it does not know stops it, naming the key; so does an id that is not one, an empty or missing needed value, an
empty `AOGOWIMSY_CHANNELS`, a key set twice, and an env file other users can read (its mode must be 600 or stricter: it
says the mode it found). The server's instructions to the session say which channels are in effect. Setting it up,
after its application (below):

1. Its owner shares a server with it and lets that server's members send them DMs (the server's Privacy Settings,
   Direct Messages), or no draft reaches them.
2. The env file, then a look at it: the line `up` names the owner, counts the users and the channels (or says every
   channel it sees), or it says what is wrong and stops. Discord hears nothing until a session is initialized.

       install -d -m 700 ~/.config/aogowimsy
       install -m 600 aogo/aogowimsy.env.example ~/.config/aogowimsy/aogowimsy.env   # then fill it in
       python3 aogo/aogowimsy.py </dev/null

3. Claude Code, from the folder whose sessions may use it (scope `project` writes `.mcp.json` there; `user` would give
   it to every session of the account, wherever it starts). A session started there asks once to use it:

       claude mcp add --scope project aogowimsy -- python3 /path/to/discord-bots/aogo/aogowimsy.py


## XujiWimsy

Xuji, the Grok Build session, on Discord as a bot user of its own. `xuji/xujiwimsy.py` runs `aogo/aogowimsy.py` with
Xuji's identity (the table `IDENTITIES` there): its bot, its env file and keys, its name in every text. Everything
else is AogoWimsy's, a fix to one a fix to both: the five tools above, with the same arguments, defaults and answers;
the owner's check mark as the only way out; the owner, the listed users and the strangers he lets through; nothing
stored, and stderr never saying what was said.

It serves any client but Claude Code: an `initialize` from `claude-code` gets an error naming it and AogoWimsy. It
offers no channel (Grok Build shows no push), so it says in its instructions how Discord reaches the session:

- by waiting: `discord_wait` on a channel, after the id of the newest message the session has seen there
  (`discord_read` gives it), and again after the `after` it returns. It brings the first message from the owner or a
  listed user in that channel or thread; `discord_read` gives the rest, the strangers' messages the owner let through
  among them. The owner's DMs with XujiWimsy are the channel of a draft's link.
- with the next tool result: the gateway still posts a draft the moment its owner answers it, waited on or not, and
  that answer (`The owner approved draft ...: posted as ...`, or refused), and the gateway's news (it stopped, cannot
  be reached, is back), come after that result's own JSON, a text each opening `XujiWimsy news:`. It keeps the newest
  20, and says how many older ones were left out.

A message addressed to Xuji in a channel nobody waits on is not heard until the session reads that channel.

Its settings, a line each of its env file, `~/.config/xujiwimsy/xujiwimsy.env` unless `--env FILE` names another (mode
600 or stricter), with AogoWimsy's meanings and checks:

| Key | Default | What it is |
|---|---|---|
| `XUJIWIMSY_TOKEN` | none: needed | the bot's token |
| `XUJIWIMSY_OWNER` | none: needed | the owner's user id: who approves every post and lets a stranger's message through |
| `XUJIWIMSY_USERS` | none: needed | `id,id`: whose messages reach the session (the owner's always do) |
| `XUJIWIMSY_CHANNELS` | every channel and thread the bot can see | `id,id`: where it reads and posts; a thread of one of them counts as it |

A key it does not know stops it, naming the key: an `AOGOWIMSY_` one too, so one bot's file never starts the other.
Setting it up, after its application (below):

1. Its owner shares a server with it and lets that server's members send them DMs, as for AogoWimsy.
2. The env file, then a look at it (the line `up`, or what is wrong):

       install -d -m 700 ~/.config/xujiwimsy
       install -m 600 xuji/xujiwimsy.env.example ~/.config/xujiwimsy/xujiwimsy.env   # then fill it in
       python3 xuji/xujiwimsy.py </dev/null

3. Grok Build, in `~/.grok/config.toml`, then `grok mcp doctor xujiwimsy` (it initializes the server, which then
   connects to Discord's gateway until the check ends):

       [mcp_servers.xujiwimsy]
       command = "python3"
       args = ["/path/to/discord-bots/xuji/xujiwimsy.py"]
       tool_timeout_sec = 3900

   Grok ends a tool call at `tool_timeout_sec`, and its docs disagree on the default (its README says 60 s, the user
   guide that came with 1.0.60 says 6000 s); a wait may take 3600 s (the most `wait` takes) and the calls to Discord
   around it, so the block sets 3900 and no wait the server takes outlasts it. With less, a longer wait ends in Grok's timeout instead of the
   tool's answer: a draft still waiting is then posted when the owner answers, and the next tool result says so.

Grok Build also starts the MCP servers of `~/.claude.json` and of a `.mcp.json` from its folder up to the git root.
A Grok session started where a `.mcp.json` names aogowimsy would start AogoWimsy, with Aogo's token: AogoWimsy refuses
it, and `grok mcp doctor` shows `handshake failed (JSON-RPC error: -32602: Invalid params: clientInfo.name is
"grok-shell-aogowimsy", not "claude-code": ...)`. To keep it from starting at all, from that folder:

    grok mcp disable aogowimsy        # writes disabled_mcp_servers = ["aogowimsy"] to ~/.grok/config.toml

In Grok Build 1.0.60, neither `[compat.claude] mcps = false` (it covers `~/.claude.json` alone) nor an
`[mcp_servers.aogowimsy]` table holding only `enabled = false` keeps a `.mcp.json` server from starting.

## Tests

    python3 aogo/test_aogowimsy.py && python3 xuji/test_xujiwimsy.py

No network and no Discord: AogoWimsy's env file, its MCP answers (and the
program itself on stdin and stdout), its tools against a fake Discord on 127.0.0.1 (drafts approved, refused, still
waiting, another person's reaction, the channels and the people it may, `from`, Discord's 429s and errors), what the
gateway's events push to the session (who and what wakes it, the owner's reaction and reply letting a stranger
through), and its gateway client against a fake gateway on 127.0.0.1 (identify, heartbeats and their ACKs, resume, the
close codes that stop it, pings, messages in frames), and that lines from several threads never mix on stdout; XujiWimsy's env file and keys (the other bot's refused), its server,
instructions and tools in its own names, the client each Wimsy serves, the news a tool result carries, a post as it
reaches Discord, and the program itself on stdin and stdout.

## The Discord applications

One application each, in the Developer Portal:

1. Bot: reset the token, put it in the env file; turn on **Message Content Intent** (without it, the messages
   AogoWimsy and XujiWimsy read come with no text, and their gateway closes with 4014). AogoWimsy and XujiWimsy: the
   name and avatar are set there too, and **Public Bot** is off, so only the owner adds it to a server. Their gateway
   asks for the intents GUILDS, GUILD_MESSAGES, GUILD_MESSAGE_REACTIONS, DIRECT_MESSAGES, DIRECT_MESSAGE_REACTIONS (the
   owner's answer to a draft, in his DMs) and MESSAGE_CONTENT (46593); only the last is privileged.
2. About me: what it does and that it keeps nothing (AogoWimsy: that it is Aogo, a Claude Code session, and posts
   only what its owner approved; XujiWimsy: that it is Xuji, a Grok Build session, and the same: its posts carry no
   signature, so the profile says who writes).
3. Invite (OAuth2, scope `bot`), with only what it needs:
   - AogoWimsy and XujiWimsy: View Channels, Send Messages, Send Messages in Threads, Read Message History (the
     drafts, their card and their reactions are in DMs, which need none): `permissions=274877975552`

   `https://discord.com/oauth2/authorize?client_id=<APPLICATION_ID>&scope=bot&permissions=<number>`

`AOGOWIMSY_OWNER` and `XUJIWIMSY_OWNER` are the owner's Discord user id (Developer Mode, right click, Copy User ID).
