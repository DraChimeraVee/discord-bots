#!/usr/bin/env python3
"""AogoWimsy and XujiWimsy: a coding session on Discord as a bot of its own, every post approved by its owner first.

    aogowimsy.py [--env FILE]           AogoWimsy, Aogo (the Claude Code session); FILE:
                                        ~/.config/aogowimsy/aogowimsy.env when not given; mode 600 or stricter
    ../xuji/xujiwimsy.py [--env FILE]   XujiWimsy, Xuji (the Grok Build session): this code with Xuji's identity
                                        (IDENTITIES), its bot and ~/.config/xujiwimsy/xujiwimsy.env

A local MCP server that its client starts and talks to on stdin and stdout, a JSON-RPC 2.0 message a line, through
the initialize handshake (protocol 2025-11-25 back to 2024-11-05): Claude Code registers no channel on revision
2026-07-28, which cannot carry its messages. AogoWimsy serves Claude Code alone (its clientInfo name, claude-code)
and XujiWimsy any client but Claude Code: each refuses the other's client, naming both, so a session never starts
the other one's bot. Its tools:

    discord_post         a draft in the owner's DMs with the bot, with a check mark and a cross: only the owner's
                         check mark posts it, as it is, pinging no one
    discord_post_status  the same wait, on a draft that came back still waiting
    discord_read         a channel's messages: the owner's, the listed users', the allowed ones' and the bot's own;
                         others only counted
    discord_wait         the first message after an id from the owner, a listed user or an allowed one, as the
                         gateway hears it
    discord_attachments  a message's attachments saved to a folder of its own, for a message discord_read gives
    discord_react        the bot's reaction on a message discord_read gives, at once and with no draft: one of its
                         identity's few alone (Identity.reactions: seen, done, agreed, cannot, and AogoWimsy's the
                         owner's emoji), so no text goes out
    discord_unreact      takes one of those reactions of the bot's off a message
    discord_quick        a reply that is one emoji of Identity.quick alone, posted at once and with no draft: no text
    discord_emoji_upload uploads one of the server's DRAWN emojis from its fixed file in EMOJI_FOLDER, by its name
                         (AogoWimsy alone: XujiWimsy answers with the unicode emojis)
    discord_allowed      who the owner allowed with /aogo allow, and until when (AogoWimsy alone)

AogoWimsy is also a Claude Code channel (experimental capability claude/channel): once the session is up it stays on
Discord's gateway, and pushes into the session, as notifications/claude/channel, each message addressed to AogoWimsy
(a mention, or a reply to one of its messages) from the owner or a listed user, their DMs with it, a stranger's
addressed message the owner let through with his WIMSY reaction, and only the name of a stranger who wrote in DMs.
The owner's reply that mentions AogoWimsy lets the message he replied to through too, and carries it whole.
XujiWimsy offers no channel, as its client shows no push: it stays on the gateway too, which feeds discord_wait and
posts a draft the moment the owner answers it, and the session hears through discord_wait; the gateway's news and
the owner's answers to drafts come with its next tool result instead.

A stranger (neither the owner nor listed) who calls AogoWimsy in a channel it reads (a mention of it or its role, or a
reply to one of its messages; a person's, not a bot's nor a webhook's) gets at once, from the server itself, with no
draft, GREETING as a reply: a fixed line saying who Aogo is that pings the owner and no one else. Once a person each
GREET_HOURS hours and GREET_PER_HOUR an hour at most, everyone together (env file keys may set both); past a limit
the call is only counted, as any other stranger's message, and the session hears nothing of a call either way. The
owner's WIMSY reaction still lets the call through. A stranger's DM is not greeted: the session gets its name, once.
XujiWimsy greets no one.

AogoWimsy registers its slash command, /aogo (command_list), in each server it is in when the gateway brings the
server, guild-scoped so it shows at once, and sends it only when the server's differs from it. /aogo help answers
anyone, seen by them alone: GREETING and how to ask, a stranger within the greeting's limits (counted apart), the
owner with his commands too. /aogo allow user [time] (2h, 1d, 7d or perm; 1d without one), /aogo deny user and
/aogo allowed are the owner's: anyone else is answered that they are his. Discord sets who sees a command for the
whole of it, never a subcommand, so every member sees all four. An allowed person is heard as a listed user until the
allow runs out, then as a stranger again, with no word to them; each allow and deny reaches the session as a notice.
Every server of the bot hears a use of it: the first to take the state's lock answers it, at once (Discord takes an
answer for 3 s, so a use is answered in a thread of its own, ahead of the gateway's queue), and every one tells its
session. XujiWimsy has no command.

Discord's REST API v10 (urllib) reads and posts; its gateway (a WebSocket of its own, ssl and socket) hears. It works
in the channels <PREFIX>_CHANNELS lists and their threads, or in every one Discord lets it see when it lists none,
and in the owner's DMs with it. The owner's check mark is the only way a session's text gets out: no setting turns it
off. A reaction or a quick reply carries no text, so it goes at once, and only one of its identity's few emojis;
the greeting and an answer to /aogo are the server's fixed lines, never the session's. Nothing is stored but the
attachments discord_attachments is asked for, in <XDG_CACHE_HOME or ~/.cache>/<server>/<channel>/<message>/ (folders
700, files 600), and the bot's state in <XDG_STATE_HOME or ~/.local/state>/<server>/ (Store; folder 700, files 600,
every server of the bot sharing it under the lock state.lock): greetings.json and helps.json, the time and the
person's id of each greeting and help of the last GREET_HOURS hours; allowed.json, each allow in force (the person's
id and name, since and until when); interactions.json, each use of /aogo of the last day and the notice it made, so
no server answers one twice. A draft waiting is a message in the owner's DMs, read again at each look, and stderr
says what ran or failed, never what was said nor who said it.
"""

import argparse
import base64
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import queue
import random
import re
import socket
import ssl
import stat
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import NamedTuple

VERSION = '1.4.0'
API = 'https://discord.com/api/v10'
AGENT = f'DiscordBot (https://github.com/scarletnx/discord-bots, {VERSION})'


class Identity(NamedTuple):
    """whose bot a Wimsy is: every name it says, its env file, and the client it serves"""

    server: str  # its MCP server's name: serverInfo, stderr's prefix, the gateway's browser
    title: str  # its bot's name, as every text says it
    who: str  # the session it is on Discord
    prefix: str  # its env file's keys: PREFIX_TOKEN and on
    env: str  # its env file when --env names none
    claude: bool  # True: Claude Code alone, as a claude/channel; False: any client but Claude Code, with no push
    greeting: str | None = None  # the line a stranger who calls the bot gets at once, {owner} his id; None: none
    command: str | None = None  # its slash command's name (COMMANDS), registered in each server it is in; None: none
    drawn: tuple = ()  # its custom emojis, one for each of MEANINGS (EMOJI_FOLDER/<name>.png); (): unicode alone

    def key(self, name):
        return f'{self.prefix}_{name}'

    @property
    def needed(self):
        return tuple(self.key(name) for name in ('TOKEN', 'OWNER', 'USERS'))

    @property
    def greet_keys(self):
        """the keys of the greeting's limits, for a bot that greets"""
        return tuple(self.key(name) for name in GREET_LIMITS) if self.greeting else ()

    @property
    def keys(self):
        return (*self.needed, self.key('CHANNELS'), *self.greet_keys)

    @property
    def says(self):
        """(its custom emoji as :name:, or None; the unicode one; what they say), for each of MEANINGS"""
        names = [f':{name}:' for name in self.drawn] or [None] * len(MEANINGS)
        return tuple((name, plain, meaning) for name, (plain, meaning) in zip(names, MEANINGS, strict=True))

    @property
    def same(self):
        """each custom emoji's unicode one, which an error names while the custom one is not uploaded"""
        return {name: plain for name, plain, _ in self.says if name}

    @property
    def quick(self):
        """what discord_quick posts alone: the custom emojis, then the unicode ones"""
        return (*self.same, *(plain for plain, _ in MEANINGS))

    @property
    def reactions(self):
        """what discord_react puts: the quick ones, and for a bot drawn as Aogo the owner's WIMSY, named for Aogo"""
        return (*self.quick, f':{WIMSY}:') if self.drawn else self.quick


# What a stranger who calls the bot gets at once, with no draft and no owner's check mark (DraVee, 2026-11-02:
# "quando alguem sem permissao te chamar, vc me quotar (logicamente com limite pra n ter abuso) de forma automatica"):
# this line alone, as a reply, pinging the owner and no one else. Each limit an env file key may set (GREET_LIMITS);
# past one the call is only counted, as any other stranger's message.
GREETING = (
    "I'm Aogo, DraVee's AI assistant (Claude) working on ScarletNX: code, reviews, tests. I act on what DraVee lets "
    'through. <@{owner}>'
)
GREET_HOURS = 24  # hours before one person is greeted again
GREET_PER_HOUR = 10  # greetings in an hour at most, everyone's together; 0 greets no one
GREET_LIMITS = {  # each limit's key (after the prefix): its default and the whole numbers it takes
    'GREET_HOURS': (GREET_HOURS, 1, 720),
    'GREET_PER_HOUR': (GREET_PER_HOUR, 0, 100),
}
# The owner's slash command (DraVee, 2026-11-02: "E precisa de um comando de help e um de allow temporary/permanent
# pra algumas pessoas"; slash commands, help for anyone, allow his alone, 24 hours when he names no time). Discord
# sets who sees a command for the whole of it, never a subcommand: /aogo shows to every member, and allow, deny and
# allowed answer anyone but the owner that they are his. help answers a stranger within the greeting's limits.
HELP_ASK = 'To ask me something, mention <@{me}> with what you need; DraVee lets it through.'
HELP_OWNER = (
    'Yours alone:\n'
    '/{command} allow user [time]: their messages to me reach the session; time 2h, 1d, 7d or perm, 1d without one\n'
    '/{command} deny user: takes their allow back\n'
    '/{command} allowed: who is allowed, and until when'
)
ALLOW_TIMES = {'2h': 2 * 3600, '1d': 24 * 3600, '7d': 7 * 24 * 3600, 'perm': None}  # seconds; None: until denied
ALLOW_NAMES = {'2h': '2 hours', '1d': '1 day', '7d': '7 days', 'perm': 'permanent'}  # as Discord's picker shows them
ALLOW_DEFAULT = '1d'  # an allow with no time
SUBCOMMANDS = ('help', 'allow', 'deny', 'allowed')
OWNERS_ALONE = ('allow', 'deny', 'allowed')
# Discord's numbers: a command of the chat input (CHAT_INPUT), its options' types, an interaction's type, the answer
# that is a message (CHANNEL_MESSAGE_WITH_SOURCE) and the flag that shows it to its asker alone
CHAT_INPUT, SUB_COMMAND, STRING_OPTION, USER_OPTION = 1, 1, 3, 6
APPLICATION_COMMAND, MESSAGE_ANSWER, EPHEMERAL = 2, 4, 1 << 6
MISSING_ACCESS = 50001  # Discord's code for a server whose install lacks applications.commands
HANDLED_FOR = 24 * 3600  # seconds an interaction's answer is kept, so another server of the bot, or a replay, does not
# answer it again
STATE_LOCK = 'state.lock'  # the lock every file of the state folder is read and written under
UNREAD = {  # what stops while a state file cannot be read, until it is mended or removed
    'greetings': 'no stranger is greeted',
    'helps': 'no stranger gets help',
    'allowed': 'no allow is read',
    'interactions': 'no command is answered',
}
YES, NO, EYES, THUMBS = chr(0x2705), chr(0x274C), chr(0x1F440), chr(0x1F44D)
# The owner's custom emoji (DraVee, 2026-10-21: "se alguem te citar, eu posso (somente eu) so responder com um
# emoji"): his reaction with it, and only his, lets one stranger's message addressed to the bot reach the session.
# Matched by its name; a constant, not a setting.
WIMSY = 'wimsyaogo'
# What the bot answers with, at once and with no draft (DraVee, 2026-11-02: "implementa reacoes, assim vc meio q
# pode responder mais rapidamente"; of the drawn ones: "vc pode ate usar como mensagem rapida tambem"): a reaction
# or a reply of one emoji alone skips the owner's check mark, so only these, which carry no text. Each unicode one
# and what it says; a bot drawn for them (Identity.drawn) answers with its server's custom emoji first.
MEANINGS = ((EYES, 'seen, on it'), (YES, 'done'), (THUMBS, 'agreed'), (NO, 'cannot'))
# Aogo's drawings of MEANINGS, in that order (wimsy-dist's emoji/, each matched by its name). Xuji has none: its
# answers are the unicode ones alone, never Aogo's face
DRAWN = ('wimsyaogo_eyes', 'wimsyaogo_done', 'wimsyaogo_thumbsup', 'wimsyaogo_no')
AOGO = Identity(
    'aogowimsy',
    'AogoWimsy',
    'Aogo',
    'AOGOWIMSY',
    '~/.config/aogowimsy/aogowimsy.env',
    claude=True,
    greeting=GREETING,
    command='aogo',
    drawn=DRAWN,
)
XUJI = Identity('xujiwimsy', 'XujiWimsy', 'Xuji', 'XUJIWIMSY', '~/.config/xujiwimsy/xujiwimsy.env', claude=False)
IDENTITIES = (AOGO, XUJI)
CLAUDE_CODE = 'claude-code'  # the clientInfo name Claude Code's MCP client gives (2.1.310)
NAME = AOGO.server  # stderr's prefix: main sets the one it runs
LIMIT = 2000  # a Discord message's letters
IMAGES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp'}
MOST_FILES = 4  # images a post carries; how big each may be is Discord's to say, in the owner's DMs first
CDN = ('https://cdn.discordapp.com/', 'https://media.discordapp.net/')  # where attachments are fetched from
MOST_SAVE = 64 << 20  # bytes of one attachment discord_attachments saves at most
POLL = 3.0  # seconds between two looks at a draft's reactions
LOOK = 1.0  # seconds a wait sleeps at most before looking again at what the gateway brought
MOST_WAIT = 3600  # seconds a tool waits at most
PAGE = 100  # messages one GET gives at most
TRIES = 5  # a request answered 429 this many times in a row is an error
MOST_RETRY = 60.0  # seconds a 429 may ask to wait
EMOJI_FOLDER = '~/WorkDir/ScarletNX/wimsy-dist/emoji'  # the owner's clone of wimsy-dist: <name>.png of each of DRAWN
MOST_EMOJI = 256 << 10  # bytes of an emoji's image Discord takes at most
CREATE_EXPRESSIONS = 1 << 43  # the permission POST /guilds/{guild}/emojis needs
ATTACH_FILES = 1 << 15  # the permission a post with images (discord_post's files) needs
# The permissions of the README's invite: View Channels, Send Messages, Add Reactions, Read Message History, Send
# Messages in Threads, Attach Files
INVITE = 1 << 10 | 1 << 11 | 1 << 6 | 1 << 16 | 1 << 38 | ATTACH_FILES
DM, THREADS, REPLY = 1, (10, 11, 12), 19  # channel types (a DM; the three threads) and a reply's message type
SNOWFLAKE = re.compile(r'[0-9]{17,20}')
TOKEN_LETTER = re.compile(r'[A-Za-z0-9._-]')
WAITING = re.compile(r'(waiting|sending|not sent): to ([0-9]{17,20})(?: replying to ([0-9]{17,20}))?')
SENT = re.compile(r'sent: ([0-9]{17,20}|@me)/([0-9]{17,20})/([0-9]{17,20})')
VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05')  # the initialize handshake's
METHODS = ('initialize', 'ping', 'tools/list', 'tools/call')
CHANNEL_PUSH = 'notifications/claude/channel'
# Grok Build 1.0.70 shows its model a server's instructions up to 2048 bytes of UTF-8: of a longer text, the first
# 2033 bytes and "… [truncated]" (measured 2026-11-04 with instructions of 3645 letters). XujiWimsy's stay within it
GROK_SHOWS = 2048
NEWS = ('error', 'notice', 'draft')  # the pushes a client with no channel gets with its next tool result
MOST_NEWS = 20  # news kept for it at most: the oldest go first, counted
# The gateway's intents: GUILDS (1), GUILD_MESSAGES (512), GUILD_MESSAGE_REACTIONS (1024), DIRECT_MESSAGES (4096),
# DIRECT_MESSAGE_REACTIONS (8192: the owner's check mark on a draft, which is in his DMs), MESSAGE_CONTENT (32768,
# privileged: the Developer Portal's Message Content Intent)
INTENTS = 1 | 1 << 9 | 1 << 10 | 1 << 12 | 1 << 13 | 1 << 15
GATEWAY_STOPS = {  # close codes after which Discord takes no new try: the bot stops hearing and says why
    4004: "authentication failed: {token} is not the bot's token",
    4010: 'invalid shard',
    4011: 'sharding required',
    4012: 'invalid API version',
    4013: 'invalid intents',
    4014: 'disallowed intents: turn on Message Content Intent (Bot, Privileged Gateway Intents) in the Developer '
    'Portal',
}
GATEWAY_FRESH = (4007, 4009)  # close codes after which the session cannot resume: identify again
HELLO_WAIT = 30.0  # seconds the gateway has to say hello
STOP_LOOK = 0.5  # seconds the gateway reads at most before looking whether the bot stops
MOST_FRAME = 64 << 20  # bytes a gateway message may have
WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'  # RFC 6455's, for Sec-WebSocket-Accept


