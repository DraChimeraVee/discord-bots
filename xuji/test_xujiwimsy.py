#!/usr/bin/env python3
"""xujiwimsy.py without Discord or the network: what makes XujiWimsy Xuji's (its env file and keys, its server's
name, no claude/channel, its instructions, its tools in its names), the client each Wimsy serves, the news a client
with no channel gets with its next tool result, a post as it reaches Discord, and the program on stdin and stdout.
AogoWimsy's suite tests the code they share; its fake Discord serves here too."""

import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'aogo'))
import aogowimsy as aw
import test_aogowimsy as base  # its fake Discord, clock and constants

TOKEN, OWNER, FRIEND, STRANGER, BOT = base.TOKEN, base.OWNER, base.FRIEND, base.STRANGER, base.BOT
GENERAL, HELP, OTHER, DM, GUILD = base.GENERAL, base.HELP, base.OTHER, base.DM, base.GUILD
YES = aw.YES
# what Grok Build 1.0.60 sends (grok mcp doctor against a server of that name logged it)
GROK = {
    'protocolVersion': '2025-11-25',
    'capabilities': {},
    'clientInfo': {'name': 'grok-shell-xujiwimsy', 'version': '1'},
}
CLAUDE = base.INITIALIZE
GOOD_ENV = base.GOOD_ENV.replace('AOGOWIMSY_', 'XUJIWIMSY_').replace('# AogoWimsy', '# XujiWimsy')
KNOWS = 'XUJIWIMSY_TOKEN, XUJIWIMSY_OWNER, XUJIWIMSY_USERS, XUJIWIMSY_CHANNELS'


