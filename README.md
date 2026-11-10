# Discord bots (DraVee's own)

## Index

* [AogoWimsy](#aogowimsy)
  * [Its slash command](#its-slash-command)
  * [Who reaches it, the pre-harness and direct posts](#who-reaches-it-the-pre-harness-and-direct-posts)
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
| `aogo/aogowimsy.py` (AogoWimsy) | Aogo, the Claude Code session, on Discord as a bot user of its own, through eleven MCP tools: post (once its owner approves the draft, or at once where the rules he sets let it), the same wait on a draft still waiting, read a channel, wait for a reply, save a message's attachments, put or take off one of a fixed few reactions, answer with one of those emojis alone (neither carries text, so both go at once), upload the server's custom emojis it answers with, list who its owner allowed, and ice someone who tried what its harness refuses. A slash command, `/aogo`: help for anyone, and its owner's trust, allow, weight and ice for people and tone for channels. A pre-harness of rules checks what comes in and what goes out direct. A Claude Code channel too: while the session runs it stays on Discord's gateway and wakes the session with what is addressed to it, each event saying how much its author is trusted, how an answer may go and its channel's tone, and greets a stranger who calls it with a fixed line that pings its owner, within limits | the messages of the channels it lists and their threads, or of every one it sees, and its owner's DMs with it: the owner's, those he trusts or allowed (as much as their weight lets) and its own reach the session, and a stranger's only once its owner lets it through; the others only counted, and a stranger's DM only by name; its owner's reactions to a draft or to a stranger's message; Claude Code's status line (the quota, the context, this session's agents) | to Discord, the drafts (to its owner's DMs), the posts approved, the direct posts, its reactions and quick replies, the four emojis it uploads, its greeting to a stranger who calls it, the pre-harness's and the ice's fixed lines, `/aogo` and its answers (seen by their asker alone), `/aogo people` (to its owner's DMs); to the session, the messages it may read and the ones addressed to it |
| `xuji/xujiwimsy.py` (XujiWimsy) | Xuji, the Grok Build session, on Discord as a bot user of its own: AogoWimsy's code and its eleven tools, `/xuji`, with Xuji's bot, settings and drawn emojis, its reactions and quick replies the unicode emojis alone. It pushes what is addressed to Xuji, its owner's answers to its drafts and the gateway's news to the session's monitor, a line each, as Grok Build takes no push from an MCP server | as AogoWimsy | as AogoWimsy, but to the session's monitor (a local socket) in place of a claude/channel, no drawn emoji, and it greets no one and has no command |

No bot keeps a message or logs what was said, and none pings anyone but AogoWimsy's greeting and its ice lines, which
ping its owner (an ice line for a secret or abuse, the server's admin role too).

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
| `discord_post(channel, text, reply_to, wait=300, files, direct)` | sends the text as a draft to its owner's DMs with AogoWimsy (the text and its images, `files`: 1 to 4 png, jpg, gif or webp by absolute path, how big each may be Discord's to say; under it a card with the channel's name and id and, for a reply, the message it answers as a link), with a check mark and a cross, then waits up to `wait` s for its owner's reaction, looking every 3 s: the check mark posts the text as it is, with the draft's images fetched from Discord's CDN (without the token), pinging no one, and edits the card to link the post; the cross edits it to say it was not sent; no answer returns the draft's id, still waiting. Another person's reaction counts for nothing. With `direct` true it posts at once, with no draft, where the rules below let it, and returns the post's link and how many replies to that message are left, or when the next interval post may go; otherwise it is an error naming the rule, and the session sends the draft |
| `discord_post_status(draft, wait=300)` | the same wait, on a draft that came back still waiting; a draft sent or refused answers that again, and is never posted twice |
| `discord_read(channel, after, limit=50, from)` | the first `limit` messages after an id, or the newest `limit` without one, oldest first: id, author, time, text, the message it answers, attachments by name, whether it is a stranger's its owner let through, and what each channel event says of its author and of how to answer (below); a message the pre-harness rejects, or of someone iced or muted, is left out |
| `discord_wait(channel, after, wait=600, from)` | the first message after an id from the owner, someone he trusts or allowed, as the gateway brings it, with the same fields; what came before it began listening, from REST |
| `discord_attachments(channel, message)` | saves the attachments of a message `discord_read` gives (the owner's, a trusted or allowed person's, its own, or a stranger's its owner let through) to `<XDG_CACHE_HOME or ~/.cache>/aogowimsy/<channel>/<message>/`, fetched from Discord's CDN without the token, for the session to open (an image, a log): each one's name, type, size, an image's width and height, and its path, or why it was not saved (over 64 MiB, the CDN's error). A file saved before is not fetched again |
| `discord_react(channel, message, emoji)` | puts AogoWimsy's reaction on a message `discord_read` gives (never a draft), at once, with no draft and no check mark, so it takes only these: the server's custom emojis `:wimsyaogo_eyes:` (seen, on it), `:wimsyaogo_done:` (done), `:wimsyaogo_thumbsup:` (agreed), `:wimsyaogo_no:` (cannot), the unicode eyes, check mark, thumbs up and cross that say the same, and `:wimsyaogo:` (the owner's emoji; its own lets nothing through). A custom one goes by its id: the one a reaction on the message has, else the channel's server's emoji of that name, else another server's the bot is in, asked again when one was missing (it may have been uploaded since); none is an error naming it and the unicode one that says the same. Any other is an error naming it, its code points and the ones taken. It answers `reacted`, or `already there` without asking Discord again, and stderr says whose reaction, on which message and channel, and which |
| `discord_unreact(channel, message, emoji)` | takes one of those reactions of AogoWimsy's off a message, the others' staying: `removed`, or `not there` |
| `discord_quick(channel, reply_to, emoji)` | a quick reply: one of those emojis alone (not `:wimsyaogo:`), posted at once with no draft, as a reply to a message `discord_read` gives (never a draft), pinging no one, where `discord_post` posts. A text, or any other emoji, is an error: a text goes through `discord_post` and the check mark. A custom one's id is asked at each reply, as a stale one would post its name as text. stderr says whose, which, the message posted and the one it answers |
| `discord_emoji_upload(guild, name)` | uploads to a server one of the four custom emojis above, `name` one of `wimsyaogo_eyes`, `wimsyaogo_done`, `wimsyaogo_thumbsup`, `wimsyaogo_no`, from its fixed file `~/WorkDir/ScarletNX/wimsy-dist/emoji/<name>.png` (a PNG of 256 KiB at most), named as it; no other name or file. One the server has by that name is `already there` and not uploaded again. It needs Create Expressions in that server: without it, the error names it and the invite's permissions with it |
| `discord_allowed()` | who the owner allowed with `/aogo allow`, the allows that run out first first: each one's id, name (as the server showed them when allowed), since and until when (ISO 8601 in UTC, `null` for good); the ids trusted now; the ids the env file lists; and the time now |
| `discord_freeze(channel, message, kind)` | ices the author of a message `discord_read` gives that tried what the session's harness refuses or what only the owner may allow: the server replies to it at once with the fixed line of `kind`, never the session's text, pinging the owner, and for `secret` and `abuse` the server's admin role (`/aogo admins`); then their messages are only counted for 2 hours, or 1 day when they were iced in the last 7 days. Never the owner nor someone he trusts (an error: the session tells the owner in a draft). It answers the ice's end, the strikes of the last 7 days, the line's id and what the admin role got |

`from` (a list of ids, each the owner, someone he trusts or one he allowed; anyone else is an error naming the id, and
someone muted or iced one naming why) narrows read and wait to those authors: the others join the count of the left
out, and wait returns only on one of theirs.

A session's text gets out through its owner's check mark, or as a direct post the rules below let; `AOGOWIMSY_DIRECT=0`
makes every post a draft. A reaction or a reply of
one emoji alone carries no text, so `discord_react` and `discord_quick` go at once, and only with the emojis above: the
server's instructions tell the session to react to say it saw a message or finished it (`:wimsyaogo_eyes:` when it
starts, `:wimsyaogo_done:` in its place when done), the server's emoji before its unicode one, rather than post. It
reads and posts in the listed channels and their threads, or, with none listed, in every channel and thread Discord lets
the bot see (a channel it cannot see is Discord's 403 or 404, naming it); it reads its owner's DMs with it too. Of what
it reads, only the owner's messages, those of the people he trusts or allowed (below) and its own reach the session; a
stranger's message reaches it once the owner lets it through, the others are counted and nothing else of them given.
The owner lets a stranger's message through, that one message:

- with his `:wimsyaogo:` reaction, on a message addressed to AogoWimsy (a mention, or a reply to one of its
  messages); only his reaction counts;
- by replying to it with a message that mentions AogoWimsy, whoever wrote it; anyone else's reply lets nothing
  through.

Someone a post of AogoWimsy's mentions (`<@id>` in its text; a draft the owner approved, or a direct post) may reply to
that post, and to that one alone, for 24 hours after it (DraVee, 2026-11-10: "so you can see the reply of who you
mentioned"). Each reply reaches the session as `kind="mentioned"`, with no greeting, 10 an hour as an allowed person's,
and `discord_read`, `discord_wait`, the reactions and `discord_attachments` take it; the session's answer to it is a
draft only. Their reply to any other message, their plain call and another person's reply to the same post are a
stranger's, as theirs are once the 24 hours are over, with no word to them. An ice, a mute still in force or the owner's
`/aogo deny` (which ends their hours, naming the posts) keeps them out. XujiWimsy's posts open none.

A stranger who calls AogoWimsy in a channel it reads (a mention of it or of its role, or a reply to one of its
messages) gets at once, from the server itself and with no draft, this reply, which pings the owner and no one else
(`allowed_mentions` names his id alone, and not the person it replies to):

> I'm Aogo, DraVee's AI assistant (Claude) working on ScarletNX: code, reviews, tests. I act on what DraVee lets
> through. <@AOGOWIMSY_OWNER>

Once a person each 24 hours, and 10 an hour at most, everyone together (`AOGOWIMSY_GREET_HOURS` and
`AOGOWIMSY_GREET_PER_HOUR` set both, below); past a limit the call is only counted, as any other stranger's message.
A bot's or a webhook's call is not greeted, so two bots never greet each other, nor is a stranger's DM (the session
gets its name, as before). The session hears nothing of a call, greeted or not, and its instructions say what the
strangers get; the owner's `:wimsyaogo:` on the call still lets it through, and the session answers with a draft as
always. A greeting Discord refuses (no Send Messages there, the call deleted) wakes the session as an `error` naming
the channel and Discord's answer, and counts toward the limits. stderr says the channel, the message posted and the
count of the hour, or why a call was only counted, never who called nor what they said.

### Its slash command

AogoWimsy registers `/aogo` in each server it is in, guild-scoped so it shows at once, when the gateway brings that
server: it asks Discord for the server's commands and sends its own (in place of what is there) only when they differ,
so a start, or a second session, changes nothing. Every member sees it, as Discord sets who sees a command for the whole
of it and never for a subcommand; each answer is seen by its asker alone and pings no one:

| Subcommand | Who | What it answers |
|---|---|---|
| `/aogo help` | anyone | the greeting's line, then `To ask me something, mention @AogoWimsy with what you need; DraVee lets it through.`; for the owner, his three commands below too. A stranger gets it within the greeting's limits (counted apart from the greeting), and past one is answered how long ago they asked, or how many asked in the hour |
| `/aogo allow user [time]` | the owner | lets that member's messages reach the session, 10 an hour, for `2h`, `1d`, `7d` or `perm` (Discord's picker shows 2 hours, 1 day, 7 days, permanent), `1d` when he names none; a new allow takes the old one's place and says until when it ran. Another time, the owner and the bot itself are refused, naming why |
| `/aogo deny user` | the owner | takes that member's allow back, or says they have none (and, for someone trusted, that `/aogo untrust` takes that); ends the hours they had to reply to the posts that mentioned them, naming those posts |
| `/aogo allowed` | the owner | each allow in force and until when, in each reader's own time zone, the soonest end first, then who is trusted |
| `/aogo trust user`, `/aogo untrust user` | the owner | their messages reach the session as one he trusts (30 an hour, and direct answers), or no longer |
| `/aogo weight user level [time]` | the owner | `mute`, `low`, `normal` or `high`: 0, 3, 10 or 30 of their messages an hour reach the session, for `2h`, `1d`, `7d` or `perm` (`1d` without one); then their level's again (trusted high, allowed normal). A stranger has none to weigh |
| `/aogo unfreeze user` | the owner | ends their ice now; their strikes stay |
| `/aogo admins role` | the owner | that server's admin role, which the ice lines for a secret or abuse ping |
| `/aogo people` | the owner | sends him, in his DMs with AogoWimsy, everyone with a state: trusted or allowed until when, mentioned by a post and until when their replies to it reach the session, their weight and until when, their ice and strikes of the last 7 days, and of the last 24 hours the messages that reached the session, were only counted, or were rejected by each rule, and the direct replies to theirs; then the interval in force and why, and the direct posts of the day |
| `/aogo tone [channel mode]` | the owner | sets that channel's tone, `playful` (jokes are common there: light, short answers) or `serious` (focused work), a hint each of its messages carries to the session; a thread takes its channel's unless set itself. Alone, every channel's tone. Without one set, the server's #general (`1558959542543589416`) is playful, every other channel and DMs serious; in a playful channel a message that starts with `serio:` (any case, with or without the accent, after spaces or mentions) is serious. A channel without a mode, or a mode without one, is refused naming the tone in force |

Anyone but the owner who uses one of his is answered `Only @DraVee can use /aogo allow.`, and nothing changes. The owner
is never limited, trusted or iced, and the bot is none of them. An allowed person's addressed messages and DMs reach the
session (`kind="message"`; `discord_read`, `discord_wait` and `from` take them) until the allow runs out; then they are
a stranger again (counted, greeted), and nothing is said to them. Each allow, deny, trust, untrust, weight and ice wakes
the session as a `notice` naming the person and what changed, and each tone set as one naming the channel and the tone;
help, allowed, admins, people and tone alone tell it nothing. Every session's server hears each use: the first to take
the state's lock answers it and writes down its answer and notice, the others see it answered and tell their session the
same notice, so a use is answered once and each session hears it once. Discord takes an answer for 3 s: a use is
answered in a thread of its own, ahead of whatever the gateway's queue holds, and the answer needs no Discord call
before it, so it never waits for a deferral. A server whose install lacks the `applications.commands` scope wakes the
session as an `error` that gives the invite with that scope (Discord's 403, Missing Access); an answer Discord refuses
is an `error` too, with the interaction's token left out, and an allow it made stays.

Nothing is stored but the attachments `discord_attachments` is asked for (folders 700, files 600, kept until someone
removes them), and the bot's state, in `<XDG_STATE_HOME or ~/.local/state>/aogowimsy/` (folder 700, files 600), so a
restart keeps it: `greetings.json` and `helps.json`, the time and the person's id of each greeting and help of the last
`AOGOWIMSY_GREET_HOURS` hours; `allowed.json`, each allow in force (the person's id and name, since and until when); and
`interactions.json`, each use of `/aogo` of the last day with the notice it made; and `mentions.json`, the time, the
post's id and the person's id of each mention in a post of the last 24 hours, nothing else of them. Every session started where
`.mcp.json` names AogoWimsy runs a server of its own, and all of them hear the same call: each look at those files and
its change are made under the lock `state.lock` beside them, so one of them greets or answers and the others see it
done. Beside them: `people.json` (each person's trust, weight, ice and strikes), `heard.json` (what became of each
message of a trusted, allowed, let-through or mentioned person of the last day, so two sessions count it once), `direct.json` (each
direct post of the last day, so they share the caps and the interval), `admins.json` (each server's admin role),
`tones.json` (each channel's tone the owner set, where it differs from the one it has without it) and `flags.json` (the
notes to the owner said once). A file there it did not write stops what reads it (the greetings, the help, the allows or
the commands), and each call or use then wakes the session as an `error` naming the file and what is wrong in it (a
`tones.json` it cannot read makes each message's `tone` `unknown:` and why); nothing rewrites it until it is mended or
removed. A draft waiting is its message in the owner's DMs, read again at each look, so a restart loses none; what the
owner let through is kept in memory while it runs; stderr says what ran or failed, never what was said nor who said it.
A 429 waits its `retry_after` and tries again; any other failure comes back to the session with Discord's status and
message, as does a value a tool refuses, named with what it takes.

It serves Claude Code alone, so that no other client posts as Aogo: an `initialize` whose `clientInfo` name is not
`claude-code` (Claude Code's) gets an error naming that name and XujiWimsy, the server logs it, and nothing reaches
Discord. XujiWimsy (below) refuses Claude Code the same way.

### Who reaches it, the pre-harness and direct posts

| Who | What reaches the session | How the session's answer goes |
|---|---|---|
| the owner | everything | direct, up to 3 replies to each of his messages; in DMs, only in his |
| someone he trusts (`/aogo trust`; `AOGOWIMSY_USERS` lists who starts trusted) | 30 messages an hour (`high`) | direct, up to 3 replies to each of theirs, no interval |
| someone he allowed (`/aogo allow`) | 10 an hour (`normal`) | direct, once an interval |
| a stranger he let through with `:wimsyaogo:` | that message | a draft only |
| someone a post of AogoWimsy's mentioned | their replies to that post, for 24 hours after it, 10 an hour | a draft only |
| a stranger | the greeting, nothing else | nothing |
| someone iced | nothing: only counted | the ice's fixed line, once |

`/aogo weight` sets another weight for a time. A post with no `reply_to`, or replying to AogoWimsy's own message, goes
once an interval. The interval is `AOGOWIMSY_DIRECT_MINUTES` (30), read each time from Claude Code's status line: this
session's `$CLAUDE_CONFIG_DIR/usage/statusline-<CLAUDE_CODE_SESSION_ID>.json`, else the account's `statusline.json`,
which the last session to refresh writes (it must then be this session's), 10 minutes old at most; else the interval
posts are refused, naming the file and why. Doubled for the quota (seven days or five hours) at 80% or
more, the context at 80% or more, and 3 or more of this session's subagent transcripts written in the last 15 minutes,
each; halved when none of those holds and the week's quota used is under the share of the week gone; held within 10
minutes and 2 hours; at 95% quota no interval post goes direct (the owner's and the trusted replies still do). A direct
post carries no files and pings no one.

The pre-harness is `aogo/preharness.json`: rules, each with its direction (`in`, a message on its way to the session;
`out`, a direct post's text), what it matches (a regex or a list of them, letters by code point with the emoji joiners
passing inside a sequence, or a language other than one named), what a hit does (`reject`, `caution`, `draft`), its
fixed reply and ice when it rejects, why, and the texts it must hit and miss. The server runs every rule on its own
examples at start, and a file it cannot take, or a rule that gets one of its examples wrong, stops it, naming the rule;
the tests run them too. Adding a rule is adding a block with its examples.

- In, for everyone but the owner (his hits, and what he quotes, only add a caution): invisible letters (zero-width,
  bidi, tag letters; the joiners inside an emoji pass) reject the message and ice its author for `injection`; a
  language other than English (three letters of another script, or, in four words or more, more common words of
  Portuguese, Spanish, French, German or Italian than of English, two at least, code, links and mentions left out)
  rejects it with
  `I only talk in English here.`, once a person each hour. A rejected message never reaches the session: it is counted,
  and the session gets a `notice` naming who and the rule, never the text. Words that try to change the instructions,
  secrets named, destructive commands, pushes and merges, and claims of DraVee's word reach it with a `caution`; a
  question about DraVee himself (`owner-info`) too, and an answer to it is a draft only.
- Out, on a direct post's text: Discord, GitHub, `sk-` and AWS keys, private key blocks, long secrets after `key=`,
  `token=` or `password=`, this machine's paths, private and loopback addresses, e-mail addresses, title IDs, the env
  file's lines, and the bot's own token: a hit is an error naming the rule, its line and letter, never the text, and
  the session sends a draft the owner sees.

The ice's lines, the server's and never the session's, each pinging the owner:

| `kind` | Line | Pings the admin role |
|---|---|---|
| `harness` | I didn't like that one, and I won't do it without DraVee's OK. | no |
| `owner-call` | That one is DraVee's call, and I've told him. | no |
| `secret` | I don't share that. | yes |
| `abuse` | Not here. | yes |
| `injection` | I only take instructions from DraVee. | no |

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
| `message` | a message addressed to AogoWimsy (a mention, or a reply to one of its messages) from the owner, someone he trusts or allowed, in a channel it may read, within their weight and passing the pre-harness; any DM one of them sends it. When the owner replies to someone while mentioning AogoWimsy, the text ends with the message he replied to, whole | `author`, `author_id`, `channel`, `message_id`, `reply_to`, `attachments`; `quoted_author`, `quoted_author_id`, `quoted_attachments` for the owner's reply; and so the session needs no rule in its head: `trust` (`owner`, `trusted`, `allowed until ...`, `let-through`, `mentioned by Aogo until ...`), `weight` and `heard` (`2 of 30 this hour`) for someone trusted or allowed, `ice` (strikes of the last 7 days), `caution` (each inbound rule it hit, and why), `tone` (`playful`, `serious`, `serious (serio:)`, or `unknown: ...` when its channel or `tones.json` cannot be read), `reply` (`direct, up to 3`, `direct from 14:30 UTC (interval 30 min: quota 56%)`, `draft only: ...`) |
| `approved` | a stranger's message addressed to AogoWimsy, once the owner puts his `:wimsyaogo:` reaction on it, once, passing the pre-harness | as `message` |
| `mentioned` | the reply of someone a post of AogoWimsy's mentioned, to that post and within 24 hours of it, within 10 an hour and passing the pre-harness, unless they are iced or muted | as `message`: `trust` is `mentioned by Aogo until ...`, `weight` `normal (10 an hour)`, `reply` `draft only: ...` |
| `dm` | someone neither the owner nor listed wrote to AogoWimsy in DMs: their name and id, never what they wrote; once a person while it runs | `author`, `author_id` |
| `draft` | the owner's check mark or cross on a draft this session made, still waiting: it is posted or refused then, not on a tool's next look (another session's draft waits for that session) | `draft`, `status` (sent, not sent), `channel`; `message_id` once posted |
| `error`, `notice` | the gateway stopped (a close code Discord takes no new try after: a token that is not the bot's, intents not turned on), cannot be reached for three tries in a row, or is back; a greeting, a registration or an answer to `/aogo` that failed; a state file it cannot read; the owner's allow, deny, trust, untrust, weight, unfreeze or tone, a weight or an ice running out, an ice another session made, and a message the pre-harness rejected (each a `notice`) | `user`, `user_id`, and what changed: `until` (an ISO 8601 time in UTC, `permanent`, `denied`, `ran out`), `trust`, `weight`, `ice`; a tone: `channel` and `tone`; a rejection: `channel` and `rule` |

Nothing else wakes it: a message not addressed to AogoWimsy, anything a stranger says before the owner lets it through
(a call it greeted too), its own messages. Without the flag, the gateway still runs and feeds `discord_wait`, and Claude
Code drops the events. The session answers in Discord with `discord_post` (reply_to the `message_id`), which still waits
for the owner's check mark.

Its settings, a line each of its env file, `~/.config/aogowimsy/aogowimsy.env` unless `--env FILE` names another:

| Key | Default | What it is |
|---|---|---|
| `AOGOWIMSY_TOKEN` | none: needed | the bot's token |
| `AOGOWIMSY_OWNER` | none: needed | the owner's user id: who approves every post and lets a stranger's message through |
| `AOGOWIMSY_USERS` | none | deprecated: `id,id`, who starts trusted, until `/aogo trust` or `untrust` says otherwise; the owner is told once, in his DMs. Empty, or no line, lists no one |
| `AOGOWIMSY_CHANNELS` | every channel and thread the bot can see | `id,id`: where it reads and posts; a thread of one of them counts as it |
| `AOGOWIMSY_GREET_HOURS` | `24` | 1 to 720: hours before the greeting goes to the same person again |
| `AOGOWIMSY_GREET_PER_HOUR` | `10` | 0 to 100: greetings in an hour at most, everyone together; `0` greets no one |
| `AOGOWIMSY_DIRECT` | `1` | `1`: direct posts within the rules above; `0`: every post is a draft |
| `AOGOWIMSY_DIRECT_MINUTES` | `30` | 10 to 120: the interval's base, for the direct posts that need one |

A key it does not know stops it, naming the key; so does an id that is not one, an empty or missing needed value, an
empty `AOGOWIMSY_CHANNELS`, a `GREET` or `DIRECT` value out of its range (it names the value), a key set
twice, and an env file other users can read (its mode must be 600 or stricter: it says the mode it found). The server's
instructions to the session say which channels and greeting limits are in effect. Setting it up, after its application
(below):

1. Its owner shares a server with it and lets that server's members send them DMs (the server's Privacy Settings,
   Direct Messages), or no draft reaches them.
2. The env file, then a look at it: the line `up` names the owner, counts the users and the channels (or says every
   channel it sees) and gives the greeting's limits, or it says what is wrong and stops. Discord hears nothing until a
   session is initialized.

       install -d -m 700 ~/.config/aogowimsy
       install -m 600 aogo/aogowimsy.env.example ~/.config/aogowimsy/aogowimsy.env   # then fill it in
       python3 aogo/aogowimsy.py </dev/null

3. Claude Code, from the folder whose sessions may use it (scope `project` writes `.mcp.json` there; `user` would give
   it to every session of the account, wherever it starts). A session started there asks once to use it:

       claude mcp add --scope project aogowimsy -- python3 /path/to/discord-bots/aogo/aogowimsy.py


## XujiWimsy

Xuji, the Grok Build session, on Discord as a bot user of its own. `xuji/xujiwimsy.py` runs `aogo/aogowimsy.py` with
Xuji's identity (the table `IDENTITIES` there): its bot, its env file and keys, its name in every text. Everything else
is AogoWimsy's, a fix to one a fix to both: the tools above, with the same arguments, defaults and answers, and its
direct posts under AogoWimsy's rules (`XUJIWIMSY_DIRECT`, `XUJIWIMSY_DIRECT_MINUTES`) but for the interval, fixed at
`XUJIWIMSY_DIRECT_MINUTES` as Grok Build reports no quota, context or agents to weigh it by. Its command is `/xuji`, AogoWimsy's `/aogo` in its own name: the
owner trusts, allows, weighs and ices people and sets a channel's tone, its state in `<XDG_STATE_HOME or
~/.local/state>/xujiwimsy/`, and the pre-harness checks what reaches it; `XUJIWIMSY_USERS` lists who starts trusted.
Its instructions say this shorter than AogoWimsy's, as Grok Build shows its model their first 2048 bytes. Its drawn
emojis are Xuji's face, wimsy-dist's `emoji/wimsyxuji_eyes`, `_done`, `_thumbsup` and `_no`: `discord_react`,
`discord_unreact` and `discord_quick` take them first and their unicode ones while a server lacks them, and
`discord_emoji_upload` uploads them, as AogoWimsy does with Aogo's. It greets no one and takes no `GREET` key: `/xuji help` says who it is
in a line of its own.

It serves any client but Claude Code: an `initialize` from `claude-code` gets an error naming it and AogoWimsy. Grok
Build takes no push from an MCP server into its model: a server's log messages and resource updates reach neither the
model nor the screen, sampling is refused (-32601), and an elicitation is a card for the person at the terminal (Grok
Build 1.0.70, measured on a scratch session). What wakes a Grok session is its own `monitor` tool: each line a command
it runs prints comes in as a new turn. So XujiWimsy pushes to a monitor:

- Once the client is initialized, the server takes monitors on a Unix socket, `<XDG_RUNTIME_DIR or
  ~/.local/state>/xujiwimsy/<client pid>.sock` (folder 700, socket 600), named for the Grok process that started it.
  `xuji/xujiwimsy.py --listen` (it reads no env file) finds the socket of its own session's server among its parent
  processes, and prints what it pushes, a line each.
- Its instructions ask the session to start that monitor when it starts: the monitor tool, persistent, description
  `XujiWimsy`, command `python3 /path/to/discord-bots/xuji/xujiwimsy.py --listen` (the path of the checkout it runs
  from). A session told only to do what its MCP servers ask at its start did so, and an owner's mention woke it in 4 s.
- A line is what AogoWimsy pushes into Claude Code, said in words: `message: DraVee (<id>) in channel <id>, message
  <id>, replying to <id>, attachments a.png; b.log: "<the text, quoted>"`, `approved: ...` (a stranger's the owner let
  through), `dm: ...` (a stranger's name only), `draft: The owner approved draft ...: posted as ...`, `error: ...`,
  `notice: ...`. Grok shows its model the first 500 characters of a line, so a line is 500 bytes at most: a longer
  text is cut, `..." (cut: discord_read gives it whole)`, and the session reads it whole.
- With no monitor listening, a message to Xuji is heard by `discord_wait` on its channel alone (after the id of the
  newest message the session has seen there, which `discord_read` gives), and the owner's answers to drafts and the
  gateway's news come with the next tool result, after its own JSON, a text each opening `XujiWimsy news:` (the newest
  20, the older ones counted). A draft is posted the moment its owner answers it, heard or not.
- When the server stops (Grok quits or reconnects it), `--listen` says so in a last line naming the command to start
  it again, and ends. A server killed leaves its socket; the next one to start takes away those of clients gone.

stderr says where each event went (`channel: a message event to 1 monitor`, or `no monitor listens`), never what it
said. Grok Build 1.0.70 shows its model the first 2048 bytes of a server's instructions and cuts the rest. XujiWimsy's
fit with three listed users and up to 7 channels (the checkout's path is in them); more ids than that are said on
stderr and with the first tool result, naming the bytes, so a list can be cut short before its model misses how to
answer.

Its settings are AogoWimsy's first four keys (the table above), named `XUJIWIMSY_TOKEN`, `XUJIWIMSY_OWNER`,
`XUJIWIMSY_USERS` and `XUJIWIMSY_CHANNELS`, with their defaults, meanings and checks, in
`~/.config/xujiwimsy/xujiwimsy.env` unless `--env FILE` names another (mode 600 or stricter). A key it does not know stops
it, naming the key: an `AOGOWIMSY_` one too, so one bot's file never starts the other.
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
4. A session, in Grok Build: its server's instructions have it start the monitor; Grok's tasks pane (`Ctrl+G`) lists
   `Monitor XujiWimsy` while it runs. Without it, ask the session to start the monitor its XujiWimsy instructions name.

Grok Build also starts the MCP servers of `~/.claude.json` and of a `.mcp.json` from its folder up to the git root.
A Grok session started where a `.mcp.json` names aogowimsy would start AogoWimsy, with Aogo's token: AogoWimsy refuses
it, and `grok mcp doctor` shows `handshake failed (JSON-RPC error: -32602: Invalid params: clientInfo.name is
"grok-shell-aogowimsy", not "claude-code": ...)`. To keep it from starting at all, from that folder:

    grok mcp disable aogowimsy        # writes disabled_mcp_servers = ["aogowimsy"] to ~/.grok/config.toml

In Grok Build 1.0.60, neither `[compat.claude] mcps = false` (it covers `~/.claude.json` alone) nor an
`[mcp_servers.aogowimsy]` table holding only `enabled = false` keeps a `.mcp.json` server from starting.

## Tests

    python3 aogo/test_aogowimsy.py && python3 xuji/test_xujiwimsy.py

No network and no Discord: AogoWimsy's env file, its MCP answers (and the program itself on stdin and stdout), its tools
against a fake Discord on 127.0.0.1 (drafts approved, refused, still waiting, another person's reaction, the channels
and the people it may, `from`, Discord's 429s and errors; its reactions and quick replies: the emojis taken, any other
or a text refused, the channels and messages it may, no draft, a custom emoji by its id and one not uploaded yet named;
the upload: the fixed file as a data URI, one already there, the missing permission named), what the gateway's events
push to the session (who and what wakes it, the owner's reaction and reply letting a stranger through; the greeting: its
text, the one mention it lets ping, a reply to the bot counting as a call, once a person each 24 h and 10 an hour, a
restart and a second server keeping both, the lock between servers, what is no call, the owner and trusted users never
greeted, Discord's refusal and a file it did not write said as errors; `/aogo`: the command registered word for word and
sent again only when it differs, the missing scope naming the invite, help for anyone and its limits, allow, deny and
allowed refused to anyone but the owner, each time and a wrong one, an allow's end, a restart, two servers answering one
use once, an allowed person's messages reaching the session and a stranger's not, an answer in a thread of its own, its
token never shown; trust, untrust and weight, each weight's cap an hour and its end, two servers deciding a message
once, the deprecation DM once; the ice: each kind's line and admin ping, the day for a second ice, unfreeze, the owner
and the trusted never iced; the pre-harness: every rule's own examples, the loader's refusals, the emoji joiners, the
languages, the owner's exemption, a rejection told and answered once; direct posts: each row of the table, the cap of 3,
each factor of the interval and its bounds, a statusline missing, stale or another session's, each outbound rule, a
refused post taking no turn; a mentioned person's replies: that post alone, 24 hours, 10 an hour, a draft only, the
ice, the mute and the deny, a file it cannot read; each event's attributes and `/aogo people`; `/aogo tone`: the owner's alone, the
default, threads, the `serio:` trigger in any case with or without its accent, the item kept only where it differs, a
restart, the notice, an unreadable file or channel said in `tone`), and its gateway client against a fake gateway
on 127.0.0.1 (identify, heartbeats and their ACKs, resume, the close codes that stop it, pings, messages in frames), and
that lines from several threads never mix on stdout; XujiWimsy's env file and keys (the other bot's refused, and its
example AogoWimsy's in its names), its server, instructions and tools in its own names (no drawn emoji: the unicode ones
alone; its instructions within what Grok shows, and too many ids said), its monitors (every event to each at once, a
line each within what Grok shows, news only when none listens, the socket private, a stale one taken over, a live one's
server named, those of clients gone taken away) and `--listen` (its own session's server found among its parents, lines
as they come, a last line once it stops, none found said; the program itself as a monitor runs it), the client each
Wimsy serves, the news a tool result carries, a post as it reaches Discord, and the program itself on stdin and stdout.

## The Discord applications

One application each, in the Developer Portal:

1. Bot: reset the token, put it in the env file; turn on **Message Content Intent** (without it, the messages
   AogoWimsy and XujiWimsy read come with no text, and their gateway closes with 4014). AogoWimsy and XujiWimsy: the
   name and avatar are set there too, and **Public Bot** is off, so only the owner adds it to a server. Their gateway
   asks for the intents GUILDS, GUILD_MESSAGES, GUILD_MESSAGE_REACTIONS, DIRECT_MESSAGES, DIRECT_MESSAGE_REACTIONS (the
   owner's answer to a draft, in his DMs) and MESSAGE_CONTENT (46593); only the last is privileged. AogoWimsy:
   **Interactions Endpoint URL** (General Information) stays empty, or Discord sends the uses of `/aogo` there and
   not over the gateway.
2. About me: what it does and that it keeps nothing (AogoWimsy: that it is Aogo, a Claude Code session, and posts
   only what its owner approved; XujiWimsy: that it is Xuji, a Grok Build session, and the same: its posts carry no
   signature, so the profile says who writes).
3. Invite (OAuth2, scopes `bot` and, for AogoWimsy's `/aogo`, `applications.commands`), with only what it needs:
   - AogoWimsy and XujiWimsy: View Channels, Send Messages, Send Messages in Threads, Read Message History, Add
     Reactions (`discord_react`), Attach Files (`discord_post`'s images; the drafts, their card and their reactions
     are in DMs, which need none): `permissions=274878008384`. AogoWimsy: a custom emoji of another server than the
     message's also needs Use External Emojis, and `discord_emoji_upload` Create Expressions: `permissions=9070971030592`
     with it.

   `https://discord.com/oauth2/authorize?client_id=<APPLICATION_ID>&scope=bot+applications.commands&permissions=<number>`

   (XujiWimsy: `scope=bot` alone.) The slash command needs no permission of the bot's: the scope is what lets it
   register `/aogo` in the server, and a member needs Use Application Commands, which `@everyone` has by default.

`AOGOWIMSY_OWNER` and `XUJIWIMSY_OWNER` are the owner's Discord user id (Developer Mode, right click, Copy User ID).
