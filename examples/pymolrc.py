# Example ~/.pymolrc.py snippet to load pymollm on PyMOL startup.

import sys
from pathlib import Path

PYMOLLM_ROOT = Path("/path/to/pymollm")  # edit to your clone

if PYMOLLM_ROOT.is_dir() and str(PYMOLLM_ROOT) not in sys.path:
    sys.path.insert(0, str(PYMOLLM_ROOT))

import pymollm

pymollm.__init_plugin__()