class Refused(Exception):
    """a value the bot does not take: the message names it and what it takes"""


class DiscordError(Exception):
    """Discord said no, or could not be reached: the message says what it answered"""

    def __init__(self, text, status=None, code=None):
        super().__init__(text)
        self.status, self.code = status, code  # code: Discord's JSON error code, when it gave one


class Cancelled(Exception):
    """the client cancelled the request, or the bot is stopping: the request gets no answer"""


class Drop(Exception):
    """a gateway connection ended: the bot connects again"""


class Stopped(Exception):
    """the gateway cannot go on: Discord takes no new try"""


class Settings(NamedTuple):
    token: str
    owner: str
    users: frozenset
    channels: frozenset | None  # None: every channel Discord lets the bot see
    identity: Identity = AOGO
    greet_hours: int = GREET_HOURS
    greet_per_hour: int = GREET_PER_HOUR


def shown(value):
    """a value as an error names it: its JSON, cut at 60 letters"""
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 60 else text[:57] + '...'


def snowflake(value, what):
    """value when it is a Discord id written as a string, else Refused naming it"""
    if not isinstance(value, str):
        raise Refused(f'{what} is {shown(value)}, not a Discord id: write it as a string of 17 to 20 digits')
    if not SNOWFLAKE.fullmatch(value) or int(value) >= 1 << 64:
        raise Refused(f'{what} is {shown(value)}, not a Discord id (17 to 20 digits)')
    return value


def whole(value, what, default, low, high):
    """value when it is a whole number from low to high, default when it is None, else Refused naming it"""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise Refused(f'{what} is {shown(value)}, not a whole number from {low} to {high}')
    return value


def read_settings(path, identity=AOGO):
    """the settings in an env file, or Refused naming what is wrong: its mode, a line, a key or a value"""
    title, keys = identity.title, identity.keys
    token_key, channels_key = identity.key('TOKEN'), identity.key('CHANNELS')
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
        text = Path(path).read_text(encoding='utf-8')
    except OSError as error:
        raise Refused(f'{path} cannot be read ({error.strerror or error}): {title} reads its settings there') from None
    except UnicodeDecodeError as error:
        raise Refused(f'{path} is not UTF-8 text (byte {error.start})') from None
    if mode & 0o7177:
        raise Refused(
            f"{path} has mode {mode:03o}: other users could read the bot's token; it must be 600 or stricter "
            f'(chmod 600 {path})'
        )
    values, lines = {}, {}
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, equals, value = line.partition('=')
        key = key.strip()
        if not equals:
            raise Refused(f'{path} line {number} has no "=": each line is KEY=VALUE, a # comment or empty')
        if key not in keys:
            raise Refused(f'{path} line {number}: {key} is not a key {title} knows; it knows {", ".join(keys)}')
        if key in values:
            raise Refused(f'{path} line {number}: {key} again, set on line {lines[key]} already')
        values[key], lines[key] = value.strip(), number
    for key in identity.needed:
        if not values.get(key):
            raise Refused(f'{path}: {key} is {"empty" if key in values else "missing"}, and {title} needs it')
    if values.get(channels_key) == '':
        raise Refused(
            f'{path}: {channels_key} is empty: list id,id, or take the line out for every channel the bot can see'
        )
    token = values[token_key]
    for place, letter in enumerate(token, 1):
        if not TOKEN_LETTER.fullmatch(letter):
            raise Refused(
                f'{path}: {token_key} has {letter!a} at letter {place}: a Discord token has only letters, '
                'digits, ".", "_" and "-"'
            )
    owner_key, users_key = identity.key('OWNER'), identity.key('USERS')
    owner = snowflake(values[owner_key], f'{path}: {owner_key}')
    users = id_list(path, users_key, values[users_key])
    channels = id_list(path, channels_key, values[channels_key]) if channels_key in values else None
    limits = []
    for name, (default, low, high) in GREET_LIMITS.items():
        key = identity.key(name)
        limits.append(whole_text(path, key, values[key], low, high) if key in values else default)
    return Settings(token, owner, users, channels, identity, *limits)


def whole_text(path, key, value, low, high):
    """an env file's value when it is a whole number from low to high, written in digits; else Refused naming it"""
    if not re.fullmatch(r'[0-9]{1,9}', value) or not low <= int(value) <= high:
        raise Refused(f'{path}: {key} is {shown(value)}, not a whole number from {low} to {high}')
    return int(value)


def id_list(path, key, value):
    """the ids of an id,id value, or Refused naming the item that is not one"""
    items = [item.strip() for item in value.split(',')]
    for place, item in enumerate(items, 1):
        if not item:
            raise Refused(f'{path}: {key} has an empty item, number {place} of {len(items)}: write id,id')
        snowflake(item, f'{path}: {key} item {place}')
    return frozenset(items)


def by_id(ids):
    return ', '.join(sorted(ids, key=int))


def scope(settings):
    """where the bot reads and posts, in words"""
    if settings.channels is None:
        return f'every channel and thread Discord lets it see ({settings.identity.key("CHANNELS")} lists none)'
    return f'channels {by_id(settings.channels)} and their threads'


def reactions_text(identity):
    """the identity's reactions in words: each custom emoji, the unicode one that says the same, and what they say"""
    return '; '.join(
        f'{name} or {plain} ({meaning})' if name else f'{plain} ({meaning})' for name, plain, meaning in identity.says
    )


def seen_and_done(identity):
    """the reactions that say seen and done: the custom ones of a bot drawn for them, else the unicode ones"""
    return tuple(name or plain for name, plain, _ in identity.says[:2])


def greeting_text(settings):
    """the greeting in words, for the session: what a stranger who calls the bot gets, and its limits in effect"""
    me, identity = settings.identity.title, settings.identity
    if not identity.greeting:
        return ''
    if settings.greet_per_hour == 0:
        return (
            f'{me} greets no stranger who calls it ({identity.key("GREET_PER_HOUR")} is 0): the call is only counted. '
        )
    return (
        f'A stranger who calls {me} in a channel it reads (a mention, or a reply to one of its messages) gets at once, '
        f'with no draft and no {YES}, a reply from the server itself that pings the owner alone: '
        f'"{identity.greeting.format(owner=settings.owner)}". Once a person each {settings.greet_hours} h, and '
        f'{settings.greet_per_hour} an hour at most, everyone together; past that the call is only counted. You are '
        f"told nothing of the call; the owner's :{WIMSY}: on it still lets it through to you, to answer with a draft. "
    )


def command_text(settings):
    """the command in words, for the session: who the owner may allow, how it hears of it, and help"""
    me, command = settings.identity.title, settings.identity.command
    if not command:
        return ''
    return (
        f'The owner may allow someone else with /{command} allow, for 2 hours, 1 day, 7 days or for good (1 day when '
        f'he names no time), and take it back with /{command} deny: while allowed they are as a listed user, their '
        f'messages addressed to {me} and their DMs reach you as kind="message", and when the allow runs out they are '
        'a stranger again, with no word to them. Each allow and deny comes as a kind="notice" event with user, '
        'user_id and until (an ISO 8601 time in UTC, "permanent", or "denied"); discord_allowed lists who is allowed '
        f"and until when. Anyone may use /{command} help, which answers them alone with the greeting's line and how "
        "to ask you, a stranger within the greeting's limits; it tells you nothing. "
    )


def instructions(settings):
    """what the server tells the session about itself: how Discord reaches it, pushed or waited for"""
    me = settings.identity.title
    allowed = (
        f', of those the owner allowed with /{settings.identity.command} allow' if settings.identity.command else ''
    )
    said = (
        f'{me} is {settings.identity.who} on Discord. Every post is a draft its owner (Discord user {settings.owner}) '
        f'answers in their DMs with {me}: {YES} posts it as it is, {NO} or no answer posts nothing. It reads and posts '
        f"in {scope(settings)}, and reads the owner's DMs with it. Of what it reads, only the owner's messages, those "
        f'of users {by_id(settings.users)}{allowed} and its own reach you; the others are counted, but for a message the '
        f'owner let through: one addressed to {me} (a mention, or a reply to one of its messages) that he put '
        f'his :{WIMSY}: reaction on, or any he replied to while mentioning {me}. '
        + greeting_text(settings)
        + command_text(settings)
        + reacting_text(settings.identity)
    )
    if settings.identity.claude:
        return said + (
            'While the session runs, Discord comes in as <channel> events: kind="message" (from the owner, a listed '
            f'user{" or one he allowed" if allowed else ""}: a message addressed to {me}, or their DM; when the owner replied to someone while mentioning '
            f'{me}, the text ends with the message he replied to, and quoted_author and quoted_author_id name its '
            'author), kind="approved" (a stranger\'s addressed message the owner let through with the reaction), '
            f'each with author, author_id, channel, message_id and reply_to; kind="dm" (someone else wrote to {me} in '
            'DMs: their name only), kind="draft" (the owner answered a draft in his DMs, and it was posted or refused '
            'at once: draft, status, channel, and message_id once posted), kind="error" or "notice" (the gateway'
            + ('; an allow or a deny' if allowed else '')
            + '). '
            + ANSWERING
        )
    return said + (
        'Nothing reaches you on its own: to hear Discord, call discord_wait on a channel after the id of the newest '
        'message you have seen there (discord_read gives it), and again after the "after" it returns. The owner\'s '
        f"DMs with {me} are the channel of a draft's link. His answer to a draft posts or refuses it at once, and the "
        "next tool result says it, after its own JSON, as it says the gateway's news (stopped, cannot be reached, "
        'back). ' + ANSWERING
    )


# How either Wimsy's session answers, whichever way Discord reached it
ANSWERING = (
    f"Answer in Discord with discord_post, reply_to the message's id: it still waits for the owner's {YES}. A "
    'message\'s attachments (its "attachments", or "quoted_attachments" of the message it replies to) are yours to '
    'open with discord_attachments, which saves them and gives their paths.'
)


def cut_by_grok(settings, text):
    """why a client that is not Claude Code loses the end of these instructions, or None: Grok Build shows its model
    the first GROK_SHOWS bytes of them"""
    size, identity = len(text.encode()), settings.identity
    if identity.claude or size <= GROK_SHOWS:
        return None
    ids = sum(len(each) + 2 for each in settings.users | (settings.channels or frozenset()))
    return (
        f"{identity.title}'s instructions are {size} bytes and Grok Build shows its model the first {GROK_SHOWS}: "
        f'the end of them (how to answer, attachments) is lost. List fewer ids in {identity.key("USERS")} or '
        f'{identity.key("CHANNELS")}, which take {ids} bytes of them'
    )


def reacting_text(identity):
    """the reactions and quick replies in words, for the session: which, and when"""
    me, (seen, done) = identity.title, seen_and_done(identity)
    if not identity.drawn:  # XujiWimsy's, kept short: Grok Build shows its model the first GROK_SHOWS bytes
        return (
            f'To say you saw a message or did what it asked, react to it with discord_react rather than post: '
            f'{reactions_text(identity)}; {seen} when you start, then discord_unreact it and put {done} when done. A '
            'reaction goes out at once, with no draft, and only these; so does discord_quick, a reply of one of them '
            f"alone, which takes no text: a text goes through discord_post and the owner's {YES}. "
        )
    return (
        'To say you saw a message or finished what it asked, react to it with discord_react instead of posting, the '
        f"server's emoji first, its unicode one only while that is not uploaded: {reactions_text(identity)}; and "
        f":{WIMSY}:, the owner's emoji. A reaction goes out at once, with no draft, and only these; put {seen} when "
        f"you start on a message and, once done, take it off with discord_unreact and put {done}. {me}'s own "
        f":{WIMSY}: lets nothing through: only the owner's does. To answer a message with one of those emojis alone, "
        'a quick reply, use discord_quick: it posts at once, with no draft, and takes no text; a text goes through '
        f"discord_post and the owner's {YES}. "
    )


class Clock:
    """time as the tools wait on it: a wait ends early when its event is set"""

    def now(self):
        return time.monotonic()

    def wait(self, seconds, event=None):
        """True when event was set during the wait"""
        if event is None:
            time.sleep(seconds)
            return False
        return event.wait(seconds)


def answer_of(raw):
    """an HTTP error's body: its JSON, else its first 300 letters"""
    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode('utf-8', 'replace').strip()[:300]


def form_errors(tree, at=''):
    """the fields and messages of an Invalid Form Body's errors"""
    if isinstance(tree, dict):
        for item in tree.get('_errors', []):
            yield f'{at or "body"}: {item.get("message") if isinstance(item, dict) else item}'
        for key, value in tree.items():
            if key != '_errors':
                yield from form_errors(value, f'{at}.{key}' if at else key)


def reason(said):
    """what Discord's error answer says"""
    if not isinstance(said, dict):
        return shown(said) if said else 'no body'
    text = f'{said.get("message", "no message")} (code {said.get("code", "none")})'
    fields = list(form_errors(said.get('errors')))
    return text + (': ' + '; '.join(fields) if fields else '')


class Discord:
    """Discord's REST API as the bot: a 429 waits its retry_after and tries again; any other failure is a
    DiscordError with Discord's status and message"""

    def __init__(self, token, clock, api=API, identity=AOGO):
        self.token, self.clock, self.api, self.identity = token, clock, api, identity

    def __call__(self, method, path, body=None, files=None, auth=True, label=None, **query):
        """files: (name, bytes, type) sent with body as Discord's multipart form, files[n] each; auth False: without
        the token (an interaction's answer, whose path carries a token of its own); label: the path as messages
        name it"""
        url = self.api + path + ('?' + urllib.parse.urlencode(query) if query else '')
        headers = {'Authorization': f'Bot {self.token}', 'User-Agent': AGENT} if auth else {'User-Agent': AGENT}
        path = label or path
        data = None
        if files:
            data, headers['Content-Type'] = multipart(body, files)
        elif body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        for attempt in range(1, TRIES + 1):
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=30) as answer:
                    raw = answer.read()
            except urllib.error.HTTPError as error:
                with error:
                    said = answer_of(error.read())
                if error.code != 429:
                    raise DiscordError(
                        f'Discord answered {error.code} to {method} {path}: {reason(said)}',
                        error.code,
                        said.get('code') if isinstance(said, dict) else None,
                    ) from None
                retry = said.get('retry_after') if isinstance(said, dict) else None
                retry = retry if isinstance(retry, (int, float)) else error.headers.get('Retry-After')
                try:
                    retry = max(0.0, float(retry))
                except (TypeError, ValueError):
                    raise DiscordError(f'Discord answered 429 to {method} {path} with no retry_after', 429) from None
                if retry > MOST_RETRY:
                    raise DiscordError(
                        f'Discord answered 429 to {method} {path}, asking to wait {retry} s: more than the '
                        f'{MOST_RETRY:.0f} s {self.identity.title} waits for one',
                        429,
                    )
                if attempt == TRIES:
                    raise DiscordError(
                        f'Discord answered 429 to {method} {path} {TRIES} times, the last asking to wait {retry} s',
                        429,
                    )
                self.clock.wait(retry)
                continue
            except OSError as error:  # URLError, a timeout, a reset
                why = getattr(error, 'reason', None) or error
                raise DiscordError(f'Discord could not be reached for {method} {path}: {why}') from None
            try:
                return json.loads(raw) if raw else None
            except ValueError:
                raise DiscordError(f'Discord answered {method} {path} with something that is not JSON') from None

    def download(self, url, most=None):
        """an attachment's bytes from Discord's CDN (or, in the tests, from where the API is), without the token;
        a DiscordError for one longer than most bytes"""
        api = urllib.parse.urlsplit(self.api)
        if not url.startswith(CDN) and not url.startswith(f'{api.scheme}://{api.netloc}/attachments/'):
            raise DiscordError(
                f'an attachment at {url}: {self.identity.title} fetches them from {" or ".join(CDN)} alone'
            )
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': AGENT}), timeout=60) as got:
                data = got.read() if most is None else got.read(most + 1)
                if most is not None and len(data) > most:
                    raise DiscordError(f"Discord's CDN gave more than {most} bytes for {url}")
                return data
        except urllib.error.HTTPError as error:
            error.close()
            raise DiscordError(f"Discord's CDN answered {error.code} to {url}", error.code) from None
        except OSError as error:
            raise DiscordError(
                f"Discord's CDN could not be reached for {url}: {getattr(error, 'reason', error)}"
            ) from None


