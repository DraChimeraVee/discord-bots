#!/usr/bin/env python3
"""aogowimsy.py without Discord or the network: its env file, MCP over stdio in a real subprocess, its tools against a
fake Discord REST served on 127.0.0.1 with a clock that only moves when a tool waits, what the gateway hears and
pushes to the session, and the gateway client itself against a fake WebSocket gateway on 127.0.0.1"""

import base64
import email.parser
import email.policy
import fcntl
import hashlib
import http.server
import json
import os
import queue
import re
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aogowimsy as aw

os.environ['no_proxy'] = os.environ['NO_PROXY'] = '127.0.0.1'  # the fakes, never through a proxy
# the greetings' state folder of every Wimsy made here, the programs started too: never the user's ~/.local/state
STATE_HOME = tempfile.TemporaryDirectory(prefix='aogowimsy-tests-')
os.environ['XDG_STATE_HOME'] = STATE_HOME.name

TOKEN = 'MTAwMDAw.fake-token_for.tests'
PNG = b'\x89PNG\r\n\x1a\n a fake image'
BOT, OWNER, FRIEND, STRANGER, OTHER_PERSON = (f'10000000000000000{n:02d}' for n in (1, 2, 3, 4, 5))
GUILD, OTHER_GUILD = '200000000000000001', '200000000000000002'
BOT_ROLE, OTHER_BOT_ROLE, HELPERS_ROLE = (f'70000000000000000{n:02d}' for n in (1, 2, 3))
GENERAL, HELP, OTHER, THREAD, OTHER_THREAD, NEW_THREAD = (f'3000000000000000{n:02d}' for n in (1, 2, 3, 11, 12, 13))
DM, FRIEND_DM, STRANGER_DM = '400000000000000001', '400000000000000002', '400000000000000003'
WIMSY = f'{aw.WIMSY}:600000000000000001'  # the owner's custom emoji, as a reaction's path names it
OTHER_EMOJI = 'wimsyother:600000000000000002'
YES, NO, EYES, THUMBS = aw.YES, aw.NO, aw.EYES, aw.THUMBS
OWNERS = f':{aw.WIMSY}:'  # the owner's custom emoji, as discord_react takes it
DRAWN_IDS = {name: f'6000000000000001{n:02d}' for n, name in enumerate(aw.DRAWN)}  # once uploaded to the server
CUSTOM = ':wimsyaogo_eyes:, :wimsyaogo_done:, :wimsyaogo_thumbsup:, :wimsyaogo_no:'
PNG_EMOJI = b'\x89PNG\r\n\x1a\n an emoji'
OTHER_BOT = '1000000000000000006'  # another bot on the server: a stranger, and a bot
APP = '900000000000000001'  # AogoWimsy's application, whose id is not its user's here
CALLERS = [f'10000000000000001{n:02d}' for n in range(12)]  # strangers the fake knows by id alone
# the greeting as DraVee worded it (2026-11-02), and the one mention it lets ping
LINE = (
    "I'm Aogo, DraVee's AI assistant (Claude) working on ScarletNX: code, reviews, tests. I act on what DraVee lets "
    f'through. <@{OWNER}>'
)
PINGS = {'parse': [], 'users': [OWNER], 'replied_user': False}
READY = {'user': {'id': BOT}, 'application': {'id': APP}, 'session_id': 's', 'resume_gateway_url': 'ws://127.0.0.1:9'}
INITIALIZE = {
    'protocolVersion': '2025-11-25',
    'capabilities': {},
    'clientInfo': {'name': 'claude-code', 'version': '1'},
}


class FakeDiscord:
    """Discord's REST routes AogoWimsy uses, over an in-memory guild: answers as Discord does, newest first"""

    ROUTES = (
        ('GET', r'/users/@me', 'me'),
        ('GET', r'/users/@me/guilds', 'guilds'),
        ('GET', r'/guilds/(\d+)/roles', 'guild_roles'),
        ('GET', r'/guilds/(\d+)/emojis', 'guild_emojis'),
        ('POST', r'/guilds/(\d+)/emojis', 'create_emoji'),
        ('POST', r'/users/@me/channels', 'open_dm'),
        ('GET', r'/gateway/bot', 'gateway'),
        ('GET', r'/channels/(\d+)', 'channel'),
        ('GET', r'/channels/(\d+)/messages', 'history'),
        ('POST', r'/channels/(\d+)/messages', 'create'),
        ('GET', r'/channels/(\d+)/messages/(\d+)', 'message'),
        ('PATCH', r'/channels/(\d+)/messages/(\d+)', 'edit'),
        ('PUT', r'/channels/(\d+)/messages/(\d+)/reactions/([^/]+)/@me', 'react_me'),
        ('DELETE', r'/channels/(\d+)/messages/(\d+)/reactions/([^/]+)/@me', 'unreact_me'),
        ('GET', r'/channels/(\d+)/messages/(\d+)/reactions/([^/]+)', 'reactors'),
        ('GET', r'/applications/@me', 'application'),
        ('GET', r'/applications/(\d+)/guilds/(\d+)/commands', 'guild_commands'),
        ('PUT', r'/applications/(\d+)/guilds/(\d+)/commands', 'overwrite_commands'),
        ('POST', r'/interactions/(\d+)/([^/]+)/callback', 'interaction_answer'),
    )

    def __init__(self):
        self.users = {
            BOT: {'id': BOT, 'username': 'aogowimsy', 'global_name': 'AogoWimsy', 'bot': True},
            OWNER: {'id': OWNER, 'username': 'dravee', 'global_name': 'DraVee'},
            FRIEND: {'id': FRIEND, 'username': 'friend', 'global_name': None},
            STRANGER: {'id': STRANGER, 'username': 'stranger', 'global_name': 'Stranger'},
            OTHER_PERSON: {'id': OTHER_PERSON, 'username': 'other', 'global_name': 'Other'},
            OTHER_BOT: {'id': OTHER_BOT, 'username': 'reiwimsy', 'global_name': 'ReiWimsy', 'bot': True},
        }
        guild = {'type': 0, 'guild_id': GUILD}
        self.channels = {
            GENERAL: dict(guild, id=GENERAL, name='general'),
            HELP: dict(guild, id=HELP, name='help'),
            OTHER: dict(guild, id=OTHER, name='other'),
            THREAD: dict(guild, id=THREAD, name='a-thread', type=11, parent_id=GENERAL),
            OTHER_THREAD: dict(guild, id=OTHER_THREAD, name='elsewhere', type=11, parent_id=OTHER),
            NEW_THREAD: dict(guild, id=NEW_THREAD, name='new-thread', type=11, parent_id=HELP),
            DM: {'id': DM, 'type': 1, 'recipients': [self.users[OWNER]]},
            FRIEND_DM: {'id': FRIEND_DM, 'type': 1, 'recipients': [self.users[FRIEND]]},
            STRANGER_DM: {'id': STRANGER_DM, 'type': 1, 'recipients': [self.users[STRANGER]]},
        }
        # the guild's roles: the one Discord made for AogoWimsy and another bot's, tagged with their bot, and a plain one
        self.server_roles = [
            {'id': GUILD, 'name': '@everyone', 'managed': False},
            {'id': BOT_ROLE, 'name': 'Aogo', 'managed': True, 'tags': {'bot_id': BOT}},
            {'id': OTHER_BOT_ROLE, 'name': 'ReiWimsy', 'managed': True, 'tags': {'bot_id': OTHER_PERSON}},
            {'id': HELPERS_ROLE, 'name': 'helpers', 'managed': False},
        ]
        self.guild_ids = [GUILD]  # the servers the bot is in
        self.server_emojis = {  # each server's custom emojis
            GUILD: [
                {'id': WIMSY.split(':')[1], 'name': aw.WIMSY},
                {'id': OTHER_EMOJI.split(':')[1], 'name': 'wimsyother'},
            ]
        }
        self.messages = {channel: [] for channel in self.channels}  # oldest first
        self.reactions = {}  # a message id: {emoji: [user ids]}
        self.requests = []  # (method, path, query, body)
        self.limits = []  # (method, path) answered 429 once each
        self.fail = {}  # (method, path): (status, body), answered until removed
        self.gateway_url = 'ws://127.0.0.1:9/'
        self.origin = 'http://127.0.0.1:9'  # the fake's own address, where its attachments are served
        self.blobs = {}  # an attachment's path: its bytes, as the CDN serves them
        self.serial = 1_500_000_000_000_000_000
        self.commands = {}  # a server's commands of the application, as Discord gives them back
        self.no_commands_scope = set()  # servers whose install lacks applications.commands
        self.answers = {}  # an interaction's id: the answer it got, once
        self.lock = threading.Lock()

    def say(self, channel, author, content='', mentions=(), reply_to=None, **extra):
        """a message from author; its id"""
        self.serial += 1
        message = {'id': str(self.serial), 'channel_id': channel, 'author': author, 'content': content, 'type': 0}
        message.update(timestamp=f'2026-10-21T12:{len(self.messages[channel]) % 60:02d}:00.000000+00:00')
        message.update(attachments=[], embeds=[], mentions=list(mentions))
        if reply_to:
            message.update(type=19, message_reference={'message_id': reply_to, 'channel_id': channel})
        message.update(extra)
        self.messages[channel].append(message)
        return message['id']

    def find(self, channel, message):
        return next((m for m in self.messages.get(channel, []) if m['id'] == message), None)

    def react(self, message, emoji, user):
        self.reactions.setdefault(message, {}).setdefault(emoji, []).append(user)

    def last(self, channel):
        return self.messages[channel][-1]

    def footer(self, message):
        return message['embeds'][0]['footer']['text']

    def posts(self, method, path):
        return [r for r in self.requests if r[0] == method and r[1] == path]

    def user(self, who):
        return self.users.get(who, {'id': who, 'username': 'webhook'})

    def render(self, message, deep=True):
        shown = {k: v for k, v in message.items() if k not in ('author', 'mentions')}
        shown['author'] = self.user(message['author'])
        shown['mentions'] = [self.user(who) for who in message.get('mentions', [])]
        reference = message.get('message_reference')
        if deep and reference and message.get('type') == 19:
            answered = self.find(message['channel_id'], reference['message_id'])
            shown['referenced_message'] = self.render(answered, deep=False) if answered else None
        reactions = self.reactions.get(message['id'], {})
        if reactions:
            shown['reactions'] = []
            for emoji, who in reactions.items():
                name, _, number = emoji.partition(':')
                shown['reactions'].append(
                    {'count': len(who), 'me': BOT in who, 'emoji': {'id': number or None, 'name': name}}
                )
        return shown

    def event(self, channel, message):
        """a message as the gateway's MESSAGE_CREATE carries it"""
        shown = self.render(self.find(channel, message))
        if self.channels[channel].get('guild_id'):
            shown['guild_id'] = self.channels[channel]['guild_id']
        return shown

    def handle(self, method, path, query, body, headers):
        with self.lock:
            return self.route(method, path, query, body, headers)

    def route(self, method, path, query, body, headers):
        path = path.removeprefix('/api/v10')
        answering = path.startswith('/interactions/')  # an interaction's answer: its token is in the path
        if headers.get('Authorization') != (None if answering else f'Bot {TOKEN}'):
            return 401, {'message': '401: Unauthorized', 'code': 0}, {}
        if not (headers.get('User-Agent') or '').startswith('DiscordBot ('):
            return 400, {'message': 'no DiscordBot User-Agent', 'code': 0}, {}
        self.requests.append((method, path, query, body))
        if (method, path) in self.limits:
            self.limits.remove((method, path))
            return 429, {'message': 'You are being rate limited.', 'retry_after': 1.5, 'global': False}, {}
        if (method, path) in self.fail:
            status, said = self.fail[(method, path)]
            return status, said, {}
        for verb, pattern, name in self.ROUTES:
            found = re.fullmatch(pattern, path)
            if verb == method and found:
                return getattr(self, name)(query, body, *found.groups())
        return 404, {'message': '404: Not Found', 'code': 0}, {}

    def me(self, query, body):
        return 200, self.users[BOT], {}

    def guilds(self, query, body):
        return 200, [{'id': guild, 'name': f'server {guild}'} for guild in self.guild_ids], {}

    def guild_roles(self, query, body, guild):
        if guild not in self.guild_ids:
            return 404, {'message': 'Unknown Guild', 'code': 10004}, {}
        return 200, self.server_roles if guild == GUILD else [], {}

    def guild_emojis(self, query, body, guild):
        if guild not in self.guild_ids:
            return 404, {'message': 'Unknown Guild', 'code': 10004}, {}
        return 200, self.server_emojis.get(guild, []), {}

    def create_emoji(self, query, body, guild):
        if guild not in self.guild_ids:
            return 404, {'message': 'Unknown Guild', 'code': 10004}, {}
        if set(body) != {'name', 'image'} or not body['image'].startswith('data:image/png;base64,'):
            return 400, {'code': 50035, 'message': 'Invalid Form Body', 'errors': {}}, {}
        made = {'id': DRAWN_IDS.get(body['name'], '600000000000000999'), 'name': body['name'], 'available': True}
        self.server_emojis.setdefault(guild, []).append(made)
        return 201, made, {}

    def upload(self, *names, guild=GUILD):
        """the server's emojis of these names, as if the owner uploaded them"""
        for name in names:
            self.server_emojis.setdefault(guild, []).append({'id': DRAWN_IDS[name], 'name': name})

    def open_dm(self, query, body):
        if body != {'recipient_id': OWNER}:
            return 400, {'message': f'fake: DMs only with the owner, not {body}', 'code': 0}, {}
        return 200, self.channels[DM], {}

    def gateway(self, query, body):
        return 200, {'url': self.gateway_url, 'shards': 1}, {}

    def channel(self, query, body, channel):
        if channel not in self.channels:
            return 404, {'message': 'Unknown Channel', 'code': 10003}, {}
        return 200, self.channels[channel], {}

    def history(self, query, body, channel):
        if channel not in self.channels:
            return 404, {'message': 'Unknown Channel', 'code': 10003}, {}
        limit, kept = int(query.get('limit', 50)), self.messages[channel]
        if 'after' in query:
            chosen = [m for m in kept if int(m['id']) > int(query['after'])][:limit]
        else:
            chosen = kept[-limit:]
        return 200, [self.render(m) for m in reversed(chosen)], {}

    def create(self, query, body, channel):
        files = body.pop('_files', [])
        listed = body.get('attachments')
        if files and [item.get('id') for item in listed or []] != list(range(len(files))):
            return 400, {'code': 50035, 'message': 'Invalid Form Body', 'errors': {'attachments': {}}}, {}
        content = body.get('content', '')
        if len(content) > 2000:
            message = 'Must be 2000 or fewer in length.'
            errors = {'content': {'_errors': [{'code': 'BASE_TYPE_MAX_LENGTH', 'message': message}]}}
            return 400, {'code': 50035, 'errors': errors, 'message': 'Invalid Form Body'}, {}
        reference = body.get('message_reference')
        if reference and not self.find(channel, reference['message_id']):
            return 400, {'code': 50035, 'message': 'Invalid Form Body', 'errors': {}}, {}
        number = self.say(
            channel, BOT, content, reply_to=reference and reference['message_id'], embeds=body.get('embeds', [])
        )
        kept = []
        for place, (name, data, kind) in enumerate(files):
            path = f'/attachments/{channel}/{number}{place}/{urllib.parse.quote(name)}'
            self.blobs[path] = (data, kind)
            kept.append({'id': f'{number}{place}', 'filename': name, 'size': len(data), 'url': self.origin + path})
            kept[-1]['content_type'] = kind
        self.find(channel, number)['attachments'] = kept
        if reference:
            self.find(channel, number)['message_reference'] = reference
        return 200, self.render(self.find(channel, number)), {}

    def message(self, query, body, channel, message):
        found = self.find(channel, message)
        if not found:
            return 404, {'message': 'Unknown Message', 'code': 10008}, {}
        return 200, self.render(found), {}

    def edit(self, query, body, channel, message):
        found = self.find(channel, message)
        if not found or found['author'] != BOT:
            return 403, {'message': 'Cannot edit a message authored by another user', 'code': 50005}, {}
        found.update(body)
        return 200, self.render(found), {}

    def react_me(self, query, body, channel, message, emoji):
        if not self.find(channel, message):
            return 404, {'message': 'Unknown Message', 'code': 10008}, {}
        name, _, number = emoji.partition(':')
        known = [item for items in self.server_emojis.values() for item in items]
        if number and not any(item['id'] == number and item['name'] == name for item in known):
            return 400, {'message': 'Unknown Emoji', 'code': 10014}, {}
        if BOT not in self.reactions.get(message, {}).get(emoji, []):
            self.react(message, emoji, BOT)
        return 204, None, {}

    def unreact_me(self, query, body, channel, message, emoji):
        if not self.find(channel, message):
            return 404, {'message': 'Unknown Message', 'code': 10008}, {}
        kept = self.reactions.get(message, {})
        if BOT in kept.get(emoji, []):
            kept[emoji].remove(BOT)
            if not kept[emoji]:
                del kept[emoji]
        return 204, None, {}

    def reactors(self, query, body, channel, message, emoji):
        return 200, [self.users[u] for u in self.reactions.get(message, {}).get(emoji, [])], {}

    def application(self, query, body):
        return 200, {'id': APP, 'name': 'Aogo', 'bot': self.users[BOT]}, {}

    def guild_commands(self, query, body, app, guild):
        if app != APP or guild not in self.guild_ids:
            return 404, {'message': 'Unknown Guild', 'code': 10004}, {}
        if guild in self.no_commands_scope:
            return 403, {'message': 'Missing Access', 'code': 50001}, {}
        return 200, self.commands.get(guild, []), {}

    def overwrite_commands(self, query, body, app, guild):
        status, said, extra = self.guild_commands(query, body, app, guild)
        if status != 200:
            return status, said, extra

        def as_kept(item):  # as Discord gives an option back: required only when true, no empty lists
            kept = {k: v for k, v in item.items() if not (k == 'required' and not v)}
            if item.get('options'):
                kept['options'] = [as_kept(each) for each in item['options']]
            return kept

        kept = []
        for place, command in enumerate(body):
            stored = dict(as_kept(command), id=f'80000000000000{place:04d}', application_id=APP, guild_id=guild)
            stored.update(version='1', nsfw=False, name_localizations=None, description_localizations=None)
            kept.append(stored)
        self.commands[guild] = kept
        return 200, kept, {}

    def interaction_answer(self, query, body, number, token):
        if token != f'token-{number}':
            return 401, {'message': 'Invalid interaction token', 'code': 50027}, {}
        if number in self.answers:
            return 400, {'message': 'Interaction has already been acknowledged.', 'code': 40060}, {}
        self.answers[number] = body
        return 204, None, {}


def form_body(kind, raw):
    """Discord's multipart form: payload_json's JSON, with its files[n] as _files [(name, bytes, type)]"""
    message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
        f'Content-Type: {kind}\r\n\r\n'.encode() + raw
    )
    body, files = None, []
    for part in message.iter_parts():
        name = part.get_param('name', header='content-disposition')
        if name == 'payload_json':
            body = json.loads(part.get_content())
        else:
            assert name == f'files[{len(files)}]', name
            files.append((part.get_filename(), part.get_payload(decode=True), part.get_content_type()))
    return dict(body, _files=files)


class Handler(http.server.BaseHTTPRequestHandler):
    def answer(self):
        parts = urllib.parse.urlsplit(self.path)
        if parts.path in self.server.fake.blobs:  # the CDN: no token
            data, kind = self.server.fake.blobs[parts.path]
            self.server.fake.requests.append(('CDN', parts.path, {}, self.headers.get('Authorization')))
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        query = dict(urllib.parse.parse_qsl(parts.query))
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b''
        kind = self.headers.get('Content-Type') or ''
        body = form_body(kind, raw) if kind.startswith('multipart/form-data') else json.loads(raw) if raw else None
        status, said, extra = self.server.fake.handle(
            self.command, urllib.parse.unquote(parts.path), query, body, self.headers
        )
        data = b'' if said is None else json.dumps(said).encode()
        self.send_response(status)
        for key, value in extra.items():
            self.send_header(key, value)
        if data:
            self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = answer

    def log_message(self, *args):
        pass


class FakeClock:
    """time that moves only when a tool waits; hooks run once their time comes"""

    def __init__(self):
        self.time, self.waits, self.hooks = 0.0, [], []

    def now(self):
        return self.time

    def at(self, when, hook):
        self.hooks.append((when, hook))

    def wait(self, seconds, event=None):
        self.waits.append(seconds)
        self.time += seconds
        for due in [h for h in self.hooks if h[0] <= self.time]:
            self.hooks.remove(due)
            due[1]()
        return bool(event and event.is_set())


def write_env(folder, text, mode=0o600, name='aogowimsy.env'):
    path = Path(folder) / name
    path.write_text(text)
    path.chmod(mode)
    return str(path)


GOOD_ENV = f"""# AogoWimsy
AOGOWIMSY_TOKEN={TOKEN}
AOGOWIMSY_OWNER={OWNER}

AOGOWIMSY_USERS = {FRIEND}
AOGOWIMSY_CHANNELS={GENERAL}, {HELP}
"""