def initialize(server, params):
    return server.handle({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': params})


class EnvFile(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def refused(self, text, identity=aw.XUJI, mode=0o600):
        with self.assertRaises(aw.Refused) as caught:
            aw.read_settings(base.write_env(self.folder.name, text, mode, 'bot.env'), identity)
        self.assertNotIn(TOKEN, str(caught.exception))
        return str(caught.exception)

    def test_its_file_takes_the_xujiwimsy_keys_with_aogowimsys_meanings(self):
        path = base.write_env(self.folder.name, GOOD_ENV, name='xujiwimsy.env')
        settings = aw.read_settings(path, aw.XUJI)
        self.assertEqual(settings, aw.Settings(TOKEN, OWNER, frozenset({FRIEND}), frozenset({GENERAL, HELP}), aw.XUJI))
        every = aw.read_settings(
            base.write_env(self.folder.name, GOOD_ENV.replace(f'XUJIWIMSY_CHANNELS={GENERAL}, {HELP}\n', '')), aw.XUJI
        )
        self.assertIsNone(every.channels)
        self.assertIn(
            'every channel and thread Discord lets it see (XUJIWIMSY_CHANNELS lists none)', aw.instructions(every)
        )
        self.assertEqual(aw.XUJI.env, '~/.config/xujiwimsy/xujiwimsy.env')

    def test_an_aogowimsy_key_in_its_file_stops_it_naming_the_key_and_the_reverse(self):
        said = self.refused(GOOD_ENV + f'AOGOWIMSY_TOKEN={TOKEN}\n')
        self.assertIn(f'line 7: AOGOWIMSY_TOKEN is not a key XujiWimsy knows; it knows {KNOWS}', said)
        said = self.refused(base.GOOD_ENV)  # AogoWimsy's whole file
        self.assertIn('line 2: AOGOWIMSY_TOKEN is not a key XujiWimsy knows', said)
        said = self.refused(base.GOOD_ENV + f'XUJIWIMSY_OWNER={OWNER}\n', aw.AOGO)
        self.assertIn('line 7: XUJIWIMSY_OWNER is not a key AogoWimsy knows; it knows AOGOWIMSY_TOKEN', said)
        said = self.refused(GOOD_ENV, aw.AOGO)
        self.assertIn('line 2: XUJIWIMSY_TOKEN is not a key AogoWimsy knows', said)

    def test_it_greets_no_one_so_it_takes_no_greeting_key(self):
        for key in ('XUJIWIMSY_GREET_HOURS', 'XUJIWIMSY_GREET_PER_HOUR', 'AOGOWIMSY_GREET_HOURS'):
            said = self.refused(GOOD_ENV + f'{key}=24\n')
            self.assertIn(f'line 7: {key} is not a key XujiWimsy knows; it knows {KNOWS}', said)
        self.assertEqual((aw.XUJI.greeting, aw.XUJI.greet_keys), (None, ()))

    def test_its_example_is_aogowimsys_first_four_keys_in_its_names(self):
        aogo = (HERE.parent / 'aogo' / 'aogowimsy.env.example').read_text()
        shared = aogo[: aogo.index('# AOGOWIMSY_CHANNELS=id,id\n') + len('# AOGOWIMSY_CHANNELS=id,id\n')]
        renamed = shared.replace('AogoWimsy', 'XujiWimsy').replace('aogowimsy', 'xujiwimsy').replace('AOGO', 'XUJI')
        self.assertEqual((HERE / 'xujiwimsy.env.example').read_text(), renamed)

    def test_its_values_are_checked_as_aogowimsys_naming_its_keys(self):
        self.assertIn('XUJIWIMSY_TOKEN is empty, and XujiWimsy needs it', self.refused(GOOD_ENV.replace(TOKEN, '')))
        # XUJIWIMSY_USERS lists who starts trusted, as AOGOWIMSY_USERS does: a file without it is read, trusting no one
        path = base.write_env(self.folder.name, GOOD_ENV.replace(f'XUJIWIMSY_USERS = {FRIEND}', ''), name='bare.env')
        self.assertEqual(aw.read_settings(path, aw.XUJI).users, frozenset())
        said = self.refused(GOOD_ENV.replace(f'{GENERAL}, {HELP}', ''))
        self.assertIn('XUJIWIMSY_CHANNELS is empty: list id,id, or take the line out', said)
        said = self.refused(GOOD_ENV.replace(f'_OWNER={OWNER}', '_OWNER=12345'))
        self.assertIn('XUJIWIMSY_OWNER is "12345", not a Discord id', said)
        self.assertIn("XUJIWIMSY_TOKEN has '\"' at letter 1", self.refused(GOOD_ENV.replace(TOKEN, f'"{TOKEN}"')))
        self.assertIn('has mode 644', self.refused(GOOD_ENV, mode=0o644))
        with self.assertRaisesRegex(aw.Refused, 'nowhere.env cannot be read .*: XujiWimsy reads its settings there'):
            aw.read_settings(str(Path(self.folder.name) / 'nowhere.env'), aw.XUJI)

    def test_the_example_lists_its_keys_and_stops_at_the_first_empty_one(self):
        example = base.write_env(self.folder.name, (HERE / 'xujiwimsy.env.example').read_text(), name='example.env')
        with self.assertRaisesRegex(aw.Refused, 'XUJIWIMSY_TOKEN is empty, and XujiWimsy needs it'):
            aw.read_settings(example, aw.XUJI)


class WithXuji(base.WithDiscord):
    """XujiWimsy's tools through its server, initialized by Grok Build, against the fake Discord"""

    def setUp(self):
        super().setUp()
        self.settings = self.settings._replace(identity=aw.XUJI)
        self.bot = aw.Wimsy(self.settings, aw.Discord(TOKEN, self.clock, self.api, identity=aw.XUJI), self.clock)
        self.server = self.started_server(self.bot)

    def started_server(self, bot, **extra):
        """bot's server, initialized by its client: Grok Build for XujiWimsy (AogoWimsy's in the base's setUp)"""
        server = aw.Server(bot, aw.instructions(bot.settings), self.sent.append, **extra)
        self.assertIn('result', initialize(server, CLAUDE if bot.settings.identity.claude else GROK))
        return server

    def aogo_server(self, **extra):
        aogo = aw.Wimsy(self.settings._replace(identity=aw.AOGO), aw.Discord(TOKEN, self.clock, self.api), self.clock)
        return aw.Server(aogo, 'test', self.sent.append, **extra)


class Handshake(WithXuji):
    def test_its_server_info_and_no_claude_channel_while_aogowimsy_keeps_it(self):
        server = aw.Server(self.bot, 'test', self.sent.append)
        result = initialize(server, GROK)['result']
        self.assertEqual(result['serverInfo'], {'name': 'xujiwimsy', 'title': 'XujiWimsy', 'version': aw.VERSION})
        self.assertEqual(result['capabilities'], {'tools': {}})
        result = initialize(self.aogo_server(), CLAUDE)['result']
        self.assertEqual(result['serverInfo']['name'], 'aogowimsy')
        self.assertEqual(result['capabilities'], {'tools': {}, 'experimental': {'claude/channel': {}}})

    def test_its_instructions_say_who_it_is_whose_and_to_hear_through_a_monitor(self):
        said = aw.instructions(self.settings)
        self.assertTrue(
            said.startswith(f'XujiWimsy is Xuji on Discord. Every post is a draft its owner (Discord user {OWNER})')
        )
        self.assertIn(
            "only the owner's messages, its own and those of whom he trusts or allowed with /xuji reach you", said
        )
        self.assertIn('/xuji sets who reaches you (trust, allow, weight, tone), each change a kind="notice"', said)
        program = HERE / 'xujiwimsy.py'
        self.assertIn(
            "Discord reaches you through a monitor: at the session's start, run the monitor tool, persistent, "
            f'description "XujiWimsy", command `python3 {program} --listen`; each line it prints is an event for you',
            said,
        )
        self.assertIn('If it stops, start it again; without it, discord_wait hears a channel.', said)
        self.assertNotIn('<channel>', said)
        self.assertNotIn('Aogo', said)
        self.assertIn('<channel> events', aw.instructions(self.settings._replace(identity=aw.AOGO)))

    def test_its_instructions_fit_in_what_grok_build_shows_its_model(self):
        users = frozenset(f'20539067360960960{n}' for n in range(3))
        channels = frozenset(f'130000000000000000{n}' for n in range(4))
        for listed in (None, channels):  # every channel, or four listed: the README's settings and more
            settings = self.settings._replace(users=users, channels=listed)
            said = aw.instructions(settings)
            self.assertLessEqual(len(said.encode()), aw.GROK_SHOWS)
            self.assertTrue(said.endswith('which saves them and gives their paths.'))
            self.assertIsNone(aw.cut_by_grok(settings, said))
        many = self.settings._replace(channels=frozenset(f'1300000000000000{n:03d}' for n in range(30)))
        said = aw.instructions(many)
        self.assertEqual(
            aw.cut_by_grok(many, said),
            f"XujiWimsy's instructions are {len(said.encode())} bytes and Grok Build shows its model the first 2048: "
            'the end of them (how to answer, attachments) is lost. List fewer ids in XUJIWIMSY_USERS or '
            'XUJIWIMSY_CHANNELS, which take 651 bytes of them',  # 31 ids of 19 digits, each with its ', '
        )
        self.assertIsNone(aw.cut_by_grok(many._replace(identity=aw.AOGO), said))  # Claude Code shows them whole

    def test_its_tools_are_aogowimsys_in_its_own_names(self):
        xuji, aogo = aw.tool_list(aw.XUJI), aw.tool_list(aw.AOGO)
        text = json.dumps(xuji, ensure_ascii=False)
        self.assertNotIn('aogo', text.lower().replace(f':{aw.WIMSY}:', ''))  # the owner's emoji alone is named for Aogo
        self.assertIn('XUJIWIMSY_CHANNELS lists', text)
        reacting = ('discord_react', 'discord_unreact', 'discord_quick')  # its own emojis: Reactions below
        # its command's tools (the allows, the ice) and its drawings' upload are Aogo's under /xuji and its own names
        aogos = ()
        as_aogo = json.loads(
            text.replace('XujiWimsy', 'AogoWimsy')
            .replace('XUJIWIMSY', 'AOGOWIMSY')
            .replace('/xuji ', '/aogo ')
            .replace('wimsyxuji_', 'wimsyaogo_')
        )
        # discord_post less what each says of its direct posts' pace: Aogo's weighs Claude Code's quota, Xuji's is fixed
        drafts = json.loads(json.dumps(aogo[0]))
        self.assertEqual(drafts['name'], 'discord_post')
        drafts['description'] = drafts['description'].removesuffix(aw.direct_text(aw.AOGO))
        mine = xuji[0]['description']
        self.assertTrue(mine.endswith(aw.direct_text(aw.XUJI)))
        as_aogo[0]['description'] = as_aogo[0]['description'][: len(drafts['description'])]
        # discord_read less the replies of whom a post mentions, which Aogo's posts alone open
        mentioned = "; and the reply of someone a post of AogoWimsy's mentioned, to that post and within 24 h of it"
        reads = json.loads(json.dumps(aogo[2]))
        self.assertEqual((reads['name'], reads['description'].count(mentioned)), ('discord_read', 1))
        reads['description'] = reads['description'].replace(mentioned, '')
        self.assertEqual(
            [tool for tool in as_aogo if tool['name'] not in reacting],
            [drafts] + [tool for tool in [aogo[1], reads, *aogo[3:]] if tool['name'] not in (*reacting, *aogos)],
        )
        self.assertIn('XUJIWIMSY_DIRECT_MINUTES (30 by default), fixed, as its client reports no quota', mine)
        self.assertNotIn('doubled for the quota', mine)
        self.assertEqual([tool['name'] for tool in xuji], [name for name in aw.TOOL_NAMES if name not in aogos])
        for name in aogos:
            call = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': name}}
            self.assertIn(f'Unknown tool: "{name}"; XujiWimsy has', self.server.handle(call)['error']['message'])
        self.assertEqual(
            self.server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})['result'], {'tools': xuji}
        )

    def test_its_attachments_go_to_a_folder_of_its_own(self):
        self.assertEqual(self.bot.files.name, 'xujiwimsy')
        self.assertEqual(
            aw.saves_folder(aw.XUJI.server, {'XDG_CACHE_HOME': '/var/tmp/c'}), Path('/var/tmp/c/xujiwimsy')
        )
        self.assertIn('discord_attachments', aw.TOOL_NAMES)

    def test_its_errors_name_it_and_its_keys(self):
        lists = f'channel {OTHER} is not one XujiWimsy may post in: XUJIWIMSY_CHANNELS lists {GENERAL}, {HELP}'
        self.assertIn(lists, self.error('discord_post', channel=OTHER, text='hi'))
        said = self.error('discord_post', channel=GENERAL, text='hi', files=['/x/a.txt'])
        self.assertIn('XujiWimsy posts images', said)
        answer = self.server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'server/discover', 'params': {}})
        self.assertEqual(
            answer['error']['message'],
            'Method not found: server/discover; XujiWimsy speaks the initialize handshake '
            '(2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05)',
        )