def multipart(body, files):
    """a multipart/form-data body as Discord takes one: payload_json, then files[n]; and its Content-Type"""
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
        'Content-Type: application/json\r\n\r\n'.encode()
        + json.dumps(body).encode()
        + b'\r\n'
    ]
    for place, (name, data, kind) in enumerate(files):
        quoted = name.replace('\\', '_').replace('"', '_').replace('\r', '_').replace('\n', '_')
        head = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="files[{place}]"; filename="{quoted}"\r\n'
            f'Content-Type: {kind}\r\n\r\n'
        )
        parts.append(head.encode() + data + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def images(value, title):
    """the files discord_post was given, read: [(name, bytes, type)]; None for none; Refused naming what is wrong"""
    if value is None:
        return None
    kinds = ', '.join(kind[1:] for kind in IMAGES)
    if not isinstance(value, list):
        raise Refused(f'files is a JSON {kind_of(value)}, not a list of 1 to {MOST_FILES} absolute paths of images')
    if not value:
        raise Refused(f'files is empty: 1 to {MOST_FILES} absolute paths of images ({kinds})')
    if len(value) > MOST_FILES:
        raise Refused(f'files names {len(value)} files: a post carries 1 to {MOST_FILES} images')
    found = []
    for place, item in enumerate(value, 1):
        if not isinstance(item, str) or not os.path.isabs(item):
            raise Refused(f'files item {place} is {shown(item)}, not an absolute path')
        path = Path(item)
        kind = IMAGES.get(path.suffix.lower())
        if not kind:
            raise Refused(
                f'files item {place} is a {path.suffix or "file without a suffix"}: {title} posts images ({kinds})'
            )
        try:
            data = path.read_bytes()
        except OSError as error:
            raise Refused(f'files item {place} is {item}, which cannot be read: {error.strerror or error}') from None
        if not data:
            raise Refused(f'files item {place}, {item}, is empty')
        found.append((path.name, data, kind))
    return found


def xdg_folder(variable, fallback, server, environ=None):
    """the XDG base folder a variable names when it is an absolute path (the XDG spec ignores any other), else
    ~/fallback; then the server's name (aogowimsy, xujiwimsy)"""
    base = (os.environ if environ is None else environ).get(variable) or ''
    root = Path(base) if os.path.isabs(base) else Path.home() / fallback
    return root / server


def saves_folder(server, environ=None):
    """where discord_attachments saves: XDG_CACHE_HOME, else ~/.cache"""
    return xdg_folder('XDG_CACHE_HOME', '.cache', server, environ)


def state_folder(server, environ=None):
    """where the greetings' limits are kept: XDG_STATE_HOME, else ~/.local/state"""
    return xdg_folder('XDG_STATE_HOME', '.local/state', server, environ)


def private_folder(folder):
    """folder made, 700, and its parents as the user's umask has them"""
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir(mode=0o700, exist_ok=True)


def stamp(value):
    """whether a value is a time: seconds since the epoch"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def an_id(value):
    return isinstance(value, str) and bool(SNOWFLAKE.fullmatch(value))


def a_notice(value):
    """whether a value is a notice an interactions file keeps: None, or {"text", "meta"} as Ear pushes them"""
    if value is None:
        return True
    return (
        isinstance(value, dict)
        and set(value) == {'text', 'meta'}
        and isinstance(value['text'], str)
        and (isinstance(value['meta'], dict) and all(isinstance(item, str) for item in value['meta'].values()))
    )


# Each file of the state folder: what one item is, in words and as a check
SHAPES = {
    'greetings': (
        '[time, person id]',
        lambda item: isinstance(item, list) and len(item) == 2 and stamp(item[0]) and an_id(item[1]),
    ),
    'helps': (
        '[time, person id]',
        lambda item: isinstance(item, list) and len(item) == 2 and stamp(item[0]) and an_id(item[1]),
    ),
    'allowed': (
        '{"id", "name", "since", "until": a time, or null for good}',
        lambda item: (
            isinstance(item, dict)
            and set(item) == {'id', 'name', 'since', 'until'}
            and an_id(item['id'])
            and isinstance(item['name'], str)
            and stamp(item['since'])
            and (item['until'] is None or stamp(item['until']))
        ),
    ),
    'interactions': (
        '[time, interaction id, notice or null]',
        lambda item: (
            isinstance(item, list) and len(item) == 3 and stamp(item[0]) and an_id(item[1]) and a_notice(item[2])
        ),
    ),
}


def hours_minutes(seconds):
    """seconds as hours and minutes, rounded down: never says a wait is over that is not"""
    minutes = int(max(0.0, seconds) // 60)
    return f'{minutes // 60} h {minutes % 60:02d} min'


def utc(when):
    """a time as ISO 8601 in UTC, to the second"""
    return datetime.datetime.fromtimestamp(when, datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


class Store:
    """the bot's state folder, which every server of the bot shares: each session runs one, and all hear the same
    gateway events. A file a kind of SHAPES, {"<kind>": [item, ...]}, read whole, and written whole beside it then
    moved over it, so a reader never sees half; a look and its change are made under the lock STATE_LOCK, which one
    server holds at a time. Times are seconds since the epoch"""

    def __init__(self, folder, now=time.time):
        self.folder, self.now = Path(folder), now
        self.seen = None  # allowed.json as last read: its stat's (inode, mtime, size), and its items

    @contextlib.contextmanager
    def locked(self):
        """the lock held: another server's look and change end first; closing the file lets go"""
        private_folder(self.folder)
        lock = os.open(self.folder / STATE_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
        finally:
            os.close(lock)

    def path(self, kind):
        return self.folder / f'{kind}.json'

    def load(self, kind):
        """the items of a kind's file, each checked; none when there is no file yet. Refused naming the file, what is
        wrong in it, and what stops until it is mended or removed; OSError for one it cannot read"""
        path, (shape, good) = self.path(kind), SHAPES[kind]
        stops = f'{UNREAD[kind]} until it is mended or removed'
        try:
            text = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            return []
        except UnicodeDecodeError as error:
            raise Refused(f'{path} is not UTF-8 text (byte {error.start}): {stops}') from None
        try:
            found = json.loads(text)
        except ValueError as error:
            raise Refused(f'{path} is not JSON ({error}): {stops}') from None
        items = found.get(kind) if isinstance(found, dict) else None
        if not isinstance(items, list):
            raise Refused(f'{path} holds {shown(found)}, not {{"{kind}": [{shape}, ...]}}: {stops}')
        for place, item in enumerate(items, 1):
            if not good(item):
                raise Refused(f'{path}: item {place} is {shown(item)}, not {shape}: {stops}')
        return items

    def save(self, kind, items):
        """a kind's items, written whole beside its file then moved over it"""
        part = self.folder / f'.{kind}.json.part'
        try:
            with open(os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w', encoding='utf-8') as out:
                json.dump({kind: items}, out)
            os.replace(part, self.path(kind))
        except OSError:
            part.unlink(missing_ok=True)
            raise

    def claim(self, kind, person, hours, per_hour):
        """under the lock: whether person may have one more of kind (greetings, helps) now, once each `hours` and
        per_hour an hour, everyone's together. (None, how many the last hour holds with this one), written down; or
        ('person', seconds since their last), or ('hour', how many the last hour holds)"""
        now = self.now()
        kept = [item for item in self.load(kind) if item[0] > now - hours * 3600]
        last = max((when for when, who in kept if who == person), default=None)
        if last is not None:
            return 'person', now - last
        hour = sum(1 for when, _ in kept if when > now - 3600)
        if hour >= per_hour:
            return 'hour', hour
        self.save(kind, kept + [[now, person]])
        return None, hour + 1

    def allowed(self):
        """the allows in force now, {id: item}, read without the lock (a file is moved in whole) and again only once
        the file changed"""
        try:
            found = self.path('allowed').stat()
        except FileNotFoundError:
            return {}
        signature = (found.st_ino, found.st_mtime_ns, found.st_size)
        if self.seen is None or self.seen[0] != signature:
            self.seen = (signature, self.load('allowed'))
        now = self.now()
        return {item['id']: item for item in self.seen[1] if item['until'] is None or item['until'] > now}


def file_name(name, fallback):
    """an attachment's name as a file of its message's folder: no slash, control letter or leading dot, at most 200
    bytes with its suffix kept; fallback when nothing is left"""
    name = re.sub(r'[\x00-\x1f\x7f/\\]', '_', name or '').lstrip('.')
    stem, suffix = os.path.splitext(name)
    if len(suffix.encode()) > 20:
        stem, suffix = name, ''
    while len((stem + suffix).encode()) > 200:
        stem = stem[:-1]
    return stem + suffix if stem else fallback


def link(guild, channel, message):
    return f'https://discord.com/channels/{guild or "@me"}/{channel}/{message}'


def view(message, approved=False):
    """a message as the session gets it"""
    author = message['author']
    reference = message.get('message_reference') or {}
    return {
        'id': message['id'],
        'author': author.get('global_name') or author.get('username'),
        'author_id': author['id'],
        'time': message.get('timestamp'),
        'text': message.get('content', ''),
        'reply_to': reference.get('message_id') if message.get('type') == REPLY else None,
        'attachments': [item.get('filename') for item in message.get('attachments', [])],
        'approved': approved,
    }


def mentions_me(message, me, roles):
    """whether a message mentions the bot's user or its role: the one Discord makes for a bot, of its name, which
    @Aogo may pick as well (DraVee's of 2026-10-24 did)"""
    if any(user.get('id') == me for user in message.get('mentions') or []):
        return True
    return any(role in roles for role in message.get('mention_roles') or [])


def bot_roles(roles, me):
    """the ids of a server's roles Discord made for the bot"""
    return {role['id'] for role in roles if (role.get('tags') or {}).get('bot_id') == me}


def addressed(message, me, roles):
    """whether a message mentions the bot or replies to one of its messages"""
    if mentions_me(message, me, roles):
        return True
    answered = message.get('referenced_message') or {}
    return message.get('type') == REPLY and (answered.get('author') or {}).get('id') == me


def quoting(message, owner, me, roles):
    """the id of the message the owner replied to while mentioning the bot, which lets it through as his WIMSY
    does (DraVee, 2026-10-21: "e literalmente eu quotando outra pessoa"); None for any other message"""
    if message['author']['id'] != owner or message.get('type') != REPLY or not mentions_me(message, me, roles):
        return None
    return (message.get('message_reference') or {}).get('message_id')


def footer(kind, channel, reply_to):
    return f'{kind}: to {channel}' + (f' replying to {reply_to}' if reply_to else '')


def waiting_card(where, reply_to, note=''):
    """the card under a draft's text: where it goes, and how the owner answers"""
    channel, name = where['id'], where.get('name') or where['id']
    lines = [f'Channel: #{name} ({channel})']
    if reply_to:
        lines.append(f'Replying to: {link(where.get("guild_id"), channel, reply_to)}')
    lines.append(f'{YES} posts the text above as it is, pinging no one; {NO} drops it.')
    if note:
        lines.append(note)
    return {
        'title': f'Draft for #{name}',
        'description': '\n'.join(lines),
        'footer': {'text': footer('waiting', channel, reply_to)},
    }


def draft_state(message):
    """what a draft's card says: waiting, sending, sent or not sent, and where to; None for a message that is no
    draft"""
    embeds = message.get('embeds') or [{}]
    text = (embeds[0].get('footer') or {}).get('text', '')
    found = SENT.fullmatch(text)
    if found:
        guild, channel, posted = found.groups()
        return {
            'kind': 'sent',
            'channel': channel,
            'reply_to': None,
            'message': posted,
            'link': link(guild, channel, posted),
        }
    found = WAITING.fullmatch(text)
    if found:
        return {'kind': found.group(1), 'channel': found.group(2), 'reply_to': found.group(3)}
    return None


def one_of(value, taken, said):
    """value when it is one of taken, else Refused naming it, its code points (an emoji's variation selector does not
    show), said, and the ones taken"""
    if value in taken:
        return value
    points = ''
    if isinstance(value, str) and not value.isascii():
        points = ' (' + ' '.join(f'U+{ord(letter):04X}' for letter in value) + ')'
    raise Refused(f'emoji is {shown(value)}{points}, {said}: it takes {", ".join(taken)}')


def is_emoji(found, emoji):
    """whether a reaction's emoji ({"id", "name"}) is emoji, one of REACTIONS: :name: for a custom one"""
    if emoji.startswith(':'):
        return found.get('name') == emoji.strip(':') and bool(found.get('id'))
    return found.get('id') is None and found.get('name') == emoji


def in_path(found):
    """a reaction's emoji as Discord's reaction routes name it: the emoji, or name:id for a custom one"""
    return f'{found["name"]}:{found["id"]}' if found.get('id') else found['name']


def take(args, tool, required, optional):
    """Refused when args name an argument the tool does not have, or lack one it needs"""
    known = required + optional
    for name in args:
        if name not in known:
            raise Refused(f'{tool} has no argument {shown(name)}; it takes {", ".join(known)}')
    for name in required:
        if args.get(name) is None:
            raise Refused(f'{tool} needs {name}')


def kind_of(value):
    kinds = {bool: 'boolean', int: 'number', float: 'number', str: 'string', list: 'array', dict: 'object'}
    return kinds.get(type(value), 'value')


class Inbox:
    """the messages the gateway heard in one channel, for one wait; gap: some may have gone unheard"""

    def __init__(self, channel):
        self.channel, self.ready, self.guard = channel, threading.Event(), threading.Lock()
        self.pending, self.gap = [], True  # a new inbox reads what came before it, once

    def put(self, message):
        with self.guard:
            self.pending.append(message)
            self.ready.set()

    def lost(self):
        with self.guard:
            self.gap = True
            self.ready.set()

    def take(self):
        with self.guard:
            items, gap = self.pending, self.gap
            self.pending, self.gap = [], False
            self.ready.clear()
        return items, gap


class Hub:
    """the gateway's messages, handed to the waits listening on their channel"""

    def __init__(self):
        self.guard, self.inboxes, self.stopped = threading.Lock(), set(), None

    @contextlib.contextmanager
    def listening(self, channel):
        inbox = Inbox(channel)
        with self.guard:
            self.inboxes.add(inbox)
        try:
            yield inbox
        finally:
            with self.guard:
                self.inboxes.discard(inbox)

    def deliver(self, message):
        with self.guard:
            inboxes = [inbox for inbox in self.inboxes if inbox.channel == message.get('channel_id')]
        for inbox in inboxes:
            inbox.put(message)

    def gap(self):
        """a new gateway session: what came while none was up went unheard"""
        with self.guard:
            inboxes = list(self.inboxes)
        for inbox in inboxes:
            inbox.lost()

    def stop(self, why):
        self.stopped = why
        with self.guard:
            inboxes = list(self.inboxes)
        for inbox in inboxes:
            inbox.ready.set()


def command_list(identity):
    """the application commands the bot registers in each server it is in: its command and SUBCOMMANDS, which every
    member sees (default_member_permissions null), as Discord sets it for a whole command"""
    if not identity.command:
        return []

    def user(what):
        return {'type': USER_OPTION, 'name': 'user', 'description': what, 'required': True}

    times = [{'name': ALLOW_NAMES[value], 'value': value} for value in ALLOW_TIMES]
    time_option = {'type': STRING_OPTION, 'name': 'time', 'description': 'For how long: 1 day without one'}
    return [
        {
            'type': CHAT_INPUT,
            'name': identity.command,
            'description': f"{identity.who}, DraVee's AI assistant on ScarletNX",
            'default_member_permissions': None,
            'options': [
                {
                    'type': SUB_COMMAND,
                    'name': 'help',
                    'description': f'What {identity.who} is and how to ask it something',
                },
                {
                    'type': SUB_COMMAND,
                    'name': 'allow',
                    'description': f"DraVee only: let someone's messages reach {identity.who} for a time",
                    'options': [user('Who to allow'), dict(time_option, choices=times)],
                },
                {
                    'type': SUB_COMMAND,
                    'name': 'deny',
                    'description': "DraVee only: take someone's allow back",
                    'options': [user('Whose allow to take back')],
                },
                {'type': SUB_COMMAND, 'name': 'allowed', 'description': 'DraVee only: who is allowed, and until when'},
            ],
        }
    ]


def command_shape(command):
    """what of a command the bot sets, as it sends it or Discord gives it back (with its ids, version and fields left
    at their defaults): two that match need no new registration"""

    def option(item):
        shape = {
            'type': item.get('type'),
            'name': item.get('name'),
            'description': item.get('description'),
            'required': bool(item.get('required')),
            'choices': [{'name': c.get('name'), 'value': c.get('value')} for c in item.get('choices') or []],
            'options': [option(each) for each in item.get('options') or []],
        }
        return shape

    return {
        'type': command.get('type', CHAT_INPUT),
        'name': command.get('name'),
        'description': command.get('description'),
        'default_member_permissions': command.get('default_member_permissions'),
        'options': [option(item) for item in command.get('options') or []],
    }


def subcommand(event):
    """an interaction's subcommand and the values of its options: (its name or None, {option: value})"""
    options = (event.get('data') or {}).get('options') or []
    first = options[0] if options and isinstance(options[0], dict) and options[0].get('type') == SUB_COMMAND else {}
    return first.get('name'), {item.get('name'): item.get('value') for item in first.get('options') or []}


def invoker(event):
    """the id of who used a command: a member in a server, a user in DMs"""
    return ((event.get('member') or {}).get('user') or event.get('user') or {}).get('id')


def member_name(event, user):
    """a user an interaction names, as the server shows them: their nickname, their name, or their id"""
    resolved = (event.get('data') or {}).get('resolved') or {}
    member, found = (resolved.get('members') or {}).get(user) or {}, (resolved.get('users') or {}).get(user) or {}
    return member.get('nick') or found.get('global_name') or found.get('username') or user


def when_markup(when):
    """a time as Discord shows it in each reader's own zone: the date and hour, and how far off"""
    return f'<t:{int(when)}:f> (<t:{int(when)}:R>)'


def ran(until, shown_as):
    """how long an allow runs: for good, or until a time shown as shown_as has it"""
    return 'for good' if until is None else f'until {shown_as(until)}'


class Wimsy:
    """the tools: Discord with the settings' identity, channels, people and owner"""

    def __init__(self, settings, discord, clock, hub=None, files=None, drawings=None, state=None):
        self.settings, self.discord, self.clock = settings, discord, clock
        self.title = settings.identity.title
        self.hub = hub or Hub()
        self.files = Path(files) if files else saves_folder(settings.identity.server)  # where discord_attachments saves
        self.drawings = Path(drawings or EMOJI_FOLDER).expanduser()  # where discord_emoji_upload reads DRAWN
        # the greetings, the help given and the allows, for a bot that greets or has a command: the state folder,
        # touched at the first need
        state = Path(state) if state else state_folder(settings.identity.server)
        identity = settings.identity
        self.store = Store(state) if identity.greeting or identity.command else None
        self.known = {}  # its own user id, its roles and the owner's DM channel, asked once
        self.approved = set()  # the messages the owner let through while the gateway heard: their ids, in memory only
        self.guard = threading.Lock()
        self.drafts = {}  # a lock a draft: one look at a time, so no draft is posted twice
        self.made = set()  # the drafts this server made: the gateway's answers act on these alone, as every
        # session started in the workspace runs one and they share no lock

    def me(self):
        if 'me' not in self.known:
            self.known['me'] = self.discord('GET', '/users/@me')['id']
        return self.known['me']

    def roles(self):
        """the roles Discord made for the bot, one a server: asked once, and again after the gateway says it joined
        a server"""
        if 'roles' not in self.known:
            me, found = self.me(), set()
            for guild in self.discord('GET', '/users/@me/guilds'):
                found |= bot_roles(self.discord('GET', f'/guilds/{guild["id"]}/roles'), me)
            self.known['roles'] = found
        return self.known['roles']

    def dm(self):
        if 'dm' not in self.known:
            self.known['dm'] = self.discord('POST', '/users/@me/channels', {'recipient_id': self.settings.owner})['id']
        return self.known['dm']

    def allowed(self):
        """the people the owner allowed with his command, their allow still running: {id: its item}"""
        return self.store.allowed() if self.settings.identity.command else {}

    def people(self):
        """whose messages reach the session: the owner, the listed users, and those he allowed"""
        return self.settings.users | {self.settings.owner} | set(self.allowed())

    def person(self, author):
        """whether author is one of people(): the state folder is read only for someone neither owner nor listed"""
        return author == self.settings.owner or author in self.settings.users or author in self.allowed()

    def authors(self, value):
        """the ids `from` names, each the owner, a listed user or one he allowed; None when it names none"""
        if value is None:
            return None
        owner, users = self.settings.owner, by_id(self.settings.users)
        if not isinstance(value, list) or not value:
            raise Refused(
                f'from is {shown(value)}: a list of 1 or more ids, of the owner ({owner}) or listed users ({users})'
            )
        for place, item in enumerate(value, 1):
            snowflake(item, f'from item {place}')
            if not self.person(item):
                raise Refused(
                    f'from item {place} is {item}, neither the owner ({owner}), a listed user ({users}) nor one he '
                    'allowed'
                )
        return frozenset(value)

    def where(self, channel, reading):
        """the channel the bot may post in, or read: listed, a thread of a listed one, any Discord lets it see when
        none is listed, or (reading) the owner's DMs; else Refused naming it and those it may"""
        listed = self.settings.channels
        if listed is None or channel in listed:
            return self.discord('GET', f'/channels/{channel}')  # Discord's 403 or 404 names it
        if reading and channel == self.dm():
            return {'id': channel, 'type': DM}
        may = f'{self.settings.identity.key("CHANNELS")} lists {by_id(listed)}, and their threads'
        if reading:
            may += f", and the owner's DMs with {self.title} are {self.dm()}"
        verb = 'read' if reading else 'post in'
        try:
            found = self.discord('GET', f'/channels/{channel}')
        except DiscordError as error:
            raise Refused(f'channel {channel} is not one {self.title} may {verb}: {may}; and {error}') from None
        if found.get('type') in THREADS and found.get('parent_id') in listed:
            return found
        raise Refused(f'channel {channel} is not one {self.title} may {verb}: {may}')

    def call(self, name, args, cancelled, progress):
        tools = {
            'discord_post': self.post,
            'discord_post_status': self.post_status,
            'discord_read': self.read,
            'discord_wait': self.wait_for,
            'discord_attachments': self.attachments,
            'discord_react': self.react,
            'discord_unreact': self.unreact,
            'discord_quick': self.quick,
            'discord_emoji_upload': self.emoji_upload,
            'discord_allowed': self.allowed_list,
        }
        return tools[name](args, cancelled, progress)

    def post(self, args, cancelled, progress):
        take(args, 'discord_post', ('channel', 'text'), ('reply_to', 'wait', 'files'))
        channel = snowflake(args['channel'], 'channel')
        text = args['text']
        if not isinstance(text, str):
            raise Refused(f'text is a JSON {kind_of(text)}, not a string')
        if not text.strip():
            raise Refused(f'text is empty: Discord posts 1 to {LIMIT} letters')
        if len(text) > LIMIT:
            raise Refused(f'text has {len(text)} letters: a Discord message holds {LIMIT} at most')
        reply_to = None if args.get('reply_to') is None else snowflake(args['reply_to'], 'reply_to')
        wait = whole(args.get('wait'), 'wait', 300, 0, MOST_WAIT)
        files = images(args.get('files'), self.title)
        where = self.where(channel, reading=False)
        if reply_to:
            self.discord('GET', f'/channels/{channel}/messages/{reply_to}')
        dm = self.dm()
        body = {'content': text, 'embeds': [waiting_card(where, reply_to)], 'allowed_mentions': {'parse': []}}
        if files:
            body['attachments'] = [{'id': place, 'filename': name} for place, (name, _, _) in enumerate(files)]
        draft = self.discord('POST', f'/channels/{dm}/messages', body, files)['id']
        self.made.add(draft)
        for emoji in (YES, NO):
            self.discord('PUT', f'/channels/{dm}/messages/{draft}/reactions/{urllib.parse.quote(emoji)}/@me')
        return self.verdict(draft, wait, cancelled, progress)

    def post_status(self, args, cancelled, progress):
        take(args, 'discord_post_status', ('draft',), ('wait',))
        draft = snowflake(args['draft'], 'draft')
        return self.verdict(draft, whole(args.get('wait'), 'wait', 300, 0, MOST_WAIT), cancelled, progress)

    def lock(self, draft):
        with self.guard:
            return self.drafts.setdefault(draft, threading.Lock())

    def verdict(self, draft, wait, cancelled, progress):
        """the owner's answer to a draft, within wait seconds: sent, not sent, or still waiting"""
        dm, me = self.dm(), self.me()
        start = self.clock.now()
        while True:
            with self.lock(draft):
                message = self.discord('GET', f'/channels/{dm}/messages/{draft}')
                state = draft_state(message) if message['author']['id'] == me else None
                if state is None:
                    raise Refused(f"message {draft} in the owner's DMs ({dm}) is not a draft of {self.title}'s")
                kind, channel = state['kind'], state['channel']
                if kind == 'sent':
                    return {
                        'status': 'sent',
                        'link': state['link'],
                        'message': state['message'],
                        'channel': channel,
                        'draft': draft,
                    }
                if kind == 'not sent':
                    return {'status': 'not sent', 'channel': channel, 'draft': draft}
                if kind == 'sending':
                    raise Refused(
                        f'draft {draft} says it is being posted to channel {channel}: another {self.title} is posting '
                        f'it, or one stopped while it did; look in that channel, {self.title} posts no draft twice'
                    )
                got = self.decide(dm, message, state)
                if got:
                    return got
            waited = self.clock.now() - start
            if waited >= wait:
                return {'status': 'waiting', 'draft': draft, 'link': link(None, dm, draft), 'waited': round(waited)}
            if self.clock.wait(min(POLL, wait - waited), cancelled):
                raise Cancelled
            progress(self.clock.now() - start, wait, f"waiting for the owner's answer to draft {draft}")

    def decide(self, dm, message, state):
        """a waiting draft, under its lock: refused or posted when the owner has answered, else None"""
        channel = state['channel']
        yes, no = self.answer(dm, message)
        if no:
            card = {'title': 'Not sent', 'description': f'{NO}: not sent to channel {channel}.'}
            card['footer'] = {'text': footer('not sent', channel, state['reply_to'])}
            self.edit(dm, message['id'], card)
            return {'status': 'not sent', 'channel': channel, 'draft': message['id']}
        if yes:
            return self.send(dm, message, state)
        return None

    def answered(self, draft):
        """the owner's answer the gateway brought, on a draft this server made and still waiting: posted or refused
        at once, whether a tool waits on it or not; None for any other message of his DMs (another session's draft
        waits for that session's look, or a discord_post_status)"""
        if draft not in self.made:
            return None
        dm, me = self.dm(), self.me()
        with self.lock(draft):
            message = self.discord('GET', f'/channels/{dm}/messages/{draft}')
            state = draft_state(message) if message['author']['id'] == me else None
            if state is None or state['kind'] != 'waiting':
                return None
            return self.decide(dm, message, state)

    def reactors(self, channel, message, emoji):
        """the ids of who reacted to a message with an emoji (a name, or name:id for a custom one)"""
        path = f'/channels/{channel}/messages/{message}/reactions/{urllib.parse.quote(emoji)}'
        return {user.get('id') for user in self.discord('GET', path, limit=PAGE)}

    def answer(self, dm, message):
        """whether the owner reacted with the check mark, and with the cross: another person's reaction, or
        the bot's own, counts for nothing"""
        said = {}
        for reaction in message.get('reactions') or []:
            emoji = reaction.get('emoji') or {}
            if emoji.get('id') is None and emoji.get('name') in (YES, NO):
                others = reaction.get('count', 0) - (1 if reaction.get('me') else 0)
                if others > 0:
                    said[emoji['name']] = self.settings.owner in self.reactors(dm, message['id'], emoji['name'])
        return said.get(YES, False), said.get(NO, False)

    def let_through(self, channel, message, me):
        """whether a stranger's message is addressed to the bot and carries the owner's WIMSY reaction"""
        if not addressed(message, me, self.roles()):
            return False
        for reaction in message.get('reactions') or []:
            emoji = reaction.get('emoji') or {}
            if emoji.get('name') == WIMSY and emoji.get('id'):
                return self.settings.owner in self.reactors(channel, message['id'], f'{WIMSY}:{emoji["id"]}')
        return False

    def edit(self, dm, draft, card):
        self.discord('PATCH', f'/channels/{dm}/messages/{draft}', {'embeds': [card]})

    def send(self, dm, message, state):
        """posts an approved draft's text where it goes, then says on the draft where it went"""
        draft, channel, reply_to = message['id'], state['channel'], state['reply_to']
        where = self.where(channel, reading=False)  # today's list, not the one of the day it was drafted
        name, guild = where.get('name') or channel, where.get('guild_id')
        sending = waiting_card(where, reply_to)
        sending.update(title=f'Sending to #{name}', footer={'text': footer('sending', channel, reply_to)})
        self.edit(dm, draft, sending)
        body = {'content': message['content'], 'allowed_mentions': {'parse': [], 'replied_user': False}}
        if reply_to:
            body['message_reference'] = {'message_id': reply_to, 'channel_id': channel, 'fail_if_not_exists': True}
        files = []
        try:
            for item in message.get('attachments') or []:  # the draft's own: what the owner saw is what goes
                kind = item.get('content_type') or 'application/octet-stream'
                files.append((item['filename'], self.discord.download(item['url']), kind))
            if files:
                body['attachments'] = [{'id': place, 'filename': name} for place, (name, _, _) in enumerate(files)]
            posted = self.discord('POST', f'/channels/{channel}/messages', body, files)['id']
        except DiscordError as error:
            try:
                self.edit(dm, draft, waiting_card(where, reply_to, f'Posting failed: {error}'))
            except DiscordError as second:
                raise DiscordError(f'{error}; and draft {draft} still says sending: {second}') from None
            raise
        where_to = link(guild, channel, posted)
        card = {'title': f'Sent to #{name}', 'description': f'Sent: {where_to}'}
        card['footer'] = {'text': f'sent: {guild or "@me"}/{channel}/{posted}'}
        try:
            self.edit(dm, draft, card)
        except DiscordError as error:
            raise DiscordError(f'posted as {where_to}, but draft {draft} still says sending: {error}') from None
        return {'status': 'sent', 'link': where_to, 'message': posted, 'channel': channel, 'draft': draft}

    def read(self, args, cancelled, progress):
        take(args, 'discord_read', ('channel',), ('after', 'limit', 'from'))
        channel = snowflake(args['channel'], 'channel')
        after = None if args.get('after') is None else snowflake(args['after'], 'after')
        limit = whole(args.get('limit'), 'limit', 50, 1, PAGE)
        named = self.authors(args.get('from'))
        self.where(channel, reading=True)
        query = {'limit': limit} | ({'after': after} if after else {})
        page = sorted(self.discord('GET', f'/channels/{channel}/messages', **query), key=lambda m: int(m['id']))
        me = self.me()
        heard = named if named is not None else self.people() | {me}
        roles = self.roles()
        quoted = self.approved | {quoting(m, self.settings.owner, me, roles) for m in page}
        kept = []
        for message in page:
            author = message['author']['id']
            if author in heard:
                kept.append(view(message))
            elif named is None and author != me and (message['id'] in quoted or self.let_through(channel, message, me)):
                kept.append(view(message, approved=True))
        newest = page[-1]['id'] if page else after
        return {'channel': channel, 'messages': kept, 'left_out': len(page) - len(kept), 'after': newest}

    def since(self, channel, after):
        """every message of a channel after an id, from Discord's REST, oldest first"""
        found = []
        while True:
            page = sorted(
                self.discord('GET', f'/channels/{channel}/messages', after=after, limit=PAGE),
                key=lambda m: int(m['id']),
            )
            found += page
            if len(page) < PAGE:
                return found
            after = page[-1]['id']

    def readable(self, channel, message):
        """Refused unless discord_read gives the message: the owner's, a listed user's, the bot's own, or one the owner
        let through (his WIMSY reaction, or his reply mentioning the bot among the PAGE messages after it); the
        refusal names no one"""
        me = self.me()
        if message['author']['id'] == me or self.person(message['author']['id']):
            return
        if message['id'] in self.approved or self.let_through(channel, message, me):
            return
        later = self.discord('GET', f'/channels/{channel}/messages', after=message['id'], limit=PAGE)
        roles = self.roles()
        if message['id'] in {quoting(m, self.settings.owner, me, roles) for m in later}:
            return
        raise Refused(
            f"message {message['id']} is not one {self.title} gives: neither the owner's ({self.settings.owner}), a listed "
            f"user's ({by_id(self.settings.users)}) nor its own, and the owner has not let it through (his :{WIMSY}: "
            f'reaction, or his reply to it mentioning {self.title})'
        )

    def attachments(self, args, cancelled, progress):
        take(args, 'discord_attachments', ('channel', 'message'), ())
        channel = snowflake(args['channel'], 'channel')
        number = snowflake(args['message'], 'message')
        self.where(channel, reading=True)
        message = self.discord('GET', f'/channels/{channel}/messages/{number}')  # Discord's 404 names it
        self.readable(channel, message)
        found = message.get('attachments') or []
        if not found:
            raise Refused(f'message {number} in channel {channel} has no attachments')
        folder = self.files / channel / number
        self.files.parent.mkdir(parents=True, exist_ok=True)
        for level in (self.files, self.files / channel, folder):  # 700 each: other people's files
            level.mkdir(mode=0o700, exist_ok=True)
        saved, used = [], set()
        for item in found:
            if cancelled.is_set():
                raise Cancelled
            name = file_name(item.get('filename'), item['id'])
            if name in used:
                name = f'{item["id"]}-{name}'
            used.add(name)
            size = item.get('size')
            entry = {'name': item.get('filename'), 'type': item.get('content_type'), 'size': size}
            entry.update({key: item[key] for key in ('width', 'height') if item.get(key)})
            path = folder / name
            if isinstance(size, int) and size > MOST_SAVE:
                entry['error'] = f'{size} bytes, more than the {MOST_SAVE} {self.title} saves of one attachment'
            elif isinstance(size, int) and path.is_file() and path.stat().st_size == size:
                entry['path'] = str(path)  # saved by an earlier call: an attachment never changes
            else:
                try:
                    data = self.discord.download(item['url'], most=MOST_SAVE)
                except DiscordError as error:
                    entry['error'] = str(error)
                else:
                    part = folder / f'.{name}.part'
                    try:
                        with open(os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'wb') as out:
                            out.write(data)
                        os.replace(part, path)
                    except OSError as error:
                        part.unlink(missing_ok=True)
                        entry['error'] = f'{path} could not be written: {error.strerror or error}'
                    else:
                        entry['path'], entry['size'] = str(path), len(data)
            saved.append(entry)
        return {'channel': channel, 'message': number, 'folder': str(folder), 'files': saved}

    def aimed(self, tool, channel, number, reading):
        """Discord's channel and the message a reaction or a quick reply is for, checked: the channel one the bot may
        read (reading) or post in, the message one discord_read gives and no draft"""
        where = self.where(channel, reading=reading)
        message = self.discord('GET', f'/channels/{channel}/messages/{number}')  # Discord's 404 names it
        self.readable(channel, message)
        if message['author']['id'] == self.me() and draft_state(message):
            raise Refused(
                f"message {number} is a draft of {self.title}'s: its {YES} and {NO} are for the owner's answer, and "
                f'{tool} touches no draft'
            )
        return where, message

    def reacting(self, tool, args):
        """the channel, its server (None in DMs), the message and the emoji a reaction tool names, each checked: the
        emoji one of REACTIONS, then as aimed has it"""
        take(args, tool, ('channel', 'message', 'emoji'), ())
        channel = snowflake(args['channel'], 'channel')
        number = snowflake(args['message'], 'message')
        emoji = one_of(args['emoji'], self.settings.identity.reactions, f'not one {self.title} reacts with')
        where, message = self.aimed(tool, channel, number, reading=True)
        return channel, where.get('guild_id'), message, emoji

    def react(self, args, cancelled, progress):
        channel, guild, message, emoji = self.reacting('discord_react', args)
        number, reactions = message['id'], message.get('reactions') or []
        if any(item.get('me') and is_emoji(item.get('emoji') or {}, emoji) for item in reactions):
            status = 'already there'
        else:
            # a custom emoji goes by its id: the one a reaction on the message has, else a server's of its name
            found = next((item['emoji'] for item in reactions if is_emoji(item.get('emoji') or {}, emoji)), None)
            name = in_path(found) if found else self.custom(emoji, guild) if emoji.startswith(':') else emoji
            try:
                self.discord('PUT', f'/channels/{channel}/messages/{number}/reactions/{urllib.parse.quote(name)}/@me')
            except DiscordError:
                if emoji.startswith(':'):
                    self.known.pop('emojis', None)  # deleted, or made again with a new id, since it was asked
                raise
            status = 'reacted'
        log(f'discord_react: {status}, {emoji} of {self.title} on message {number} in channel {channel}')
        return {'status': status, 'channel': channel, 'message': number, 'emoji': emoji}

    def unreact(self, args, cancelled, progress):
        channel, _, message, emoji = self.reacting('discord_unreact', args)
        number = message['id']
        mine = (item.get('emoji') or {} for item in message.get('reactions') or [] if item.get('me'))
        found = next((each for each in mine if is_emoji(each, emoji)), None)
        if found:
            name = urllib.parse.quote(in_path(found))
            self.discord('DELETE', f'/channels/{channel}/messages/{number}/reactions/{name}/@me')
        status = 'removed' if found else 'not there'
        log(f'discord_unreact: {status}, {emoji} of {self.title} on message {number} in channel {channel}')
        return {'status': status, 'channel': channel, 'message': number, 'emoji': emoji}

    def quick(self, args, cancelled, progress):
        take(args, 'discord_quick', ('channel', 'reply_to', 'emoji'), ())
        channel = snowflake(args['channel'], 'channel')
        reply_to = snowflake(args['reply_to'], 'reply_to')
        emoji = one_of(
            args['emoji'],
            self.settings.identity.quick,
            f"not one {self.title} posts alone; a text goes through discord_post and the owner's {YES}",
        )
        where, _ = self.aimed('discord_quick', channel, reply_to, reading=False)
        # a custom emoji's id asked now: a stale one would post its name as text, which Discord takes
        content = f'<:{self.custom(emoji, where.get("guild_id"), fresh=True)}>' if emoji.startswith(':') else emoji
        body = {
            'content': content,
            'allowed_mentions': {'parse': [], 'replied_user': False},
            'message_reference': {'message_id': reply_to, 'channel_id': channel, 'fail_if_not_exists': True},
        }
        posted = self.discord('POST', f'/channels/{channel}/messages', body)['id']
        said = f'{emoji} of {self.title} as message {posted} replying to {reply_to} in channel {channel}'
        log(f'discord_quick: posted, {said}')
        return {
            'status': 'posted',
            'link': link(where.get('guild_id'), channel, posted),
            'message': posted,
            'channel': channel,
            'reply_to': reply_to,
            'emoji': emoji,
        }

    def greet(self, message):
        """the identity's greeting, posted at once as a reply to a stranger's message that called the bot, pinging the
        owner alone; nothing past a limit, and stderr says which. The id posted, or None. stderr names the channel and
        the counts, never the caller nor what they said"""
        channel, settings = message['channel_id'], self.settings
        why, value = self.limit('greetings', message['author']['id'])
        said = {
            'off': f'{settings.identity.key("GREET_PER_HOUR")} is 0',
            'person': f'the caller was greeted {hours_minutes(value)} ago: once each {settings.greet_hours} h',
            'hour': f'{value} greetings in the last hour: {settings.greet_per_hour} at most',
        }.get(why, f'{value} of {settings.greet_per_hour} in the last hour')
        if why:
            log(f"greet: a stranger's call in channel {channel} is only counted: {said}")
            return None
        body = {
            'content': settings.identity.greeting.format(owner=settings.owner),
            'allowed_mentions': {'parse': [], 'users': [settings.owner], 'replied_user': False},
            'message_reference': {'message_id': message['id'], 'channel_id': channel, 'fail_if_not_exists': True},
        }
        posted = self.discord('POST', f'/channels/{channel}/messages', body)['id']
        log(f"greet: posted message {posted} replying to a stranger's call in channel {channel} ({said})")
        return posted

    def limit(self, kind, person, held=False):
        """one more of kind (greetings, helps) for a stranger, within the greeting's limits: (None, how many the last
        hour holds with it), written down; ('off', 0) when GREET_PER_HOUR is 0; or Store.claim's why and value.
        held: the caller holds the state's lock already"""
        settings = self.settings
        if settings.greet_per_hour == 0:
            return 'off', 0
        with contextlib.nullcontext() if held else self.store.locked():
            return self.store.claim(kind, person, settings.greet_hours, settings.greet_per_hour)

    def application(self):
        """the bot's application id: READY's, else asked once"""
        if 'application' not in self.known:
            self.known['application'] = self.discord('GET', '/applications/@me')['id']
        return self.known['application']

    def reinvite(self):
        """the invite that gives the bot its command's scope with the permissions it has"""
        return (
            f'https://discord.com/oauth2/authorize?client_id={self.application()}&scope=bot+applications.commands'
            f'&permissions={INVITE | CREATE_EXPRESSIONS}'
        )

    def register(self, guild):
        """the identity's command in a server, as command_list has it: sent (bulk, in place of what the server has)
        only when the server's differ. 'registered', or 'already there'"""
        command, wanted = self.settings.identity.command, command_list(self.settings.identity)
        path = f'/applications/{self.application()}/guilds/{guild}/commands'
        try:
            there = self.discord('GET', path)
            if sorted(map(command_shape, there), key=json.dumps) == sorted(map(command_shape, wanted), key=json.dumps):
                status = 'already there'
            else:
                self.discord('PUT', path, wanted)
                status = 'registered'
        except DiscordError as error:
            if error.code != MISSING_ACCESS:
                raise
            raise DiscordError(
                f'{error}: {self.title} needs the applications.commands scope in server {guild} for /{command}; '
                f'invite it again with {self.reinvite()}',
                error.status,
                error.code,
            ) from None
        log(f'commands: /{command} ({", ".join(SUBCOMMANDS)}) {status} in server {guild}')
        return status

    def command(self, event):
        """a use of the identity's command, decided once whichever server of the bot hears it first: {"sub", "text"
        (the answer, None when another server answered it), "notice" (for the session, or None)}"""
        number, (sub, _) = event['id'], subcommand(event)
        with self.store.locked():
            now = self.store.now()
            kept = [item for item in self.store.load('interactions') if item[0] > now - HANDLED_FOR]
            done = next((item for item in kept if item[1] == number), None)
            if done:
                return {'sub': sub, 'text': None, 'notice': done[2]}
            text, notice = self.use(event, now)
            self.store.save('interactions', kept + [[now, number, notice]])
        return {'sub': sub, 'text': text, 'notice': notice}

    def use(self, event, now):
        """under the state's lock: the answer to a use of the command and the notice for the session (None for
        none), the change it makes written"""
        settings, command = self.settings, self.settings.identity.command
        (sub, values), asker = subcommand(event), invoker(event)
        if sub == 'help':
            return self.help(asker), None
        if sub not in OWNERS_ALONE:
            return f'/{command} {sub} is not a command of {self.title}: it has {", ".join(SUBCOMMANDS)}.', None
        if asker != settings.owner:
            return f'Only <@{settings.owner}> can use /{command} {sub}.', None
        if sub == 'allowed':
            return self.allowed_text(), None
        target = values.get('user')
        if not an_id(target):
            return f'user is {shown(target)}, not a member: /{command} {sub} takes one.', None
        if target == settings.owner:
            return f'<@{target}> is the owner: his messages always reach the session.', None
        if target in settings.users:
            return (
                f'<@{target}> is listed in {settings.identity.key("USERS")}: their messages always reach the session, '
                'and the env file takes them out.'
            ), None
        if target == self.me():
            return f'<@{target}> is {self.title} itself.', None
        if sub == 'allow':
            return self.allow(target, member_name(event, target), values.get('time'), now)
        return self.deny(target, now)

    def in_force(self, now):
        """under the state's lock: the allows not run out at now, read for a change"""
        return [item for item in self.store.load('allowed') if item['until'] is None or item['until'] > now]

    def allow(self, target, name, time_value, now):
        time_value = ALLOW_DEFAULT if time_value is None else time_value
        if time_value not in ALLOW_TIMES:
            return (
                f'time is {shown(time_value)}, not one of {", ".join(ALLOW_TIMES)}: <@{target}> is not allowed.',
                None,
            )
        seconds = ALLOW_TIMES[time_value]
        until = None if seconds is None else now + seconds
        items = self.in_force(now)
        before = next((item for item in items if item['id'] == target), None)
        items = [item for item in items if item['id'] != target]
        self.store.save('allowed', items + [{'id': target, 'name': name, 'since': now, 'until': until}])
        if until is None:
            answer, span = 'for good, until you deny them', 'for good, until he denies them'
        else:
            answer, span = f'until {when_markup(until)}', f'until {utc(until)} ({ALLOW_NAMES[time_value]})'
        text = (
            f'The owner allowed {name} ({target}) {span}: their messages addressed to {self.title} reach you as a '
            "listed user's do, and discord_allowed lists them."
        )
        answer = f'<@{target}> is allowed {answer}: their messages to me reach the session.'
        if before:
            text += f' It ran {ran(before["until"], utc)} before.'
            answer += f' It ran {ran(before["until"], when_markup)} before.'
        meta = {
            'kind': 'notice',
            'user': name,
            'user_id': target,
            'until': 'permanent' if until is None else utc(until),
        }
        return answer, {'text': text, 'meta': meta}

    def deny(self, target, now):
        items = self.in_force(now)
        before = next((item for item in items if item['id'] == target), None)
        if before is None:
            return f'<@{target}> has no allow to take back.', None
        self.store.save('allowed', [item for item in items if item['id'] != target])
        name = before['name']
        text = (
            f'The owner took back the allow of {name} ({target}), which ran {ran(before["until"], utc)}: their '
            "messages are a stranger's again"
        )
        meta = {'kind': 'notice', 'user': name, 'user_id': target, 'until': 'denied'}
        answer = f'<@{target}> is not allowed anymore; it ran {ran(before["until"], when_markup)}.'
        return answer, {'text': text, 'meta': meta}

    def allowed_text(self):
        """the allows in force as the owner's answer: each one's mention, name and end, then the listed users"""
        found = sorted(self.allowed().values(), key=lambda item: (item['until'] is None, item['until'] or 0))
        lines = [f'<@{item["id"]}> ({item["name"]}): {ran(item["until"], when_markup)}' for item in found]
        listed = ', '.join(f'<@{user}>' for user in sorted(self.settings.users, key=int))
        tail = [f'Listed in {self.settings.identity.key("USERS")}, always: {listed}']
        head = ['Allowed:'] if lines else ['No one is allowed now.']
        kept = len(lines)
        while True:  # past a message's letters, the last ones go: discord_allowed lists them all
            more = [f'{len(lines) - kept} more: discord_allowed lists them all.'] if kept < len(lines) else []
            text = '\n'.join(head + lines[:kept] + more + tail)
            if len(text) <= LIMIT or not kept:
                return text
            kept -= 1

    def help(self, asker):
        """what the bot is and how to ask it, for anyone; a stranger's within the greeting's limits; the owner's with
        his commands"""
        settings, identity = self.settings, self.settings.identity
        if not self.person(asker):
            why, value = self.limit('helps', asker, held=True)
            if why == 'off':
                return f'{self.title} answers no stranger now: {identity.key("GREET_PER_HOUR")} is 0.'
            if why == 'person':
                return f'You asked {hours_minutes(value)} ago: help comes once each {settings.greet_hours} h.'
            if why == 'hour':
                return f'Help was asked {value} times in the last hour, {settings.greet_per_hour} at most: ask later.'
        text = identity.greeting.format(owner=settings.owner) + '\n' + HELP_ASK.format(me=self.me())
        if asker == settings.owner:
            text += '\n' + HELP_OWNER.format(command=identity.command)
        return text

    def respond(self, event, text):
        """the answer to an interaction, which its asker alone sees, pinging no one: its token in no message"""
        number = event['id']
        body = {
            'type': MESSAGE_ANSWER,
            'data': {'content': text, 'flags': EPHEMERAL, 'allowed_mentions': {'parse': []}},
        }
        path, label = f'/interactions/{number}/{event["token"]}/callback', f'/interactions/{number}/<token>/callback'
        self.discord('POST', path, body, auth=False, label=label)

    def allowed_list(self, args, cancelled, progress):
        take(args, 'discord_allowed', (), ())
        found = sorted(self.allowed().values(), key=lambda item: (item['until'] is None, item['until'] or 0))
        allowed = [
            {
                'user_id': item['id'],
                'name': item['name'],
                'since': utc(item['since']),
                'until': None if item['until'] is None else utc(item['until']),
            }
            for item in found
        ]
        return {'allowed': allowed, 'listed': sorted(self.settings.users, key=int), 'now': utc(self.store.now())}

    def emoji_upload(self, args, cancelled, progress):
        take(args, 'discord_emoji_upload', ('guild', 'name'), ())
        guild = snowflake(args['guild'], 'guild')
        name = args['name']
        drawn = self.settings.identity.drawn
        if name not in drawn:
            raise Refused(
                f'name is {shown(name)}, not one {self.title} uploads: it takes {", ".join(drawn)}, each from '
                f'{self.drawings}/<name>.png'
            )
        there = self.emoji_id(guild, name, fresh=True)
        if there:
            status = 'already there'
        else:
            path = self.drawings / f'{name}.png'
            try:
                data = path.read_bytes()
            except OSError as error:
                raise Refused(
                    f'{path} cannot be read ({error.strerror or error}): {name} is uploaded from it'
                ) from None
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise Refused(f'{path} is not a PNG: {name} is uploaded from a PNG')
            if len(data) > MOST_EMOJI:
                raise Refused(f'{path} has {len(data)} bytes: an emoji takes {MOST_EMOJI} at most')
            image = 'data:image/png;base64,' + base64.b64encode(data).decode()
            try:
                there = self.discord('POST', f'/guilds/{guild}/emojis', {'name': name, 'image': image})['id']
            except DiscordError as error:
                if error.code != 50013:
                    raise
                raise DiscordError(
                    f'{error}: {self.title} needs Create Expressions ({CREATE_EXPRESSIONS}) in server {guild}; give '
                    'its role that permission (Server Settings, Roles), or invite it again with '
                    f'permissions={INVITE | CREATE_EXPRESSIONS}',
                    error.status,
                    error.code,
                ) from None
            self.known.setdefault('emojis', {}).setdefault(guild, {})[name] = there
            status = 'uploaded'
        log(f'discord_emoji_upload: {status}, {name} of {self.title} as emoji {there} in server {guild}')
        return {'status': status, 'guild': guild, 'name': name, 'id': there}

    def emoji_id(self, guild, name, fresh=False):
        """the id of a server's custom emoji of that name, None when it has none: a hit from what was asked before
        (fresh: asked now), a miss asked again, as an emoji may have been uploaded since"""
        known = self.known.setdefault('emojis', {})
        if fresh or name not in known.get(guild, {}):
            found = self.discord('GET', f'/guilds/{guild}/emojis')
            known[guild] = {item.get('name'): item['id'] for item in found if item.get('id')}
        return known[guild].get(name)

    def custom(self, emoji, guild, fresh=False):
        """a custom emoji of REACTIONS (:name:) as name:id, from the channel's server (guild: None in DMs), else from
        another server the bot is in; Refused naming the servers looked in when none has it"""
        name = emoji.strip(':')

        def servers():  # the list of the others asked only when the channel's server has none
            if guild:
                yield guild
            yield from (server['id'] for server in self.discord('GET', '/users/@me/guilds') if server['id'] != guild)

        looked = []
        for server in servers():
            looked.append(server)
            found = self.emoji_id(server, name, fresh)
            if found:
                return f'{name}:{found}'
        missing = f'no server {self.title} is in has an emoji named {name} (it looked in '
        missing += f'{by_id(looked) if looked else "none: it is in no server"})'
        same = self.settings.identity.same
        if emoji in same:
            missing += f': it is not uploaded yet (discord_emoji_upload uploads it); {same[emoji]} says the same'
        raise Refused(missing)

    def wait_for(self, args, cancelled, progress):
        take(args, 'discord_wait', ('channel', 'after'), ('wait', 'from'))
        channel = snowflake(args['channel'], 'channel')
        after = snowflake(args['after'], 'after')
        wait = whole(args.get('wait'), 'wait', 600, 0, MOST_WAIT)
        named = self.authors(args.get('from'))
        heard = (lambda author: author in named) if named is not None else self.person  # an allow may begin or end
        self.where(channel, reading=True)
        me = self.me()
        start, left_out = self.clock.now(), 0
        with self.hub.listening(channel) as inbox:
            while True:
                if self.hub.stopped:
                    raise DiscordError(
                        f'the gateway stopped ({self.hub.stopped}): discord_wait hears nothing; discord_read reads'
                    )
                items, gap = inbox.take()
                if gap:
                    items = items + self.since(channel, after)
                for message in sorted({m['id']: m for m in items}.values(), key=lambda m: int(m['id'])):
                    if int(message['id']) <= int(after):
                        continue
                    after = message['id']
                    if heard(message['author']['id']):
                        return {'channel': channel, 'message': view(message), 'left_out': left_out, 'after': after}
                    if message['author']['id'] != me:
                        left_out += 1
                waited = self.clock.now() - start
                if waited >= wait:
                    return {
                        'channel': channel,
                        'message': None,
                        'waited': round(waited),
                        'left_out': left_out,
                        'after': after,
                    }
                self.clock.wait(min(LOOK, wait - waited), inbox.ready)
                if cancelled.is_set():
                    raise Cancelled
                progress(self.clock.now() - start, wait, f'waiting for a message in channel {channel}')


class WebSocket:
    """a WebSocket client (RFC 6455) on a socket of its own: text frames out, masked; text frames in; pings
    answered; no extensions. wss://, or ws:// only to 127.0.0.1"""

    def __init__(self, url, timeout=30.0):
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ''
        if parts.scheme == 'wss':
            port, tls = parts.port or 443, True
        elif parts.scheme == 'ws' and host in ('127.0.0.1', 'localhost'):
            port, tls = parts.port or 80, False
        else:
            raise DiscordError(f'the gateway url {shown(url)} is not wss://')
        sock = socket.create_connection((host, port), timeout=timeout)
        try:
            if tls:
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            key = base64.b64encode(os.urandom(16)).decode()
            target = (parts.path or '/') + (f'?{parts.query}' if parts.query else '')
            sock.sendall(
                f'GET {target} HTTP/1.1\r\nHost: {parts.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nUser-Agent: {AGENT}\r\n\r\n'.encode()
            )
            head = bytearray()
            while b'\r\n\r\n' not in head:
                chunk = sock.recv(4096)
                if not chunk:
                    raise ConnectionError('the gateway closed the connection during the WebSocket handshake')
                head += chunk
                if len(head) > 65536:
                    raise ConnectionError('the gateway answered the WebSocket handshake with more than 64 KB of head')
            end = head.index(b'\r\n\r\n') + 4
            lines = head[:end].decode('latin-1').split('\r\n')
            status = lines[0].split(' ', 2)
            if len(status) < 2 or status[1] != '101':
                raise ConnectionError(f'the gateway answered {shown(lines[0])} to the WebSocket handshake, not 101')
            fields = {
                name.strip().lower(): value.strip() for name, _, value in (x.partition(':') for x in lines[1:] if x)
            }
            accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
            if fields.get('sec-websocket-accept') != accept:
                raise ConnectionError(
                    f'the gateway answered Sec-WebSocket-Accept {shown(fields.get("sec-websocket-accept"))}, '
                    f'not {accept}'
                )
        except BaseException:
            sock.close()
            raise
        self.sock, self.buffer, self.parts = sock, bytearray(head[end:]), None

    def frame(self, opcode, payload):
        """one frame, masked as a client's must be"""
        header = bytearray([0x80 | opcode])
        size = len(payload)
        if size < 126:
            header.append(0x80 | size)
        elif size < 1 << 16:
            header += bytes([0x80 | 126]) + size.to_bytes(2, 'big')
        else:
            header += bytes([0x80 | 127]) + size.to_bytes(8, 'big')
        mask = os.urandom(4)
        body = bytes(byte ^ mask[place % 4] for place, byte in enumerate(payload))
        self.sock.settimeout(30.0)
        self.sock.sendall(bytes(header) + mask + body)

    def send(self, text):
        self.frame(0x1, text.encode())

    def close(self, code):
        """says close with a code: 1000 ends the session; another lets it resume"""
        try:
            self.frame(0x8, code.to_bytes(2, 'big'))
        except OSError as error:
            log(f'gateway: the close frame {code} did not go out: {error}')

    def shut(self):
        self.sock.close()

    def parse(self):
        """the next whole frame in the buffer: (fin, opcode, payload), or None while it is not all there"""
        data = self.buffer
        if len(data) < 2:
            return None
        fin, opcode, size, at = bool(data[0] & 0x80), data[0] & 0x0F, data[1] & 0x7F, 2
        if data[1] & 0x80:
            raise ConnectionError('the gateway sent a masked frame, which a server never does')
        if size == 126:
            if len(data) < 4:
                return None
            size, at = int.from_bytes(data[2:4], 'big'), 4
        elif size == 127:
            if len(data) < 10:
                return None
            size, at = int.from_bytes(data[2:10], 'big'), 10
        if size > MOST_FRAME:
            raise ConnectionError(f'the gateway sent a frame of {size} bytes, more than the {MOST_FRAME} taken')
        if len(data) < at + size:
            return None
        payload = bytes(data[at : at + size])
        del data[: at + size]
        return fin, opcode, payload

    def receive(self, timeout):
        """('text', str), ('close', code, reason), or None when nothing whole came within timeout seconds"""
        deadline = time.monotonic() + timeout
        while True:
            frame = self.parse()
            if frame is None:
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self.sock.settimeout(left)
                try:
                    chunk = self.sock.recv(65536)
                except TimeoutError:
                    return None
                if not chunk:
                    raise ConnectionError('the gateway closed the connection with no close frame')
                self.buffer += chunk
                continue
            fin, opcode, payload = frame
            if opcode == 0x9:
                self.frame(0xA, payload)
            elif opcode == 0x8:
                code = int.from_bytes(payload[:2], 'big') if len(payload) >= 2 else 1005
                return 'close', code, payload[2:].decode('utf-8', 'replace')
            elif opcode in (0x1, 0x0):
                if opcode == 0x1:
                    self.parts = []
                elif self.parts is None:
                    raise ConnectionError('the gateway sent a continuation frame with no message begun')
                self.parts.append(payload)
                if fin:
                    text, self.parts = b''.join(self.parts).decode('utf-8'), None
                    return 'text', text
            elif opcode != 0xA:
                raise ConnectionError(f'the gateway sent a frame of opcode {opcode}, which JSON over text never uses')


class Gateway:
    """Discord's gateway, v10, JSON, no compression: hello, identify or resume, heartbeats and their ACKs, reconnects
    with backoff, as discord's identity; each event goes to hear(kind, data), and each change worth saying to
    report(kind, text)"""

    def __init__(self, token, discord, hear, report, stop, connect=WebSocket, rng=random.random, backoff=(1.0, 60.0)):
        self.token, self.discord, self.hear, self.report, self.stop = token, discord, hear, report, stop
        self.connect, self.rng, self.backoff = connect, rng, backoff
        self.identity = discord.identity
        self.session = None  # (session id, resume url), from READY
        self.seq = None
        self.ready = self.reported = False

    def identify(self):
        properties = {'os': sys.platform, 'browser': self.identity.server, 'device': self.identity.server}
        return {'op': 2, 'd': {'token': self.token, 'intents': INTENTS, 'properties': properties}}

    def run(self):
        delay, failures = self.backoff[0], 0
        while not self.stop.is_set():
            try:
                self.connection()
                return  # the bot stops
            except Stopped as error:
                log(f'gateway stopped: {error}')
                self.report('stopped', str(error))
                return
            except Drop as error:
                why = str(error)
            except (OSError, DiscordError, ValueError) as error:  # ValueError: a message that is not JSON or UTF-8
                why = f'{type(error).__name__}: {error}'
            except Exception as error:  # noqa: BLE001 - a gateway message it did not expect: connect again, said
                log(traceback.format_exc())
                why = f'{type(error).__name__}: {error}'
            if self.ready:
                delay, failures = self.backoff[0], 0
            else:
                failures += 1
            pause = delay * (0.5 + self.rng())
            log(f'gateway: {why}; again in {pause:.1f} s')
            if failures == 3 and not self.reported:
                self.reported = True
                self.report('trouble', f'{why}; it tries again, {self.backoff[1]:.0f} s apart at most')
            delay = min(delay * 2, self.backoff[1])
            if self.stop.wait(pause):
                return

    def connection(self):
        """one connection: returns when the bot stops; Drop when it ends, Stopped when Discord takes no new try"""
        self.ready = False
        resuming = self.session is not None and self.seq is not None
        if resuming:
            url = self.session[1]
        else:
            try:
                url = self.discord('GET', '/gateway/bot')['url']
            except DiscordError as error:
                if error.status == 401:
                    raise Stopped(
                        f"Discord answered 401 to GET /gateway/bot: {self.identity.key('TOKEN')} is not the bot's token"
                    ) from None
                raise
        ws = self.connect(url.rstrip('/') + '/?v=10&encoding=json')
        try:
            self.converse(ws, resuming)
        finally:
            ws.shut()

    def converse(self, ws, resuming):
        hello = ws.receive(HELLO_WAIT)
        if hello is None or hello[0] != 'text':
            raise Drop(
                f'the gateway said no hello in {HELLO_WAIT:.0f} s'
                if hello is None
                else f'the gateway closed with {hello[1]} before its hello'
            )
        hello = json.loads(hello[1])
        if hello.get('op') != 10:
            raise Drop(f'the gateway opened with op {shown(hello.get("op"))}, not 10 (hello)')
        interval = hello['d']['heartbeat_interval'] / 1000
        if resuming:
            ws.send(json.dumps({'op': 6, 'd': {'token': self.token, 'session_id': self.session[0], 'seq': self.seq}}))
        else:
            ws.send(json.dumps(self.identify()))
        beat_at, acked = time.monotonic() + interval * self.rng(), True
        while True:
            if self.stop.is_set():
                ws.close(1000)
                return
            got = ws.receive(max(0.0, min(beat_at - time.monotonic(), STOP_LOOK)))
            if got is not None:
                if got[0] == 'close':
                    self.closed(got[1], got[2])
                message = json.loads(got[1])
                op = message.get('op')
                if message.get('s') is not None:
                    self.seq = message['s']
                if op == 0:
                    self.dispatched(message.get('t'), message.get('d') or {})
                elif op == 1:
                    ws.send(json.dumps({'op': 1, 'd': self.seq}))
                elif op == 7:
                    ws.close(4000)
                    raise Drop('Discord asked to reconnect')
                elif op == 9:
                    if not message.get('d'):
                        self.session, self.seq = None, None
                    ws.close(4000)
                    raise Drop(
                        'Discord invalidated the session'
                        + ('; it resumes' if message.get('d') else '; it identifies again')
                    )
                elif op == 11:
                    acked = True
            if time.monotonic() >= beat_at:
                if not acked:
                    ws.close(4000)
                    raise Drop(f'no heartbeat ACK in {interval:.1f} s')
                ws.send(json.dumps({'op': 1, 'd': self.seq}))
                beat_at, acked = time.monotonic() + interval, False

    def closed(self, code, said):
        why = f'Discord closed the gateway with {code}' + (f' ({said})' if said else '')
        if code in GATEWAY_STOPS:
            raise Stopped(f'{why}: {GATEWAY_STOPS[code].format(token=self.identity.key("TOKEN"))}')
        if code in GATEWAY_FRESH:
            self.session, self.seq = None, None
        raise Drop(why)

    def dispatched(self, kind, data):
        if kind == 'READY':
            self.session = (data['session_id'], data['resume_gateway_url'])
        if kind in ('READY', 'RESUMED'):
            self.ready = True
            log(f'gateway: {kind.lower()}')
            if self.reported:
                self.reported = False
                self.report('back', f'{self.identity.title} hears Discord again')
        self.hear(kind, data)


def safe_name(name):
    """a file name as one item of the attachments list"""
    return re.sub(r'[;\r\n]', '_', name or '')


class Ear:
    """what the gateway hears, sorted: every message goes to the waits on its channel; the session gets, pushed as a
    channel event, each message addressed to the bot from the owner or a listed user, their DMs, a stranger's
    addressed message the owner let through with his WIMSY reaction, and only the name of a stranger who wrote in
    DMs; the owner's reply that mentions the bot carries the message he replied to, and lets it through. A stranger
    who calls the bot in a channel gets the identity's greeting, within its limits, and the session hears nothing of
    it. Someone the owner allowed with his command is heard as a listed user until the allow runs out. The command is
    registered in each server the bot joins, and each use of it answered; an allow or a deny is told to the session.
    Nothing for anyone else."""

    def __init__(self, tools, push, stop):
        self.tools, self.hub, self.push, self.stop = tools, tools.hub, push, stop
        self.title = tools.title
        self.queue = queue.Queue()
        self.kinds = {}  # a channel's id: its type and parent, from the gateway or asked once
        self.knocked = set()  # strangers whose DM was told
        self.told_uses = set()  # the uses of the command whose notice the session got from this server

    def feed(self, kind, data):
        """from the gateway's thread: never waits on Discord's REST there. A use of the command is answered in a
        thread of its own, ahead of what the queue holds, as Discord takes its answer for 3 s"""
        if kind == 'INTERACTION_CREATE':
            started(lambda: self.sort(kind, data))
        else:
            self.queue.put((kind, data))

    def run(self):
        while not self.stop.is_set():
            try:
                kind, data = self.queue.get(timeout=STOP_LOOK)
            except queue.Empty:
                continue
            self.sort(kind, data)

    def sort(self, kind, data):
        """one event heard; its failure said to stderr and the session, and the ear goes on"""
        try:
            self.hear(kind, data)
        except Exception as error:  # noqa: BLE001 - a Discord error or a bug: said, and the ear goes on
            log(f'channel: a {kind} event failed: {type(error).__name__}: {error}')
            if not isinstance(error, DiscordError):
                log(traceback.format_exc())
            self.push(f'{self.title} could not sort a {kind} event: {type(error).__name__}: {error}', {'kind': 'error'})

    def report(self, kind, text):
        """the gateway's news, to the session and the waits"""
        if kind == 'stopped':
            self.hub.stop(text)
            self.push(
                f'{self.title} stopped hearing Discord: {text}. discord_wait cannot hear; discord_read and '
                'discord_post work.',
                {'kind': 'error'},
            )
        elif kind == 'trouble':
            self.push(f"{self.title} cannot reach Discord's gateway: {text}", {'kind': 'error'})
        else:
            self.push(text, {'kind': 'notice'})

    def hear(self, kind, data):
        if kind == 'READY':
            self.tools.known['me'] = data['user']['id']
            if (data.get('application') or {}).get('id'):
                self.tools.known['application'] = data['application']['id']
            self.hub.gap()
        elif kind == 'GUILD_CREATE':
            self.tools.known.pop('roles', None)  # a server joined, or seen again: its role may be new
            self.tools.known.get('emojis', {}).pop(data.get('id'), None)  # and its emojis too
            for channel in (data.get('channels') or []) + (data.get('threads') or []):
                self.kinds[channel['id']] = (channel.get('type'), channel.get('parent_id'))
            if self.tools.settings.identity.command and not data.get('unavailable'):
                self.register(data['id'])
        elif kind == 'INTERACTION_CREATE':
            self.interaction(data)
        elif kind in ('CHANNEL_CREATE', 'CHANNEL_UPDATE', 'THREAD_CREATE', 'THREAD_UPDATE'):
            self.kinds[data['id']] = (data.get('type'), data.get('parent_id'))
        elif kind == 'MESSAGE_CREATE':
            self.hub.deliver(data)
            self.message(data)
        elif kind == 'MESSAGE_REACTION_ADD':
            self.reaction(data)

    def in_scope(self, channel):
        listed = self.tools.settings.channels
        if listed is None or channel in listed:
            return True
        if channel not in self.kinds:
            found = self.tools.discord('GET', f'/channels/{channel}')
            self.kinds[channel] = (found.get('type'), found.get('parent_id'))
        kind, parent = self.kinds[channel]
        return kind in THREADS and parent in listed

    def message(self, message):
        me, author = self.tools.me(), message['author']['id']
        if author == me:
            return
        settings = self.tools.settings
        if not message.get('guild_id'):
            if self.tools.person(author):
                self.tell(message, 'message')
            elif author not in self.knocked:
                self.knocked.add(author)
                name = message['author'].get('global_name') or message['author'].get('username') or ''
                text = f'{name} ({author}) wrote to {self.title} in DMs; nothing of what they wrote reaches the session'
                self.push(text, {'kind': 'dm', 'author': name, 'author_id': author})
                self.told('dm')
            return
        channel = message['channel_id']
        if author != settings.owner and author not in settings.users:
            # someone else: an addressed call alone is looked at, so the allows are read for it alone
            if not addressed(message, me, self.tools.roles()) or not self.in_scope(channel):
                return
            if author in self.tools.allowed():
                self.tell(message, 'message')
            elif settings.identity.greeting and self.calls(message):
                self.greet(message)
            return
        roles = self.tools.roles()
        if addressed(message, me, roles) and self.in_scope(channel):
            quoted, number = None, quoting(message, self.tools.settings.owner, me, roles)
            if number:
                self.tools.approved.add(number)
                if 'referenced_message' in message:
                    quoted = message['referenced_message']  # None: it was deleted
                else:
                    quoted = self.tools.discord('GET', f'/channels/{channel}/messages/{number}')
            self.tell(message, 'message', quoted)

    def calls(self, message):
        """whether a stranger's message addressed to the bot where it reads is a person's call it greets: not a
        bot's nor a webhook's, as two bots would greet each other"""
        return not message['author'].get('bot') and not message.get('webhook_id')

    def greet(self, message):
        """the greeting; its failure goes to the session as an error, and nothing else of the call does"""
        channel = message['channel_id']
        try:
            self.tools.greet(message)
        except (DiscordError, Refused, OSError) as error:
            text = str(error) + ('; the call counts toward the limits' if isinstance(error, DiscordError) else '')
            log(f'greet: failed in channel {channel}: {text}')
            self.push(
                f'{self.title} could not greet a stranger who called it in channel {channel}: {text}', {'kind': 'error'}
            )

    def register(self, guild):
        """the command in a server the bot is in; a failure said to the session, naming the fix"""
        try:
            self.tools.register(guild)
        except DiscordError as error:
            command = self.tools.settings.identity.command
            log(f'commands: /{command} not registered in server {guild}: {error}')
            self.push(f'{self.title} could not register /{command} in server {guild}: {error}', {'kind': 'error'})

    def interaction(self, event):
        """a use of the command, answered at once by the first server of the bot to hear it, the others leaving it
        be; each server tells its session of an allow or a deny, once"""
        settings, channel = self.tools.settings, event.get('channel_id')
        command, data = settings.identity.command, event.get('data') or {}
        if not command or event.get('type') != APPLICATION_COMMAND:
            log(f'commands: an interaction of type {shown(event.get("type"))} in channel {channel}: none is answered')
            return
        sub = subcommand(event)[0]
        if data.get('name') != command:
            got = {'sub': sub, 'text': f'/{data.get("name")} is not a command of {self.title}: it has /{command}.'}
            got['notice'] = None
        else:
            try:
                got = self.tools.command(event)
            except (Refused, OSError) as error:  # a state file it cannot read or write: the asker is answered still
                log(f'commands: /{command} {sub} failed in channel {channel}: {error}')
                self.push(
                    f'{self.title} could not answer /{command} {sub} in channel {channel}: {error}', {'kind': 'error'}
                )
                why = str(error) if invoker(event) == settings.owner else "its owner's session was told why"
                got = {'sub': sub, 'text': f'{self.title} could not answer this: {why}.', 'notice': None}
        if got['text'] is None:
            log(
                f'commands: /{command} {got["sub"]} in channel {channel} was answered by another server of {self.title}'
            )
        else:
            try:
                self.tools.respond(event, got['text'])
                log(f'commands: /{command} {got["sub"]} answered in channel {channel}')
            except DiscordError as error:
                log(f'commands: /{command} {got["sub"]} not answered in channel {channel}: {error}')
                self.push(
                    f'{self.title} could not answer /{command} {got["sub"]} in channel {channel}: {error}',
                    {'kind': 'error'},
                )
        notice = got['notice']
        if notice and event['id'] not in self.told_uses:
            self.told_uses.add(event['id'])
            self.push(notice['text'], notice['meta'])
            self.told('notice')

    def reaction(self, event):
        emoji = event.get('emoji') or {}
        if event.get('user_id') != self.tools.settings.owner:
            return
        if not event.get('guild_id'):
            if event['channel_id'] == self.tools.dm() and emoji.get('id') is None and emoji.get('name') in (YES, NO):
                self.drafted(event['message_id'])
            return
        if emoji.get('name') != WIMSY:
            return
        channel, number = event['channel_id'], event['message_id']
        if number in self.tools.approved:
            return
        message = self.tools.discord('GET', f'/channels/{channel}/messages/{number}')
        me, author = self.tools.me(), message['author']['id']
        if author == me or self.tools.person(author) or not addressed(message, me, self.tools.roles()):
            return
        if not self.in_scope(channel):
            return
        self.tools.approved.add(number)
        self.tell(dict(message, channel_id=channel), 'approved')

    def drafted(self, draft):
        """the owner's check mark or cross on a waiting draft: it is posted or refused now, not on a tool's next look,
        and the session is told"""
        got = self.tools.answered(draft)
        if got is None:
            return
        meta = {'kind': 'draft', 'draft': draft, 'status': got['status'], 'channel': got['channel']}
        if got['status'] == 'sent':
            meta['message_id'] = got['message']
            self.push(f'The owner approved draft {draft}: posted as {got["link"]}', meta)
        else:
            self.push(f'The owner refused draft {draft}: not posted to channel {got["channel"]}', meta)
        log(f'channel: draft {got["status"]}')

    def tell(self, message, kind, quoted=None):
        """a message pushed whole; with quoted, the message the owner replied to, whole too"""
        seen = view(message)
        meta = {
            'kind': kind,
            'author': seen['author'] or '',
            'author_id': seen['author_id'],
            'channel': message['channel_id'],
            'message_id': seen['id'],
        }
        if seen['reply_to']:
            meta['reply_to'] = seen['reply_to']
        if seen['attachments']:
            meta['attachments'] = '; '.join(safe_name(name) for name in seen['attachments'])
        text = seen['text'] or ('(no text: attachments only)' if seen['attachments'] else '(no text)')
        if quoted:
            them = view(quoted)
            meta.update(quoted_author=them['author'] or '', quoted_author_id=them['author_id'])
            if them['attachments']:
                meta['quoted_attachments'] = '; '.join(safe_name(name) for name in them['attachments'])
            said = them['text'] or ('(no text: attachments only)' if them['attachments'] else '(no text)')
            text += f'\n\nReplying to {them["author"]} ({them["author_id"]}), message {them["id"]}:\n{said}'
        self.push(text, meta)
        self.told(kind)

    def told(self, kind):
        """stderr's line for an event pushed, or not, as the client has a channel or not"""
        if self.tools.settings.identity.claude:
            log(f'channel: pushed a {kind} event')
        else:
            log(f'channel: a {kind} event, not pushed: {self.title} offers no channel')


ID = {'type': 'string', 'pattern': '^[0-9]{17,20}$'}
SECONDS = {'type': 'integer', 'minimum': 0, 'maximum': MOST_WAIT}
FROM = {
    'type': 'array',
    'items': ID,
    'minItems': 1,
    'description': 'only these authors: ids of the owner or of listed users',
}
MESSAGE = (
    '{"id", "author" (their name), "author_id", "time" (ISO 8601), "text", "reply_to" (the id it answers, or null), '
    '"attachments" (file names: discord_attachments saves them), "approved" (true for a stranger\'s message the owner '
    'let through)}'
)
TOOL_NAMES = (
    'discord_post',
    'discord_post_status',
    'discord_read',
    'discord_wait',
    'discord_attachments',
    'discord_react',
    'discord_unreact',
    'discord_quick',
    'discord_emoji_upload',
    'discord_allowed',
)


def reacting_schema(identity, emoji):
    """discord_react's and discord_unreact's arguments"""
    return {
        'type': 'object',
        'properties': {
            'channel': dict(ID, description='the channel, thread or DM id the message is in'),
            'message': dict(ID, description='the message id'),
            'emoji': {'type': 'string', 'enum': list(identity.reactions), 'description': emoji},
        },
        'required': ['channel', 'message', 'emoji'],
        'additionalProperties': False,
    }


def where_text(identity):
    """the channels a tool's description says it works in"""
    return (
        f'Channels: those {identity.key("CHANNELS")} lists and their threads, or every one Discord lets the bot see '
        f"when it lists none, and the owner's DMs with {identity.title} (the channel in each draft's link)."
    )


def tool_list(identity):
    """the tools as tools/list gives them, in the identity's names: discord_allowed for a bot with a command alone"""
    me, channels, where = identity.title, identity.key('CHANNELS'), where_text(identity)
    allowed = {
        'name': 'discord_allowed',
        'description': (
            f'Who the owner allowed with /{identity.command} allow: their messages addressed to {me} reach you as a '
            "listed user's do, until the allow runs out or he takes it back with /"
            f'{identity.command} deny; then they are a stranger\'s again. Returns JSON {{"allowed": [{{"user_id", '
            '"name" (as the server showed them when allowed), "since", "until" (ISO 8601 in UTC; null: for good)}], '
            '"listed" (the ids the env file lists), "now"}, the allows that run out first first.'
        ),
        'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
    }
    upload = {
        'name': 'discord_emoji_upload',
        'description': (
            f'Upload to a server one of the custom emojis {me} answers with, from its fixed file: name is one of '
            f'{", ".join(identity.drawn)}, the file {EMOJI_FOLDER}/<name>.png, uploaded as <name>. No other name or '
            'file. One the server has by that name already is not uploaded again. It needs the Create Expressions '
            f"permission there: without it, the error says so and the invite's permissions with it. Returns JSON "
            '{"status": "uploaded", or "already there" when it was, "guild", "name", "id"}.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'guild': dict(ID, description='the server id to upload to'),
                'name': {'type': 'string', 'enum': list(identity.drawn), 'description': 'the emoji, and its file'},
            },
            'required': ['guild', 'name'],
            'additionalProperties': False,
        },
    }
    seen, done = seen_and_done(identity)
    if identity.drawn:
        first = ' The custom one first: its unicode one only while the server has not got it (that error names it).'
        taken = f"{reactions_text(identity)}; and :{WIMSY}:, the owner's emoji.{first[:-1]}"
        custom, own = (
            " A custom one is the server's emoji of its name.",
            f" {me}'s own :{WIMSY}: lets nothing through: only the owner's does.",
        )
    else:
        first = custom = own = ''
        taken = reactions_text(identity)
    tools = [
        {
            'name': 'discord_post',
            'description': (
                f"Post a message on Discord once the owner approves it. The draft goes to the owner's DMs with {me} "
                f"(the text and its images, and under it where it goes) with {YES} and {NO}: only the owner's {YES} "
                "posts it, as it is, pinging no one; another person's reaction counts for nothing. It posts in the "
                f'channels {channels} lists and their threads, or in any Discord lets the bot see when it lists none. '
                'Waits up to `wait` seconds for the answer, then returns JSON: {"status": "sent", "link", "message", '
                '"channel", "draft"} when approved; {"status": "not sent", "channel", "draft"} when refused; {"status": '
                '"waiting", "draft", "link", "waited"} when not answered yet: call discord_post_status with that draft '
                'to wait on. An error names the value refused and what is taken.'
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'channel': dict(ID, description='the channel or thread id to post in'),
                    'text': {
                        'type': 'string',
                        'minLength': 1,
                        'maxLength': LIMIT,
                        'description': f"what to post, 1 to {LIMIT} letters of Discord's Markdown",
                    },
                    'reply_to': dict(ID, description="the id of that channel's message it answers"),
                    'wait': dict(SECONDS, default=300, description="seconds to wait for the owner's answer"),
                    'files': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'minItems': 1,
                        'maxItems': MOST_FILES,
                        'description': (
                            f'absolute paths of 1 to {MOST_FILES} images ({", ".join(k[1:] for k in IMAGES)}) posted '
                            "under the text: the draft carries them, and the post sends the draft's"
                        ),
                    },
                },
                'required': ['channel', 'text'],
                'additionalProperties': False,
            },
        },
        {
            'name': 'discord_post_status',
            'description': (
                f"Wait on a draft discord_post returned still waiting: up to `wait` seconds (0: one look) for the owner's "
                f'{YES} or {NO}. Returns the JSON discord_post does. A draft already sent or refused answers that again: '
                'no draft is posted twice.'
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'draft': dict(ID, description='the draft id discord_post returned'),
                    'wait': dict(SECONDS, default=300, description="seconds to wait for the owner's answer"),
                },
                'required': ['draft'],
                'additionalProperties': False,
            },
        },
        {
            'name': 'discord_read',
            'description': (
                "Read a channel's messages: the first `limit` after the id `after`, or the newest `limit` without it, "
                'oldest first. Returns JSON {"channel", "messages": [' + MESSAGE + '], "left_out", "after"}. Only the '
                f"owner's messages, the listed users' and {me}'s own are given, or only those of the authors `from` "
                f"names; and, without `from`, a stranger's message the owner let through: addressed to {me} with "
                f'his :{WIMSY}: reaction on it, or one he replied to mentioning {me}. left_out counts the others, '
                'and nothing else of them is given. "after" is the newest id read, to read on from. ' + where
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'channel': dict(ID, description='the channel, thread or DM id to read'),
                    'after': dict(ID, description='read the messages after this message id'),
                    'limit': {
                        'type': 'integer',
                        'minimum': 1,
                        'maximum': PAGE,
                        'default': 50,
                        'description': 'how many messages to read',
                    },
                    'from': FROM,
                },
                'required': ['channel'],
                'additionalProperties': False,
            },
        },
        {
            'name': 'discord_wait',
            'description': (
                'Wait up to `wait` seconds for the first message after the id `after` from the owner or a listed user '
                '(or from the authors `from` names), as Discord\'s gateway brings it. Returns JSON {"channel", '
                '"message": ' + MESSAGE + ', "left_out", "after"}, or {"channel", "message": null, "waited", '
                f'"left_out", "after"}} when none came: wait again after that "after". {me}\'s own messages are '
                "passed over; left_out counts the other people's, and nothing else of them is given. " + where
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'channel': dict(ID, description='the channel, thread or DM id to watch'),
                    'after': dict(ID, description='wait for a message after this message id'),
                    'wait': dict(SECONDS, default=600, description='seconds to wait'),
                    'from': FROM,
                },
                'required': ['channel', 'after'],
                'additionalProperties': False,
            },
        },
        {
            'name': 'discord_attachments',
            'description': (
                "Save a message's attachments, each a file of the message's own folder, to open with the Read tool (an "
                f"image, a log): a message discord_read gives (the owner's, a listed user's, {me}'s own, or a "
                "stranger's the owner let through), fetched from Discord's CDN without the token. Returns JSON "
                '{"channel", "message", "folder", "files": [{"name" (as Discord has it), "type", "size", "width" and '
                '"height" (images), and "path" when saved or "error" saying why not}]}. One over '
                f'{MOST_SAVE >> 20} MiB is not saved, and says so. A file saved before is not fetched again. ' + where
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'channel': dict(ID, description='the channel, thread or DM id the message is in'),
                    'message': dict(ID, description='the message id'),
                },
                'required': ['channel', 'message'],
                'additionalProperties': False,
            },
        },
        {
            'name': 'discord_react',
            'description': (
                f"Put a reaction of {me}'s on a message, at once: no draft and no owner's {YES}, so it takes only "
                f'these: {taken}. Use one instead of a post to say you saw a message or finished it: {seen} when you '
                f'start on it, then discord_unreact it and {done} when done.{custom} The message is one discord_read '
                f"gives (the owner's, a listed user's, {me}'s own, or a stranger's the owner let through), never a "
                f'draft.{own} Returns JSON {{"status": "reacted", or "already there" when it was, "channel", '
                '"message", "emoji"}. Another emoji is an error naming it and these. ' + where
            ),
            'inputSchema': reacting_schema(identity, 'the emoji to put'),
        },
        {
            'name': 'discord_unreact',
            'description': (
                f"Take a reaction of {me}'s off a message: one discord_react put. Another person's reaction stays. "
                'Returns JSON {"status": "removed", or "not there" when it was not, "channel", "message", "emoji"}. '
                + where
            ),
            'inputSchema': reacting_schema(identity, 'the emoji to take off'),
        },
        {
            'name': 'discord_quick',
            'description': (
                f"Answer a message with one emoji alone, a quick reply, posted at once: no draft and no owner's "
                f'{YES}, so it takes no text and only these: {reactions_text(identity)}.{first} A text goes through '
                'discord_post. '
                f'It replies to reply_to, a message discord_read gives (never a draft), pinging no one, in the '
                f'channels {channels} lists and their threads, or in any Discord lets the bot see when it lists none. '
                'Returns JSON {"status": "posted", "link", "message", "channel", "reply_to", "emoji"}. Another emoji, '
                'or a text, is an error naming it and these.'
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'channel': dict(ID, description='the channel or thread id to post in'),
                    'reply_to': dict(ID, description="the id of that channel's message it answers"),
                    'emoji': {
                        'type': 'string',
                        'enum': list(identity.quick),
                        'description': 'the one emoji to post',
                    },
                },
                'required': ['channel', 'reply_to', 'emoji'],
                'additionalProperties': False,
            },
        },
    ]
    return tools + ([upload] if identity.drawn else []) + ([allowed] if identity.command else [])