class EnvFile(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def env(self, text, mode=0o600):
        return write_env(self.folder.name, text, mode)

    def refused(self, text, mode=0o600):
        with self.assertRaises(aw.Refused) as caught:
            aw.read_settings(self.env(text, mode))
        self.assertNotIn(TOKEN, str(caught.exception))
        return str(caught.exception)

    def test_a_good_file_with_comments_blanks_and_spaces(self):
        settings = aw.read_settings(self.env(GOOD_ENV))
        self.assertEqual(settings, aw.Settings(TOKEN, OWNER, frozenset({FRIEND}), frozenset({GENERAL, HELP})))

    def test_without_channels_it_works_where_discord_lets_it_and_says_so(self):
        settings = aw.read_settings(self.env(GOOD_ENV.replace(f'AOGOWIMSY_CHANNELS={GENERAL}, {HELP}\n', '')))
        self.assertIsNone(settings.channels)
        self.assertIn(
            'every channel and thread Discord lets it see (AOGOWIMSY_CHANNELS lists none)', aw.instructions(settings)
        )
        listed = aw.instructions(settings._replace(channels=frozenset({GENERAL})))
        self.assertIn(f'channels {GENERAL} and their threads', listed)
        said = self.refused(GOOD_ENV.replace(f'{GENERAL}, {HELP}', ''))
        self.assertIn('AOGOWIMSY_CHANNELS is empty: list id,id, or take the line out', said)

    def test_mode_600_and_stricter_are_taken(self):
        for mode in (0o600, 0o400):
            self.assertEqual(aw.read_settings(self.env(GOOD_ENV, mode)).owner, OWNER)

    def test_a_mode_others_can_read_is_refused_naming_it(self):
        self.assertIn('has mode 644', self.refused(GOOD_ENV, 0o644))
        self.assertIn('has mode 640', self.refused(GOOD_ENV, 0o640))
        self.assertIn('has mode 700', self.refused(GOOD_ENV, 0o700))

    def test_an_unknown_key_stops_it_naming_the_key(self):
        said = self.refused(GOOD_ENV + 'AOGOWIMSY_CHANNEL=1\n')
        self.assertIn('line 7: AOGOWIMSY_CHANNEL is not a key AogoWimsy knows', said)
        self.assertIn('AOGOWIMSY_CHANNELS', said)

    def test_an_id_that_is_not_one_is_named(self):
        said = self.refused(GOOD_ENV.replace(f'= {FRIEND}', f'= {FRIEND},abc'))
        self.assertIn('AOGOWIMSY_USERS item 2 is "abc", not a Discord id (17 to 20 digits)', said)
        said = self.refused(GOOD_ENV.replace(f'_OWNER={OWNER}', '_OWNER=12345'))
        self.assertIn('AOGOWIMSY_OWNER is "12345", not a Discord id', said)
        said = self.refused(GOOD_ENV.replace(f'{GENERAL}, {HELP}', f'{GENERAL},,{HELP}'))
        self.assertIn('AOGOWIMSY_CHANNELS has an empty item, number 2 of 3', said)

    def test_an_empty_or_missing_needed_value_is_named(self):
        self.assertIn('AOGOWIMSY_TOKEN is empty', self.refused(GOOD_ENV.replace(TOKEN, '')))
        self.assertIn('AOGOWIMSY_USERS is missing', self.refused(GOOD_ENV.replace(f'AOGOWIMSY_USERS = {FRIEND}', '')))

    def test_a_key_twice_a_line_with_no_equals_and_a_bad_token_letter_never_show_the_token(self):
        said = self.refused(GOOD_ENV + f'AOGOWIMSY_OWNER={OWNER}\n')
        self.assertIn('line 7: AOGOWIMSY_OWNER again, set on line 3', said)
        self.assertIn('line 7 has no "="', self.refused(GOOD_ENV + TOKEN + '\n'))
        said = self.refused(GOOD_ENV.replace(TOKEN, f'"{TOKEN}"'))
        self.assertIn("AOGOWIMSY_TOKEN has '\"' at letter 1", said)

    def test_the_example_lists_the_keys_it_knows_and_stops_at_the_first_empty_one(self):
        example = self.env((HERE / 'aogowimsy.env.example').read_text())
        with self.assertRaisesRegex(aw.Refused, 'AOGOWIMSY_TOKEN is empty, and AogoWimsy needs it'):
            aw.read_settings(example)

    def test_the_greetings_limits_are_read_checked_and_named(self):
        settings = aw.read_settings(self.env(GOOD_ENV))
        self.assertEqual((settings.greet_hours, settings.greet_per_hour), (aw.GREET_HOURS, aw.GREET_PER_HOUR))
        self.assertEqual((aw.GREET_HOURS, aw.GREET_PER_HOUR), (24, 10))
        settings = aw.read_settings(self.env(GOOD_ENV + 'AOGOWIMSY_GREET_HOURS=48\nAOGOWIMSY_GREET_PER_HOUR = 0\n'))
        self.assertEqual((settings.greet_hours, settings.greet_per_hour), (48, 0))
        hours, per_hour = 'not a whole number from 1 to 720', 'not a whole number from 0 to 100'
        for line, said in (
            ('AOGOWIMSY_GREET_HOURS=abc', f'AOGOWIMSY_GREET_HOURS is "abc", {hours}'),
            ('AOGOWIMSY_GREET_HOURS=0', f'AOGOWIMSY_GREET_HOURS is "0", {hours}'),
            ('AOGOWIMSY_GREET_HOURS=721', f'AOGOWIMSY_GREET_HOURS is "721", {hours}'),
            ('AOGOWIMSY_GREET_HOURS=', f'AOGOWIMSY_GREET_HOURS is "", {hours}'),
            ('AOGOWIMSY_GREET_PER_HOUR=101', f'AOGOWIMSY_GREET_PER_HOUR is "101", {per_hour}'),
            ('AOGOWIMSY_GREET_PER_HOUR=-1', f'AOGOWIMSY_GREET_PER_HOUR is "-1", {per_hour}'),
            ('AOGOWIMSY_GREET_PER_HOUR=1e1', f'AOGOWIMSY_GREET_PER_HOUR is "1e1", {per_hour}'),
        ):
            self.assertIn(said, self.refused(GOOD_ENV + line + '\n'))
        example = (HERE / 'aogowimsy.env.example').read_text()  # it says the defaults the code has
        self.assertIn(f'\n# AOGOWIMSY_GREET_HOURS={aw.GREET_HOURS}\n', example)
        self.assertIn(f'\n# AOGOWIMSY_GREET_PER_HOUR={aw.GREET_PER_HOUR}\n', example)

    def test_a_missing_file_says_so(self):
        with self.assertRaisesRegex(aw.Refused, 'nowhere.env cannot be read'):
            aw.read_settings(str(Path(self.folder.name) / 'nowhere.env'))


class WithDiscord(unittest.TestCase):
    """the tools through the server's tools/call, against the fake Discord over HTTP on 127.0.0.1"""

    @classmethod
    def setUpClass(cls):
        cls.http = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def setUp(self):
        state = tempfile.TemporaryDirectory()  # each test's greetings, and the restarts it makes
        self.addCleanup(state.cleanup)
        self.addCleanup(os.environ.__setitem__, 'XDG_STATE_HOME', os.environ['XDG_STATE_HOME'])
        os.environ['XDG_STATE_HOME'] = state.name
        self.state = Path(state.name) / 'aogowimsy'
        self.fake = self.http.fake = FakeDiscord()
        self.fake.origin = f'http://127.0.0.1:{self.http.server_port}'
        self.clock = FakeClock()
        self.settings = aw.Settings(TOKEN, OWNER, frozenset({FRIEND}), frozenset({GENERAL, HELP}))
        self.api = f'http://127.0.0.1:{self.http.server_port}/api/v10'
        self.bot = aw.Wimsy(self.settings, aw.Discord(TOKEN, self.clock, self.api), self.clock)
        self.sent = []
        self.server = self.started_server(self.bot)
        self.logs = []
        self.addCleanup(setattr, aw, 'log', aw.log)
        aw.log = self.logs.append

    def started_server(self, bot, **extra):
        server = aw.Server(bot, 'test', self.sent.append, **extra)
        server.handle({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': INITIALIZE})
        return server

    def answer(self, name, meta=None, cancelled=None, **args):
        params = {'name': name, 'arguments': args}
        if meta:
            params['_meta'] = meta
        return self.server.handle({'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call', 'params': params}, cancelled)

    def tool(self, name, **args):
        """the tool's JSON when it worked; fails the test with its error when not"""
        result = self.answer(name, **args)['result']
        self.assertFalse(result['isError'], result['content'][0]['text'])
        return json.loads(result['content'][0]['text'])

    def error(self, name, **args):
        """the tool's error text; fails the test when it worked"""
        result = self.answer(name, **args)['result']
        self.assertTrue(result['isError'], result['content'][0]['text'])
        return result['content'][0]['text']

    def owner_answers(self, when, emoji, who=OWNER):
        self.clock.at(when, lambda: self.fake.react(self.fake.last(DM)['id'], emoji, who))

    def arrive(self, channel, author, content='', **extra):
        """a message Discord keeps and the gateway brings to the waits"""
        number = self.fake.say(channel, author, content, **extra)
        self.bot.hub.deliver(self.fake.event(channel, number))
        return number


class Post(WithDiscord):
    def test_approved_posts_the_text_as_it_is_pinging_no_one_and_says_so_on_the_draft(self):
        text = 'Built: <@1000000000000000004> @everyone **done**\nsecond line'
        self.owner_answers(6, YES)
        got = self.tool('discord_post', channel=GENERAL, text=text)
        posted = self.fake.last(GENERAL)
        self.assertEqual(got['status'], 'sent')
        self.assertEqual((got['message'], got['channel']), (posted['id'], GENERAL))
        self.assertEqual(got['link'], f'https://discord.com/channels/{GUILD}/{GENERAL}/{posted["id"]}')
        self.assertEqual(posted['content'], text)
        body = self.fake.posts('POST', f'/channels/{GENERAL}/messages')[0][3]
        self.assertEqual(body['allowed_mentions'], {'parse': [], 'replied_user': False})
        self.assertNotIn('message_reference', body)
        draft = self.fake.last(DM)
        self.assertEqual(got['draft'], draft['id'])
        self.assertEqual(draft['content'], text)
        self.assertEqual(self.fake.reactions[draft['id']][YES][0], BOT)
        self.assertEqual(self.fake.reactions[draft['id']][NO], [BOT])
        self.assertEqual(self.fake.footer(draft), f'sent: {GUILD}/{GENERAL}/{posted["id"]}')
        self.assertIn(got['link'], draft['embeds'][0]['description'])
        self.assertEqual(self.clock.waits, [3.0, 3.0])
        self.assertEqual(self.logs, ['discord_post: sent'])

    def test_the_draft_says_where_it_goes_and_the_message_it_answers_as_a_link(self):
        asked = self.fake.say(GENERAL, FRIEND, 'does it build?')
        self.owner_answers(3, YES)
        got = self.tool('discord_post', channel=GENERAL, text='it does', reply_to=asked)
        card = self.fake.posts('POST', f'/channels/{DM}/messages')[0][3]['embeds'][0]
        self.assertIn(f'Channel: #general ({GENERAL})', card['description'])
        self.assertIn(f'Replying to: https://discord.com/channels/{GUILD}/{GENERAL}/{asked}', card['description'])
        self.assertEqual(card['footer']['text'], f'waiting: to {GENERAL} replying to {asked}')
        self.assertEqual(self.fake.posts('POST', f'/channels/{DM}/messages')[0][3]['allowed_mentions'], {'parse': []})
        body = self.fake.posts('POST', f'/channels/{GENERAL}/messages')[0][3]
        reference = {'message_id': asked, 'channel_id': GENERAL, 'fail_if_not_exists': True}
        self.assertEqual(body['message_reference'], reference)
        self.assertEqual(got['status'], 'sent')

    def test_refused_posts_nothing_and_says_so_on_the_draft(self):
        self.owner_answers(3, NO)
        got = self.tool('discord_post', channel=GENERAL, text='hello')
        self.assertEqual(got, {'status': 'not sent', 'channel': GENERAL, 'draft': self.fake.last(DM)['id']})
        self.assertEqual(self.fake.messages[GENERAL], [])
        self.assertEqual(self.fake.footer(self.fake.last(DM)), f'not sent: to {GENERAL}')

    def test_both_answers_post_nothing(self):
        self.owner_answers(3, YES)
        self.owner_answers(3, NO)
        self.assertEqual(self.tool('discord_post', channel=GENERAL, text='hello')['status'], 'not sent')
        self.assertEqual(self.fake.messages[GENERAL], [])

    def test_timed_out_then_approved_through_post_status_and_never_posted_twice(self):
        got = self.tool('discord_post', channel=GENERAL, text='hello', wait=7)
        draft = self.fake.last(DM)['id']
        link = f'https://discord.com/channels/@me/{DM}/{draft}'
        self.assertEqual(got, {'status': 'waiting', 'draft': draft, 'link': link, 'waited': 7})
        self.assertEqual(self.clock.waits, [3.0, 3.0, 1.0])
        self.assertEqual(self.fake.messages[GENERAL], [])
        self.assertEqual(self.tool('discord_post_status', draft=draft, wait=0)['status'], 'waiting')
        self.fake.react(draft, YES, OWNER)
        sent = self.tool('discord_post_status', draft=draft)
        self.assertEqual((sent['status'], sent['draft']), ('sent', draft))
        again = self.tool('discord_post_status', draft=draft)
        self.assertEqual(again, sent)
        self.assertEqual(len(self.fake.messages[GENERAL]), 1)

    def image(self, name, data=PNG):
        folder = tempfile.TemporaryDirectory(prefix='aogowimsy-')
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / name
        path.write_bytes(data)
        return str(path)

    def test_images_go_with_the_draft_and_with_the_post(self):
        shots = [self.image('menu before-after.png'), self.image('b.JPG', b'\xff\xd8\xff jpeg')]
        self.owner_answers(3, YES)
        got = self.tool('discord_post', channel=GENERAL, text='the menu', files=shots)
        draft, posted = self.fake.last(DM), self.fake.last(GENERAL)
        self.assertEqual(got['status'], 'sent')
        for message in (draft, posted):
            names = [(a['filename'], a['content_type']) for a in message['attachments']]
            self.assertEqual(names, [('menu before-after.png', 'image/png'), ('b.JPG', 'image/jpeg')])
        self.assertEqual(self.fake.blobs[urllib.parse.urlsplit(posted['attachments'][0]['url']).path][0], PNG)
        self.assertEqual(posted['content'], 'the menu')
        # the post's images come from the draft, fetched from the CDN without the token
        fetched = [r for r in self.fake.requests if r[0] == 'CDN']
        self.assertEqual(
            [(r[1].rsplit('/', 1)[1], r[3]) for r in fetched], [('menu%20before-after.png', None), ('b.JPG', None)]
        )

    def test_a_restart_keeps_the_drafts_images(self):
        draft = self.tool('discord_post', channel=GENERAL, text='later', files=[self.image('a.webp', b'RIFF webp')])
        fresh = aw.Wimsy(self.settings, aw.Discord(TOKEN, self.clock, self.api), self.clock)
        self.server = self.started_server(fresh)
        self.fake.react(draft['draft'], YES, OWNER)
        self.assertEqual(self.tool('discord_post_status', draft=draft['draft'])['status'], 'sent')
        self.assertEqual([a['filename'] for a in self.fake.last(GENERAL)['attachments']], ['a.webp'])

    def test_files_are_checked_before_discord_hears_of_them(self):
        png = self.image('a.png')
        cases = (
            ('a.png', 'files is a JSON string, not a list of 1 to 4 absolute paths of images'),
            ([], 'files is empty: 1 to 4 absolute paths of images (png, jpg, jpeg, gif, webp)'),
            ([png] * 5, 'files names 5 files: a post carries 1 to 4 images'),
            (['a.png'], 'files item 1 is "a.png", not an absolute path'),
            ([png + '.gone.png'], f'files item 1 is {png}.gone.png, which cannot be read: '),
            ([self.image('log.txt')], 'files item 1 is a .txt: AogoWimsy posts images (png, jpg, jpeg, gif, webp)'),
            ([self.image('empty.png', b'')], 'files item 1, '),
        )
        for files, said in cases:
            with self.subTest(files=files):
                self.assertIn(said, self.error('discord_post', channel=GENERAL, text='x', files=files))
        self.assertIn(
            'is empty', self.error('discord_post', channel=GENERAL, text='x', files=[self.image('e.gif', b'')])
        )
        self.assertEqual(self.fake.messages[DM], [])

    def test_a_download_from_anywhere_but_discord_is_refused(self):
        discord = aw.Discord(TOKEN, self.clock, self.api)
        for url in ('https://example.com/a.png', 'http://cdn.discordapp.com/a.png', 'file:///etc/passwd'):
            with self.subTest(url=url), self.assertRaises(aw.DiscordError) as caught:
                discord.download(url)
            self.assertIn(url, str(caught.exception))

    def test_a_restart_loses_no_draft_the_draft_is_the_state(self):
        draft = self.tool('discord_post', channel=GENERAL, text='after a restart', wait=0)['draft']
        fresh = aw.Wimsy(self.settings, aw.Discord(TOKEN, self.clock, self.api), self.clock)
        self.server = self.started_server(fresh)
        self.fake.react(draft, YES, OWNER)
        self.assertEqual(self.tool('discord_post_status', draft=draft)['status'], 'sent')
        self.assertEqual(self.fake.last(GENERAL)['content'], 'after a restart')

    def test_a_strangers_check_mark_and_its_own_count_for_nothing(self):
        self.owner_answers(3, YES, who=STRANGER)
        got = self.tool('discord_post', channel=GENERAL, text='hello', wait=9)
        self.assertEqual(got['status'], 'waiting')
        self.assertEqual(self.fake.messages[GENERAL], [])
        self.assertTrue(self.fake.posts('GET', f'/channels/{DM}/messages/{got["draft"]}/reactions/{YES}'))

    def test_a_channel_not_listed_is_refused_naming_it_and_the_list(self):
        said = self.error('discord_post', channel=OTHER, text='hello')
        lists = f'channel {OTHER} is not one AogoWimsy may post in: AOGOWIMSY_CHANNELS lists {GENERAL}, {HELP}'
        self.assertIn(lists, said)
        said = self.error('discord_post', channel=OTHER_THREAD, text='hello')
        self.assertIn(f'channel {OTHER_THREAD} is not one AogoWimsy may post in', said)
        said = self.error('discord_post', channel='3000000000000000099', text='hello')
        self.assertIn('Discord answered 404 to GET /channels/3000000000000000099: Unknown Channel (code 10003)', said)
        self.assertEqual(self.fake.messages[DM], [])

    def test_with_no_channels_listed_any_channel_discord_shows_it_and_its_404_names_the_rest(self):
        self.bot.settings = self.settings._replace(channels=None)
        self.owner_answers(3, YES)
        self.assertEqual(self.tool('discord_post', channel=OTHER, text='elsewhere')['status'], 'sent')
        self.assertEqual(self.fake.last(OTHER)['content'], 'elsewhere')
        said = self.error('discord_post', channel='3000000000000000099', text='hello')
        self.assertEqual(
            said, 'Discord answered 404 to GET /channels/3000000000000000099: Unknown Channel (code 10003)'
        )

    def test_a_thread_of_a_listed_channel_is_one(self):
        self.owner_answers(3, YES)
        got = self.tool('discord_post', channel=THREAD, text='in the thread')
        self.assertEqual((got['status'], self.fake.last(THREAD)['content']), ('sent', 'in the thread'))
        card = self.fake.posts('POST', f'/channels/{DM}/messages')[0][3]['embeds'][0]
        self.assertIn(f'#a-thread ({THREAD})', card['description'])

    def test_a_text_over_2000_letters_is_refused_naming_its_length(self):
        said = self.error('discord_post', channel=GENERAL, text='x' * 2001)
        self.assertIn('text has 2001 letters: a Discord message holds 2000 at most', said)
        self.assertEqual(self.fake.messages[DM], [])
        self.assertEqual(self.tool('discord_post', channel=GENERAL, text='x' * 2000, wait=0)['status'], 'waiting')
        self.assertIn('text is empty', self.error('discord_post', channel=GENERAL, text=' \n'))

    def test_arguments_are_checked_before_discord_hears_of_them(self):
        said = self.error('discord_post', channel=int(GENERAL), text='hi')
        self.assertIn('channel is 300000000000000001, not a Discord id: write it as a string', said)
        said = self.error('discord_post', channel=GENERAL, text='hi', wait=3601)
        self.assertIn('wait is 3601, not a whole number from 0 to 3600', said)
        said = self.error('discord_post', channel=GENERAL, text='hi', wait=True)
        self.assertIn('wait is true, not a whole number', said)
        said = self.error('discord_post', channel=GENERAL, text='hi', mention=True)
        self.assertIn('discord_post has no argument "mention"; it takes channel, text, reply_to, wait', said)
        self.assertIn('discord_post needs text', self.error('discord_post', channel=GENERAL))
        self.assertIn('text is a JSON array, not a string', self.error('discord_post', channel=GENERAL, text=['hi']))
        self.assertEqual(self.fake.requests, [])

    def test_post_status_takes_only_its_own_drafts(self):
        mine = self.fake.say(DM, OWNER, 'a message of the owner')
        said = self.error('discord_post_status', draft=mine)
        self.assertIn(f"message {mine} in the owner's DMs ({DM}) is not a draft of AogoWimsy's", said)
        plain = self.fake.say(DM, BOT, 'a plain message of its own')
        self.assertIn('is not a draft', self.error('discord_post_status', draft=plain))

    def test_a_post_discord_refuses_shows_its_error_and_the_draft_waits_again(self):
        self.fake.fail[('POST', f'/channels/{GENERAL}/messages')] = (
            403,
            {'message': 'Missing Permissions', 'code': 50013},
        )
        self.owner_answers(3, YES)
        said = self.error('discord_post', channel=GENERAL, text='hello')
        refused = f'Discord answered 403 to POST /channels/{GENERAL}/messages: Missing Permissions (code 50013)'
        self.assertIn(refused, said)
        draft = self.fake.last(DM)
        self.assertEqual(self.fake.footer(draft), f'waiting: to {GENERAL}')
        self.assertIn('Posting failed: Discord answered 403', draft['embeds'][0]['description'])
        del self.fake.fail[('POST', f'/channels/{GENERAL}/messages')]
        self.assertEqual(self.tool('discord_post_status', draft=draft['id'])['status'], 'sent')
        self.assertEqual(len(self.fake.messages[GENERAL]), 1)

    def test_a_draft_left_sending_is_never_posted_again(self):
        self.owner_answers(3, YES)
        self.tool('discord_post', channel=GENERAL, text='hello')
        draft = self.fake.last(DM)
        draft['embeds'][0]['footer']['text'] = f'sending: to {GENERAL}'
        self.assertIn('says it is being posted to channel', self.error('discord_post_status', draft=draft['id']))
        self.assertEqual(len(self.fake.messages[GENERAL]), 1)

    def test_a_channel_no_longer_listed_when_approved_is_refused(self):
        got = self.tool('discord_post', channel=HELP, text='hello', wait=0)
        self.bot.settings = self.settings._replace(channels=frozenset({GENERAL}))
        self.fake.react(got['draft'], YES, OWNER)
        said = self.error('discord_post_status', draft=got['draft'])
        self.assertIn(f'channel {HELP} is not one AogoWimsy may post in', said)
        self.assertEqual(self.fake.messages[HELP], [])


class Read(WithDiscord):
    def conversation(self, channel):
        ids = [self.fake.say(channel, OWNER, 'first', attachments=[{'filename': 'build.log', 'url': 'x'}])]
        ids.append(self.fake.say(channel, STRANGER, 'a secret of the stranger'))
        ids.append(self.fake.say(channel, FRIEND, 'a reply', reply_to=ids[0]))
        ids.append(self.fake.say(channel, BOT, 'its own'))
        ids.append(self.fake.say(channel, '1000000000000000099', 'a webhook', webhook_id='1000000000000000099'))
        return ids

    def test_only_the_owner_the_listed_users_and_its_own_reach_the_session_the_others_counted(self):
        ids = self.conversation(GENERAL)
        got = self.tool('discord_read', channel=GENERAL)
        self.assertEqual([m['id'] for m in got['messages']], [ids[0], ids[2], ids[3]])
        self.assertEqual((got['left_out'], got['after'], got['channel']), (2, ids[4], GENERAL))
        first, reply = got['messages'][0], got['messages'][1]
        self.assertEqual((first['author'], first['author_id'], first['text']), ('DraVee', OWNER, 'first'))
        self.assertEqual((first['attachments'], first['reply_to'], first['approved']), (['build.log'], None, False))
        self.assertEqual((reply['author'], reply['reply_to']), ('friend', ids[0]))
        self.assertTrue(first['time'].startswith('2026-10-21T12:'))
        self.assertNotIn('stranger', json.dumps(got).lower())
        self.assertNotIn('webhook', json.dumps(got))

    def test_after_and_limit(self):
        ids = self.conversation(GENERAL)
        got = self.tool('discord_read', channel=GENERAL, after=ids[1], limit=2)
        self.assertEqual(
            ([m['id'] for m in got['messages']], got['left_out'], got['after']), ([ids[2], ids[3]], 0, ids[3])
        )
        self.assertEqual(
            self.fake.posts('GET', f'/channels/{GENERAL}/messages')[-1][2], {'limit': '2', 'after': ids[1]}
        )
        newest = self.tool('discord_read', channel=GENERAL, limit=1)
        self.assertEqual((newest['messages'], newest['left_out'], newest['after']), ([], 1, ids[4]))
        empty = self.tool('discord_read', channel=GENERAL, after=ids[4])
        self.assertEqual((empty['messages'], empty['after']), ([], ids[4]))
        said = self.error('discord_read', channel=GENERAL, limit=101)
        self.assertIn('limit is 101, not a whole number from 1 to 100', said)

    def test_from_gives_only_those_authors_and_refuses_anyone_else(self):
        ids = self.conversation(GENERAL)
        got = self.tool('discord_read', channel=GENERAL, **{'from': [FRIEND]})
        self.assertEqual(([m['id'] for m in got['messages']], got['left_out']), ([ids[2]], 4))
        both = self.tool('discord_read', channel=GENERAL, **{'from': [OWNER, FRIEND]})
        self.assertEqual([m['id'] for m in both['messages']], [ids[0], ids[2]])
        said = self.error('discord_read', channel=GENERAL, **{'from': [FRIEND, STRANGER]})
        self.assertEqual(
            said,
            f'from item 2 is {STRANGER}, neither the owner ({OWNER}), a listed user ({FRIEND}) nor one he allowed',
        )
        self.assertIn(
            'from is []: a list of 1 or more ids', self.error('discord_read', channel=GENERAL, **{'from': []})
        )
        self.assertIn(
            'from item 1 is "abc", not a Discord id', self.error('discord_read', channel=GENERAL, **{'from': ['abc']})
        )

    def test_a_strangers_message_to_aogo_the_owner_let_through_is_read_and_marked(self):
        mine = self.fake.say(GENERAL, BOT, 'a post of mine')
        let = self.fake.say(GENERAL, STRANGER, 'quoting you', reply_to=mine)
        other = self.fake.say(GENERAL, STRANGER, 'me too', mentions=[BOT])
        plain = self.fake.say(GENERAL, STRANGER, 'not to aogo')
        self.fake.react(let, WIMSY, OWNER)
        self.fake.react(other, WIMSY, OTHER_PERSON)
        self.fake.react(plain, WIMSY, OWNER)
        got = self.tool('discord_read', channel=GENERAL)
        self.assertEqual([(m['id'], m['approved']) for m in got['messages']], [(mine, False), (let, True)])
        self.assertEqual(got['left_out'], 2)
        self.assertNotIn('me too', json.dumps(got))
        self.assertTrue(self.fake.posts('GET', f'/channels/{GENERAL}/messages/{let}/reactions/{WIMSY}'))
        named = self.tool('discord_read', channel=GENERAL, **{'from': [OWNER]})
        self.assertEqual((named['messages'], named['left_out']), ([], 4))

    def test_only_the_wimsyaogo_reaction_lets_a_strangers_message_through(self):
        mine = self.fake.say(GENERAL, BOT, 'a post of mine')
        old = self.fake.say(GENERAL, STRANGER, 'with the old emoji', reply_to=mine)
        new = self.fake.say(GENERAL, STRANGER, 'with the new one', reply_to=mine)
        self.fake.react(old, 'wimsytetoutau:600000000000000002', OWNER)
        self.fake.react(new, 'wimsyaogo:600000000000000001', OWNER)
        got = self.tool('discord_read', channel=GENERAL)
        self.assertEqual(aw.WIMSY, 'wimsyaogo')
        self.assertEqual([(m['id'], m['approved']) for m in got['messages']], [(mine, False), (new, True)])
        self.assertNotIn('with the old emoji', json.dumps(got))

    def test_a_message_the_owner_replied_to_mentioning_aogo_is_read_with_his_reply_in_the_page(self):
        start = self.fake.say(GENERAL, FRIEND, 'before')
        theirs = self.fake.say(GENERAL, STRANGER, 'a question for the room')
        reply = self.fake.say(GENERAL, OWNER, 'asking <@1000000000000000001>', reply_to=theirs, mentions=[BOT])
        got = self.tool('discord_read', channel=GENERAL, after=start)
        self.assertEqual([(m['id'], m['approved']) for m in got['messages']], [(theirs, True), (reply, False)])
        alone = self.tool('discord_read', channel=GENERAL, after=start, limit=1)  # no reply in the page, none heard
        self.assertEqual((alone['messages'], alone['left_out']), ([], 1))

    def test_a_message_the_owner_replied_to_mentioning_aogos_role_is_read_too(self):
        start = self.fake.say(GENERAL, FRIEND, 'before')
        theirs = self.fake.say(GENERAL, STRANGER, 'a question for the room')
        reply = self.fake.say(GENERAL, OWNER, f'<@&{BOT_ROLE}> also this', reply_to=theirs, mention_roles=[BOT_ROLE])
        got = self.tool('discord_read', channel=GENERAL, after=start)
        self.assertEqual([(m['id'], m['approved']) for m in got['messages']], [(theirs, True), (reply, False)])

    def test_a_thread_of_a_listed_channel_and_the_owners_dm_read_without_being_listed(self):
        ids = self.conversation(THREAD)
        got = self.tool('discord_read', channel=THREAD)
        self.assertEqual(([m['id'] for m in got['messages']], got['left_out']), ([ids[0], ids[2], ids[3]], 2))
        self.fake.say(DM, OWNER, 'in the DMs')
        self.assertEqual([m['text'] for m in self.tool('discord_read', channel=DM)['messages']], ['in the DMs'])

    def test_other_channels_are_refused_naming_what_it_reads(self):
        said = self.error('discord_read', channel=OTHER)
        lists = f'channel {OTHER} is not one AogoWimsy may read: AOGOWIMSY_CHANNELS lists {GENERAL}, {HELP}'
        self.assertIn(lists, said)
        self.assertIn(f"the owner's DMs with AogoWimsy are {DM}", said)
        self.assertIn('may read', self.error('discord_read', channel=OTHER_THREAD))
        self.assertFalse(self.fake.posts('GET', f'/channels/{OTHER}/messages'))
        self.bot.settings = self.settings._replace(channels=None)
        self.fake.say(OTHER, OWNER, 'anywhere')
        self.assertEqual([m['text'] for m in self.tool('discord_read', channel=OTHER)['messages']], ['anywhere'])


class Attachments(WithDiscord):
    def setUp(self):
        super().setUp()
        folder = tempfile.TemporaryDirectory(prefix='aogowimsy-files-')
        self.addCleanup(folder.cleanup)
        self.bot.files = Path(folder.name) / 'cache' / 'aogowimsy'

    def carrying(self, channel, author, files, content='', **extra):
        """a message with files [(name, bytes, type)], each served by the fake CDN; its id"""
        number = self.fake.say(channel, author, content, **extra)
        kept = []
        for place, (name, data, kind) in enumerate(files):
            path = f'/attachments/{channel}/{number}{place}/{urllib.parse.quote(name)}'
            self.fake.blobs[path] = (data, kind)
            item = {'id': f'{number}{place}', 'filename': name, 'size': len(data), 'url': self.fake.origin + path}
            kept.append(dict(item, content_type=kind))
        self.fake.find(channel, number)['attachments'] = kept
        return number

    def cdn(self):
        return [r for r in self.fake.requests if r[0] == 'CDN']

    def test_the_owners_files_land_in_the_messages_folder_private_and_fetched_without_the_token(self):
        log = b'line 1\nline 2\n'
        number = self.carrying(GENERAL, OWNER, [('shot.png', PNG, 'image/png'), ('game.log', log, 'text/plain')])
        self.fake.find(GENERAL, number)['attachments'][0].update(width=1920, height=1080)
        got = self.tool('discord_attachments', channel=GENERAL, message=number)
        folder = self.bot.files / GENERAL / number
        self.assertEqual((got['channel'], got['message'], got['folder']), (GENERAL, number, str(folder)))
        self.assertEqual(
            got['files'],
            [
                {
                    'name': 'shot.png',
                    'type': 'image/png',
                    'size': len(PNG),
                    'width': 1920,
                    'height': 1080,
                    'path': str(folder / 'shot.png'),
                },
                {'name': 'game.log', 'type': 'text/plain', 'size': len(log), 'path': str(folder / 'game.log')},
            ],
        )
        self.assertEqual(((folder / 'shot.png').read_bytes(), (folder / 'game.log').read_bytes()), (PNG, log))
        for level in (self.bot.files, self.bot.files / GENERAL, folder):
            self.assertEqual(level.stat().st_mode & 0o777, 0o700, level)
        self.assertEqual((folder / 'shot.png').stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ['game.log', 'shot.png'])  # no .part left
        self.assertEqual([r[3] for r in self.cdn()], [None, None])

    def test_a_file_saved_before_is_not_fetched_again(self):
        number = self.carrying(GENERAL, FRIEND, [('a.png', PNG, 'image/png')])
        first = self.tool('discord_attachments', channel=GENERAL, message=number)
        again = self.tool('discord_attachments', channel=GENERAL, message=number)
        self.assertEqual(first, again)
        self.assertEqual(len(self.cdn()), 1)

    def test_a_strangers_message_the_owner_did_not_let_through_is_refused_naming_no_one(self):
        number = self.carrying(GENERAL, STRANGER, [('a.png', PNG, 'image/png')], 'look', mentions=[BOT])
        self.fake.react(number, WIMSY, OTHER_PERSON)
        said = self.error('discord_attachments', channel=GENERAL, message=number)
        self.assertEqual(
            said,
            f"message {number} is not one AogoWimsy gives: neither the owner's ({OWNER}), a listed user's ({FRIEND}) "
            f'nor its own, and the owner has not let it through (his :{aw.WIMSY}: reaction, or his reply to it '
            'mentioning AogoWimsy)',
        )
        self.assertNotIn('tranger', said)
        self.assertEqual(self.cdn(), [])
        self.assertFalse(self.bot.files.exists())

    def test_a_strangers_message_the_owner_replied_to_mentioning_aogo_or_let_through_is_saved(self):
        quoted = self.carrying(GENERAL, STRANGER, [('q.jpg', b'\xff\xd8\xff jpeg', 'image/jpeg')])
        self.fake.say(GENERAL, FRIEND, 'in between')
        self.fake.say(GENERAL, OWNER, '<@1000000000000000001> any idea?', reply_to=quoted, mentions=[BOT])
        mine = self.fake.say(GENERAL, BOT, 'a post of mine')
        let = self.carrying(GENERAL, STRANGER, [('l.png', PNG, 'image/png')], 'for you', reply_to=mine)
        self.fake.react(let, WIMSY, OWNER)
        for number in (quoted, let):
            with self.subTest(message=number):
                got = self.tool('discord_attachments', channel=GENERAL, message=number)
                self.assertEqual([('path' in f, 'error' in f) for f in got['files']], [(True, False)])
        self.bot.approved.add(heard := self.carrying(GENERAL, STRANGER, [('h.png', PNG, 'image/png')]))
        self.assertIn('path', self.tool('discord_attachments', channel=GENERAL, message=heard)['files'][0])

    def test_one_too_big_or_failing_says_why_and_the_others_are_saved(self):
        self.addCleanup(setattr, aw, 'MOST_SAVE', aw.MOST_SAVE)
        aw.MOST_SAVE = 20
        number = self.carrying(
            GENERAL,
            OWNER,
            [
                ('big.png', b'x' * 21, 'image/png'),
                ('gone.png', b'gone', 'image/png'),
                ('ok.txt', b'fits', 'text/plain'),
            ],
        )
        attached = self.fake.find(GENERAL, number)['attachments']
        del self.fake.blobs[urllib.parse.urlsplit(attached[1]['url']).path]
        got = self.tool('discord_attachments', channel=GENERAL, message=number)
        big, gone, ok = got['files']
        self.assertEqual(big['error'], '21 bytes, more than the 20 AogoWimsy saves of one attachment')
        self.assertTrue(gone['error'].startswith(f"Discord's CDN answered 401 to {attached[1]['url']}"), gone)
        self.assertNotIn('path', big)
        self.assertEqual(Path(ok['path']).read_bytes(), b'fits')
        self.assertEqual([r[1].rsplit('/', 1)[1] for r in self.cdn()], ['ok.txt'])  # the big one is never fetched

    def test_a_size_discord_did_not_give_is_capped_while_reading(self):
        self.addCleanup(setattr, aw, 'MOST_SAVE', aw.MOST_SAVE)
        aw.MOST_SAVE = 4
        number = self.carrying(GENERAL, OWNER, [('a.png', PNG, 'image/png')])
        del self.fake.find(GENERAL, number)['attachments'][0]['size']
        got = self.tool('discord_attachments', channel=GENERAL, message=number)
        self.assertIn("Discord's CDN gave more than 4 bytes for", got['files'][0]['error'])
        self.assertEqual(list((self.bot.files / GENERAL / number).iterdir()), [])

    def test_names_stay_in_the_folder_and_a_name_twice_takes_its_id(self):
        number = self.carrying(
            GENERAL,
            OWNER,
            [
                ('../../up.txt', b'1', 'text/plain'),
                ('a.png', PNG, 'image/png'),
                ('a.png', b'2', 'image/png'),
                ('...', b'3', 'text/plain'),
                ('tab\there\n.log', b'4', 'text/plain'),
            ],
        )
        ids = [a['id'] for a in self.fake.find(GENERAL, number)['attachments']]
        got = self.tool('discord_attachments', channel=GENERAL, message=number)
        folder = self.bot.files / GENERAL / number
        names = [Path(f['path']).name for f in got['files']]
        self.assertEqual(names, ['_.._up.txt', 'a.png', f'{ids[2]}-a.png', ids[3], 'tab_here_.log'])
        self.assertTrue(all(Path(f['path']).parent == folder for f in got['files']))
        self.assertEqual((folder / f'{ids[2]}-a.png').read_bytes(), b'2')

    def test_what_is_refused_before_any_file_is_fetched(self):
        plain = self.fake.say(GENERAL, OWNER, 'no files')
        cases = (
            ({'channel': GENERAL, 'message': plain}, f'message {plain} in channel {GENERAL} has no attachments'),
            ({'channel': GENERAL, 'message': '1999999999999999999'}, 'Discord answered 404 to GET'),
            ({'channel': OTHER, 'message': plain}, f'channel {OTHER} is not one AogoWimsy may read'),
            ({'channel': GENERAL}, 'discord_attachments needs message'),
            ({'channel': GENERAL, 'message': 'abc'}, 'message is "abc", not a Discord id'),
            ({'channel': GENERAL, 'message': plain, 'into': '/tmp'}, 'discord_attachments has no argument "into"'),
        )
        for args, said in cases:
            with self.subTest(args=args):
                self.assertIn(said, self.error('discord_attachments', **args))
        self.assertEqual(self.cdn(), [])

    def test_a_write_that_fails_says_where_and_leaves_no_part(self):
        number = self.carrying(GENERAL, OWNER, [('a.png', PNG, 'image/png')])
        folder = self.bot.files / GENERAL / number
        folder.mkdir(parents=True)
        (folder / 'a.png').mkdir()  # a folder where the file goes: os.replace fails
        got = self.tool('discord_attachments', channel=GENERAL, message=number)
        self.assertTrue(got['files'][0]['error'].startswith(f'{folder / "a.png"} could not be written: '))
        self.assertEqual([p.name for p in folder.iterdir()], ['a.png'])


class React(WithDiscord):
    """discord_react and discord_unreact: a fixed few reactions, at once, on a message discord_read gives"""

    def put(self, channel, message, emoji):
        return self.fake.posts('PUT', f'/channels/{channel}/messages/{message}/reactions/{emoji}/@me')

    def emojis_asked(self, guild=GUILD):
        return len(self.fake.posts('GET', f'/guilds/{guild}/emojis'))

    def test_each_reaction_goes_at_once_with_no_draft_and_stderr_says_whose_where_and_which(self):
        asked = self.fake.say(GENERAL, OWNER, 'can you look at the build?')
        for emoji in (EYES, YES, THUMBS, NO):
            with self.subTest(emoji=emoji):
                got = self.tool('discord_react', channel=GENERAL, message=asked, emoji=emoji)
                self.assertEqual(got, {'status': 'reacted', 'channel': GENERAL, 'message': asked, 'emoji': emoji})
                self.assertEqual(self.fake.reactions[asked][emoji], [BOT])
                self.assertEqual(len(self.put(GENERAL, asked, emoji)), 1)
        self.assertEqual((self.fake.messages[DM], self.clock.waits), ([], []))  # no draft, no wait
        said = f'discord_react: reacted, {EYES} of AogoWimsy on message {asked} in channel {GENERAL}'
        self.assertEqual(self.logs[:2], [said, 'discord_react: reacted'])
        self.assertNotIn('can you look', ' '.join(self.logs))

    def test_any_other_emoji_is_refused_naming_it_its_code_points_and_the_ones_taken(self):
        asked = self.fake.say(GENERAL, OWNER, 'hello')
        taken = f'not one AogoWimsy reacts with: it takes {CUSTOM}, {EYES}, {YES}, {THUMBS}, {NO}, :wimsyaogo:'
        party, selector = chr(0x1F389), chr(0xFE0F)
        cases = (
            (party, f'emoji is "{party}" (U+1F389), {taken}'),
            (THUMBS + selector, f'emoji is "{THUMBS}{selector}" (U+1F44D U+FE0F), {taken}'),
            ('wimsyaogo', f'emoji is "wimsyaogo", {taken}'),
            ('wimsyaogo_eyes', f'emoji is "wimsyaogo_eyes", {taken}'),
            (':wimsytetoutau:', f'emoji is ":wimsytetoutau:", {taken}'),
            (WIMSY, f'emoji is "{WIMSY}", {taken}'),
            ('', f'emoji is "", {taken}'),
            (5, f'emoji is 5, {taken}'),
        )
        for tool in ('discord_react', 'discord_unreact'):
            for emoji, said in cases:
                with self.subTest(tool=tool, emoji=emoji):
                    self.assertEqual(self.error(tool, channel=GENERAL, message=asked, emoji=emoji), said)
        self.assertEqual((self.fake.requests, self.fake.reactions), ([], {}))
        self.assertIn(f'discord_react failed: emoji is "{party}" (U+1F389), {taken}', self.logs)

    def test_a_channel_it_may_not_read_is_refused_and_nothing_is_put(self):
        elsewhere = self.fake.say(OTHER, OWNER, 'in a channel not listed')
        in_thread = self.fake.say(OTHER_THREAD, OWNER, 'in a thread of it')
        said = self.error('discord_react', channel=OTHER, message=elsewhere, emoji=EYES)
        lists = f'channel {OTHER} is not one AogoWimsy may read: AOGOWIMSY_CHANNELS lists {GENERAL}, {HELP}'
        self.assertIn(lists, said)
        self.assertIn(f"the owner's DMs with AogoWimsy are {DM}", said)
        said = self.error('discord_react', channel=OTHER_THREAD, message=in_thread, emoji=EYES)
        self.assertIn(f'channel {OTHER_THREAD} is not one AogoWimsy may read', said)
        said = self.error('discord_unreact', channel=OTHER, message=elsewhere, emoji=EYES)
        self.assertIn(f'channel {OTHER} is not one AogoWimsy may read', said)
        self.assertEqual([r for r in self.fake.requests if '/messages' in r[1]], [])  # the message never asked for
        self.assertEqual(self.fake.reactions, {})
        for channel in (THREAD, DM):  # a thread of a listed channel, and the owner's DMs, without being listed
            number = self.fake.say(channel, OWNER, 'here')
            self.assertEqual(
                self.tool('discord_react', channel=channel, message=number, emoji=EYES)['status'], 'reacted'
            )
        self.bot.settings = self.settings._replace(channels=None)
        self.assertEqual(self.tool('discord_react', channel=OTHER, message=elsewhere, emoji=EYES)['status'], 'reacted')

    def test_a_strangers_message_the_owner_did_not_let_through_is_refused_naming_no_one(self):
        theirs = self.fake.say(GENERAL, STRANGER, 'a secret of the stranger', mentions=[BOT])
        said = self.error('discord_react', channel=GENERAL, message=theirs, emoji=EYES)
        self.assertIn(f'message {theirs} is not one AogoWimsy gives', said)
        self.assertNotIn(STRANGER, said)
        self.assertFalse(self.put(GENERAL, theirs, EYES))
        self.fake.react(theirs, WIMSY, OWNER)
        self.assertEqual(self.tool('discord_react', channel=GENERAL, message=theirs, emoji=EYES)['status'], 'reacted')

    def test_a_draft_takes_no_reaction_and_loses_none(self):
        draft = self.tool('discord_post', channel=GENERAL, text='hello', wait=0)['draft']
        for tool in ('discord_react', 'discord_unreact'):
            for emoji in (YES, EYES):
                said = self.error(tool, channel=DM, message=draft, emoji=emoji)
                self.assertEqual(
                    said,
                    f"message {draft} is a draft of AogoWimsy's: its {YES} and {NO} are for the owner's answer, and "
                    f'{tool} touches no draft',
                )
        self.assertEqual(self.fake.reactions[draft], {YES: [BOT], NO: [BOT]})
        self.assertFalse([r for r in self.fake.requests if r[0] == 'DELETE'])
        plain = self.fake.say(DM, BOT, 'a plain message of its own')
        self.assertEqual(self.tool('discord_react', channel=DM, message=plain, emoji=YES)['status'], 'reacted')

    def test_twice_is_already_there_and_unreact_takes_off_its_own_alone(self):
        asked = self.fake.say(GENERAL, FRIEND, 'is it fixed?')
        self.fake.react(asked, EYES, OWNER)
        self.assertEqual(self.tool('discord_react', channel=GENERAL, message=asked, emoji=EYES)['status'], 'reacted')
        again = self.tool('discord_react', channel=GENERAL, message=asked, emoji=EYES)
        self.assertEqual(again, {'status': 'already there', 'channel': GENERAL, 'message': asked, 'emoji': EYES})
        self.assertEqual(len(self.put(GENERAL, asked, EYES)), 1)
        gone = self.tool('discord_unreact', channel=GENERAL, message=asked, emoji=EYES)
        self.assertEqual(gone, {'status': 'removed', 'channel': GENERAL, 'message': asked, 'emoji': EYES})
        self.assertEqual(self.fake.reactions[asked], {EYES: [OWNER]})  # the owner's stays
        self.assertEqual(
            self.tool('discord_unreact', channel=GENERAL, message=asked, emoji=EYES)['status'], 'not there'
        )
        self.assertEqual(
            len(self.fake.posts('DELETE', f'/channels/{GENERAL}/messages/{asked}/reactions/{EYES}/@me')), 1
        )
        self.assertEqual(self.tool('discord_react', channel=GENERAL, message=asked, emoji=YES)['status'], 'reacted')
        self.assertEqual(self.fake.reactions[asked], {EYES: [OWNER], YES: [BOT]})
        said = f'discord_unreact: not there, {EYES} of AogoWimsy on message {asked} in channel {GENERAL}'
        self.assertIn(said, self.logs)

    def test_wimsyaogo_goes_by_the_servers_emoji_asked_once_and_comes_off_by_its_own(self):
        first, second = self.fake.say(GENERAL, OWNER, 'one'), self.fake.say(HELP, FRIEND, 'two')
        for channel, number in ((GENERAL, first), (HELP, second)):
            got = self.tool('discord_react', channel=channel, message=number, emoji=OWNERS)
            self.assertEqual(got, {'status': 'reacted', 'channel': channel, 'message': number, 'emoji': OWNERS})
            self.assertEqual(self.fake.reactions[number], {WIMSY: [BOT]})
        self.assertEqual(self.emojis_asked(), 1)
        self.assertFalse(self.fake.posts('GET', '/users/@me/guilds'))  # the channel's server had it
        gone = self.tool('discord_unreact', channel=GENERAL, message=first, emoji=OWNERS)
        self.assertEqual(gone['status'], 'removed')
        self.assertEqual(self.fake.reactions[first], {})
        self.assertEqual(self.emojis_asked(), 1)

    def test_wimsyaogo_takes_the_id_a_reaction_on_the_message_has(self):
        mine = self.fake.say(GENERAL, BOT, 'a post of mine')
        theirs = self.fake.say(GENERAL, STRANGER, 'thanks', reply_to=mine)
        self.fake.react(theirs, WIMSY, OWNER)  # the owner let it through
        self.assertEqual(self.tool('discord_react', channel=GENERAL, message=theirs, emoji=OWNERS)['status'], 'reacted')
        self.assertEqual(self.fake.reactions[theirs], {WIMSY: [OWNER, BOT]})
        self.assertEqual(self.emojis_asked(), 0)
        said = self.error('discord_react', channel=GENERAL, message=mine, emoji='wimsyother')
        self.assertIn('emoji is "wimsyother", not one AogoWimsy reacts with', said)

    def test_wimsyaogo_in_the_owners_dms_or_a_server_without_it_comes_from_another_server_it_is_in(self):
        self.fake.guild_ids.append(OTHER_GUILD)
        made = 'wimsyaogo:600000000000000003'
        self.fake.server_emojis = {GUILD: [], OTHER_GUILD: [{'id': made.split(':')[1], 'name': aw.WIMSY}]}
        in_dm, in_general = self.fake.say(DM, OWNER, 'in the DMs'), self.fake.say(GENERAL, OWNER, 'in general')
        for channel, number in ((DM, in_dm), (GENERAL, in_general)):
            self.assertEqual(
                self.tool('discord_react', channel=channel, message=number, emoji=OWNERS)['status'], 'reacted'
            )
            self.assertEqual(self.fake.reactions[number], {made: [BOT]})
        # the channel's server asked again for what it lacked: an emoji may have been uploaded since
        self.assertEqual((self.emojis_asked(GUILD), self.emojis_asked(OTHER_GUILD)), (2, 1))

    def test_wimsyaogo_no_server_has_is_refused_naming_the_servers_looked_in(self):
        self.fake.guild_ids.append(OTHER_GUILD)
        self.fake.server_emojis = {GUILD: [{'id': OTHER_EMOJI.split(':')[1], 'name': 'wimsyother'}]}
        asked = self.fake.say(HELP, OWNER, 'hi')
        said = self.error('discord_react', channel=HELP, message=asked, emoji=OWNERS)
        self.assertEqual(
            said,
            f'no server AogoWimsy is in has an emoji named wimsyaogo (it looked in {GUILD}, {OTHER_GUILD})',
        )
        self.assertEqual(self.fake.reactions, {})

    def test_the_servers_emojis_are_asked_again_once_it_is_joined_again_or_discord_refuses_the_one_known(self):
        asked = self.fake.say(GENERAL, OWNER, 'hi')
        self.tool('discord_react', channel=GENERAL, message=asked, emoji=OWNERS)
        self.tool('discord_unreact', channel=GENERAL, message=asked, emoji=OWNERS)
        renewed = 'wimsyaogo:600000000000000004'
        self.fake.server_emojis[GUILD] = [{'id': renewed.split(':')[1], 'name': aw.WIMSY}]  # made again: a new id
        aw.Ear(self.bot, lambda text, meta: None, threading.Event()).hear(
            'GUILD_CREATE', {'id': GUILD, 'channels': [], 'threads': []}
        )
        self.tool('discord_react', channel=GENERAL, message=asked, emoji=OWNERS)
        self.assertEqual((self.fake.reactions[asked], self.emojis_asked()), ({renewed: [BOT]}, 2))
        later, newest = self.fake.say(GENERAL, OWNER, 'again'), 'wimsyaogo:600000000000000005'
        self.fake.server_emojis[GUILD] = [{'id': newest.split(':')[1], 'name': aw.WIMSY}]  # with no event this time
        said = self.error('discord_react', channel=GENERAL, message=later, emoji=OWNERS)
        quoted = urllib.parse.quote(renewed)
        self.assertEqual(
            said,
            f'Discord answered 400 to PUT /channels/{GENERAL}/messages/{later}/reactions/{quoted}/@me: Unknown Emoji '
            '(code 10014)',
        )
        self.assertEqual(self.tool('discord_react', channel=GENERAL, message=later, emoji=OWNERS)['status'], 'reacted')
        self.assertEqual((self.fake.reactions[later], self.emojis_asked()), ({newest: [BOT]}, 3))

    def test_discords_refusal_shows_with_its_status_and_message(self):
        asked = self.fake.say(GENERAL, OWNER, 'hi')
        path = f'/channels/{GENERAL}/messages/{asked}/reactions/{EYES}/@me'
        self.fake.fail[('PUT', path)] = (403, {'message': 'Missing Permissions', 'code': 50013})
        said = self.error('discord_react', channel=GENERAL, message=asked, emoji=EYES)
        quoted = urllib.parse.quote(EYES)
        self.assertEqual(
            said,
            f'Discord answered 403 to PUT /channels/{GENERAL}/messages/{asked}/reactions/{quoted}/@me: Missing '
            'Permissions (code 50013)',
        )
        self.assertEqual(self.logs, [f'discord_react failed: {said}'])
        gone = '1500000000000000099'
        said = self.error('discord_react', channel=GENERAL, message=gone, emoji=EYES)
        self.assertEqual(
            said, f'Discord answered 404 to GET /channels/{GENERAL}/messages/{gone}: Unknown Message (code 10008)'
        )

    def test_arguments_are_checked_before_discord_hears_of_them(self):
        asked = '1500000000000000001'
        self.assertEqual(self.error('discord_react', channel=GENERAL, message=asked), 'discord_react needs emoji')
        said = self.error('discord_react', channel=GENERAL, message=asked, emoji=EYES, text='hi')
        self.assertEqual(said, 'discord_react has no argument "text"; it takes channel, message, emoji')
        said = self.error('discord_unreact', channel=GENERAL, message='abc', emoji=EYES)
        self.assertEqual(said, 'message is "abc", not a Discord id (17 to 20 digits)')
        said = self.error('discord_unreact', channel=int(GENERAL), message=asked, emoji=EYES)
        self.assertIn('channel is 300000000000000001, not a Discord id: write it as a string', said)
        self.assertEqual(self.fake.requests, [])

    def test_the_tools_and_the_instructions_say_which_reactions_and_when(self):
        tools = {tool['name']: tool for tool in aw.tool_list(aw.AOGO)}
        self.assertEqual(list(tools), list(aw.TOOL_NAMES))
        quick = [
            ':wimsyaogo_eyes:',
            ':wimsyaogo_done:',
            ':wimsyaogo_thumbsup:',
            ':wimsyaogo_no:',
            EYES,
            YES,
            THUMBS,
            NO,
        ]
        for name in ('discord_react', 'discord_unreact'):
            emoji = tools[name]['inputSchema']['properties']['emoji']
            self.assertEqual(emoji['enum'], [*quick, ':wimsyaogo:'])
            self.assertEqual(tools[name]['inputSchema']['required'], ['channel', 'message', 'emoji'])
        self.assertEqual(tools['discord_quick']['inputSchema']['properties']['emoji']['enum'], quick)
        self.assertEqual(tools['discord_quick']['inputSchema']['required'], ['channel', 'reply_to', 'emoji'])
        names = tools['discord_emoji_upload']['inputSchema']['properties']['name']['enum']
        self.assertEqual(names, ['wimsyaogo_eyes', 'wimsyaogo_done', 'wimsyaogo_thumbsup', 'wimsyaogo_no'])
        meanings = (
            f':wimsyaogo_eyes: or {EYES} (seen, on it); :wimsyaogo_done: or {YES} (done); :wimsyaogo_thumbsup: or '
            f'{THUMBS} (agreed); :wimsyaogo_no: or {NO} (cannot)'
        )
        for name in ('discord_react', 'discord_quick'):
            self.assertIn(meanings, tools[name]['description'])
        said = aw.instructions(self.settings)
        self.assertIn(
            "react to it with discord_react instead of posting, the server's emoji first, its unicode one only while "
            f"that is not uploaded: {meanings}; and :wimsyaogo:, the owner's emoji",
            said,
        )
        self.assertIn(
            'put :wimsyaogo_eyes: when you start on a message and, once done, take it off with discord_unreact and '
            'put :wimsyaogo_done:',
            said,
        )
        self.assertIn("AogoWimsy's own :wimsyaogo: lets nothing through: only the owner's does", said)
        self.assertIn('a quick reply, use discord_quick: it posts at once, with no draft, and takes no text', said)


class Drawn(WithDiscord):
    """the server's custom emojis drawn for the bot's answers: found by name, a missing one named with its unicode"""

    def test_each_drawn_emoji_goes_by_the_servers_one_of_its_name_and_comes_off(self):
        self.fake.upload(*aw.DRAWN)
        asked = self.fake.say(GENERAL, OWNER, 'merged?')
        for name in aw.DRAWN:
            with self.subTest(name=name):
                got = self.tool('discord_react', channel=GENERAL, message=asked, emoji=f':{name}:')
                self.assertEqual(got['status'], 'reacted')
                self.assertEqual(self.fake.reactions[asked][f'{name}:{DRAWN_IDS[name]}'], [BOT])
        self.assertEqual(len(self.fake.posts('GET', f'/guilds/{GUILD}/emojis')), 1)  # hits from the first answer
        gone = self.tool('discord_unreact', channel=GENERAL, message=asked, emoji=':wimsyaogo_eyes:')
        self.assertEqual(gone['status'], 'removed')
        self.assertNotIn(f'wimsyaogo_eyes:{DRAWN_IDS["wimsyaogo_eyes"]}', self.fake.reactions[asked])
        said = f'discord_react: reacted, :wimsyaogo_done: of AogoWimsy on message {asked} in channel {GENERAL}'
        self.assertIn(said, self.logs)

    def test_one_not_uploaded_yet_is_refused_naming_it_and_its_unicode_and_found_once_it_is(self):
        asked = self.fake.say(GENERAL, OWNER, 'merged?')
        said = self.error('discord_react', channel=GENERAL, message=asked, emoji=':wimsyaogo_eyes:')
        self.assertEqual(
            said,
            f'no server AogoWimsy is in has an emoji named wimsyaogo_eyes (it looked in {GUILD}): it is not uploaded '
            f'yet (discord_emoji_upload uploads it); {EYES} says the same',
        )
        self.assertEqual(self.fake.reactions, {})
        self.fake.upload('wimsyaogo_eyes')  # no gateway event: the miss is asked again
        self.assertEqual(
            self.tool('discord_react', channel=GENERAL, message=asked, emoji=':wimsyaogo_eyes:')['status'], 'reacted'
        )
        self.assertEqual(self.fake.reactions[asked], {f'wimsyaogo_eyes:{DRAWN_IDS["wimsyaogo_eyes"]}': [BOT]})


class Quick(WithDiscord):
    """discord_quick: a reply of one emoji alone, posted at once; a text never"""

    def test_one_emoji_alone_posts_at_once_replying_pinging_no_one_with_no_draft(self):
        self.fake.upload(*aw.DRAWN)
        asked = self.fake.say(GENERAL, OWNER, 'is it merged?')
        got = self.tool('discord_quick', channel=GENERAL, reply_to=asked, emoji=':wimsyaogo_done:')
        posted = self.fake.last(GENERAL)
        link = f'https://discord.com/channels/{GUILD}/{GENERAL}/{posted["id"]}'
        want = {'status': 'posted', 'link': link, 'message': posted['id'], 'channel': GENERAL, 'reply_to': asked}
        self.assertEqual(got, dict(want, emoji=':wimsyaogo_done:'))
        self.assertEqual(posted['content'], f'<:wimsyaogo_done:{DRAWN_IDS["wimsyaogo_done"]}>')
        body = self.fake.posts('POST', f'/channels/{GENERAL}/messages')[0][3]
        self.assertEqual(body['allowed_mentions'], {'parse': [], 'replied_user': False})
        reference = {'message_id': asked, 'channel_id': GENERAL, 'fail_if_not_exists': True}
        self.assertEqual(body['message_reference'], reference)
        self.assertEqual((self.fake.messages[DM], self.clock.waits), ([], []))  # no draft, no wait
        said = f'discord_quick: posted, :wimsyaogo_done: of AogoWimsy as message {posted["id"]} replying to {asked} '
        self.assertEqual(self.logs, [said + f'in channel {GENERAL}', 'discord_quick: posted'])
        plain = self.tool('discord_quick', channel=GENERAL, reply_to=asked, emoji=THUMBS)
        self.assertEqual((plain['status'], self.fake.last(GENERAL)['content']), ('posted', THUMBS))
        self.tool('discord_quick', channel=GENERAL, reply_to=asked, emoji=':wimsyaogo_eyes:')
        self.assertEqual(len(self.fake.posts('GET', f'/guilds/{GUILD}/emojis')), 2)  # asked at each custom one

    def test_a_text_or_any_other_emoji_is_refused_and_nothing_is_posted(self):
        asked = self.fake.say(GENERAL, OWNER, 'is it merged?')
        taken = (
            "not one AogoWimsy posts alone; a text goes through discord_post and the owner's "
            f'{YES}: it takes {CUSTOM}, {EYES}, {YES}, {THUMBS}, {NO}'
        )
        for emoji, said in (
            ('done, merged', f'emoji is "done, merged", {taken}'),
            (
                f'{YES} merged',
                f'emoji is "{YES} merged" (U+2705 U+0020 U+006D U+0065 U+0072 U+0067 U+0065 U+0064), {taken}',
            ),
            (OWNERS, f'emoji is ":wimsyaogo:", {taken}'),
            (f'{EYES}{EYES}', f'emoji is "{EYES}{EYES}" (U+1F440 U+1F440), {taken}'),
        ):
            with self.subTest(emoji=emoji):
                self.assertEqual(self.error('discord_quick', channel=GENERAL, reply_to=asked, emoji=emoji), said)
        said = self.error('discord_quick', channel=GENERAL, reply_to=asked, emoji=YES, text='merged')
        self.assertEqual(said, 'discord_quick has no argument "text"; it takes channel, reply_to, emoji')
        self.assertEqual(self.error('discord_quick', channel=GENERAL, emoji=YES), 'discord_quick needs reply_to')
        self.assertEqual(self.fake.requests, [])
        self.assertEqual(len(self.fake.messages[GENERAL]), 1)

    def test_a_channel_it_may_not_post_in_a_strangers_message_a_draft_and_a_missing_emoji_post_nothing(self):
        elsewhere = self.fake.say(OTHER, OWNER, 'elsewhere')
        said = self.error('discord_quick', channel=OTHER, reply_to=elsewhere, emoji=YES)
        self.assertIn(f'channel {OTHER} is not one AogoWimsy may post in: AOGOWIMSY_CHANNELS lists', said)
        theirs = self.fake.say(GENERAL, STRANGER, 'a secret of the stranger', mentions=[BOT])
        said = self.error('discord_quick', channel=GENERAL, reply_to=theirs, emoji=YES)
        self.assertIn(f'message {theirs} is not one AogoWimsy gives', said)
        asked = self.fake.say(GENERAL, OWNER, 'merged?')
        said = self.error('discord_quick', channel=GENERAL, reply_to=asked, emoji=':wimsyaogo_no:')
        self.assertIn(f'emoji named wimsyaogo_no (it looked in {GUILD}): it is not uploaded yet', said)
        self.assertIn(f'{NO} says the same', said)
        in_dm = self.fake.say(DM, OWNER, 'in the DMs')  # read there, but posted in only as discord_post does
        said = self.error('discord_quick', channel=DM, reply_to=in_dm, emoji=YES)
        self.assertIn(f'channel {DM} is not one AogoWimsy may post in', said)
        draft = self.tool('discord_post', channel=GENERAL, text='hello', wait=0)['draft']
        self.bot.settings = self.settings._replace(channels=None)  # the owner's DMs are a channel to post in now
        said = self.error('discord_quick', channel=DM, reply_to=draft, emoji=YES)
        self.assertIn(f"message {draft} is a draft of AogoWimsy's", said)
        self.assertEqual([len(self.fake.messages[c]) for c in (OTHER, GENERAL, DM)], [1, 2, 2])


class EmojiUpload(WithDiscord):
    """discord_emoji_upload: one of the four drawn emojis, from its fixed file, by its name"""

    def setUp(self):
        super().setUp()
        folder = tempfile.TemporaryDirectory(prefix='aogowimsy-emoji-')
        self.addCleanup(folder.cleanup)
        self.bot.drawings = Path(folder.name)
        for name in aw.DRAWN:
            (self.bot.drawings / f'{name}.png').write_bytes(PNG_EMOJI + name.encode())

    def call(self, **args):
        """discord_emoji_upload's result: its argument name is one tool() and error() take for the tool's"""
        params = {'name': 'discord_emoji_upload', 'arguments': args}
        return self.server.handle({'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call', 'params': params})['result']

    def uploads(self, **args):
        result = self.call(**args)
        self.assertFalse(result['isError'], result['content'][0]['text'])
        return json.loads(result['content'][0]['text'])

    def refused(self, **args):
        result = self.call(**args)
        self.assertTrue(result['isError'], result['content'][0]['text'])
        return result['content'][0]['text']

    def test_it_uploads_the_png_as_a_data_uri_by_its_name_and_reacts_with_it_at_once(self):
        got = self.uploads(guild=GUILD, name='wimsyaogo_eyes')
        eyes = DRAWN_IDS['wimsyaogo_eyes']
        self.assertEqual(got, {'status': 'uploaded', 'guild': GUILD, 'name': 'wimsyaogo_eyes', 'id': eyes})
        body = self.fake.posts('POST', f'/guilds/{GUILD}/emojis')[0][3]
        image = 'data:image/png;base64,' + base64.b64encode(PNG_EMOJI + b'wimsyaogo_eyes').decode()
        self.assertEqual(body, {'name': 'wimsyaogo_eyes', 'image': image})
        self.assertEqual(
            self.logs[0],
            f'discord_emoji_upload: uploaded, wimsyaogo_eyes of AogoWimsy as emoji {eyes} in server {GUILD}',
        )
        asked = self.fake.say(GENERAL, OWNER, 'merged?')
        self.tool('discord_react', channel=GENERAL, message=asked, emoji=':wimsyaogo_eyes:')
        self.assertEqual(self.fake.reactions[asked], {f'wimsyaogo_eyes:{eyes}': [BOT]})
        self.assertEqual(len(self.fake.posts('GET', f'/guilds/{GUILD}/emojis')), 1)  # the upload's own answer

    def test_one_already_there_is_not_uploaded_again(self):
        self.fake.upload('wimsyaogo_done')
        got = self.uploads(guild=GUILD, name='wimsyaogo_done')
        self.assertEqual(
            got,
            {'status': 'already there', 'guild': GUILD, 'name': 'wimsyaogo_done', 'id': DRAWN_IDS['wimsyaogo_done']},
        )
        self.assertFalse(self.fake.posts('POST', f'/guilds/{GUILD}/emojis'))
        (self.bot.drawings / 'wimsyaogo_done.png').unlink()  # the file is not needed for one already there
        self.assertEqual(self.uploads(guild=GUILD, name='wimsyaogo_done')['status'], 'already there')

    def test_without_create_expressions_the_error_names_it_and_the_invite_with_it(self):
        self.fake.fail[('POST', f'/guilds/{GUILD}/emojis')] = (403, {'message': 'Missing Permissions', 'code': 50013})
        said = self.refused(guild=GUILD, name='wimsyaogo_no')
        self.assertEqual(274878008384 + (1 << 43), 9070971030592)
        self.assertEqual(
            said,
            f'Discord answered 403 to POST /guilds/{GUILD}/emojis: Missing Permissions (code 50013): AogoWimsy needs '
            f'Create Expressions (8796093022208) in server {GUILD}; give its role that permission (Server Settings, '
            'Roles), or invite it again with permissions=9070971030592',
        )
        self.fake.fail[('POST', f'/guilds/{GUILD}/emojis')] = (403, {'message': 'Missing Access', 'code': 50001})
        said = self.refused(guild=GUILD, name='wimsyaogo_no')
        self.assertEqual(said, f'Discord answered 403 to POST /guilds/{GUILD}/emojis: Missing Access (code 50001)')

    def test_the_invite_carries_attach_files_which_a_post_with_images_needs(self):
        self.assertEqual(aw.ATTACH_FILES, 1 << 15)
        self.assertEqual(aw.INVITE, 274878008384)
        self.assertEqual(aw.INVITE & aw.ATTACH_FILES, aw.ATTACH_FILES)

    def test_only_the_four_names_each_from_its_own_png_and_no_path(self):
        for name in ('wimsyaogo', 'wimsyaogo_eyes.png', '../wimsyaogo_eyes', '/etc/passwd', ':wimsyaogo_eyes:', 5):
            with self.subTest(name=name):
                said = self.refused(guild=GUILD, name=name)
                self.assertEqual(
                    said,
                    f'name is {aw.shown(name)}, not one AogoWimsy uploads: it takes wimsyaogo_eyes, wimsyaogo_done, '
                    f'wimsyaogo_thumbsup, wimsyaogo_no, each from {self.bot.drawings}/<name>.png',
                )
        said = self.refused(guild=GUILD, name='wimsyaogo_eyes', path='/tmp/x.png')
        self.assertEqual(said, 'discord_emoji_upload has no argument "path"; it takes guild, name')
        self.assertEqual(self.fake.requests, [])
        folder = self.bot.drawings
        (folder / 'wimsyaogo_eyes.png').unlink()
        (folder / 'wimsyaogo_done.png').write_bytes(b'GIF89a not a png')
        (folder / 'wimsyaogo_no.png').write_bytes(PNG_EMOJI + b'x' * aw.MOST_EMOJI)
        said = self.refused(guild=GUILD, name='wimsyaogo_eyes')
        self.assertIn(f'{folder}/wimsyaogo_eyes.png cannot be read (No such file or directory)', said)
        said = self.refused(guild=GUILD, name='wimsyaogo_done')
        self.assertEqual(said, f'{folder}/wimsyaogo_done.png is not a PNG: wimsyaogo_done is uploaded from a PNG')
        said = self.refused(guild=GUILD, name='wimsyaogo_no')
        size = len(PNG_EMOJI) + aw.MOST_EMOJI
        self.assertEqual(said, f'{folder}/wimsyaogo_no.png has {size} bytes: an emoji takes 262144 at most')
        self.assertFalse(self.fake.posts('POST', f'/guilds/{GUILD}/emojis'))
        said = self.refused(guild='200000000000000099', name='wimsyaogo_thumbsup')
        self.assertEqual(
            said, 'Discord answered 404 to GET /guilds/200000000000000099/emojis: Unknown Guild (code 10004)'
        )

    def test_its_folder_is_the_owners_wimsy_dist_clone(self):
        fresh = aw.Wimsy(self.settings, aw.Discord(TOKEN, self.clock, self.api), self.clock)
        self.assertEqual(fresh.drawings, Path.home() / 'WorkDir/ScarletNX/wimsy-dist/emoji')


class SavesFolder(unittest.TestCase):
    def test_xdg_cache_home_when_absolute_else_the_home_cache(self):
        home = Path.home() / '.cache' / 'aogowimsy'
        self.assertEqual(aw.saves_folder('aogowimsy', {'XDG_CACHE_HOME': '/var/tmp/c'}), Path('/var/tmp/c/aogowimsy'))
        self.assertEqual(aw.saves_folder('aogowimsy', {'XDG_CACHE_HOME': 'relative/c'}), home)
        self.assertEqual(aw.saves_folder('aogowimsy', {'XDG_CACHE_HOME': ''}), home)
        self.assertEqual(aw.saves_folder('aogowimsy', {}), home)

    def test_the_greetings_state_is_xdg_state_home_when_absolute_else_the_home_one(self):
        home = Path.home() / '.local' / 'state' / 'aogowimsy'
        self.assertEqual(aw.state_folder('aogowimsy', {'XDG_STATE_HOME': '/var/tmp/s'}), Path('/var/tmp/s/aogowimsy'))
        self.assertEqual(aw.state_folder('aogowimsy', {'XDG_STATE_HOME': 'relative/s'}), home)
        self.assertEqual(aw.state_folder('aogowimsy', {}), home)

    def test_a_long_name_keeps_its_suffix_within_200_bytes(self):
        name = aw.file_name('é' * 300 + '.png', 'fallback')
        self.assertTrue(name.endswith('.png'))
        self.assertLessEqual(len(name.encode()), 200)
        self.assertEqual(aw.file_name('', '123'), '123')


class Wait(WithDiscord):
    def test_the_first_message_from_the_owner_or_a_listed_user_passing_over_the_others(self):
        start = self.fake.say(GENERAL, OWNER, 'go')
        self.fake.say(GENERAL, STRANGER, 'noise')
        self.fake.say(GENERAL, BOT, 'its own')
        self.clock.at(2, lambda: self.arrive(GENERAL, STRANGER, 'more noise'))
        self.clock.at(3, lambda: self.arrive(GENERAL, FRIEND, 'here'))
        got = self.tool('discord_wait', channel=GENERAL, after=start)
        self.assertEqual((got['message']['text'], got['message']['author_id'], got['left_out']), ('here', FRIEND, 2))
        self.assertEqual(got['after'], got['message']['id'])
        self.assertEqual(self.clock.waits, [1.0, 1.0, 1.0])
        self.assertNotIn('noise', json.dumps(got))
        self.assertEqual(len(self.fake.posts('GET', f'/channels/{GENERAL}/messages')), 1)  # the gateway, not polling

    def test_from_waits_only_for_those_authors(self):
        start = self.fake.say(GENERAL, OWNER, 'go')
        self.clock.at(1, lambda: self.arrive(GENERAL, OWNER, 'not this one'))
        self.clock.at(2, lambda: self.arrive(GENERAL, FRIEND, 'this one'))
        got = self.tool('discord_wait', channel=GENERAL, after=start, **{'from': [FRIEND]})
        self.assertEqual((got['message']['text'], got['left_out']), ('this one', 1))
        said = self.error('discord_wait', channel=GENERAL, after=start, **{'from': [STRANGER]})
        self.assertIn(f'from item 1 is {STRANGER}, neither the owner', said)

    def test_none_in_time_says_so_with_the_id_to_wait_after_next(self):
        start = self.fake.say(GENERAL, OWNER, 'go')
        noise = self.fake.say(GENERAL, STRANGER, 'noise')
        got = self.tool('discord_wait', channel=GENERAL, after=start, wait=5)
        self.assertEqual(got, {'channel': GENERAL, 'message': None, 'waited': 5, 'left_out': 1, 'after': noise})

    def test_what_came_before_it_listened_is_read_from_rest_page_after_page(self):
        start = self.fake.say(GENERAL, OWNER, 'go')
        for n in range(150):
            self.fake.say(GENERAL, STRANGER, f'noise {n}')
        self.fake.say(GENERAL, OWNER, 'mine')
        got = self.tool('discord_wait', channel=GENERAL, after=start)
        self.assertEqual((got['message']['text'], got['left_out'], self.clock.waits), ('mine', 150, []))

    def test_a_new_gateway_session_reads_what_went_unheard(self):
        start = self.fake.say(GENERAL, OWNER, 'go')

        def unheard():
            self.fake.say(GENERAL, FRIEND, 'said while the gateway was down')
            self.bot.hub.gap()

        self.clock.at(2, unheard)
        got = self.tool('discord_wait', channel=GENERAL, after=start)
        self.assertEqual(got['message']['text'], 'said while the gateway was down')

    def test_a_thread_of_a_listed_channel_and_the_owners_dm(self):
        start = self.fake.say(THREAD, FRIEND, 'start')
        self.clock.at(3, lambda: self.arrive(THREAD, OWNER, 'in the thread'))
        self.assertEqual(self.tool('discord_wait', channel=THREAD, after=start)['message']['text'], 'in the thread')
        start = self.fake.say(DM, BOT, 'a draft')
        self.clock.at(6, lambda: self.arrive(DM, OWNER, 'answer in the DMs'))
        self.assertEqual(self.tool('discord_wait', channel=DM, after=start)['message']['text'], 'answer in the DMs')
        self.assertIn('may read', self.error('discord_wait', channel=OTHER, after=start))

    def test_a_stopped_gateway_is_an_error_naming_why(self):
        start = self.fake.say(GENERAL, OWNER, 'go')
        self.clock.at(2, lambda: self.bot.hub.stop('Discord closed the gateway with 4014: disallowed intents'))
        said = self.error('discord_wait', channel=GENERAL, after=start)
        self.assertEqual(
            said,
            'the gateway stopped (Discord closed the gateway with 4014: disallowed intents): discord_wait hears '
            'nothing; discord_read reads',
        )


class RateLimits(WithDiscord):
    def test_a_429_waits_its_retry_after_and_tries_again(self):
        self.fake.say(GENERAL, OWNER, 'hello')
        self.fake.limits.append(('GET', f'/channels/{GENERAL}/messages'))
        got = self.tool('discord_read', channel=GENERAL)
        self.assertEqual([m['text'] for m in got['messages']], ['hello'])
        self.assertEqual(self.clock.waits, [1.5])
        self.assertEqual(len(self.fake.posts('GET', f'/channels/{GENERAL}/messages')), 2)

    def test_429s_without_end_and_other_failures_are_errors_with_discords_status_and_message(self):
        self.fake.limits.extend([('GET', f'/channels/{GENERAL}/messages')] * aw.TRIES)
        said = self.error('discord_read', channel=GENERAL)
        self.assertIn(f'Discord answered 429 to GET /channels/{GENERAL}/messages 5 times', said)
        self.fake.fail[('GET', f'/channels/{HELP}/messages')] = (403, {'message': 'Missing Access', 'code': 50001})
        said = self.error('discord_read', channel=HELP)
        self.assertEqual(said, f'Discord answered 403 to GET /channels/{HELP}/messages: Missing Access (code 50001)')

    def test_an_invalid_form_body_names_its_fields(self):
        errors = {'content': {'_errors': [{'message': 'Must be 2000 or fewer in length.'}]}}
        said = aw.reason({'code': 50035, 'message': 'Invalid Form Body', 'errors': errors})
        self.assertEqual(said, 'Invalid Form Body (code 50035): content: Must be 2000 or fewer in length.')


class Protocol(WithDiscord):
    """the JSON-RPC answers, in process"""

    def ask(self, method, params=None, rid=1, server=None):
        message = {'jsonrpc': '2.0', 'id': rid, 'method': method}
        if params is not None:
            message['params'] = params
        return (server or self.server).handle(message)

    def test_initialize_answers_the_clients_version_when_it_has_it_else_its_newest_and_says_it_is_a_channel(self):
        for asked, agreed in (('2025-06-18', '2025-06-18'), ('2024-11-05', '2024-11-05'), ('2026-07-28', '2025-11-25')):
            server = aw.Server(self.bot, 'test', self.sent.append)
            params = dict(INITIALIZE, protocolVersion=asked)
            result = self.ask('initialize', params, server=server)['result']
            self.assertEqual(result['protocolVersion'], agreed)
            self.assertEqual(result['capabilities'], {'tools': {}, 'experimental': {'claude/channel': {}}})
            self.assertEqual(result['serverInfo']['name'], 'aogowimsy')
        self.assertEqual(self.ask('initialize', {})['error']['code'], -32602)

    def test_2026_07_28_is_not_spoken_so_a_client_falls_back_to_initialize(self):
        server = aw.Server(self.bot, 'test', self.sent.append)
        meta = {
            'io.modelcontextprotocol/protocolVersion': '2026-07-28',
            'io.modelcontextprotocol/clientCapabilities': {},
        }
        error = self.ask('server/discover', {'_meta': meta}, server=server)['error']
        self.assertEqual(error['code'], -32601)
        self.assertIn(
            'speaks the initialize handshake (2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05)', error['message']
        )
        error = self.ask('tools/list', {'_meta': meta}, server=server)['error']
        self.assertEqual(error['code'], -32602)
        self.assertIn('tools/list came before initialize; AogoWimsy speaks 2025-11-25', error['message'])
        self.assertEqual(self.ask('ping', server=server), {'jsonrpc': '2.0', 'id': 1, 'result': {}})
        self.assertEqual(self.ask('tools/list')['result'], {'tools': aw.tool_list(aw.AOGO)})

    def test_it_starts_hearing_discord_once_the_client_is_initialized_and_only_then(self):
        calls = []

        def listen(push):
            calls.append(push)
            return [aw.started(lambda: None)]

        server = aw.Server(self.bot, 'test', self.sent.append, listen=listen)
        server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual(calls, [])  # no initialize yet
        self.ask('initialize', INITIALIZE, server=server)
        self.assertEqual(calls, [])
        server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual(calls, [server.push])
        calls[0]('a text', {'kind': 'message'})
        self.assertEqual(
            self.sent[-1],
            {
                'jsonrpc': '2.0',
                'method': 'notifications/claude/channel',
                'params': {'content': 'a text', 'meta': {'kind': 'message'}},
            },
        )
        server.stop()
        self.assertTrue(server.stopping.is_set())

    def test_methods_it_has_not_and_unknown_tools(self):
        error = self.ask('resources/list')['error']
        self.assertEqual(error['code'], -32601)
        self.assertIn('"resources/list"; AogoWimsy answers initialize, ping, tools/list, tools/call', error['message'])
        error = self.ask('tools/call', {'name': 'discord_delete', 'arguments': {}})['error']
        self.assertEqual(error['code'], -32602)
        self.assertIn('Unknown tool: "discord_delete"; AogoWimsy has discord_post', error['message'])
        self.assertEqual(self.ask('tools/list', {'cursor': 'x'})['error']['code'], -32602)

    def test_notifications_and_bad_messages(self):
        self.assertIsNone(self.server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))
        cancel = {'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': 9}}
        self.assertIsNone(self.server.handle(cancel))
        self.assertEqual(self.server.handle({'id': 1, 'method': 'ping'})['error']['code'], -32600)
        self.assertEqual(self.server.handle({'jsonrpc': '2.0', 'id': None, 'method': 'ping'})['error']['code'], -32600)
        params = {'jsonrpc': '2.0', 'id': 2, 'method': 'ping', 'params': [1]}
        self.assertEqual(self.server.handle(params)['error']['code'], -32602)

    def test_a_cancelled_wait_stops_and_gets_no_answer(self):
        cancelled = threading.Event()
        self.clock.at(2, cancelled.set)
        start = self.fake.say(GENERAL, OWNER, 'go')
        self.assertIsNone(self.answer('discord_wait', cancelled=cancelled, channel=GENERAL, after=start))
        self.assertEqual(self.clock.waits, [1.0, 1.0])

    def test_progress_when_asked_for_it_always_growing(self):
        start = self.fake.say(GENERAL, OWNER, 'go')
        self.clock.at(3, lambda: self.arrive(GENERAL, FRIEND, 'here'))
        answer = self.answer('discord_wait', meta={'progressToken': 'p1'}, channel=GENERAL, after=start)
        here = json.loads(answer['result']['content'][0]['text'])['message']
        self.assertEqual(here['text'], 'here')
        sent = [(n['params']['progressToken'], n['params']['progress'], n['params']['total']) for n in self.sent]
        self.assertEqual(sent, [('p1', 1.0, 600), ('p1', 2.0, 600), ('p1', 3.0, 600)])
        self.assertTrue(all(n['method'] == 'notifications/progress' for n in self.sent))
        self.assertIsNone(self.tool('discord_wait', channel=GENERAL, after=here['id'], wait=2)['message'])
        self.assertEqual(len(self.sent), 3)  # asked for none: none sent

    def test_progress_never_repeats_nor_goes_back_and_stops_once_cancelled(self):
        cancelled = threading.Event()
        send = self.server.progress(5, cancelled)
        for done in (1.0, 1.02, 0.5, 2.0):
            send(done, 10, 'waiting')
        cancelled.set()
        send(3.0, 10, 'waiting')
        self.assertEqual([n['params']['progress'] for n in self.sent], [1.0, 2.0])


class Hearing(WithDiscord):
    """an ear on the gateway's events, after READY and the server's GUILD_CREATE"""

    def setUp(self):
        super().setUp()
        self.pushes = []
        self.ear = aw.Ear(self.bot, lambda text, meta: self.pushes.append((text, meta)), threading.Event())
        self.ear.hear('READY', READY)
        guild = {'id': GUILD, 'channels': [self.fake.channels[c] for c in (GENERAL, HELP, OTHER)]}
        guild['threads'] = [self.fake.channels[THREAD], self.fake.channels[OTHER_THREAD]]
        self.ear.hear('GUILD_CREATE', guild)  # which registers /aogo there
        self.logs.clear()

    def heard(self, channel, author, content='', **extra):
        number = self.fake.say(channel, author, content, **extra)
        self.ear.hear('MESSAGE_CREATE', self.fake.event(channel, number))
        return number

    def reacted(self, channel, message, emoji, who):
        self.fake.react(message, emoji, who)
        name, _, number = emoji.partition(':')
        event = {'user_id': who, 'channel_id': channel, 'message_id': message}
        if self.fake.channels[channel].get('guild_id'):
            event['guild_id'] = self.fake.channels[channel]['guild_id']
        self.ear.hear('MESSAGE_REACTION_ADD', dict(event, emoji={'id': number or None, 'name': name}))


class Channels(Hearing):
    """what the gateway hears and what reaches the session as a channel event"""

    def test_the_owners_answer_to_a_draft_posts_it_at_once_with_no_tool_waiting(self):
        draft = self.tool('discord_post', channel=GENERAL, text='approved later', wait=0)['draft']
        refused = self.tool('discord_post', channel=HELP, text='refused later', wait=0)['draft']
        self.reacted(DM, draft, YES, STRANGER)
        self.reacted(DM, draft, YES, BOT)
        self.assertEqual((self.fake.messages[GENERAL], self.pushes), ([], []))
        self.reacted(DM, draft, YES, OWNER)
        posted = self.fake.last(GENERAL)
        self.assertEqual((posted['content'], len(self.fake.messages[GENERAL])), ('approved later', 1))
        sent = f'https://discord.com/channels/{GUILD}/{GENERAL}/{posted["id"]}'
        meta = {'kind': 'draft', 'draft': draft, 'status': 'sent', 'channel': GENERAL, 'message_id': posted['id']}
        self.assertEqual(self.pushes, [(f'The owner approved draft {draft}: posted as {sent}', meta)])
        self.reacted(DM, draft, YES, OWNER)  # the event again, or a tool that saw it first: never twice
        self.assertEqual((len(self.fake.messages[GENERAL]), len(self.pushes)), (1, 1))
        self.assertEqual(self.tool('discord_post_status', draft=draft, wait=0)['message'], posted['id'])
        self.reacted(DM, refused, NO, OWNER)
        self.assertEqual(self.fake.messages[HELP], [])
        self.assertEqual(self.fake.footer(self.fake.find(DM, refused)), f'not sent: to {HELP}')
        meta = {'kind': 'draft', 'draft': refused, 'status': 'not sent', 'channel': HELP}
        self.assertEqual(self.pushes[1:], [(f'The owner refused draft {refused}: not posted to channel {HELP}', meta)])
        mine = self.fake.say(DM, OWNER, 'not a draft')
        self.reacted(DM, mine, YES, OWNER)
        self.assertEqual(len(self.pushes), 2)

    def test_a_draft_another_session_made_waits_for_that_sessions_look(self):
        other = aw.Wimsy(self.settings, aw.Discord(TOKEN, self.clock, self.api), self.clock)
        self.server = self.started_server(other)
        draft = self.tool('discord_post', channel=GENERAL, text='from another session', wait=0)['draft']
        self.reacted(DM, draft, YES, OWNER)  # this session's ear: not its draft
        self.assertEqual((self.fake.messages[GENERAL], self.pushes), ([], []))
        self.assertEqual(self.tool('discord_post_status', draft=draft, wait=0)['status'], 'sent')
        self.assertEqual(len(self.fake.messages[GENERAL]), 1)

    def test_a_reply_to_aogo_from_the_owner_is_pushed_once_with_its_fields(self):
        mine = self.fake.say(GENERAL, BOT, 'a post of mine')
        files = [{'filename': 'log;1\n.txt'}, {'filename': 'shot.png'}]
        number = self.heard(GENERAL, OWNER, 'is this it?', reply_to=mine, attachments=files)
        meta = {'kind': 'message', 'author': 'DraVee', 'author_id': OWNER, 'channel': GENERAL, 'message_id': number}
        meta.update(reply_to=mine, attachments='log_1_.txt; shot.png')
        self.assertEqual(self.pushes, [('is this it?', meta)])
        self.assertEqual(self.logs, ['channel: pushed a message event'])

    def test_a_mention_from_a_listed_user_is_pushed(self):
        number = self.heard(HELP, FRIEND, '<@1000000000000000001> look', mentions=[BOT])
        meta = {'kind': 'message', 'author': 'friend', 'author_id': FRIEND, 'channel': HELP, 'message_id': number}
        self.assertEqual(self.pushes, [('<@1000000000000000001> look', meta)])

    def test_a_mention_of_aogos_role_is_a_mention_of_aogo(self):
        number = self.heard(HELP, FRIEND, f'<@&{BOT_ROLE}> look', mention_roles=[BOT_ROLE])
        meta = {'kind': 'message', 'author': 'friend', 'author_id': FRIEND, 'channel': HELP, 'message_id': number}
        self.assertEqual(self.pushes, [(f'<@&{BOT_ROLE}> look', meta)])
        self.heard(HELP, FRIEND, 'another bot, a plain role', mention_roles=[OTHER_BOT_ROLE, HELPERS_ROLE, GUILD])
        self.assertEqual(len(self.pushes), 1)

    def test_the_owners_reply_mentioning_aogos_role_carries_the_message_he_replied_to(self):
        theirs = self.fake.say(GENERAL, STRANGER, 'the percent is the current game only')
        asked = f'<@&{BOT_ROLE}> also fix this'
        number = self.heard(GENERAL, OWNER, asked, reply_to=theirs, mention_roles=[BOT_ROLE])
        quote = f'\n\nReplying to Stranger ({STRANGER}), message {theirs}:\nthe percent is the current game only'
        meta = {'kind': 'message', 'author': 'DraVee', 'author_id': OWNER, 'channel': GENERAL, 'message_id': number}
        meta.update(reply_to=theirs, quoted_author='Stranger', quoted_author_id=STRANGER)
        self.assertEqual(self.pushes, [(asked + quote, meta)])
        self.assertEqual(self.bot.approved, {theirs})

    def test_aogos_roles_are_asked_once_and_again_after_a_server_is_joined(self):
        for _ in range(2):
            self.heard(GENERAL, OWNER, f'<@&{BOT_ROLE}> ping', mention_roles=[BOT_ROLE])
        self.assertEqual(len(self.fake.posts('GET', f'/guilds/{GUILD}/roles')), 1)
        self.fake.server_roles[1] = dict(self.fake.server_roles[1], id=HELPERS_ROLE)  # invited again: a new role
        self.fake.server_roles.pop()
        self.ear.hear('GUILD_CREATE', {'id': GUILD, 'channels': [], 'threads': []})
        self.heard(GENERAL, OWNER, f'<@&{BOT_ROLE}> the old role', mention_roles=[BOT_ROLE])
        self.heard(GENERAL, OWNER, f'<@&{HELPERS_ROLE}> the new one', mention_roles=[HELPERS_ROLE])
        self.assertEqual([text for text, _ in self.pushes][2:], [f'<@&{HELPERS_ROLE}> the new one'])
        self.assertEqual(len(self.fake.posts('GET', f'/guilds/{GUILD}/roles')), 2)

    def test_a_message_not_addressed_to_aogo_is_not_pushed(self):
        theirs = self.fake.say(GENERAL, FRIEND, 'a post of a friend')
        self.heard(GENERAL, OWNER, 'talking to the room')
        self.heard(GENERAL, OWNER, 'answering the friend', reply_to=theirs)
        self.heard(GENERAL, OWNER, 'naming someone', mentions=[FRIEND])
        self.heard(GENERAL, BOT, 'its own, naming itself', mentions=[BOT])
        self.assertEqual(self.pushes, [])

    def test_a_strangers_message_to_aogo_reaches_the_session_only_on_the_owners_wimsy_once(self):
        mine = self.fake.say(GENERAL, BOT, 'a post of mine')
        quoted = self.heard(GENERAL, STRANGER, 'quoting you', reply_to=mine)
        self.assertEqual(self.pushes, [])
        self.reacted(GENERAL, quoted, WIMSY, OTHER_PERSON)
        self.reacted(GENERAL, quoted, OTHER_EMOJI, OWNER)
        self.reacted(GENERAL, quoted, YES, OWNER)
        self.assertEqual(self.pushes, [])
        self.reacted(GENERAL, quoted, WIMSY, OWNER)
        meta = {'kind': 'approved', 'author': 'Stranger', 'author_id': STRANGER, 'channel': GENERAL}
        meta.update(message_id=quoted, reply_to=mine)
        self.assertEqual(self.pushes, [('quoting you', meta)])
        self.reacted(GENERAL, quoted, WIMSY, OWNER)
        self.assertEqual(len(self.pushes), 1)

    def test_the_owners_reply_mentioning_aogo_carries_the_message_he_replied_to_and_lets_it_through(self):
        before = self.fake.say(GENERAL, FRIEND, 'before')
        theirs = self.fake.say(GENERAL, STRANGER, 'a question for the room', attachments=[{'filename': 'crash.log'}])
        asked = 'Gonna ask <@1000000000000000001>, lets see if this works'
        number = self.heard(GENERAL, OWNER, asked, reply_to=theirs, mentions=[STRANGER, BOT])
        quote = f'\n\nReplying to Stranger ({STRANGER}), message {theirs}:\na question for the room'
        meta = {'kind': 'message', 'author': 'DraVee', 'author_id': OWNER, 'channel': GENERAL, 'message_id': number}
        meta.update(
            reply_to=theirs, quoted_author='Stranger', quoted_author_id=STRANGER, quoted_attachments='crash.log'
        )
        self.assertEqual(self.pushes, [(asked + quote, meta)])
        self.assertEqual(self.bot.approved, {theirs})
        self.reacted(GENERAL, theirs, WIMSY, OWNER)  # through already: once
        self.assertEqual(len(self.pushes), 1)
        got = self.tool('discord_read', channel=GENERAL, after=before)
        self.assertEqual([(m['id'], m['approved']) for m in got['messages']], [(theirs, True), (number, False)])
        self.assertEqual(got['left_out'], 0)
        alone = self.tool('discord_read', channel=GENERAL, after=before, limit=1)  # his reply is not in this page
        self.assertEqual([(m['id'], m['approved']) for m in alone['messages']], [(theirs, True)])

    def test_a_reply_whose_answered_message_the_event_lacks_reads_it_from_discord(self):
        theirs = self.fake.say(GENERAL, STRANGER, 'asked before')
        number = self.fake.say(GENERAL, OWNER, 'see this <@1000000000000000001>', reply_to=theirs, mentions=[BOT])
        event = self.fake.event(GENERAL, number)
        del event['referenced_message']
        self.ear.hear('MESSAGE_CREATE', event)
        self.assertTrue(self.pushes[0][0].endswith(f'message {theirs}:\nasked before'))
        self.assertEqual(len(self.fake.posts('GET', f'/channels/{GENERAL}/messages/{theirs}')), 1)

    def test_only_the_owners_reply_with_a_mention_lets_a_message_through(self):
        theirs = self.fake.say(GENERAL, STRANGER, 'a question for the room')
        self.heard(GENERAL, FRIEND, 'asking <@1000000000000000001>', reply_to=theirs, mentions=[BOT])
        self.heard(GENERAL, OWNER, 'answering them, no mention', reply_to=theirs)
        self.assertEqual(
            [(text, 'quoted_author_id' in meta) for text, meta in self.pushes],
            [('asking <@1000000000000000001>', False)],
        )
        self.assertEqual(self.bot.approved, set())
        self.assertNotIn(theirs, [m['id'] for m in self.tool('discord_read', channel=GENERAL)['messages']])

    def test_the_owners_wimsy_elsewhere_pushes_nothing(self):
        plain = self.heard(GENERAL, STRANGER, 'not to aogo')
        own = self.heard(GENERAL, OWNER, 'his own, to aogo', mentions=[BOT])
        outside = self.heard(OTHER, STRANGER, 'to aogo, in a channel not listed', mentions=[BOT])
        self.pushes.clear()
        for channel, message in ((GENERAL, plain), (GENERAL, own), (OTHER, outside)):
            self.reacted(channel, message, WIMSY, OWNER)
        self.assertEqual(self.pushes, [])

    def test_the_owners_and_a_listed_users_dms_are_pushed_a_strangers_only_says_who_once(self):
        self.heard(DM, BOT, 'a draft of its own, as the gateway brings it back')
        self.heard(DM, OWNER, 'in my DMs')
        self.heard(FRIEND_DM, FRIEND, 'in the friend DMs')
        self.heard(STRANGER_DM, STRANGER, 'a secret to aogo')
        self.heard(STRANGER_DM, STRANGER, 'and another')
        self.assertEqual(
            [(text, meta['kind']) for text, meta in self.pushes[:2]],
            [('in my DMs', 'message'), ('in the friend DMs', 'message')],
        )
        knock = f'Stranger ({STRANGER}) wrote to AogoWimsy in DMs; nothing of what they wrote reaches the session'
        self.assertEqual(self.pushes[2:], [(knock, {'kind': 'dm', 'author': 'Stranger', 'author_id': STRANGER})])
        self.assertNotIn('secret', json.dumps(self.pushes))

    def test_with_channels_listed_their_threads_count_and_others_do_not(self):
        self.heard(OTHER, OWNER, 'to aogo elsewhere', mentions=[BOT])
        self.heard(OTHER_THREAD, OWNER, 'to aogo in a thread elsewhere', mentions=[BOT])
        self.assertEqual(self.pushes, [])
        self.heard(THREAD, OWNER, 'to aogo in a thread of general', mentions=[BOT])
        self.assertEqual([text for text, _ in self.pushes], ['to aogo in a thread of general'])
        self.assertFalse(self.fake.posts('GET', f'/channels/{THREAD}'))  # known from GUILD_CREATE
        self.heard(NEW_THREAD, FRIEND, 'to aogo in a new thread of help', mentions=[BOT])
        self.assertEqual(self.pushes[-1][0], 'to aogo in a new thread of help')
        self.assertEqual(len(self.fake.posts('GET', f'/channels/{NEW_THREAD}')), 1)  # asked once
        self.heard(NEW_THREAD, FRIEND, 'again', mentions=[BOT])
        self.assertEqual(len(self.fake.posts('GET', f'/channels/{NEW_THREAD}')), 1)

    def test_with_no_channels_listed_every_channel_it_sees_counts(self):
        self.bot.settings = self.settings._replace(channels=None)
        self.heard(OTHER, OWNER, 'to aogo anywhere', mentions=[BOT])
        self.assertEqual([text for text, _ in self.pushes], ['to aogo anywhere'])

    def test_ready_and_the_guilds_push_nothing_and_ready_makes_the_waits_read_again(self):
        self.assertEqual(self.pushes, [])
        with self.bot.hub.listening(GENERAL) as inbox:
            inbox.take()
            self.ear.hear('READY', {'user': {'id': BOT}})
            self.assertEqual(inbox.take(), ([], True))

    def test_the_gateway_stopping_tells_the_session_and_the_waits(self):
        self.ear.report('stopped', 'Discord closed the gateway with 4004')
        self.assertEqual(self.bot.hub.stopped, 'Discord closed the gateway with 4004')
        self.assertEqual(self.pushes[0][1], {'kind': 'error'})
        self.assertIn('AogoWimsy stopped hearing Discord: Discord closed the gateway with 4004', self.pushes[0][0])

    def test_the_ear_runs_apart_from_the_gateway_and_stops(self):
        stop = threading.Event()
        pushes = queue.Queue()
        ear = aw.Ear(self.bot, lambda text, meta: pushes.put(text), stop)
        thread = aw.started(ear.run)
        number = self.fake.say(GENERAL, OWNER, 'to aogo', mentions=[BOT])
        ear.feed('MESSAGE_CREATE', self.fake.event(GENERAL, number))
        self.assertEqual(pushes.get(timeout=5), 'to aogo')
        ear.feed('MESSAGE_CREATE', {'channel_id': GENERAL, 'guild_id': GUILD})
        self.assertEqual(pushes.get(timeout=5), "AogoWimsy could not sort a MESSAGE_CREATE event: KeyError: 'author'")
        number = self.fake.say(GENERAL, FRIEND, 'still hearing', mentions=[BOT])
        ear.feed('MESSAGE_CREATE', self.fake.event(GENERAL, number))
        self.assertEqual(pushes.get(timeout=5), 'still hearing')
        stop.set()
        thread.join(5)
        self.assertFalse(thread.is_alive())


class Greet(Hearing):
    """a stranger who calls AogoWimsy gets the fixed line at once, within its limits, and the session hears nothing"""

    CALL = '<@1000000000000000001> who is this?'

    def setUp(self):
        super().setUp()
        self.start = self.now = 1_800_000_000.0
        self.bot.store.now = lambda: self.now

    def greetings(self, channel=GENERAL):
        """what AogoWimsy posted in a channel: the bodies of its POSTs"""
        return [body for _, _, _, body in self.fake.posts('POST', f'/channels/{channel}/messages')]

    def answered(self, channel=GENERAL):
        """the messages each greeting in a channel replies to"""
        return [body['message_reference']['message_id'] for body in self.greetings(channel)]

    def call(self, who=STRANGER, channel=GENERAL):
        return self.heard(channel, who, self.CALL, mentions=[BOT])

    def counted(self, why, channel=GENERAL):
        return f"greet: a stranger's call in channel {channel} is only counted: {why}"

    def restarted(self, now):
        """another server of the bot, as after a restart or in another session: the same state folder"""
        fresh = aw.Wimsy(self.settings, aw.Discord(TOKEN, self.clock, self.api), self.clock)
        fresh.store.now = lambda: now
        ear = aw.Ear(fresh, lambda text, meta: self.pushes.append((text, meta)), threading.Event())
        ear.hear('READY', READY)
        return ear

    def test_a_strangers_mention_gets_the_line_at_once_as_a_reply_pinging_the_owner_alone(self):
        number = self.call()
        reference = {'message_id': number, 'channel_id': GENERAL, 'fail_if_not_exists': True}
        self.assertEqual(
            self.greetings(), [{'content': LINE, 'allowed_mentions': PINGS, 'message_reference': reference}]
        )
        posted = self.fake.last(GENERAL)
        self.assertEqual((posted['author'], posted['message_reference']['message_id']), (BOT, number))
        self.assertEqual(self.pushes, [])  # the session hears nothing of it
        self.assertEqual((self.fake.messages[DM], self.fake.posts('POST', '/users/@me/channels')), ([], []))  # no DM
        said = f"greet: posted message {posted['id']} replying to a stranger's call in channel {GENERAL} (1 of 10 "
        self.assertEqual([line for line in self.logs if line.startswith('greet')], [said + 'in the last hour)'])
        role = self.heard(HELP, OTHER_PERSON, f'<@&{BOT_ROLE}> and you?', mention_roles=[BOT_ROLE])
        self.assertEqual(self.answered(HELP), [role])  # its role, as Discord's autocomplete picks it, calls it too
        self.assertNotIn(STRANGER, ' '.join(self.logs))
        self.assertNotIn('who is this', ' '.join(self.logs))

    def test_a_reply_to_one_of_its_messages_calls_it_in_a_listed_channel_or_its_thread(self):
        mine = self.fake.say(GENERAL, BOT, 'a post of mine')
        theirs = self.fake.say(GENERAL, FRIEND, 'a post of a friend')
        self.heard(GENERAL, OTHER_PERSON, 'answering the friend', reply_to=theirs)
        self.assertEqual(self.greetings(), [])
        number = self.heard(GENERAL, STRANGER, 'what is this bot?', reply_to=mine)
        self.assertEqual(
            [(body['content'], body['message_reference']['message_id']) for body in self.greetings()], [(LINE, number)]
        )
        in_thread = self.call(OTHER_PERSON, THREAD)
        self.assertEqual(self.answered(THREAD), [in_thread])
        self.assertEqual(self.pushes, [])

    def test_a_second_call_within_24_hours_is_only_counted_and_one_after_them_is_greeted(self):
        before = self.fake.say(GENERAL, FRIEND, 'before')
        first = self.call()
        greeting = self.fake.last(GENERAL)['id']
        self.now += 23 * 3600 + 59 * 60 + 59
        self.heard(GENERAL, STRANGER, 'thanks', reply_to=greeting)  # a reply to the greeting calls it too: no loop
        self.call()
        self.assertEqual(self.answered(), [first])
        late = self.counted('the caller was greeted 23 h 59 min ago: once each 24 h')
        self.assertEqual([line for line in self.logs if 'only counted' in line], [late, late])
        got = self.tool('discord_read', channel=GENERAL, after=before)
        self.assertEqual([m['author_id'] for m in got['messages']], [BOT])  # its greeting; the calls are counted
        self.assertEqual(got['left_out'], 3)
        self.now += 2
        again = self.call()
        self.assertEqual(self.answered(), [first, again])
        self.assertEqual(self.pushes, [])

    def test_the_eleventh_stranger_within_an_hour_is_only_counted_and_the_hour_rolls_on(self):
        called = []
        for caller in CALLERS[:11]:
            called.append(self.call(caller))
            self.now += 300  # five minutes apart: the eleventh at 50 minutes
        self.assertEqual(self.answered(), called[:10])
        self.assertEqual(self.logs[-1], self.counted('10 greetings in the last hour: 10 at most'))
        self.now = self.start + 3601  # the first greeting is over an hour old
        late = self.call(CALLERS[11])
        self.assertEqual(self.answered(), called[:10] + [late])
        self.assertTrue(self.logs[-1].endswith('(10 of 10 in the last hour)'), self.logs[-1])
        self.assertEqual(self.pushes, [])

    def test_the_owner_and_listed_users_reach_the_session_and_get_no_greeting(self):
        self.call(OWNER)
        self.call(FRIEND)
        self.assertEqual([(text, meta['kind']) for text, meta in self.pushes], [(self.CALL, 'message')] * 2)
        self.assertEqual(self.greetings(), [])
        self.assertFalse((self.state / 'greetings.json').exists())

    def test_the_owners_wimsy_still_lets_a_greeted_call_through_to_the_session(self):
        number = self.call()
        self.assertEqual(self.answered(), [number])
        self.reacted(GENERAL, number, WIMSY, OWNER)
        meta = {'kind': 'approved', 'author': 'Stranger', 'author_id': STRANGER, 'channel': GENERAL}
        self.assertEqual(self.pushes, [(self.CALL, dict(meta, message_id=number))])
        got = self.tool('discord_read', channel=GENERAL)
        self.assertEqual([(m['id'], m['approved']) for m in got['messages']], [(number, True), (got['after'], False)])
        self.assertEqual(self.answered(), [number])  # greeted once

    def test_a_restart_keeps_the_limits_in_a_private_file(self):
        callers = [STRANGER] + CALLERS[:9]
        for caller in callers:
            self.call(caller)
        self.assertEqual(len(self.greetings()), 10)
        path = self.state / 'greetings.json'
        self.assertEqual(json.loads(path.read_text()), {'greetings': [[self.now, caller] for caller in callers]})
        modes = stat.S_IMODE(path.stat().st_mode), stat.S_IMODE(self.state.stat().st_mode)
        self.assertEqual(modes, (0o600, 0o700))
        self.ear = self.restarted(self.now + 1800)
        self.call()  # once each 24 h, across the restart
        self.call(OTHER_PERSON)  # and the eleventh within the hour
        self.assertEqual(len(self.greetings()), 10)
        said = [self.counted('the caller was greeted 0 h 30 min ago: once each 24 h')]
        said.append(self.counted('10 greetings in the last hour: 10 at most'))
        self.assertEqual(self.logs[-2:], said)
        self.ear = self.restarted(self.now + 25 * 3600)  # a day on, the file still holds the old greetings
        self.call()
        self.assertEqual(len(self.greetings()), 11)
        self.assertEqual(json.loads(path.read_text()), {'greetings': [[self.now + 25 * 3600, STRANGER]]})

    def test_two_servers_hearing_one_call_greet_it_once(self):
        other = self.restarted(self.now)  # another session's server, on the same gateway events
        number = self.fake.say(GENERAL, STRANGER, self.CALL, mentions=[BOT])
        for ear in (self.ear, other):
            ear.hear('MESSAGE_CREATE', self.fake.event(GENERAL, number))
        self.assertEqual(self.answered(), [number])
        self.assertEqual(self.logs[-1], self.counted('the caller was greeted 0 h 00 min ago: once each 24 h'))

    def test_a_look_waits_while_another_server_holds_the_lock(self):
        aw.private_folder(self.state)
        held = os.open(self.state / aw.STATE_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
        got = []
        try:
            fcntl.flock(held, fcntl.LOCK_EX)
            looking = aw.started(lambda: got.append(self.bot.limit('greetings', STRANGER)))
            looking.join(0.3)
            self.assertTrue(looking.is_alive())  # waiting for the other server's look to end
            self.assertEqual(got, [])
        finally:
            fcntl.flock(held, fcntl.LOCK_UN)
            os.close(held)
        looking.join(5)
        self.assertEqual(got, [(None, 1)])

    def test_what_is_not_a_strangers_call_where_it_reads_gets_nothing(self):
        mine = self.fake.say(GENERAL, BOT, 'a post of mine')
        self.heard(GENERAL, STRANGER, 'talking to the room')
        self.heard(GENERAL, STRANGER, 'naming someone', mentions=[FRIEND])
        self.heard(GENERAL, STRANGER, '@everyone look', mention_everyone=True)
        self.heard(GENERAL, STRANGER, 'another bot, a plain role', mention_roles=[OTHER_BOT_ROLE, HELPERS_ROLE])
        self.call(STRANGER, OTHER)  # a channel not listed
        self.call(STRANGER, OTHER_THREAD)  # a thread of one not listed
        self.call(OTHER_BOT)  # a bot: two bots would greet each other
        self.heard(GENERAL, OTHER_BOT, 'its answer', reply_to=mine)
        self.heard(GENERAL, CALLERS[0], self.CALL, mentions=[BOT], webhook_id='800000000000000001')
        self.heard(STRANGER_DM, STRANGER, 'in DMs, to aogo')
        for channel in (GENERAL, OTHER, OTHER_THREAD, STRANGER_DM):
            self.assertEqual(self.greetings(channel), [])
        self.assertEqual([meta['kind'] for _, meta in self.pushes], ['dm'])  # a stranger's DM: its name, as before
        self.assertFalse((self.state / 'greetings.json').exists())

    def test_a_greeting_discord_refuses_is_an_error_to_the_session_and_counts(self):
        route = ('POST', f'/channels/{GENERAL}/messages')
        self.fake.fail[route] = (403, {'message': 'Missing Permissions', 'code': 50013})
        self.call()
        said = (
            f'AogoWimsy could not greet a stranger who called it in channel {GENERAL}: Discord answered 403 to POST '
            f'/channels/{GENERAL}/messages: Missing Permissions (code 50013); the call counts toward the limits'
        )
        self.assertEqual(self.pushes, [(said, {'kind': 'error'})])
        del self.fake.fail[route]
        self.call()
        self.assertEqual([m for m in self.fake.messages[GENERAL] if m['author'] == BOT], [])
        self.assertEqual(self.logs[-1], self.counted('the caller was greeted 0 h 00 min ago: once each 24 h'))

    def test_a_greetings_file_it_cannot_read_stops_the_greetings_says_so_and_stays(self):
        aw.private_folder(self.state)
        path = self.state / 'greetings.json'
        cases = (
            ('{"greetings": [[1, "x"]', 'is not JSON (Expecting'),
            ('[]', 'holds [], not {"greetings": [[time, person id], ...]}'),
            (json.dumps({'greetings': [[True, STRANGER]]}), f': item 1 is [true, "{STRANGER}"], not [time, person id]'),
            (json.dumps({'greetings': [[1, 'someone']]}), ': item 1 is [1, "someone"], not [time, person id]'),
        )
        for text, why in cases:
            path.write_text(text)
            self.pushes.clear()
            self.call()
            [(said, meta)] = self.pushes
            self.assertEqual(meta, {'kind': 'error'})
            self.assertIn(f'could not greet a stranger who called it in channel {GENERAL}: {path}', said)
            self.assertIn(why, said)
            self.assertTrue(said.endswith(': no stranger is greeted until it is mended or removed'), said)
            self.assertEqual(path.read_text(), text)  # left for the owner to see
        self.assertEqual(self.greetings(), [])
        path.unlink()
        number = self.call()
        self.assertEqual(self.answered(), [number])

    def test_greet_per_hour_0_greets_no_one_and_greet_hours_sets_the_wait(self):
        self.bot.settings = self.settings._replace(greet_per_hour=0)
        self.call()
        self.assertEqual(self.greetings(), [])
        self.assertEqual(self.logs[-1], self.counted('AOGOWIMSY_GREET_PER_HOUR is 0'))
        self.assertFalse(self.state.exists())
        self.bot.settings = self.settings._replace(greet_hours=1)
        first = self.call()
        self.now += 1800
        self.call()
        self.assertEqual(self.logs[-1], self.counted('the caller was greeted 0 h 30 min ago: once each 1 h'))
        self.now += 1801
        again = self.call()
        self.assertEqual(self.answered(), [first, again])

    def test_the_instructions_tell_the_session_of_the_greeting_and_its_limits(self):
        said = aw.instructions(self.settings)
        self.assertIn(
            f'gets at once, with no draft and no {YES}, a reply from the server itself that pings the owner alone: '
            f'"{LINE}". Once a person each 24 h, and 10 an hour at most, everyone together; past that the call is only '
            "counted. You are told nothing of the call; the owner's :wimsyaogo: on it still lets it through to you",
            said,
        )
        others = aw.instructions(self.settings._replace(greet_hours=48, greet_per_hour=3))
        self.assertIn('Once a person each 48 h, and 3 an hour at most', others)
        none = aw.instructions(self.settings._replace(greet_per_hour=0))
        self.assertIn('AogoWimsy greets no stranger who calls it (AOGOWIMSY_GREET_PER_HOUR is 0)', none)
        self.assertNotIn(LINE, none)


HELP_TEXT = f'To ask me something, mention <@{BOT}> with what you need; DraVee lets it through.'
OWNERS_HELP = (
    'Yours alone:\n'
    '/aogo allow user [time]: their messages to me reach the session; time 2h, 1d, 7d or perm, 1d without one\n'
    '/aogo deny user: takes their allow back\n'
    '/aogo allowed: who is allowed, and until when'
)
# /aogo as AogoWimsy registers it, word for word
AOGO_COMMAND = {
    'type': 1,
    'name': 'aogo',
    'description': "Aogo, DraVee's AI assistant on ScarletNX",
    'default_member_permissions': None,
    'options': [
        {'type': 1, 'name': 'help', 'description': 'What Aogo is and how to ask it something'},
        {
            'type': 1,
            'name': 'allow',
            'description': "DraVee only: let someone's messages reach Aogo for a time",
            'options': [
                {'type': 6, 'name': 'user', 'description': 'Who to allow', 'required': True},
                {
                    'type': 3,
                    'name': 'time',
                    'description': 'For how long: 1 day without one',
                    'choices': [
                        {'name': '2 hours', 'value': '2h'},
                        {'name': '1 day', 'value': '1d'},
                        {'name': '7 days', 'value': '7d'},
                        {'name': 'permanent', 'value': 'perm'},
                    ],
                },
            ],
        },
        {
            'type': 1,
            'name': 'deny',
            'description': "DraVee only: take someone's allow back",
            'options': [{'type': 6, 'name': 'user', 'description': 'Whose allow to take back', 'required': True}],
        },
        {'type': 1, 'name': 'allowed', 'description': 'DraVee only: who is allowed, and until when'},
    ],
}


class Commands(Hearing):
    """/aogo: registered in each server, help for anyone, allow, deny and allowed for the owner alone"""

    def setUp(self):
        super().setUp()
        self.start = self.now = 1_800_000_000.0
        self.bot.store.now = lambda: self.now

    def used(self, who, sub, channel=GENERAL, name='aogo', **options):
        """a use of the command as the gateway brings it"""
        self.fake.serial += 1
        number = str(self.fake.serial)
        values = [
            {'name': key, 'type': aw.USER_OPTION if key == 'user' else aw.STRING_OPTION, 'value': value}
            for key, value in options.items()
        ]
        data = {'id': '800000000000000000', 'name': name, 'type': 1, 'options': [{'type': 1, 'name': sub}]}
        if values:
            data['options'][0]['options'] = values
        if 'user' in options:
            user = options['user']
            data['resolved'] = {'users': {user: self.fake.user(user)}, 'members': {user: {'nick': None}}}
        return {
            'id': number,
            'application_id': APP,
            'type': aw.APPLICATION_COMMAND,
            'data': data,
            'guild_id': GUILD,
            'channel_id': channel,
            'member': {'user': self.fake.user(who), 'roles': []},
            'token': f'token-{number}',
            'version': 1,
        }

    def use(self, who, sub, ear=None, **options):
        """the answer's text a use of the command got, after the ear heard it"""
        event = self.used(who, sub, **options)
        (ear or self.ear).hear('INTERACTION_CREATE', event)
        answer = self.fake.answers[event['id']]
        self.assertEqual((answer['type'], answer['data']['flags']), (4, 64))  # a message its asker alone sees
        self.assertEqual(answer['data']['allowed_mentions'], {'parse': []})  # pinging no one
        return answer['data']['content']

    def restarted(self, now):
        fresh = aw.Wimsy(self.settings, aw.Discord(TOKEN, self.clock, self.api), self.clock)
        fresh.store.now = lambda: now
        ear = aw.Ear(fresh, lambda text, meta: self.pushes.append((text, meta)), threading.Event())
        ear.hear('READY', READY)
        return fresh, ear

    def notices(self):
        return [(text, meta) for text, meta in self.pushes if meta['kind'] == 'notice']

    def test_the_command_is_registered_in_each_server_as_it_is_and_again_only_when_it_differs(self):
        path = f'/applications/{APP}/guilds/{GUILD}/commands'
        self.assertEqual([body for _, _, _, body in self.fake.posts('PUT', path)], [[AOGO_COMMAND]])
        self.assertEqual(aw.command_list(aw.AOGO), [AOGO_COMMAND])
        self.assertFalse(self.fake.posts('GET', '/applications/@me'))  # READY's application id
        self.ear.hear('GUILD_CREATE', {'id': GUILD, 'channels': [], 'threads': []})  # seen again, or another server
        self.assertEqual((len(self.fake.posts('GET', path)), len(self.fake.posts('PUT', path))), (2, 1))
        self.assertEqual(self.logs, [f'commands: /aogo (help, allow, deny, allowed) already there in server {GUILD}'])
        self.fake.commands[GUILD][0]['description'] = 'an older text'
        self.ear.hear('GUILD_CREATE', {'id': GUILD, 'channels': [], 'threads': []})
        self.assertEqual(len(self.fake.posts('PUT', path)), 2)
        self.fake.commands[GUILD].append(dict(self.fake.commands[GUILD][0], name='old', id='800000000000000999'))
        self.ear.hear('GUILD_CREATE', {'id': GUILD, 'channels': [], 'threads': []})
        self.assertEqual([command['name'] for command in self.fake.commands[GUILD]], ['aogo'])
        self.assertEqual(self.logs[-1], f'commands: /aogo (help, allow, deny, allowed) registered in server {GUILD}')
        self.assertEqual(self.pushes, [])

    def test_a_server_without_the_commands_scope_says_so_with_the_invite_that_gives_it(self):
        self.fake.guild_ids.append(OTHER_GUILD)
        self.fake.no_commands_scope.add(OTHER_GUILD)
        self.ear.hear('GUILD_CREATE', {'id': OTHER_GUILD, 'channels': [], 'threads': []})
        said = (
            f'AogoWimsy could not register /aogo in server {OTHER_GUILD}: Discord answered 403 to GET /applications/'
            f'{APP}/guilds/{OTHER_GUILD}/commands: Missing Access (code 50001): AogoWimsy needs the '
            f'applications.commands scope in server {OTHER_GUILD} for /aogo; invite it again with '
            f'https://discord.com/oauth2/authorize?client_id={APP}&scope=bot+applications.commands'
            '&permissions=9070971030592'
        )
        self.assertEqual(self.pushes, [(said, {'kind': 'error'})])
        self.ear.hear('GUILD_CREATE', {'id': OTHER_GUILD, 'unavailable': True})  # an outage: nothing asked
        self.assertEqual(len(self.pushes), 1)

    def test_without_readys_application_it_is_asked_once(self):
        self.bot.known.pop('application')
        for _ in range(2):
            self.ear.hear('GUILD_CREATE', {'id': GUILD, 'channels': [], 'threads': []})
        self.assertEqual(len(self.fake.posts('GET', '/applications/@me')), 1)

    def test_help_answers_anyone_alone_with_the_greetings_line_and_how_to_ask_the_owner_with_his_commands(self):
        self.assertEqual(self.use(STRANGER, 'help'), f'{LINE}\n{HELP_TEXT}')
        self.assertEqual(self.use(FRIEND, 'help'), f'{LINE}\n{HELP_TEXT}')
        self.assertEqual(self.use(OWNER, 'help'), f'{LINE}\n{HELP_TEXT}\n{OWNERS_HELP}')
        answers = [r for r in self.fake.requests if r[1].startswith('/interactions/')]
        self.assertEqual(len(answers), 3)  # answered without the bot's token: the fake refuses one that has it
        self.assertEqual(self.pushes, [])  # the session hears nothing of a help
        self.assertEqual(self.logs[-1], f'commands: /aogo help answered in channel {GENERAL}')
        self.assertNotIn(STRANGER, ' '.join(self.logs))
        self.assertFalse(any('token-' in line for line in self.logs))

    def test_help_for_a_stranger_keeps_the_greetings_limits_apart_from_the_greeting(self):
        self.heard(GENERAL, STRANGER, '<@1000000000000000001> hi', mentions=[BOT])  # greeted: help is counted apart
        self.assertEqual(self.use(STRANGER, 'help'), f'{LINE}\n{HELP_TEXT}')
        self.now += 1800
        self.assertEqual(self.use(STRANGER, 'help'), 'You asked 0 h 30 min ago: help comes once each 24 h.')
        for caller in CALLERS[:9]:
            self.assertEqual(self.use(caller, 'help'), f'{LINE}\n{HELP_TEXT}')
        self.assertEqual(
            self.use(CALLERS[9], 'help'), 'Help was asked 10 times in the last hour, 10 at most: ask later.'
        )
        for _ in range(3):  # the owner and the listed users are never held back
            self.assertEqual(self.use(OWNER, 'help'), f'{LINE}\n{HELP_TEXT}\n{OWNERS_HELP}')
            self.assertEqual(self.use(FRIEND, 'help'), f'{LINE}\n{HELP_TEXT}')
        self.now += 24 * 3600
        self.assertEqual(self.use(STRANGER, 'help'), f'{LINE}\n{HELP_TEXT}')
        self.bot.settings = self.settings._replace(greet_per_hour=0)
        self.assertEqual(
            self.use(CALLERS[10], 'help'), 'AogoWimsy answers no stranger now: AOGOWIMSY_GREET_PER_HOUR is 0.'
        )

    def test_allow_deny_and_allowed_answer_anyone_but_the_owner_that_they_are_his(self):
        for who in (STRANGER, FRIEND):
            self.assertEqual(self.use(who, 'allow', user=OTHER_PERSON), f'Only <@{OWNER}> can use /aogo allow.')
            self.assertEqual(self.use(who, 'deny', user=OTHER_PERSON), f'Only <@{OWNER}> can use /aogo deny.')
            self.assertEqual(self.use(who, 'allowed'), f'Only <@{OWNER}> can use /aogo allowed.')
        self.assertFalse((self.state / 'allowed.json').exists())
        self.assertEqual(self.pushes, [])

    def test_allow_takes_each_time_and_one_day_without_one_and_refuses_any_other_naming_it(self):
        for time_value, seconds in (('2h', 7200), ('1d', 86400), ('7d', 604800), (None, 86400)):
            options = {'user': STRANGER} if time_value is None else {'user': STRANGER, 'time': time_value}
            said = self.use(OWNER, 'allow', **options)
            until = int(self.now + seconds)
            self.assertTrue(
                said.startswith(f'<@{STRANGER}> is allowed until <t:{until}:f> (<t:{until}:R>): their '), said
            )
            self.assertEqual(self.bot.allowed()[STRANGER]['until'], self.now + seconds)
        said = self.use(OWNER, 'allow', user=STRANGER, time='perm')
        self.assertTrue(said.startswith(f'<@{STRANGER}> is allowed for good, until you deny them: their messages'))
        self.assertIsNone(self.bot.allowed()[STRANGER]['until'])
        for wrong in ('forever', '3h', ''):
            said = self.use(OWNER, 'allow', user=OTHER_PERSON, time=wrong)
            self.assertEqual(said, f'time is "{wrong}", not one of 2h, 1d, 7d, perm: <@{OTHER_PERSON}> is not allowed.')
        self.assertNotIn(OTHER_PERSON, self.bot.allowed())
        self.assertEqual(len(self.notices()), 5)  # the five allows, none of the refused

    def test_an_allow_is_told_to_the_session_and_a_new_one_says_the_one_it_replaces(self):
        said = self.use(OWNER, 'allow', user=STRANGER, time='2h')
        until = int(self.now + 7200)
        self.assertEqual(
            said,
            f'<@{STRANGER}> is allowed until <t:{until}:f> (<t:{until}:R>): their messages to me reach the session.',
        )
        text = (
            f'The owner allowed Stranger ({STRANGER}) until 2027-01-15T10:00:00Z (2 hours): their messages addressed to '
            "AogoWimsy reach you as a listed user's do, and discord_allowed lists them."
        )
        meta = {'kind': 'notice', 'user': 'Stranger', 'user_id': STRANGER, 'until': '2027-01-15T10:00:00Z'}
        self.assertEqual(self.notices(), [(text, meta)])
        self.assertEqual(aw.utc(self.now + 7200), '2027-01-15T10:00:00Z')
        said = self.use(OWNER, 'allow', user=STRANGER, time='perm')
        self.assertTrue(said.endswith(f'It ran until <t:{until}:f> (<t:{until}:R>) before.'), said)
        text, meta = self.notices()[-1]
        self.assertTrue(text.startswith(f'The owner allowed Stranger ({STRANGER}) for good, until he denies them:'))
        self.assertTrue(text.endswith(' It ran until 2027-01-15T10:00:00Z before.'), text)
        self.assertEqual(meta['until'], 'permanent')
        self.assertEqual(self.logs[-1], 'channel: pushed a notice event')

    def test_an_allowed_persons_calls_reach_the_session_as_a_listed_users_until_the_allow_runs_out(self):
        before = self.fake.say(GENERAL, FRIEND, 'before')
        self.use(OWNER, 'allow', user=STRANGER, time='2h')
        self.pushes.clear()
        number = self.heard(GENERAL, STRANGER, '<@1000000000000000001> can you look?', mentions=[BOT])
        meta = {'kind': 'message', 'author': 'Stranger', 'author_id': STRANGER, 'channel': GENERAL}
        self.assertEqual(self.pushes, [('<@1000000000000000001> can you look?', dict(meta, message_id=number))])
        self.heard(GENERAL, OTHER_PERSON, '<@1000000000000000001> and me?', mentions=[BOT])  # a stranger still
        self.assertEqual(len(self.pushes), 1)
        self.assertEqual(len(self.fake.posts('POST', f'/channels/{GENERAL}/messages')), 1)  # its greeting alone
        got = self.tool('discord_read', channel=GENERAL, after=before)
        self.assertIn(number, [m['id'] for m in got['messages']])
        self.assertEqual(
            self.tool('discord_read', channel=GENERAL, after=before, **{'from': [STRANGER]})['messages'][0]['id'],
            number,
        )
        self.now += 7200  # it runs out: nothing is said to them, and they are a stranger again
        self.pushes.clear()
        self.heard(GENERAL, STRANGER, '<@1000000000000000001> still there?', mentions=[BOT])
        self.assertEqual(self.pushes, [])
        self.assertNotIn(
            number, [m['id'] for m in self.tool('discord_read', channel=GENERAL, after=before)['messages']]
        )
        self.assertIn('nor one he allowed', self.error('discord_read', channel=GENERAL, **{'from': [STRANGER]}))
        bodies = [body for _, _, _, body in self.fake.posts('POST', f'/channels/{GENERAL}/messages')]
        self.assertEqual([body['content'] for body in bodies], [LINE, LINE])  # a stranger's call is greeted again

    def test_an_allowed_persons_message_ends_a_wait_and_their_dm_reaches_the_session(self):
        self.use(OWNER, 'allow', user=STRANGER)
        after = self.fake.say(GENERAL, OWNER, 'start')
        self.clock.at(1, lambda: self.arrive(GENERAL, STRANGER, 'here'))
        got = self.tool('discord_wait', channel=GENERAL, after=after, wait=10)
        self.assertEqual(got['message']['author_id'], STRANGER)
        self.pushes.clear()
        self.heard(STRANGER_DM, STRANGER, 'in DMs')
        self.assertEqual([(text, meta['kind']) for text, meta in self.pushes], [('in DMs', 'message')])

    def test_deny_takes_an_allow_back_says_so_and_refuses_what_it_cannot_take(self):
        self.use(OWNER, 'allow', user=STRANGER, time='7d')
        until = int(self.now + 604800)
        self.now += 60
        said = self.use(OWNER, 'deny', user=STRANGER)
        self.assertEqual(said, f'<@{STRANGER}> is not allowed anymore; it ran until <t:{until}:f> (<t:{until}:R>).')
        text = (
            f'The owner took back the allow of Stranger ({STRANGER}), which ran until 2027-01-22T08:00:00Z: their '
            "messages are a stranger's again"
        )
        meta = {'kind': 'notice', 'user': 'Stranger', 'user_id': STRANGER, 'until': 'denied'}
        self.assertEqual(self.notices()[-1], (text, meta))
        self.assertEqual(self.bot.allowed(), {})
        self.assertEqual(self.use(OWNER, 'deny', user=STRANGER), f'<@{STRANGER}> has no allow to take back.')
        self.assertEqual(
            self.use(OWNER, 'deny', user=FRIEND),
            f'<@{FRIEND}> is listed in AOGOWIMSY_USERS: their messages always reach the session, and the env file '
            'takes them out.',
        )
        self.assertEqual(
            self.use(OWNER, 'allow', user=OWNER), f'<@{OWNER}> is the owner: his messages always reach the session.'
        )
        self.assertEqual(self.use(OWNER, 'allow', user=BOT), f'<@{BOT}> is AogoWimsy itself.')
        self.assertEqual(len(self.notices()), 2)

    def test_allowed_and_discord_allowed_list_the_allows_in_force_the_soonest_end_first(self):
        self.assertEqual(
            self.use(OWNER, 'allowed'), f'No one is allowed now.\nListed in AOGOWIMSY_USERS, always: <@{FRIEND}>'
        )
        self.use(OWNER, 'allow', user=STRANGER, time='perm')
        self.use(OWNER, 'allow', user=OTHER_PERSON, time='7d')
        self.use(OWNER, 'allow', user=CALLERS[0], time='2h')
        self.now += 7200  # the 2 h one runs out
        week = int(self.start + 604800)
        self.assertEqual(
            self.use(OWNER, 'allowed'),
            f'Allowed:\n<@{OTHER_PERSON}> (Other): until <t:{week}:f> (<t:{week}:R>)\n<@{STRANGER}> (Stranger): for good\n'
            f'Listed in AOGOWIMSY_USERS, always: <@{FRIEND}>',
        )
        got = self.tool('discord_allowed')
        self.assertEqual(
            got,
            {
                'allowed': [
                    {'user_id': OTHER_PERSON, 'name': 'Other', 'since': aw.utc(self.start), 'until': aw.utc(week)},
                    {'user_id': STRANGER, 'name': 'Stranger', 'since': aw.utc(self.start), 'until': None},
                ],
                'listed': [FRIEND],
                'now': aw.utc(self.now),
            },
        )
        self.assertIn('discord_allowed has no argument "x"', self.error('discord_allowed', x=1))

    def test_allowed_past_a_messages_letters_says_how_many_more_discord_allowed_lists(self):
        many = [f'10000000000000002{n:02d}' for n in range(60)]  # 60 lines of 43 letters
        for user in many:
            self.use(OWNER, 'allow', user=user, time='perm')
        said = self.use(OWNER, 'allowed')
        lines = said.split('\n')
        self.assertLessEqual(len(said), 2000)
        shown = len(lines) - 3  # Allowed:, the count of the rest, the listed users
        self.assertEqual(lines[-2], f'{60 - shown} more: discord_allowed lists them all.')
        self.assertEqual(lines[1:3], [f'<@{many[0]}> (webhook): for good', f'<@{many[1]}> (webhook): for good'])
        self.assertEqual(len(self.tool('discord_allowed')['allowed']), 60)

    def test_a_restart_keeps_the_allows_and_their_ends_in_a_private_file(self):
        self.use(OWNER, 'allow', user=STRANGER, time='2h')
        self.use(OWNER, 'allow', user=OTHER_PERSON, time='perm')
        path = self.state / 'allowed.json'
        modes = stat.S_IMODE(path.stat().st_mode), stat.S_IMODE(self.state.stat().st_mode)
        self.assertEqual(modes, (0o600, 0o700))
        fresh, ear = self.restarted(self.now + 3600)
        self.assertEqual(set(fresh.allowed()), {STRANGER, OTHER_PERSON})
        self.pushes.clear()
        number = self.fake.say(GENERAL, STRANGER, 'after a restart <@1000000000000000001>', mentions=[BOT])
        ear.hear('MESSAGE_CREATE', self.fake.event(GENERAL, number))
        self.assertEqual([meta['kind'] for _, meta in self.pushes], ['message'])
        fresh.store.now = lambda: self.now + 7201
        self.assertEqual(set(fresh.allowed()), {OTHER_PERSON})

    def test_two_servers_hearing_one_use_answer_it_once_and_each_tells_its_session(self):
        _, other = self.restarted(self.now)
        event = self.used(OWNER, 'allow', user=STRANGER)
        for ear in (self.ear, other, other, self.ear):  # and the gateway's replay of it
            ear.hear('INTERACTION_CREATE', event)
        self.assertEqual(len(self.fake.posts('POST', f'/interactions/{event["id"]}/token-{event["id"]}/callback')), 1)
        self.assertEqual(len(self.notices()), 2)  # once from each server
        self.assertEqual(self.notices()[0], self.notices()[1])
        later = f'commands: /aogo allow in channel {GENERAL} was answered by another server of AogoWimsy'
        self.assertEqual(self.logs.count(later), 3)

    def test_a_use_waits_while_another_server_holds_the_lock(self):
        aw.private_folder(self.state)
        held = os.open(self.state / aw.STATE_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
        event = self.used(OWNER, 'allow', user=STRANGER)
        try:
            fcntl.flock(held, fcntl.LOCK_EX)
            looking = aw.started(lambda: self.ear.hear('INTERACTION_CREATE', event))
            looking.join(0.3)
            self.assertTrue(looking.is_alive())  # waiting for the other server's look and change to end
            self.assertNotIn(event['id'], self.fake.answers)
            self.assertFalse((self.state / 'interactions.json').exists())
        finally:
            fcntl.flock(held, fcntl.LOCK_UN)
            os.close(held)
        looking.join(5)
        self.assertIn(event['id'], self.fake.answers)
        self.assertIn(STRANGER, self.bot.allowed())

    def test_a_use_is_answered_in_a_thread_of_its_own_ahead_of_the_queue(self):
        event = self.used(STRANGER, 'help')
        self.ear.feed('INTERACTION_CREATE', event)  # no ear.run: the queue is never read
        for _ in range(500):
            if event['id'] in self.fake.answers:
                break
            time.sleep(0.01)
        self.assertEqual(self.fake.answers[event['id']]['data']['content'], f'{LINE}\n{HELP_TEXT}')
        self.assertTrue(self.ear.queue.empty())

    def test_an_answer_discord_refuses_is_an_error_without_its_token_and_the_allow_holds(self):
        event = self.used(OWNER, 'allow', user=STRANGER)
        self.fake.answers[event['id']] = 'answered already'
        self.ear.hear('INTERACTION_CREATE', event)
        said = (
            f'AogoWimsy could not answer /aogo allow in channel {GENERAL}: Discord answered 400 to POST /interactions/'
            f'{event["id"]}/<token>/callback: Interaction has already been acknowledged. (code 40060)'
        )
        self.assertEqual([text for text, meta in self.pushes if meta['kind'] == 'error'], [said])
        self.assertEqual(len(self.notices()), 1)
        self.assertIn(STRANGER, self.bot.allowed())
        self.assertNotIn('token-', json.dumps([self.pushes, self.logs]))

    def test_a_state_file_it_cannot_read_is_said_to_the_session_and_answered_to_the_asker(self):
        aw.private_folder(self.state)
        path = self.state / 'allowed.json'
        path.write_text('{"allowed": [{"id": 5}]}')
        said = self.use(OWNER, 'allow', user=STRANGER)
        self.assertTrue(said.startswith(f'AogoWimsy could not answer this: {path}: item 1 is {{"id": 5}}, not '), said)
        self.assertTrue(said.endswith('no allow is read until it is mended or removed.'), said)
        self.assertEqual(self.use(STRANGER, 'allowed'), f'Only <@{OWNER}> can use /aogo allowed.')
        told = "AogoWimsy could not answer this: its owner's session was told why."
        self.assertEqual(self.use(STRANGER, 'help'), told)  # whether they are allowed is read for help too
        errors = [text for text, meta in self.pushes if meta['kind'] == 'error']
        self.assertEqual(
            [text.split(': ')[0] for text in errors],
            [f'AogoWimsy could not answer /aogo {sub} in channel {GENERAL}' for sub in ('allow', 'help')],
        )
        self.assertTrue(all(f': {path}: item 1 is ' in text for text in errors), errors)
        self.assertEqual(path.read_text(), '{"allowed": [{"id": 5}]}')

    def test_another_subcommand_or_command_is_answered_naming_what_it_has(self):
        self.assertEqual(
            self.use(OWNER, 'forget'), '/aogo forget is not a command of AogoWimsy: it has help, allow, deny, allowed.'
        )
        event = self.used(OWNER, 'help', name='other')
        self.ear.hear('INTERACTION_CREATE', event)
        self.assertEqual(
            self.fake.answers[event['id']]['data']['content'], '/other is not a command of AogoWimsy: it has /aogo.'
        )
        self.ear.hear('INTERACTION_CREATE', dict(event, id='1600000000000000001', type=3))  # a button: none here
        self.assertNotIn('1600000000000000001', self.fake.answers)

    def test_the_instructions_and_tools_tell_the_session_of_the_allows(self):
        said = aw.instructions(self.settings)
        self.assertIn('/aogo allow', said)
        self.assertIn('discord_allowed', said)
        self.assertIn('kind="notice"', said)
        self.assertIn('discord_allowed', [tool['name'] for tool in aw.tool_list(aw.AOGO)])


def ws_frame(opcode, payload, fin=True):
    """a frame as a server sends it: never masked"""
    size = len(payload)
    head = bytes([(0x80 if fin else 0) | opcode])
    if size < 126:
        head += bytes([size])
    elif size < 1 << 16:
        head += bytes([126]) + size.to_bytes(2, 'big')
    else:
        head += bytes([127]) + size.to_bytes(8, 'big')
    return head + payload


class FakeGateway:
    """Discord's gateway on 127.0.0.1: hello, READY on identify, RESUMED on resume, heartbeat ACKs unless told not to;
    each frame the client sends is kept, and checked masked"""

    def __init__(self, interval=0.05, accept_right=True):
        self.listener = socket.create_server(('127.0.0.1', 0))
        self.url = f'ws://127.0.0.1:{self.listener.getsockname()[1]}'
        self.interval, self.accept_right, self.ack = interval, accept_right, True
        self.got = queue.Queue()  # (connection, what the client sent)
        self.connections, self.paths, self.seq, self.unmasked = [], [], 0, 0
        threading.Thread(target=self.accept, daemon=True).start()

    def shut(self):
        self.listener.close()
        for conn in self.connections:
            conn.close()

    def accept(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            self.connections.append(conn)
            threading.Thread(target=self.serve, args=(conn, len(self.connections) - 1), daemon=True).start()

    def send(self, payload, conn=None, opcode=1):
        (conn or self.connections[-1]).sendall(
            ws_frame(opcode, payload if isinstance(payload, bytes) else json.dumps(payload).encode())
        )

    def dispatch(self, kind, data, conn=None):
        self.seq += 1
        self.send({'op': 0, 't': kind, 's': self.seq, 'd': data}, conn)

    def close_with(self, code):
        self.send(code.to_bytes(2, 'big') + b'bye', opcode=8)

    def serve(self, conn, number):
        try:
            head = b''
            while b'\r\n\r\n' not in head:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                head += chunk
            lines = head.decode().split('\r\n')
            self.paths.append(lines[0].split(' ')[1])
            key = next(x.split(':', 1)[1].strip() for x in lines if x.lower().startswith('sec-websocket-key:'))
            accept = base64.b64encode(hashlib.sha1((key + aw.WS_GUID).encode()).digest()).decode()
            if not self.accept_right:
                accept = 'wrong'
            conn.sendall(
                f'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                f'Sec-WebSocket-Accept: {accept}\r\n\r\n'.encode()
            )
            self.send({'op': 10, 'd': {'heartbeat_interval': self.interval * 1000}}, conn)
            buffer = b''
            while True:
                while True:
                    frame = self.parse(buffer)
                    if frame:
                        break
                    chunk = conn.recv(65536)
                    if not chunk:
                        return
                    buffer += chunk
                opcode, payload, masked, buffer = frame
                if not masked:
                    self.unmasked += 1
                elif opcode == 8:
                    self.got.put((number, {'close': int.from_bytes(payload[:2], 'big')}))
                    conn.close()
                    return
                elif opcode == 10:
                    self.got.put((number, {'pong': payload}))
                else:
                    message = json.loads(payload)
                    self.got.put((number, message))
                    if message['op'] == 1 and self.ack:
                        self.send({'op': 11}, conn)
                    elif message['op'] == 2:
                        ready = {'session_id': 'fake-session', 'resume_gateway_url': self.url, 'user': {'id': BOT}}
                        self.dispatch('READY', ready, conn)
                    elif message['op'] == 6:
                        self.dispatch('RESUMED', {}, conn)
        except OSError:
            return

    @staticmethod
    def parse(data):
        if len(data) < 2:
            return None
        opcode, masked, size, at = data[0] & 0x0F, bool(data[1] & 0x80), data[1] & 0x7F, 2
        if size == 126:
            size, at = int.from_bytes(data[2:4], 'big'), 4
        elif size == 127:
            size, at = int.from_bytes(data[2:10], 'big'), 10
        mask = data[at : at + 4] if masked else b''
        at += len(mask)
        if len(data) < at + size:
            return None
        payload = data[at : at + size]
        if masked:
            payload = bytes(byte ^ mask[place % 4] for place, byte in enumerate(payload))
        return opcode, payload, masked, data[at + size :]

    def next(self, want, timeout=5.0):
        """the next thing a connection got that want(message) takes: (connection, message)"""
        deadline = time.monotonic() + timeout
        while True:
            number, message = self.got.get(timeout=max(0.01, deadline - time.monotonic()))
            if want(message):
                return number, message


def op(code):
    return lambda message: isinstance(message, dict) and message.get('op') == code


class GatewayClient(WithDiscord):
    """aogowimsy's Gateway and WebSocket against FakeGateway; the REST /gateway/bot gives its url"""

    def setUp(self):
        super().setUp()
        self.begin()

    def begin(self, interval=0.05):
        """a fake gateway beating every interval seconds, and a client on it in a thread of its own"""
        if getattr(self, 'thread', None):
            self.stop.set()
            self.thread.join(5)
        self.gateway = FakeGateway(interval)
        self.addCleanup(self.gateway.shut)
        self.fake.gateway_url = self.gateway.url
        self.heard, self.reports, self.stop = queue.Queue(), queue.Queue(), threading.Event()
        self.client = aw.Gateway(
            TOKEN,
            self.bot.discord,
            lambda kind, data: self.heard.put((kind, data)),
            lambda kind, text: self.reports.put((kind, text)),
            self.stop,
            rng=lambda: 0.5,
            backoff=(0.01, 0.05),
        )
        self.thread = aw.started(self.client.run)
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.stop.set)

    def kind(self, want, timeout=5.0):
        deadline = time.monotonic() + timeout
        while True:
            kind, data = self.heard.get(timeout=max(0.01, deadline - time.monotonic()))
            if kind == want:
                return data

    def test_identify_with_its_intents_then_heartbeats_carrying_the_last_seq(self):
        _, identify = self.gateway.next(op(2))
        self.assertEqual(identify['d']['token'], TOKEN)
        self.assertEqual(identify['d']['intents'], 46593)
        # 8192, DIRECT_MESSAGE_REACTIONS: without it Discord sends no reaction in the owner's DMs, and a draft he
        # answered waited for a tool's next look
        self.assertEqual(aw.INTENTS, 1 + 512 + 1024 + 4096 + 8192 + 32768)
        self.assertEqual(identify['d']['properties']['browser'], 'aogowimsy')
        self.assertEqual(self.kind('READY')['session_id'], 'fake-session')
        self.gateway.dispatch('MESSAGE_CREATE', {'id': '1', 'content': 'x'})
        self.gateway.seq = 41
        self.gateway.dispatch('MESSAGE_CREATE', {'id': '2', 'content': 'y'})
        self.assertEqual(self.kind('MESSAGE_CREATE')['id'], '1')
        self.gateway.next(lambda m: op(1)(m) and m['d'] == 42)
        self.assertEqual(self.gateway.paths[0], '/?v=10&encoding=json')
        self.assertEqual(self.client.seq, 42)
        self.assertEqual(self.gateway.unmasked, 0)

    def test_a_heartbeat_asked_for_goes_at_once(self):
        self.begin(interval=30)  # its own first beat would come in 15 s
        self.gateway.next(op(2))
        self.kind('READY')
        self.gateway.send({'op': 1, 'd': None})
        self.assertEqual(self.gateway.next(op(1), timeout=2)[1], {'op': 1, 'd': 1})

    def test_a_missed_ack_reconnects_and_resumes_the_session(self):
        self.gateway.next(op(2))
        self.kind('READY')
        self.gateway.ack = False
        number, closed = self.gateway.next(lambda m: isinstance(m, dict) and 'close' in m)
        self.assertEqual((number, closed['close']), (0, 4000))
        number, resume = self.gateway.next(op(6))
        self.assertEqual(number, 1)
        self.assertEqual((resume['d']['session_id'], resume['d']['token']), ('fake-session', TOKEN))
        self.assertEqual(resume['d']['seq'], 1)
        self.kind('RESUMED')

    def test_reconnect_resumes_an_invalid_session_identifies_again(self):
        self.gateway.next(op(2))
        self.kind('READY')
        self.gateway.send({'op': 7, 'd': None})
        self.assertEqual(self.gateway.next(op(6))[0], 1)
        self.kind('RESUMED')
        self.gateway.send({'op': 9, 'd': False})
        self.assertEqual(self.gateway.next(op(2))[0], 2)
        self.kind('READY')
        self.gateway.close_with(4009)
        self.assertEqual(self.gateway.next(op(2))[0], 3)

    def test_a_close_discord_takes_no_new_try_after_stops_it_saying_why(self):
        self.gateway.next(op(2))
        self.kind('READY')
        self.gateway.close_with(4014)
        kind, text = self.reports.get(timeout=5)
        self.assertEqual(kind, 'stopped')
        self.assertIn(
            'Discord closed the gateway with 4014 (bye): disallowed intents: turn on Message Content Intent', text
        )
        self.thread.join(5)
        self.assertFalse(self.thread.is_alive())
        self.assertEqual(len(self.gateway.connections), 1)

    def test_a_bad_token_stops_it(self):
        self.gateway.next(op(2))
        self.gateway.close_with(4004)
        self.assertIn(
            "4004 (bye): authentication failed: AOGOWIMSY_TOKEN is not the bot's token", self.reports.get(timeout=5)[1]
        )

    def test_a_ping_gets_its_pong_and_a_message_in_two_frames_comes_whole(self):
        self.gateway.next(op(2))
        self.kind('READY')
        self.gateway.send(b'are you there', opcode=9)
        self.assertEqual(
            self.gateway.next(lambda m: isinstance(m, dict) and 'pong' in m)[1], {'pong': b'are you there'}
        )
        whole = json.dumps({'op': 0, 't': 'MESSAGE_CREATE', 's': 9, 'd': {'id': '3', 'content': 'two halves'}}).encode()
        conn = self.gateway.connections[-1]
        conn.sendall(ws_frame(1, whole[:20], fin=False) + ws_frame(0, whole[20:]))
        self.assertEqual(self.kind('MESSAGE_CREATE')['content'], 'two halves')

    def test_a_stop_closes_with_1000(self):
        self.gateway.next(op(2))
        self.kind('READY')
        self.stop.set()
        self.assertEqual(self.gateway.next(lambda m: isinstance(m, dict) and 'close' in m)[1], {'close': 1000})


class GatewayRefusals(WithDiscord):
    def test_a_gateway_url_that_is_not_wss_is_refused_naming_it(self):
        with self.assertRaisesRegex(aw.DiscordError, 'the gateway url "ws://example.com/" is not wss://'):
            aw.WebSocket('ws://example.com/')
        with self.assertRaisesRegex(aw.DiscordError, 'is not wss://'):
            aw.WebSocket('http://127.0.0.1:9/')

    def test_a_wrong_handshake_answer_is_refused(self):
        gateway = FakeGateway(accept_right=False)
        self.addCleanup(gateway.shut)
        with self.assertRaisesRegex(ConnectionError, 'Sec-WebSocket-Accept "wrong", not '):
            aw.WebSocket(gateway.url + '/?v=10&encoding=json')

    def test_a_401_for_the_gateway_url_stops_it(self):
        self.fake.fail[('GET', '/gateway/bot')] = (401, {'message': '401: Unauthorized', 'code': 0})
        reports, stop = [], threading.Event()
        self.addCleanup(stop.set)
        report = lambda kind, text: reports.append((kind, text))
        client = aw.Gateway(TOKEN, self.bot.discord, None, report, stop, rng=lambda: 0.5, backoff=(0.01, 0.05))
        thread = aw.started(client.run)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(
            reports, [('stopped', "Discord answered 401 to GET /gateway/bot: AOGOWIMSY_TOKEN is not the bot's token")]
        )

    def test_from_the_gateway_to_the_session_end_to_end(self):
        gateway = FakeGateway()
        self.addCleanup(gateway.shut)
        self.fake.gateway_url = gateway.url
        stop, pushes = threading.Event(), queue.Queue()
        self.addCleanup(stop.set)
        ear = aw.Ear(self.bot, lambda text, meta: pushes.put((text, meta)), stop)
        client = aw.Gateway(TOKEN, self.bot.discord, ear.feed, ear.report, stop, rng=lambda: 0.5, backoff=(0.01, 0.05))
        threads = [aw.started(ear.run), aw.started(client.run)]
        gateway.next(op(2))
        number = self.fake.say(GENERAL, OWNER, 'to aogo, live', mentions=[BOT])
        gateway.dispatch('MESSAGE_CREATE', self.fake.event(GENERAL, number))
        text, meta = pushes.get(timeout=5)
        self.assertEqual((text, meta['message_id'], meta['kind']), ('to aogo, live', number, 'message'))
        stop.set()
        for thread in threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())


class Writer(unittest.TestCase):
    def test_lines_from_many_threads_never_mix(self):
        class Slow:
            """a stream that writes a line in two halves, with time for another thread between them"""

            def __init__(self):
                self.data = bytearray()

            def write(self, line):
                half = len(line) // 2
                self.data += line[:half]
                time.sleep(0.002)
                self.data += line[half:]

            def flush(self):
                pass

        stream = Slow()
        write = aw.LineWriter(stream)

        def many(who):
            for n in range(25):
                write({'jsonrpc': '2.0', 'method': 'notifications/claude/channel', 'params': {'content': f'{who} {n}'}})

        threads = [aw.started(lambda who=who: many(who)) for who in 'abcd']
        for thread in threads:
            thread.join(10)
        lines = bytes(stream.data).split(b'\n')
        self.assertEqual(lines[-1], b'')
        self.assertEqual(len([json.loads(line) for line in lines[:-1]]), 100)


class Stdio(unittest.TestCase):
    """the real program, as Claude Code starts it: a line a message on stdin and stdout, logs on stderr. It is never
    told initialized here, so it never reaches for Discord's gateway"""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = write_env(self.folder.name, GOOD_ENV)

    program = HERE / 'aogowimsy.py'  # xuji/test_xujiwimsy.py's Stdio runs its own with these helpers

    def start(self, *args, environ=None, program=None):
        command = [sys.executable, str(program or self.program), *args]
        proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environ
        )
        watchdog = threading.Timer(20, proc.kill)
        watchdog.start()
        self.addCleanup(self.ended, proc, watchdog)
        return proc

    def ended(self, proc, watchdog):
        """a program a test left running or open, when it failed halfway: killed and closed"""
        watchdog.cancel()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()

    def exchange(self, proc, message):
        line = message if isinstance(message, bytes) else json.dumps(message).encode()
        proc.stdin.write(line + b'\n')
        proc.stdin.flush()
        answer = proc.stdout.readline()
        self.assertTrue(answer.endswith(b'\n') and answer.isascii(), answer)
        return json.loads(answer)

    def finish(self, proc):
        proc.stdin.close()
        self.assertEqual(proc.wait(), 0)
        rest, errors = proc.stdout.read(), proc.stderr.read().decode()
        proc.stdout.close()
        proc.stderr.close()
        self.assertEqual(rest, b'')
        self.assertNotIn(TOKEN, errors)
        self.assertNotIn('Traceback', errors)
        return errors

    def test_the_handshake_tools_list_and_a_tool_call_through_a_subprocess(self):
        proc = self.start('--env', self.env)
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': INITIALIZE})
        self.assertEqual((answer['id'], answer['result']['protocolVersion']), (1, '2025-11-25'))
        self.assertEqual(answer['result']['capabilities'], {'tools': {}, 'experimental': {'claude/channel': {}}})
        self.assertIn(f'channels {GENERAL}, {HELP} and their threads', answer['result']['instructions'])
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 'list', 'method': 'tools/list'})
        self.assertEqual(answer, {'jsonrpc': '2.0', 'id': 'list', 'result': {'tools': aw.tool_list(aw.AOGO)}})
        self.assertEqual(self.exchange(proc, {'jsonrpc': '2.0', 'id': 3, 'method': 'ping'})['result'], {})
        answer = self.exchange(proc, b'{"jsonrpc": "2.0", "id": 4, "method": ')
        self.assertEqual(answer['error']['code'], -32700)
        self.assertNotIn('id', answer)
        call = {'name': 'discord_read', 'arguments': {'channel': 'general'}}
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': call})
        self.assertTrue(answer['result']['isError'])
        self.assertEqual(
            answer['result']['content'][0]['text'], 'channel is "general", not a Discord id (17 to 20 digits)'
        )
        errors = self.finish(proc)
        up = (
            f'aogowimsy: up: owner {OWNER}, 1 users, 2 channels, greeting a stranger once each 24 h, 10 an hour at most'
        )
        self.assertIn(up + '\n', errors)
        self.assertIn('aogowimsy: discord_read failed: channel is "general"', errors)

    def test_a_2026_07_28_client_gets_method_not_found_for_discovery(self):
        proc = self.start('--env', self.env)
        meta = {
            'io.modelcontextprotocol/protocolVersion': '2026-07-28',
            'io.modelcontextprotocol/clientCapabilities': {},
        }
        answer = self.exchange(
            proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'server/discover', 'params': {'_meta': meta}}
        )
        self.assertEqual(answer['error']['code'], -32601)
        self.finish(proc)

    def test_a_bad_env_file_or_option_stops_it_naming_what(self):
        os.chmod(self.env, 0o644)
        proc = self.start('--env', self.env)
        self.assertEqual(proc.wait(), 1)
        self.assertIn(f'aogowimsy: {self.env} has mode 644', proc.stderr.read().decode())
        self.assertEqual(proc.stdout.read(), b'')
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()
        proc = self.start('--bogus')
        self.assertEqual(proc.wait(), 2)
        self.assertIn('unrecognized arguments: --bogus', proc.stderr.read().decode())
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()


if __name__ == '__main__':
    unittest.main()