class Drafts(WithXuji):
    def test_its_direct_posts_pass_aogowimsys_pre_harness_first(self):
        said = self.error('discord_post', channel=GENERAL, text='see /home/dravee/WorkDir/notes.txt', direct=True)
        self.assertIn('the pre-harness keeps this text from going direct: machine-path', said)
        self.assertIn('post it without direct, as a draft the owner sees', said)
        self.assertEqual(self.fake.requests, [])  # nothing reached Discord

    def test_its_direct_posts_go_at_a_fixed_interval_from_its_own_keys(self):
        self.assertEqual(aw.XUJI.direct_keys, ('XUJIWIMSY_DIRECT', 'XUJIWIMSY_DIRECT_MINUTES'))
        got = self.tool('discord_post', channel=GENERAL, text='hello', direct=True)
        self.assertEqual((got['status'], got['direct']), ('sent', 'interval'))
        self.assertEqual(self.fake.last(GENERAL)['content'], 'hello')
        said = self.error('discord_post', channel=GENERAL, text='again', direct=True)
        self.assertIn('XUJIWIMSY_DIRECT_MINUTES 30, fixed: its client reports no quota', said)  # the next waits 30 min
        self.assertEqual(
            self.tool('discord_post', channel=GENERAL, text='again', direct=False, wait=0)['status'], 'waiting'
        )


class Clients(WithXuji):
    """each Wimsy serves its own client: Claude Code AogoWimsy alone, any other XujiWimsy, so a session started
    where the other one's server is listed cannot post as the other bot"""

    def listening(self, server_of):
        calls = []
        server = server_of(lambda push: calls.append(push) or [])
        return server, calls

    def test_aogowimsy_refuses_a_client_that_is_not_claude_code_naming_both(self):
        server, calls = self.listening(lambda listen: self.aogo_server(listen=listen))
        grok = dict(GROK, clientInfo={'name': 'grok-shell-aogowimsy', 'version': '1.0.60'})
        error = initialize(server, grok)['error']
        self.assertEqual(error['code'], -32602)
        self.assertEqual(
            error['message'],
            'Invalid params: clientInfo.name is "grok-shell-aogowimsy", not "claude-code": AogoWimsy is Aogo\'s, for '
            'Claude Code alone; another client runs XujiWimsy (xujiwimsy) and keeps aogowimsy off (Grok Build: grok '
            'mcp disable aogowimsy)',
        )
        self.assertIn(f'initialize refused: {error["message"].removeprefix("Invalid params: ")}', self.logs)
        no_info = initialize(server, {'protocolVersion': '2025-11-25', 'capabilities': {}})['error']['message']
        self.assertIn('clientInfo.name is null, not "claude-code"', no_info)
        server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual(calls, [])  # refused: it never hears Discord with Aogo's token
        error = server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})['error']
        self.assertIn('tools/list came before initialize', error['message'])
        self.assertIn('result', initialize(server, CLAUDE))

    def test_xujiwimsy_refuses_claude_code_naming_both_and_serves_any_other(self):
        server, calls = self.listening(lambda listen: aw.Server(self.bot, 'test', self.sent.append, listen=listen))
        error = initialize(server, CLAUDE)['error']
        self.assertEqual(
            error['message'],
            'Invalid params: clientInfo.name is "claude-code": XujiWimsy is Xuji\'s, for any client but Claude Code, '
            'which runs AogoWimsy (aogowimsy); take xujiwimsy out of its MCP servers',
        )
        server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual(calls, [])
        for params in (GROK, {'protocolVersion': '2025-11-25', 'capabilities': {}}):
            self.assertIn('result', initialize(server, params))
        server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual(calls, [server.push])