def failure(rid, code, message, data=None):
    """a JSON-RPC error answer; with no id when the request's could not be read"""
    error = {'code': code, 'message': message}
    if data is not None:
        error['data'] = data
    answer = {'jsonrpc': '2.0', 'error': error}
    if rid is not None:
        answer['id'] = rid
    return answer


def tool_result(value, error=False):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return {'content': [{'type': 'text', 'text': text}], 'isError': error}


def valid_id(rid):
    return isinstance(rid, str) or (isinstance(rid, int) and not isinstance(rid, bool))


def log(text):
    print(f'{NAME}: {text}', file=sys.stderr, flush=True)


def refusal(identity, client):
    """why a Wimsy does not serve the client its initialize names (clientInfo's name), or None when it does: Claude
    Code's Wimsy serves it alone, the other any client but it, so neither bot's token reaches the other's session"""
    if (client == CLAUDE_CODE) == identity.claude:
        return None
    other = next(each for each in IDENTITIES if each.claude != identity.claude)
    if identity.claude:
        return (
            f'clientInfo.name is {shown(client)}, not "{CLAUDE_CODE}": {identity.title} is {identity.who}\'s, for '
            f'Claude Code alone; another client runs {other.title} ({other.server}) and keeps {identity.server} off '
            f'(Grok Build: grok mcp disable {identity.server})'
        )
    return (
        f'clientInfo.name is "{CLAUDE_CODE}": {identity.title} is {identity.who}\'s, for any client but Claude Code, '
        f'which runs {other.title} ({other.server}); take {identity.server} out of its MCP servers'
    )


