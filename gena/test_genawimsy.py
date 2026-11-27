#!/usr/bin/env python3
"""genawimsy.py without Discord or the network: what makes GenaWimsy Gena's (its env file and keys, its server's
name, no claude/channel, its instructions, its tools in its names, the unicode emojis, :wimsygena:), the client each
Wimsy serves, its fixed direct interval, and what agy needs: a monitor that ends on what it gets (the relay's one
delivery a monitor, the backlog that waits for the next, --listen ending with 0), down to the program on stdin and
stdout. AogoWimsy's suite tests the code they share; its fake Discord serves here too."""

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
# agy's clientInfo is not known here (nothing of it was captured): any name but Claude Code's is served the same
AGY = {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'antigravity', 'version': '1'}}
GROK = {
    'protocolVersion': '2025-11-25',
    'capabilities': {},
    'clientInfo': {'name': 'grok-shell-aogowimsy', 'version': '1'},
}
CLAUDE = base.INITIALIZE
GOOD_ENV = base.GOOD_ENV.replace('AOGOWIMSY_', 'GENAWIMSY_').replace('# AogoWimsy', '# GenaWimsy')
KNOWS = 'GENAWIMSY_TOKEN, GENAWIMSY_OWNER, GENAWIMSY_USERS, GENAWIMSY_CHANNELS'