class Reactions(WithXuji):
    """XujiWimsy answers with its own drawn emojis (wimsy-dist's emoji/wimsyxuji_*), the unicode ones while a server
    lacks them, as AogoWimsy does with Aogo's"""

    def test_it_reacts_with_its_drawn_emojis_and_their_unicode_ones(self):
        drawn = [f':{name}:' for name in aw.XUJI.drawn]
        self.assertEqual(drawn, [':wimsyxuji_eyes:', ':wimsyxuji_done:', ':wimsyxuji_thumbsup:', ':wimsyxuji_no:'])
        plain = [aw.EYES, aw.YES, aw.THUMBS, aw.NO]
        tools = {tool['name']: tool for tool in aw.tool_list(aw.XUJI)}
        for name in ('discord_react', 'discord_unreact'):
            self.assertEqual(
                tools[name]['inputSchema']['properties']['emoji']['enum'], [*drawn, *plain, f':{aw.WIMSY}:']
            )
        self.assertEqual(tools['discord_quick']['inputSchema']['properties']['emoji']['enum'], [*drawn, *plain])
        asked = self.fake.say(GENERAL, OWNER, 'can you look at the build?')
        said = self.error('discord_react', channel=GENERAL, message=asked, emoji=':wimsyaogo_eyes:')
        self.assertIn('emoji is ":wimsyaogo_eyes:", not one XujiWimsy reacts with', said)  # Aogo's face is not hers
        said = self.error('discord_react', channel=GENERAL, message=asked, emoji=':wimsyxuji_eyes:')
        self.assertIn('no server XujiWimsy is in has an emoji named wimsyxuji_eyes', said)
        self.assertIn(f'(discord_emoji_upload uploads it); {aw.EYES} says the same', said)
        self.assertEqual(self.tool('discord_react', channel=GENERAL, message=asked, emoji=aw.EYES)['status'], 'reacted')
        self.assertEqual(self.tool('discord_quick', channel=GENERAL, reply_to=asked, emoji=aw.YES)['status'], 'posted')
        self.assertEqual(self.fake.last(GENERAL)['content'], aw.YES)
        said = aw.instructions(self.settings)
        self.assertIn(
            'React rather than post, at once and with no draft: discord_react :wimsyxuji_eyes: when you start on a '
            'message, then discord_unreact it and put :wimsyxuji_done: when done; :wimsyxuji_thumbsup: agreed, '
            ':wimsyxuji_no: cannot, each its unicode one while the server lacks it.',
            said,
        )
        self.assertNotIn('wimsyaogo_', said + json.dumps(tools, ensure_ascii=False))


class Posting(WithXuji):
    def test_a_post_reaches_discord_as_its_text_with_no_signature(self):
        text = 'Built: **done**\nsecond line'
        self.owner_answers(6, YES)
        got = self.tool('discord_post', channel=GENERAL, text=text)
        self.assertEqual(got['status'], 'sent')
        self.assertEqual(self.fake.find(DM, got['draft'])['content'], text)
        posted = self.fake.posts('POST', f'/channels/{GENERAL}/messages')
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0][3]['content'], text)
        self.assertEqual(self.fake.last(GENERAL)['content'], text)