class LineWriter:
    """JSON-RPC messages on a stream, a whole line each: one lock for the answers, the progress and the channel
    pushes, so no two threads write into one line"""

    def __init__(self, stream):
        self.stream, self.guard = stream, threading.Lock()

    def __call__(self, message):
        line = json.dumps(message, separators=(',', ':')).encode() + b'\n'
        with self.guard:
            try:
                self.stream.write(line)
                self.stream.flush()
            except OSError as error:
                log(f'stdout is closed: {error}')


class Server:
    """MCP's JSON-RPC after the initialize handshake, 2025-11-25 back to 2024-11-05, for the client the tools'
    identity serves; once the client says it is initialized, listen(push) starts hearing Discord and returns its
    threads"""

    def __init__(self, tools, instructions, write, listen=None, stopping=None):
        self.tools, self.instructions, self.write, self.listen = tools, instructions, write, listen
        self.identity = tools.settings.identity
        self.title, self.listed = self.identity.title, tool_list(self.identity)
        self.names = tuple(tool['name'] for tool in self.listed)  # the tools of its identity
        self.stopping = stopping or threading.Event()
        self.agreed = None  # the version an initialize agreed on
        self.running = {}  # a tools/call's id: the event that cancels it
        self.threads = []  # the ones listen started
        self.guard = threading.Lock()
        self.news, self.dropped = [], 0  # with no channel: the pushes NEWS names, until a tool result carries them

    def begin(self, rid):
        with self.guard:
            return self.running.setdefault(rid, threading.Event())

    def end(self, rid):
        with self.guard:
            self.running.pop(rid, None)

    def stop(self):
        """every running request cancelled and the listening ended: the client closed stdin"""
        self.stopping.set()
        with self.guard:
            for event in self.running.values():
                event.set()

    def work(self, message, cancelled):
        """a tools/call in a thread of its own: its answer written unless it was cancelled"""
        try:
            answer = self.handle(message, cancelled)
            if answer is not None and not cancelled.is_set():
                self.write(answer)
        finally:
            self.end(message['id'])

    def push(self, content, meta):
        """a channel event into the session; with no channel, the gateway's news and a draft's answer wait for the
        next tool result, and the messages for discord_wait and discord_read"""
        if self.identity.claude:
            self.write({'jsonrpc': '2.0', 'method': CHANNEL_PUSH, 'params': {'content': content, 'meta': meta}})
        elif meta.get('kind') in NEWS:
            with self.guard:
                self.news.append(content)
                if len(self.news) > MOST_NEWS:
                    del self.news[0]
                    self.dropped += 1

    def with_news(self, result):
        """a tool's result, the news it waited for after its own text"""
        with self.guard:
            news, dropped, self.news, self.dropped = self.news, self.dropped, [], 0
        if dropped:
            news.insert(0, f'{dropped} older news were left out: {self.title} keeps the newest {MOST_NEWS}')
        for text in news:
            result['content'].append({'type': 'text', 'text': f'{self.title} news: {text}'})
        return result

    def notified(self, method, params):
        if method == 'notifications/cancelled':
            event = self.running.get(params.get('requestId'))
            if event:
                event.set()
        elif method == 'notifications/initialized':
            if self.agreed and self.listen and not self.threads and not self.stopping.is_set():
                self.threads = self.listen(self.push)
        else:
            log(f'notification {shown(method)} does nothing here')

    def handle(self, message, cancelled=None):
        """the answer to one message, or None for a notification and a cancelled request"""
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            return failure(None, -32600, 'Invalid Request: a JSON-RPC 2.0 message is an object with "jsonrpc": "2.0"')
        method, rid = message.get('method'), message.get('id')
        rid_ok = rid if valid_id(rid) else None
        if method is None:
            if 'result' in message or 'error' in message:
                log(f'an answer came for request {shown(rid)}: {self.title} sends no requests')
                return None
            return failure(rid_ok, -32600, 'Invalid Request: no method')
        if not isinstance(method, str):
            return failure(rid_ok, -32600, f'Invalid Request: method is {shown(method)}, not a string')
        params = message.get('params')
        params = {} if params is None else params
        if 'id' not in message:
            if isinstance(params, dict):
                self.notified(method, params)
            return None
        if rid_ok is None:
            return failure(None, -32600, f'Invalid Request: id is {shown(rid)}, not a string or a whole number')
        if not isinstance(params, dict):
            return failure(rid, -32602, f'Invalid params: params is a JSON {kind_of(params)}, not an object')
        if method == 'server/discover':
            why = ', as Claude Code registers no channel on 2026-07-28' if self.identity.claude else ''
            return failure(
                rid,
                -32601,
                f'Method not found: server/discover; {self.title} speaks the initialize handshake '
                f'({", ".join(VERSIONS)}){why}',
            )
        if method not in METHODS:
            return failure(rid, -32601, f'Method not found: {shown(method)}; {self.title} answers {", ".join(METHODS)}')
        if method == 'initialize':
            return self.initialize(rid, params)
        if self.agreed is None and method != 'ping':
            return failure(
                rid,
                -32602,
                f'Invalid params: {method} came before initialize; {self.title} speaks {", ".join(VERSIONS)}',
            )
        if method == 'ping':
            result = {}
        elif method == 'tools/list':
            if params.get('cursor') is not None:
                return failure(rid, -32602, f'Invalid params: cursor {shown(params["cursor"])}: the tools are one page')
            result = {'tools': self.listed}
        else:
            meta = params.get('_meta') if isinstance(params.get('_meta'), dict) else {}
            result = self.call(rid, params, meta, cancelled or threading.Event())
            if result is None or 'error' in result:
                return result
            result = self.with_news(result)
        return {'jsonrpc': '2.0', 'id': rid, 'result': result}

    def initialize(self, rid, params):
        asked = params.get('protocolVersion')
        if not isinstance(asked, str):
            return failure(rid, -32602, f'Invalid params: protocolVersion is {shown(asked)}, not a version string')
        client = params.get('clientInfo')
        refused = refusal(self.identity, client.get('name') if isinstance(client, dict) else None)
        if refused:
            log(f'initialize refused: {refused}')
            return failure(rid, -32602, f'Invalid params: {refused}')
        self.agreed = asked if asked in VERSIONS else VERSIONS[0]
        capabilities = {'tools': {}, 'experimental': {'claude/channel': {}}} if self.identity.claude else {'tools': {}}
        result = {
            'protocolVersion': self.agreed,
            'capabilities': capabilities,
            'serverInfo': {'name': self.identity.server, 'title': self.title, 'version': VERSION},
            'instructions': self.instructions,
        }
        return {'jsonrpc': '2.0', 'id': rid, 'result': result}

    def call(self, rid, params, meta, cancelled):
        """a tools/call's result: a protocol error for an unknown tool, a tool error for what the tool refused"""
        name, args = params.get('name'), params.get('arguments')
        args = {} if args is None else args
        if not isinstance(name, str) or not isinstance(args, dict):
            return failure(rid, -32602, 'Invalid params: tools/call takes a name (a string) and arguments (an object)')
        if name not in self.names:
            return failure(rid, -32602, f'Unknown tool: {shown(name)}; {self.title} has {", ".join(self.names)}')
        token = meta.get('progressToken')
        progress = self.progress(token, cancelled) if valid_id(token) else (lambda *_: None)
        try:
            value = self.tools.call(name, args, cancelled, progress)
        except Cancelled:
            log(f'{name}: cancelled')
            return None
        except (Refused, DiscordError) as error:
            log(f'{name} failed: {error}')
            return tool_result(str(error), error=True)
        except Exception as error:  # noqa: BLE001 - a bug: the session sees it, stderr has where
            log(f'{name} failed: {type(error).__name__}: {error}\n{traceback.format_exc()}')
            return tool_result(f'{type(error).__name__}: {error}', error=True)
        log(f'{name}: {value.get("status", "done")}')
        return tool_result(value)

    def progress(self, token, cancelled):
        """notifications/progress for a request that asked for them, the seconds waited always growing"""
        last = [-1.0]

        def send(done, total, text):
            done = round(done, 1)
            if cancelled.is_set() or done <= last[0]:
                return
            last[0] = done
            params = {'progressToken': token, 'progress': done, 'total': total, 'message': text}
            self.write({'jsonrpc': '2.0', 'method': 'notifications/progress', 'params': params})

        return send


