#!/usr/bin/env python3
"""GenaWimsy: Gena, the session in Antigravity's agy, on Discord as a bot of its own, every post approved by its owner
first, or direct within his rules.

    genawimsy.py [--env FILE]       FILE: ~/.config/genawimsy/genawimsy.env when not given; mode 600 or stricter
    genawimsy.py --listen           what this session's server has for it, then it ends: the session runs it in the
                                    background and starts it again after each

aogo/aogowimsy.py with Gena's identity: its bot, its env file and GENAWIMSY_ keys, its tools in its names (the
unicode emojis, until Gena is drawn), /gena, no claude/channel, and any client but Claude Code. agy wakes its session
when a background command ends, so its monitor ends on the first events (Identity.once). A fix there is a fix here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'aogo'))
import aogowimsy

if __name__ == '__main__':
    aogowimsy.main(identity=aogowimsy.GENA)