class News(WithXuji):
    """with no channel, the gateway's news and the owner's answers to drafts come with the next tool result"""

    def setUp(self):
        super().setUp()
        self.ear = aw.Ear(self.bot, self.server.push, threading.Event())
        self.ear.hear('READY', {'user': {'id': BOT}, 'session_id': 's', 'resume_gateway_url': 'ws://127.0.0.1:9'})

    def contents(self, **args):
        return self.answer('discord_read', channel=GENERAL, **args)['result']['content']

    def test_nothing_is_pushed_and_a_drafts_answer_comes_with_the_next_tool_result(self):
        draft = self.tool('discord_post', channel=GENERAL, text='approved later', wait=0)['draft']
        number = self.fake.say(GENERAL, OWNER, 'to xuji', mentions=[BOT])
        self.ear.hear('MESSAGE_CREATE', self.fake.event(GENERAL, number))
        self.fake.react(draft, YES, OWNER)
        self.ear.hear(
            'MESSAGE_REACTION_ADD',
            {'user_id': OWNER, 'channel_id': DM, 'message_id': draft, 'emoji': {'id': None, 'name': YES}},
        )
        posted = self.fake.last(GENERAL)
        self.assertEqual(posted['content'], 'approved later')  # posted at once, no tool waiting
        self.assertNotIn(aw.CHANNEL_PUSH, [message.get('method') for message in self.sent])
        self.assertIn('channel: a message event, no monitor listens', self.logs)
        self.assertIn('channel: a draft event, no monitor listens: kept for the next tool result', self.logs)
        self.assertNotIn('channel: pushed a message event', self.logs)
        content = self.contents()
        self.assertEqual(json.loads(content[0]['text'])['channel'], GENERAL)
        link = f'https://discord.com/channels/{GUILD}/{GENERAL}/{posted["id"]}'
        news = f'XujiWimsy news: The owner approved draft {draft}: posted as {link}'
        self.assertEqual(content[1:], [{'type': 'text', 'text': news}])
        self.assertEqual(len(self.contents()), 1)  # said once

    def test_a_strangers_call_gets_no_greeting_and_nothing_is_kept(self):
        mine = self.fake.say(GENERAL, BOT, 'a post of mine')
        for extra in ({'mentions': [BOT]}, {'reply_to': mine}):
            number = self.fake.say(GENERAL, STRANGER, 'who is this?', **extra)
            self.ear.hear('MESSAGE_CREATE', self.fake.event(GENERAL, number))
        self.assertEqual(self.fake.posts('POST', f'/channels/{GENERAL}/messages'), [])
        self.assertEqual(self.bot.allowed(), {})  # its store holds the owner's allows, and a call adds none
        self.assertNotIn('greet', aw.instructions(self.settings))
        self.assertEqual([line for line in self.logs if 'greet' in line], [])

    def test_its_command_is_xuji_registered_in_each_server_and_answering_its_own_alone(self):
        self.assertEqual(aw.XUJI.command, 'xuji')
        self.ear.hear('GUILD_CREATE', {'id': GUILD, 'channels': [], 'threads': []})
        self.assertEqual([command['name'] for command in self.fake.commands[GUILD]], ['xuji'])
        self.assertEqual(aw.command_list(aw.XUJI)[0]['name'], 'xuji')
        event = {'id': '1600000000000000001', 'type': 2, 'token': 'token-1600000000000000001', 'channel_id': GENERAL}
        self.ear.hear('INTERACTION_CREATE', dict(event, data={'name': 'aogo'}, member={'user': {'id': OWNER}}))
        said = json.dumps(self.fake.answers['1600000000000000001'])
        self.assertIn('/aogo is not a command of XujiWimsy: it has /xuji.', said)  # AogoWimsy's is not its own
        helping = dict(event, id='1600000000000000002', token='token-1600000000000000002')
        helping['data'] = {'name': 'xuji', 'options': [{'name': 'help', 'type': 1}]}
        self.ear.hear('INTERACTION_CREATE', dict(helping, member={'user': {'id': OWNER}}))
        said = json.dumps(self.fake.answers['1600000000000000002'], ensure_ascii=False)
        self.assertIn(f"I'm Xuji, <@{OWNER}>'s AI agent here: every post of mine waits for their approval.", said)
        self.assertIn('/xuji', said)  # the owner's commands
        asking = dict(helping, id='1600000000000000003', token='token-1600000000000000003')
        self.ear.hear('INTERACTION_CREATE', dict(asking, member={'user': {'id': STRANGER}}))
        said = json.dumps(self.fake.answers['1600000000000000003'], ensure_ascii=False)
        self.assertIn("I'm Xuji", said)  # anyone may ask for help, a stranger within the limits
        self.assertNotIn('/xuji allow', said)
        self.assertIn('allow', aw.instructions(self.settings))

    def test_the_gateways_news_come_with_a_tool_error_too(self):
        self.ear.report('trouble', 'OSError: down; it tries again, 60 s apart at most')
        self.ear.report('back', 'XujiWimsy hears Discord again')
        result = self.answer('discord_read', channel='general')['result']
        self.assertTrue(result['isError'])
        self.assertEqual(
            [item['text'] for item in result['content'][1:]],
            [
                "XujiWimsy news: XujiWimsy cannot reach Discord's gateway: OSError: down; it tries again, 60 s apart at most",
                'XujiWimsy news: XujiWimsy hears Discord again',
            ],
        )

    def test_a_stopped_gateway_is_said_and_discord_wait_says_it_cannot_hear(self):
        self.ear.report('stopped', 'Discord closed the gateway with 4004')
        start = self.fake.say(GENERAL, OWNER, 'go')
        result = self.answer('discord_wait', channel=GENERAL, after=start)['result']
        self.assertTrue(result['isError'])
        self.assertIn('the gateway stopped (Discord closed the gateway with 4004)', result['content'][0]['text'])
        self.assertIn(
            'XujiWimsy stopped hearing Discord: Discord closed the gateway with 4004', result['content'][1]['text']
        )

    def test_past_twenty_the_oldest_news_go_and_are_counted(self):
        for number in range(1, 26):
            self.ear.report('trouble', f'try {number}')
        texts = [item['text'] for item in self.contents()[1:]]
        self.assertEqual(texts[0], 'XujiWimsy news: 5 older news were left out: XujiWimsy keeps the newest 20')
        self.assertEqual(len(texts), 21)
        self.assertEqual(texts[1], "XujiWimsy news: XujiWimsy cannot reach Discord's gateway: try 6")
        self.assertEqual(texts[-1], "XujiWimsy news: XujiWimsy cannot reach Discord's gateway: try 25")


def until(check, what, seconds=5.0):
    """waits for another thread's work (a socket accepted, a line read), failing the test after seconds"""
    end = time.monotonic() + seconds
    while not check():
        if time.monotonic() > end:
            raise AssertionError(f'{what} did not happen in {seconds} s')
        time.sleep(0.01)