def serve(server, reader, write, linger=40.0):
    """reads messages a line until stdin closes; each tools/call runs in a thread of its own"""
    workers = []
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError as error:  # UnicodeDecodeError is one
            write(failure(None, -32700, f'Parse error: {error}'))
            continue
        if isinstance(message, list):
            write(failure(None, -32600, 'Invalid Request: a batch; MCP takes one message a line'))
            continue
        if isinstance(message, dict) and message.get('method') == 'tools/call' and valid_id(message.get('id')):
            worker = threading.Thread(target=server.work, args=(message, server.begin(message['id'])), daemon=True)
            worker.start()
            workers = [w for w in workers if w.is_alive()] + [worker]
            continue
        answer = server.handle(message)
        if answer is not None:
            write(answer)
    server.stop()
    end = time.monotonic() + linger  # a post under way ends; a wait and the gateway end at once
    for thread in workers + server.threads:
        thread.join(max(0.0, end - time.monotonic()))


def started(target):
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def main(argv=None, identity=AOGO):
    """the server of identity: AogoWimsy run as aogowimsy.py, XujiWimsy as xuji/xujiwimsy.py"""
    global NAME
    NAME = identity.server
    parser = argparse.ArgumentParser(
        prog=f'{identity.server}.py',
        description=f'{identity.title}: an MCP server (stdio) for Discord, every post approved first',
    )
    env = identity.env
    parser.add_argument('--env', default=env, help=f'the env file of its settings (default: {env}, mode 600)')
    options = parser.parse_args(argv)
    path = os.path.expanduser(options.env)
    try:
        settings = read_settings(path, identity)
    except Refused as error:
        sys.exit(f'{identity.server}: {error}')
    clock, stop = Clock(), threading.Event()
    discord = Discord(settings.token, clock, identity=identity)
    tools = Wimsy(settings, discord, clock)
    write = LineWriter(sys.stdout.buffer)

    def listen(push):
        ear = Ear(tools, push, stop)
        gateway = Gateway(settings.token, discord, ear.feed, ear.report, stop)
        return [started(ear.run), started(gateway.run)]

    where = 'every channel it sees' if settings.channels is None else f'{len(settings.channels)} channels'
    greets = ''
    if identity.greeting and settings.greet_per_hour == 0:
        greets = f', greeting no stranger ({identity.key("GREET_PER_HOUR")} is 0)'
    elif identity.greeting:
        greets = f', greeting a stranger once each {settings.greet_hours} h, {settings.greet_per_hour} an hour at most'
    log(f'up: owner {settings.owner}, {len(settings.users)} users, {where}{greets}')
    said = instructions(settings)
    server = Server(tools, said, write, listen, stop)
    cut = cut_by_grok(settings, said)
    if cut:
        log(cut)
        server.push(cut, {'kind': 'error'})  # with the first tool result too
    serve(server, sys.stdin.buffer, write)


if __name__ == '__main__':
    main()
