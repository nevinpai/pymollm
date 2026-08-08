# Add to ~/.pymolrc.py (or replace that file with this).
# Prefer installing into PyMOL's Python; path fallback works without pip.

import sys
from pathlib import Path

# <<< edit if your clone lives elsewhere
PYMOLLM_ROOT = Path("/Users/nevinpai/git/pymollm")
# >>>

if PYMOLLM_ROOT.is_dir() and str(PYMOLLM_ROOT) not in sys.path:
    sys.path.insert(0, str(PYMOLLM_ROOT))

try:
    import pymollm

    pymollm.__init_plugin__()
except Exception as exc:
    print(f"pymollm: failed to load ({exc})")
    print("pymollm: install with PyMOL's python, or fix PYMOLLM_ROOT in ~/.pymolrc.py")