class Monitors(WithXuji):
    """what its server pushes reaches the session's monitors, a line each, at once; with none, the news wait"""

    def setUp(self):
        super().setUp()
        runtime = tempfile.TemporaryDirectory(prefix='xr-')  # short: a Unix socket's path has 107 bytes at most
        self.addCleanup(runtime.cleanup)
        self.runtime = Path(runtime.name)
        self.stop = threading.Event()
        self.addCleanup(self.stop.set)
        self.relay = aw.Relay(self.runtime / 'xujiwimsy', os.getpid())  # its client: alive, as a server's is
        self.threads = self.relay.start(self.stop, self.sent.append)
        self.server = self.started_server(self.bot, relay=self.relay)
        self.ear = aw.Ear(self.bot, self.server.push, threading.Event())
        self.ear.hear('READY', {'user': {'id': BOT}, 'session_id': 's', 'resume_gateway_url': 'ws://127.0.0.1:9'})

    def monitor(self):
        """a monitor connected, as --listen connects: its lines as they come"""
        count = len(self.relay.peers)
        conn = socket.socket(socket.AF_UNIX)
        conn.connect(str(self.relay.path))
        self.addCleanup(conn.close)
        until(lambda: len(self.relay.peers) > count, 'the relay taking the monitor')
        conn.settimeout(5)
        return conn.makefile('r', encoding='utf-8')

    def test_its_socket_is_its_clients_private_to_the_user(self):
        self.assertEqual(self.relay.path, self.runtime / 'xujiwimsy' / f'{os.getpid()}.sock')
        self.assertEqual(oct(self.relay.path.stat().st_mode & 0o777), '0o600')
        self.assertEqual(oct(self.relay.path.parent.stat().st_mode & 0o777), '0o700')
        self.assertIn(f'monitors: listening at {self.relay.path}', self.logs)
        self.assertEqual(
            aw.runtime_folder('xujiwimsy', {'XDG_RUNTIME_DIR': '/run/user/7'}), Path('/run/user/7/xujiwimsy')
        )
        self.assertEqual(aw.runtime_folder('xujiwimsy', {}), Path.home() / '.local/state/xujiwimsy')
        relay = aw.relay_for(aw.XUJI, 31, {'XDG_RUNTIME_DIR': '/run/user/7'})
        self.assertEqual(relay.path, Path('/run/user/7/xujiwimsy/31.sock'))
        self.assertIsNone(aw.relay_for(aw.AOGO, 31))  # a claude/channel pushes into its session

    def test_each_event_reaches_every_monitor_at_once_and_waits_as_news_only_when_none_listens(self):
        first, second = self.monitor(), self.monitor()
        number = self.fake.say(GENERAL, OWNER, 'to xuji, two\nlines', mentions=[BOT])
        self.ear.hear('MESSAGE_CREATE', self.fake.event(GENERAL, number))
        line = f'message: DraVee ({OWNER}) in channel {GENERAL}, message {number}: "to xuji, two\\nlines"\n'
        self.assertEqual((first.readline(), second.readline()), (line, line))
        self.assertIn('channel: a message event to 2 monitors', self.logs)
        draft = self.tool('discord_post', channel=GENERAL, text='approved later', wait=0)['draft']
        self.fake.react(draft, YES, OWNER)
        event = {'user_id': OWNER, 'channel_id': DM, 'message_id': draft, 'emoji': {'id': None, 'name': YES}}
        self.ear.hear('MESSAGE_REACTION_ADD', event)
        link = f'https://discord.com/channels/{GUILD}/{GENERAL}/{self.fake.last(GENERAL)["id"]}'
        self.assertEqual(first.readline(), f'draft: The owner approved draft {draft}: posted as {link}\n')
        self.assertEqual(second.readline(), f'draft: The owner approved draft {draft}: posted as {link}\n')
        self.assertEqual(len(self.answer('discord_read', channel=GENERAL)['result']['content']), 1)  # no news: heard
        first.close()
        second.close()
        for peer in list(self.relay.peers):
            peer.shutdown(socket.SHUT_RDWR)  # as a monitor Grok stopped: its next line fails and it is dropped
        self.ear.report('trouble', 'OSError: down; it tries again, 60 s apart at most')
        self.assertEqual(self.relay.peers, [])
        content = self.answer('discord_read', channel=GENERAL)['result']['content']
        self.assertEqual(
            content[1]['text'],
            "XujiWimsy news: XujiWimsy cannot reach Discord's gateway: OSError: down; it tries again, 60 s apart at "
            'most',
        )
        self.assertIn('channel: a error event, no monitor listens: kept for the next tool result', self.logs)

    def test_a_strangers_call_the_owner_let_through_and_a_strangers_dm_reach_it_as_aogowimsys_channel(self):
        lines = self.monitor()
        number = self.fake.say(GENERAL, STRANGER, 'hey xuji', mentions=[BOT])
        self.ear.hear('MESSAGE_CREATE', self.fake.event(GENERAL, number))  # a stranger's: nothing yet
        self.ear.hear(
            'MESSAGE_CREATE', self.fake.event(base.STRANGER_DM, self.fake.say(base.STRANGER_DM, STRANGER, 'psst'))
        )
        self.assertEqual(
            lines.readline(),
            f'dm: Stranger ({STRANGER}) wrote to XujiWimsy in DMs; nothing of what they wrote reaches the session\n',
        )
        self.fake.react(number, base.WIMSY, OWNER)
        name, _, emoji_id = base.WIMSY.partition(':')
        event = {'user_id': OWNER, 'channel_id': GENERAL, 'message_id': number, 'guild_id': GUILD}
        self.ear.hear('MESSAGE_REACTION_ADD', dict(event, emoji={'id': emoji_id, 'name': name}))
        self.assertEqual(
            lines.readline(), f'approved: Stranger ({STRANGER}) in channel {GENERAL}, message {number}: "hey xuji"\n'
        )

    def test_the_other_wimsy_listed_reaches_it_by_naming_it_in_its_text(self):
        # as AogoWimsy hands a session's work over: its post pings no one, so Discord gives it no mentions
        self.bot.settings = self.bot.settings._replace(users=self.bot.settings.users | {base.OTHER_BOT})
        lines = self.monitor()
        number = self.fake.say(GENERAL, base.OTHER_BOT, f'<@{BOT}> triage the open PRs, please')
        self.ear.hear('MESSAGE_CREATE', self.fake.event(GENERAL, number))
        said = f'"<@{BOT}> triage the open PRs, please"'
        self.assertEqual(
            lines.readline(), f'message: ReiWimsy ({base.OTHER_BOT}) in channel {GENERAL}, message {number}: {said}\n'
        )

    def test_a_line_fits_what_the_monitor_shows_its_text_cut_short_and_said(self):
        meta = {'kind': 'message', 'author': 'DraVee', 'author_id': OWNER, 'channel': GENERAL, 'message_id': HELP}
        meta.update(reply_to=OTHER, attachments='build.log; shot.png')
        text = 'olá, tudo bem? ' * 200 + 'THE END'
        line = aw.event_line(text, meta)
        self.assertLessEqual(len(line.encode()), aw.MONITOR_SHOWS)
        self.assertGreater(len(line.encode()), aw.MONITOR_SHOWS - 8)  # as much of the text as fits
        head = (
            f'message: DraVee ({OWNER}) in channel {GENERAL}, message {HELP}, replying to {OTHER}, attachments '
            'build.log; shot.png: "olá, tudo bem? '
        )
        self.assertTrue(line.startswith(head), line)
        self.assertTrue(line.endswith('..." (cut: discord_read gives it whole)'), line)
        self.assertNotIn('\n', line)
        short = aw.event_line('two\nlines "quoted"', meta)
        self.assertTrue(short.endswith(': "two\\nlines \\"quoted\\""'), short)
        said = aw.event_line('XujiWimsy stopped hearing Discord:\nwhy ' + 'x' * 600, {'kind': 'error'})
        self.assertTrue(said.startswith('error: XujiWimsy stopped hearing Discord: why xxx'), said)
        self.assertTrue(said.endswith('... (cut)'), said)
        self.assertLessEqual(len(said.encode()), aw.MONITOR_SHOWS)
        names = aw.event_line('hi', dict(meta, attachments='a' * 900))  # a head over the limit is cut too
        self.assertLessEqual(len(names.encode()), aw.MONITOR_SHOWS)

    def test_a_stale_socket_is_taken_over_and_a_live_ones_server_named(self):
        again = aw.Relay(self.relay.path.parent, os.getpid())
        with self.assertRaisesRegex(
            OSError, f'another server listens there, for the same client: .*{os.getpid()}.sock'
        ):
            again.open()
        self.assertTrue(self.relay.path.exists())
        stale = self.runtime / 'xujiwimsy' / '77.sock'
        left = socket.socket(socket.AF_UNIX)
        left.bind(str(stale))
        left.close()  # a server killed before it took its socket away
        relay = aw.Relay(stale.parent, 77)
        relay.open()
        self.addCleanup(relay.close)
        probe = socket.socket(socket.AF_UNIX)
        probe.connect(str(stale))
        probe.close()

    def test_the_sockets_of_clients_gone_are_taken_away_and_the_others_left(self):
        folder = self.runtime / 'xujiwimsy'
        gone, live = folder / '999999999.sock', folder / f'{os.getppid()}.sock'
        for path in (gone, live):
            left = socket.socket(socket.AF_UNIX)
            left.bind(str(path))
            left.close()
        (folder / '999999998.sock').mkdir()  # not a socket: left as it is
        relay = aw.Relay(folder, 4343)
        relay.open()
        self.addCleanup(relay.close)
        self.assertEqual(
            sorted(p.name for p in folder.iterdir()),
            sorted([self.relay.path.name, '4343.sock', live.name, '999999998.sock']),
        )
        self.assertIn(f'monitors: took away {gone}, its client 999999999 gone', self.logs)
        self.assertTrue(aw.alive(os.getpid()))
        self.assertFalse(aw.alive(999999999))

    def test_a_socket_it_cannot_open_is_said_and_waits_as_news(self):
        pushed = []
        long = aw.Relay(self.runtime / ('x' * 120), 4242)  # past a socket path's 107 bytes
        self.assertEqual(long.start(self.stop, lambda text, meta: pushed.append((text, meta))), [])
        self.assertEqual(len(pushed), 1)
        text, meta = pushed[0]
        self.assertEqual(meta, {'kind': 'error'})
        self.assertRegex(text, r'^it cannot open .*/4242.sock for its monitors: .+; discord_wait still hears$')
        self.assertIn(f'monitors: {text}', self.logs)

    def test_a_monitor_stopping_the_server_closes_its_socket(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(5)
        self.assertFalse(self.relay.path.exists())


class Listener(unittest.TestCase):
    """--listen's side: the server of its own session, found among its parents, each line as it comes"""

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='xl-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.proc = self.root / 'proc'  # a process tree: 300 (the monitor's shell) under 200 (the client) under 1
        for pid, parent in ((300, 200), (200, 1)):
            (self.proc / str(pid)).mkdir(parents=True)
            (self.proc / str(pid) / 'stat').write_text(f'{pid} (a (strange) name) S {parent} {pid} 0 0 -1\n')
        self.environ = {'XDG_RUNTIME_DIR': str(self.root)}
        self.out = io.StringIO()

    def listen(self):
        return aw.listen_to(aw.XUJI, self.out, self.environ, self.proc, parent=300)

    def test_its_parents_come_from_proc(self):
        self.assertEqual(aw.ancestors(300, self.proc), [300, 200])

    def test_it_prints_its_sessions_server_lines_and_says_when_it_stopped(self):
        stop = threading.Event()
        relay = aw.Relay(self.root / 'xujiwimsy', 200)
        relay.start(stop, None)
        got = []
        thread = threading.Thread(target=lambda: got.append(self.listen()))
        thread.start()
        until(lambda: relay.peers, 'the listener connecting')
        self.assertEqual(relay.send('message: one'), 1)
        self.assertEqual(relay.send('draft: two'), 1)
        until(lambda: self.out.getvalue().count('\n') == 2, 'the two lines printed')
        stop.set()
        thread.join(5)
        lines = self.out.getvalue().splitlines()
        self.assertEqual(lines[:2], ['message: one', 'draft: two'])
        self.assertEqual(
            lines[2],
            'XujiWimsy: its server for this session stopped; once it is up again, start this monitor again: '
            + aw.listen_command(aw.XUJI),
        )
        self.assertEqual(got, [1])

    def test_with_no_server_or_a_stopped_ones_socket_it_says_where_it_looked(self):
        (self.root / 'xujiwimsy').mkdir()
        left = socket.socket(socket.AF_UNIX)
        left.bind(str(self.root / 'xujiwimsy' / '200.sock'))
        left.close()
        self.assertEqual(self.listen(), 1)
        self.assertEqual(
            self.out.getvalue(),
            f'XujiWimsy: no XujiWimsy server listens for this session (none of {self.root}/xujiwimsy/<pid>.sock for '
            'its parents 300, 200): is xujiwimsy one of its MCP servers, and connected?\n',
        )

    def test_without_proc_it_says_it_cannot_find_its_server(self):
        self.assertEqual(aw.listen_to(aw.XUJI, self.out, self.environ, self.root / 'nowhere', parent=300), 1)
        self.assertRegex(
            self.out.getvalue(),
            r'^XujiWimsy: this monitor cannot see its parents \(.+\), so it cannot find its server\n$',
        )