def initialize(server, params):
    return server.handle({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': params})


def until(check, what, seconds=5.0):
    end = time.monotonic() + seconds
    while not check():
        if time.monotonic() > end:
            raise AssertionError(f'{what} did not happen in {seconds} s')
        time.sleep(0.01)


class EnvFile(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def refused(self, text, identity=aw.GENA, mode=0o600):
        with self.assertRaises(aw.Refused) as caught:
            aw.read_settings(base.write_env(self.folder.name, text, mode, 'bot.env'), identity)
        self.assertNotIn(TOKEN, str(caught.exception))
        return str(caught.exception)

    def test_its_file_takes_the_genawimsy_keys_with_aogowimsys_meanings(self):
        path = base.write_env(self.folder.name, GOOD_ENV, name='genawimsy.env')
        settings = aw.read_settings(path, aw.GENA)
        self.assertEqual(settings, aw.Settings(TOKEN, OWNER, frozenset({FRIEND}), frozenset({GENERAL, HELP}), aw.GENA))
        self.assertEqual(aw.GENA.env, '~/.config/genawimsy/genawimsy.env')
        self.assertEqual(aw.GENA.direct_keys, ('GENAWIMSY_DIRECT', 'GENAWIMSY_DIRECT_MINUTES'))

    def test_another_bots_key_in_its_file_stops_it_naming_the_key_and_the_reverse(self):
        said = self.refused(GOOD_ENV + f'XUJIWIMSY_TOKEN={TOKEN}\n')
        self.assertIn(f'line 7: XUJIWIMSY_TOKEN is not a key GenaWimsy knows; it knows {KNOWS}', said)
        self.assertIn('line 2: AOGOWIMSY_TOKEN is not a key GenaWimsy knows', self.refused(base.GOOD_ENV))
        said = self.refused(GOOD_ENV, aw.XUJI)
        self.assertIn('line 2: GENAWIMSY_TOKEN is not a key XujiWimsy knows', said)
        self.assertIn('line 2: GENAWIMSY_TOKEN is not a key AogoWimsy knows', self.refused(GOOD_ENV, aw.AOGO))
        for key in ('GENAWIMSY_GREET_HOURS', 'GENAWIMSY_GREET_PER_HOUR'):  # it greets no one
            self.assertIn(f'line 7: {key} is not a key GenaWimsy knows', self.refused(GOOD_ENV + f'{key}=24\n'))

    def test_its_example_is_xujiwimsys_in_its_names_and_stops_at_the_first_empty_key(self):
        xuji = (HERE.parent / 'xuji' / 'xujiwimsy.env.example').read_text()
        renamed = xuji.replace('XujiWimsy', 'GenaWimsy').replace('xujiwimsy', 'genawimsy').replace('XUJI', 'GENA')
        self.assertEqual((HERE / 'genawimsy.env.example').read_text(), renamed)
        example = base.write_env(self.folder.name, renamed, name='example.env')
        with self.assertRaisesRegex(aw.Refused, 'GENAWIMSY_TOKEN is empty, and GenaWimsy needs it'):
            aw.read_settings(example, aw.GENA)


class WithGena(base.WithDiscord):
    """GenaWimsy's tools through its server, initialized by agy, against the fake Discord"""

    def setUp(self):
        super().setUp()
        self.settings = self.settings._replace(identity=aw.GENA)
        self.bot = aw.Wimsy(self.settings, aw.Discord(TOKEN, self.clock, self.api, identity=aw.GENA), self.clock)
        self.server = aw.Server(self.bot, aw.instructions(self.bot.settings), self.sent.append)
        self.assertIn('result', initialize(self.server, AGY))


class Handshake(WithGena):
    def test_its_server_info_and_no_claude_channel(self):
        result = initialize(aw.Server(self.bot, 'test', self.sent.append), AGY)['result']
        self.assertEqual(result['serverInfo'], {'name': 'genawimsy', 'title': 'GenaWimsy', 'version': aw.VERSION})
        self.assertEqual(result['capabilities'], {'tools': {}})

    def test_its_instructions_say_who_it_is_and_to_run_its_listener_as_a_background_command(self):
        said = aw.instructions(self.settings)
        self.assertTrue(
            said.startswith(f'GenaWimsy is Gena on Discord. Every post is a draft its owner (Discord user {OWNER})')
        )
        self.assertIn('/gena sets who reaches you (trust, allow, weight, tone)', said)
        self.assertIn(
            f'Discord reaches you through a listener: at the start, run `python3 {HERE / "genawimsy.py"} --listen` in '
            'the background (run_command, WaitMsBeforeAsync 500). It ends with what came, a line each (a text cut short '
            'is whole in discord_read), which wakes you; answer, then run it again (what comes meanwhile waits). '
            "Without it, discord_wait hears a channel. The owner's DMs with GenaWimsy are the channel of a draft's link.",
            said,
        )
        self.assertNotIn('monitor tool, persistent', said)
        for other in ('Aogo', 'Xuji', 'xuji', '<channel>', 'wimsyaogo'):
            self.assertNotIn(other, said)

    def test_its_instructions_fit_the_bound_and_too_many_ids_are_said_naming_agy(self):
        users = frozenset(f'20539067360960960{n}' for n in range(3))
        channels = frozenset(f'130000000000000000{n}' for n in range(4))
        for listed in (None, channels):
            settings = self.settings._replace(users=users, channels=listed)
            said = aw.instructions(settings)
            self.assertLessEqual(len(said.encode()), aw.GROK_SHOWS)
            self.assertTrue(said.endswith('which saves them and gives their paths.'))
            self.assertIsNone(aw.cut_by_grok(settings, said))
        many = self.settings._replace(channels=frozenset(f'1300000000000000{n:03d}' for n in range(30)))
        said = aw.instructions(many)
        self.assertEqual(
            aw.cut_by_grok(many, said),
            f"GenaWimsy's instructions are {len(said.encode())} bytes and agy may show its model no more than Grok "
            'Build, the first 2048 (its own limit is not measured): the end of them (how to answer, attachments) is '
            'lost. List fewer ids in GENAWIMSY_USERS or GENAWIMSY_CHANNELS, which take 651 bytes of them',
        )
        xuji = many._replace(identity=aw.XUJI)
        self.assertIn('bytes and Grok Build shows its model the first 2048: the end', aw.cut_by_grok(xuji, said))

    def test_its_tools_are_xujiwimsys_in_its_own_names_with_the_unicode_emojis(self):
        gena, xuji = aw.tool_list(aw.GENA), aw.tool_list(aw.XUJI)
        # Xuji's less the upload of drawn emojis: Gena has none yet
        self.assertEqual(
            [tool['name'] for tool in gena], [t['name'] for t in xuji if t['name'] != 'discord_emoji_upload']
        )
        text = json.dumps(gena, ensure_ascii=False)
        for other in ('aogo', 'xuji'):
            self.assertNotIn(other, text.lower())
        self.assertIn('GENAWIMSY_DIRECT_MINUTES (30 by default), fixed, as its client reports no quota', text)
        tools = {tool['name']: tool for tool in gena}
        plain = [aw.EYES, aw.YES, aw.THUMBS, aw.NO]
        self.assertEqual(tools['discord_react']['inputSchema']['properties']['emoji']['enum'], plain)  # no drawings
        self.assertEqual(tools['discord_quick']['inputSchema']['properties']['emoji']['enum'], plain)
        self.assertNotIn('discord_cancel', tools)
        self.assertEqual(
            self.server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})['result'], {'tools': gena}
        )

    def test_its_files_and_state_go_to_folders_of_their_own(self):
        self.assertEqual(self.bot.files.name, 'genawimsy')
        self.assertEqual(aw.state_folder('genawimsy', {'XDG_STATE_HOME': '/var/s'}), Path('/var/s/genawimsy'))
        self.assertEqual(aw.listen_command(aw.GENA), f'python3 {HERE / "genawimsy.py"} --listen')


class Clients(WithGena):
    def test_genawimsy_refuses_claude_code_naming_aogowimsy_and_serves_any_other(self):
        server = aw.Server(self.bot, 'test', self.sent.append)
        self.assertEqual(
            initialize(server, CLAUDE)['error']['message'],
            'Invalid params: clientInfo.name is "claude-code": GenaWimsy is Gena\'s, for any client but Claude Code, '
            'which runs AogoWimsy (aogowimsy); take genawimsy out of its MCP servers',
        )
        for params in (AGY, GROK, {'protocolVersion': '2025-11-25', 'capabilities': {}}):
            self.assertIn('result', initialize(server, params))

    def test_aogowimsy_refuses_agy_naming_both_bots_another_client_runs(self):
        aogo = aw.Wimsy(self.settings._replace(identity=aw.AOGO), aw.Discord(TOKEN, self.clock, self.api), self.clock)
        error = initialize(aw.Server(aogo, 'test', self.sent.append), AGY)['error']
        self.assertEqual(
            error['message'],
            'Invalid params: clientInfo.name is "antigravity", not "claude-code": AogoWimsy is Aogo\'s, for Claude '
            'Code alone; another client runs XujiWimsy (xujiwimsy) or GenaWimsy (genawimsy) and keeps aogowimsy off '
            '(Grok Build: grok mcp disable aogowimsy; agy: agy mcp remove aogowimsy)',
        )


class Posting(WithGena):
    def test_its_direct_posts_pass_the_pre_harness_and_go_at_a_fixed_interval_from_its_keys(self):
        said = self.error('discord_post', channel=GENERAL, text='see /home/dravee/WorkDir/notes.txt', direct=True)
        self.assertIn('the pre-harness keeps this text from going direct: machine-path', said)
        got = self.tool('discord_post', channel=GENERAL, text='hello', direct=True)
        self.assertEqual((got['status'], got['direct']), ('sent', 'interval'))
        said = self.error('discord_post', channel=GENERAL, text='again', direct=True)
        self.assertIn('GENAWIMSY_DIRECT_MINUTES 30, fixed: its client reports no quota', said)

    def test_only_the_wimsygena_reaction_lets_a_strangers_message_through(self):
        self.assertEqual(aw.GENA.wimsy, 'wimsygena')
        mine = self.fake.say(GENERAL, base.BOT, 'a post of mine')
        xujis = self.fake.say(GENERAL, STRANGER, "with xuji's emoji", reply_to=mine)
        hers = self.fake.say(GENERAL, STRANGER, 'with hers', reply_to=mine)
        self.fake.react(xujis, 'wimsyxuji:600000000000000003', OWNER)
        self.fake.react(hers, 'wimsygena:600000000000000004', OWNER)
        got = self.tool('discord_read', channel=GENERAL)
        self.assertEqual([(m['id'], m['approved']) for m in got['messages']], [(mine, False), (hers, True)])
        self.assertIn("another's when his :wimsygena: is on it", aw.instructions(self.settings))

    def test_its_command_is_gena_and_its_help_says_who_it_is(self):
        ear = aw.Ear(self.bot, self.server.push, threading.Event())
        ear.hear('READY', {'user': {'id': BOT}, 'session_id': 's', 'resume_gateway_url': 'ws://127.0.0.1:9'})
        ear.hear('GUILD_CREATE', {'id': GUILD, 'channels': [], 'threads': []})
        self.assertEqual([command['name'] for command in self.fake.commands[GUILD]], ['gena'])
        event = {'id': '1600000000000000002', 'type': 2, 'token': 'token-1600000000000000002', 'channel_id': GENERAL}
        event['data'] = {'name': 'gena', 'options': [{'name': 'help', 'type': 1}]}
        ear.hear('INTERACTION_CREATE', dict(event, member={'user': {'id': STRANGER}}))
        said = json.dumps(self.fake.answers['1600000000000000002'], ensure_ascii=False)
        self.assertIn(f"I'm Gena, <@{OWNER}>'s AI agent here", said)


class Monitors(WithGena):
    """agy wakes on a command's end: each monitor gets one delivery and is closed; what comes meanwhile waits"""

    def setUp(self):
        super().setUp()
        runtime = tempfile.TemporaryDirectory(prefix='gr-')  # short: a Unix socket's path has 107 bytes at most
        self.addCleanup(runtime.cleanup)
        self.stop = threading.Event()
        self.addCleanup(self.stop.set)
        self.relay = aw.relay_for(aw.GENA, os.getpid(), {'XDG_RUNTIME_DIR': runtime.name})
        self.assertTrue(self.relay.once)
        self.relay.start(self.stop, self.sent.append)
        self.server = aw.Server(self.bot, aw.instructions(self.bot.settings), self.sent.append, relay=self.relay)
        self.assertIn('result', initialize(self.server, AGY))

    def monitor(self, accepted=True):
        count = len(self.relay.peers)
        conn = socket.socket(socket.AF_UNIX)
        conn.connect(str(self.relay.path))
        self.addCleanup(conn.close)
        if accepted:
            until(lambda: len(self.relay.peers) > count, 'the relay taking the monitor')
        conn.settimeout(5)
        return conn.makefile('r', encoding='utf-8')

    def test_a_monitor_gets_one_event_and_is_closed_so_its_command_ends(self):
        first, second = self.monitor(), self.monitor()
        self.server.push('one', {'kind': 'notice'})
        self.assertEqual((first.readline(), second.readline()), ('notice: one\n', 'notice: one\n'))
        self.assertEqual((first.readline(), second.readline()), ('', ''))  # closed: the listener ends
        self.assertEqual(self.relay.peers, [])
        self.assertIn('channel: a notice event to 2 monitors', self.logs)

    def test_what_comes_while_none_listens_waits_for_the_next_monitor_and_the_next_tool_result(self):
        self.server.push('first', {'kind': 'notice'})
        self.server.push('second', {'kind': 'error'})
        self.assertIn(
            'channel: a notice event, no monitor listens: kept for the next monitor and the next tool result', self.logs
        )
        lines = self.monitor(accepted=False)
        self.assertEqual(
            [lines.readline(), lines.readline(), lines.readline()], ['notice: first\n', 'error: second\n', '']
        )
        self.assertEqual(self.relay.backlog, [])
        self.assertIn('monitors: 2 lines that waited went to a monitor', self.logs)
        later = self.monitor()  # nothing waits: it listens for the next
        self.server.push('third', {'kind': 'notice'})
        self.assertEqual(later.readline(), 'notice: third\n')
        self.assertEqual(self.relay.peers, [])  # the third went to the monitor, which was closed
        content = self.answer('discord_read', channel=GENERAL)['result']['content']
        self.assertEqual([each['text'] for each in content[1:3]], ['GenaWimsy news: first', 'GenaWimsy news: second'])

    def test_while_no_listener_waits_each_result_says_how_to_start_it_as_agy_shows_no_instructions(self):
        reminder = (
            'GenaWimsy news: no listener of yours waits, so Discord wakes no one: run '
            f'`{aw.listen_command(aw.GENA)}` in the background (run_command, WaitMsBeforeAsync 500)'
        )
        content = self.answer('discord_read', channel=GENERAL)['result']['content']
        self.assertEqual(content[-1]['text'], reminder)
        self.monitor()
        content = self.answer('discord_read', channel=GENERAL)['result']['content']
        self.assertEqual(len(content), 1)  # one waits: nothing to say

    def test_past_twenty_the_oldest_that_wait_go_and_the_next_monitor_is_told_how_many(self):
        for number in range(1, 24):
            self.server.push(f'n{number}', {'kind': 'notice'})
        lines = self.monitor(accepted=False)
        got = [line.rstrip('\n') for line in lines]
        self.assertEqual(got[0], 'notice: 3 older events were left out: the newest 20 waited')
        self.assertEqual((got[1], got[-1], len(got)), ('notice: n4', 'notice: n23', 21))

    def test_a_monitor_gone_before_its_delivery_leaves_the_backlog_for_the_next(self):
        self.server.push('kept', {'kind': 'notice'})
        relay = aw.Relay(self.relay.path.parent, 4242, once=True)
        relay.backlog = ['notice: kept']

        class Gone:
            def sendall(self, data):
                raise BrokenPipeError(32, 'Broken pipe')

            def close(self):
                pass

        with relay.guard:
            relay.deliver(Gone())
        self.assertEqual(relay.backlog, ['notice: kept'])
        self.assertIn('monitors: one is gone before its delivery (Broken pipe); 1 lines wait', self.logs)


class Listener(unittest.TestCase):
    """--listen for agy: the lines of its one delivery, then what to do, and 0; nothing, then the server stopped, 1"""

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='gl-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.proc = self.root / 'proc'
        for pid, parent in ((300, 200), (200, 1)):
            (self.proc / str(pid)).mkdir(parents=True)
            (self.proc / str(pid) / 'stat').write_text(f'{pid} (sh) S {parent} {pid} 0 0 -1\n')
        self.environ = {'XDG_RUNTIME_DIR': str(self.root)}
        self.out = io.StringIO()
        self.stop = threading.Event()
        self.addCleanup(self.stop.set)

    def listen(self, seconds=5.0):
        """listen_to's answer, failing the test when it has none within seconds rather than hanging it"""
        got = []
        thread = threading.Thread(
            target=lambda: got.append(aw.listen_to(aw.GENA, self.out, self.environ, self.proc, parent=300)),
            daemon=True,
        )
        thread.start()
        thread.join(seconds)
        if not got:
            raise AssertionError(f'listen_to did not end in {seconds} s; it printed {self.out.getvalue()!r}')
        return got[0]

    def test_it_prints_its_one_delivery_says_to_start_it_again_and_ends_with_0(self):
        relay = aw.Relay(self.root / 'genawimsy', 200, once=True)
        relay.start(self.stop, None)
        relay.send('message: one')  # none listens: it waits
        self.assertEqual(self.listen(), 0)
        self.assertEqual(
            self.out.getvalue().splitlines(),
            [
                'message: one',
                f'GenaWimsy: once you have answered, start this listener again: {aw.listen_command(aw.GENA)}',
            ],
        )

    def test_no_server_found_is_said_with_the_sandbox_as_a_cause(self):
        self.assertEqual(self.listen(), 1)
        self.assertEqual(
            self.out.getvalue(),
            f'GenaWimsy: no GenaWimsy server listens for this session (none of {self.root}/genawimsy/<pid>.sock for '
            "its parents 300, 200): is genawimsy one of its MCP servers, and connected? Or agy's sandbox hides the "
            'folder: run this with BypassSandbox.\n',
        )

    def test_a_server_that_stops_before_anything_came_is_said_with_1(self):
        relay = aw.Relay(self.root / 'genawimsy', 200, once=True)
        relay.start(self.stop, None)
        threading.Timer(0.3, self.stop.set).start()  # once the listener is connected
        self.assertEqual(self.listen(), 1)
        self.assertTrue(self.out.getvalue().startswith('GenaWimsy: its server for this session stopped;'))


class Stdio(unittest.TestCase):
    """the real genawimsy.py, as agy starts it; never told initialized, so it never reaches for Discord"""

    exchange, finish, start, ended = base.Stdio.exchange, base.Stdio.finish, base.Stdio.start, base.Stdio.ended
    program = HERE / 'genawimsy.py'

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = base.write_env(self.folder.name, GOOD_ENV, name='genawimsy.env')

    def test_the_handshake_tools_list_and_claude_code_refused_through_a_subprocess(self):
        proc = self.start('--env', self.env)
        result = self.exchange(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': AGY})['result']
        self.assertEqual((result['serverInfo']['name'], result['capabilities']), ('genawimsy', {'tools': {}}))
        self.assertIn('--listen` in the background (run_command', result['instructions'])
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 'list', 'method': 'tools/list'})
        self.assertEqual(answer['result'], {'tools': aw.tool_list(aw.GENA)})
        self.assertIn(f'genawimsy: up: owner {OWNER}, 1 users, 2 channels\n', self.finish(proc))
        proc = self.start('--env', self.env)
        answer = self.exchange(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': CLAUDE})
        self.assertIn('clientInfo.name is "claude-code": GenaWimsy is Gena\'s', answer['error']['message'])
        self.assertIn('genawimsy: initialize refused', self.finish(proc))

    def test_listen_prints_its_one_delivery_and_ends_with_0(self):
        runtime = tempfile.TemporaryDirectory(prefix='gs-')
        self.addCleanup(runtime.cleanup)
        stop = threading.Event()
        relay = aw.Relay(Path(runtime.name) / 'genawimsy', os.getpid(), once=True)  # this test is its client
        relay.start(stop, None)
        self.addCleanup(stop.set)
        proc = self.start('--listen', environ=dict(os.environ, XDG_RUNTIME_DIR=runtime.name))
        until(lambda: relay.peers, 'genawimsy.py --listen connecting')
        self.assertEqual(relay.send('message: DraVee (1) in channel 2, message 3: "oi Gena"'), 1)
        self.assertEqual(proc.wait(5), 0)
        lines = proc.stdout.read().decode().splitlines()
        self.assertEqual(lines[0], 'message: DraVee (1) in channel 2, message 3: "oi Gena"')
        self.assertTrue(lines[1].startswith('GenaWimsy: once you have answered, start this listener again: python3 '))
        self.assertEqual(proc.stderr.read(), b'')


if __name__ == '__main__':
    unittest.main(verbosity=1)