class GatewayNames(WithXuji):
    def test_the_gateway_identifies_as_xujiwimsy_and_names_its_token(self):
        stop, reports = threading.Event(), []
        client = aw.Gateway(TOKEN, self.bot.discord, None, lambda kind, text: reports.append((kind, text)), stop)
        self.assertEqual(client.identify()['d']['properties']['browser'], 'xujiwimsy')
        with self.assertRaisesRegex(aw.Stopped, "4004: authentication failed: XUJIWIMSY_TOKEN is not the bot's token"):
            client.closed(4004, '')
        self.fake.fail[('GET', '/gateway/bot')] = (401, {'message': '401: Unauthorized', 'code': 0})
        client.run()
        self.assertEqual(
            reports, [('stopped', "Discord answered 401 to GET /gateway/bot: XUJIWIMSY_TOKEN is not the bot's token")]
        )


class Stdio(unittest.TestCase):
    """the real xujiwimsy.py, as Grok Build starts it; never told initialized, so it never reaches for Discord"""

    exchange, finish, start, ended = base.Stdio.exchange, base.Stdio.finish, base.Stdio.start, base.Stdio.ended
    program = HERE / 'xujiwimsy.py'

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = base.write_env(self.folder.name, GOOD_ENV, name='xujiwimsy.env')

    def test_the_handshake_tools_list_and_a_tool_call_through_a_subprocess(self):
        proc = self.start('--env', self.env)
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': GROK})
        result = answer['result']
        self.assertEqual(result['serverInfo']['name'], 'xujiwimsy')
        self.assertEqual(result['capabilities'], {'tools': {}})
        self.assertIn('--listen`; each line it prints is an event for you', result['instructions'])
        self.assertIn(f'channels {GENERAL}, {HELP} and their threads', result['instructions'])
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 'list', 'method': 'tools/list'})
        self.assertEqual(answer['result'], {'tools': aw.tool_list(aw.XUJI)})
        call = {'name': 'discord_read', 'arguments': {'channel': 'general'}}
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': call})
        self.assertEqual(
            answer['result']['content'],
            [{'type': 'text', 'text': 'channel is "general", not a Discord id (17 to 20 digits)'}],
        )
        errors = self.finish(proc)
        self.assertIn(f'xujiwimsy: up: owner {OWNER}, 1 users, 2 channels\n', errors)
        self.assertIn('xujiwimsy: discord_read failed: channel is "general"', errors)
        self.assertNotIn('aogowimsy', errors)

    def test_instructions_grok_would_cut_are_said_on_stderr_and_with_the_first_tool_result(self):
        channels = ', '.join(f'1300000000000000{n:03d}' for n in range(30))
        env = base.write_env(self.folder.name, GOOD_ENV.replace(f'{GENERAL}, {HELP}', channels), name='many.env')
        proc = self.start('--env', env)
        self.exchange(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': GROK})
        call = {'name': 'discord_read', 'arguments': {'channel': 'general'}}
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': call})
        news = answer['result']['content'][1]['text']
        self.assertRegex(news, r"^XujiWimsy news: XujiWimsy's instructions are [0-9]+ bytes and Grok Build shows")
        self.assertIn('List fewer ids in XUJIWIMSY_USERS or XUJIWIMSY_CHANNELS', news)
        self.assertIn(news.removeprefix('XujiWimsy news: '), self.finish(proc))

    def test_listen_prints_what_its_sessions_server_pushes_and_exits_once_it_stops(self):
        runtime = tempfile.TemporaryDirectory(prefix='xs-')
        self.addCleanup(runtime.cleanup)
        stop = threading.Event()
        relay = aw.Relay(Path(runtime.name) / 'xujiwimsy', os.getpid())  # this test is the client it runs under
        relay.start(stop, None)
        self.addCleanup(stop.set)
        proc = self.start('--listen', environ=dict(os.environ, XDG_RUNTIME_DIR=runtime.name))
        until(lambda: relay.peers, 'xujiwimsy.py --listen connecting')
        relay.send('message: DraVee (1) in channel 2, message 3: "hi"')
        self.assertEqual(proc.stdout.readline(), b'message: DraVee (1) in channel 2, message 3: "hi"\n')
        stop.set()
        self.assertEqual(proc.wait(5), 1)
        self.assertTrue(proc.stdout.read().decode().startswith('XujiWimsy: its server for this session stopped;'))
        self.assertEqual(proc.stderr.read(), b'')
        aogo = self.start('--listen', program=HERE.parent / 'aogo' / 'aogowimsy.py')
        self.assertEqual(aogo.wait(5), 1)
        self.assertIn(
            b'aogowimsy: --listen is for a client with no channel; AogoWimsy pushes into Claude Code',
            aogo.stderr.read(),
        )

    def test_claude_code_is_refused_and_stderr_says_so(self):
        proc = self.start('--env', self.env)
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': CLAUDE})
        self.assertIn('clientInfo.name is "claude-code": XujiWimsy is Xuji\'s', answer['error']['message'])
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
        self.assertIn('tools/list came before initialize; XujiWimsy speaks', answer['error']['message'])
        self.assertIn('xujiwimsy: initialize refused: clientInfo.name is "claude-code"', self.finish(proc))

    def test_aogowimsy_refuses_grok_through_its_subprocess(self):
        aogo_env = base.write_env(self.folder.name, base.GOOD_ENV)
        proc = self.start('--env', aogo_env, program=HERE.parent / 'aogo' / 'aogowimsy.py')
        grok = dict(GROK, clientInfo={'name': 'grok-shell-aogowimsy', 'version': '1.0.60'})
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': grok})
        self.assertIn('"grok-shell-aogowimsy", not "claude-code": AogoWimsy is Aogo\'s', answer['error']['message'])
        self.assertIn('aogowimsy: initialize refused: clientInfo.name is "grok-shell-aogowimsy"', self.finish(proc))

    def test_its_env_file_is_found_where_it_says_and_an_aogowimsy_one_stops_it(self):
        home = Path(self.folder.name) / 'home'
        (home / '.config' / 'xujiwimsy').mkdir(parents=True)
        base.write_env(home / '.config' / 'xujiwimsy', GOOD_ENV, name='xujiwimsy.env')
        proc = self.start(environ=dict(os.environ, HOME=str(home)))
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': GROK})
        self.assertEqual(answer['result']['serverInfo']['title'], 'XujiWimsy')
        self.assertIn(f'xujiwimsy: up: owner {OWNER}', self.finish(proc))
        aogo_env = base.write_env(self.folder.name, base.GOOD_ENV)
        proc = self.start('--env', aogo_env)
        self.assertEqual(proc.wait(), 1)
        said = proc.stderr.read().decode()
        self.assertIn(f'xujiwimsy: {aogo_env} line 2: AOGOWIMSY_TOKEN is not a key XujiWimsy knows', said)
        self.assertNotIn(TOKEN, said)
        proc = self.start('--help')
        self.assertEqual(proc.wait(), 0)
        said = proc.stdout.read().decode()
        self.assertIn('usage: xujiwimsy.py', said)
        self.assertIn('~/.config/xujiwimsy/xujiwimsy.env', said)


if __name__ == '__main__':
    unittest.main()
