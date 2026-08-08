# pymollm

Natural-language agent for [PyMOL](https://pymol.org). Type English on the PyMOL command line; an LLM plans with tools, runs real PyMOL commands, asks when information is missing, and can export a replayable `.pml` script.

## Why pymollm

Compared to one-shot “NL → PML” plugins, pymollm is built for accuracy on multi-step structural biology requests:

- **RCSB resolve** — `"get BARSTAR…"` searches RCSB before guessing or asking
- **Typed science tools** — B-factor coloring, residue select, align+RMSD, solvents (plus raw `run_pymol` for everything else)
- **Verify / repair** — check objects/selections after mutations; feed errors back to the model
- **CLI ask/answer** — `ask_user` pauses; you reply with `llm_answer`
- **Undo + export** — session snapshot undo and `.pml` transcript export
- **OpenAI, Claude, Gemini** — native tool-calling for each provider

## Install

**Recommended for macOS `PyMOL.app`:** put the repo on `sys.path` in `~/.pymolrc.py` (no pip required; HTTP uses the stdlib):

```python
import sys
from pathlib import Path

PYMOLLM_ROOT = Path("/Users/nevinpai/git/pymollm")  # <- your clone
if str(PYMOLLM_ROOT) not in sys.path:
    sys.path.insert(0, str(PYMOLLM_ROOT))

import pymollm
pymollm.__init_plugin__()
```

See also [`examples/pymolrc.py`](examples/pymolrc.py).

**conda / pymol-open-source** (optional pip install):

```bash
python -m pip install -e /path/to/pymollm
```

Optional faster HTTP: `pip install httpx` (same Python as PyMOL). Without it, pymollm uses `urllib`.

## Configure

```text
PyMOL> llm_config provider openai key sk-... model gpt-4.1
PyMOL> llm_config provider anthropic key sk-ant-... model claude-sonnet-4-20250514
PyMOL> llm_config provider gemini key AIza... model gemini-2.5-flash
PyMOL> llm_config          # show (key is masked)
```

Config is stored at `~/.pymollm/config.json` (mode `0600`).  
Env fallbacks: `PYMOLLM_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` / `GEMINI_API_KEY`, plus `PYMOLLM_PROVIDER`, `PYMOLLM_MODEL`, `PYMOLLM_BASE_URL`.

OpenAI-compatible proxies:

```text
PyMOL> llm_config provider openai base_url https://openrouter.ai/api/v1 key sk-or-... model openai/gpt-4.1
```

## Usage

```text
PyMOL> llm get BARSTAR, colour by b-factor, select residues 29+33+37, load the mutant, align them, show RMSD and solvents
pymollm: → resolve_structure({"query": "BARSTAR"})
pymollm: Multiple candidates; ask the user to choose.
pymollm: Which BARSTAR structure should I use?
pymollm:   1) 1A19 — BARSTAR (MUTANT) ...
pymollm:   2) 1BTA — ...
pymollm: Reply with: llm_answer <text or choice number>
PyMOL> llm_answer 1
...
PyMOL> llm_answer /path/to/barstar_mutant.pdb
...
pymollm: Aligned 'barstar_mutant' onto '1A19' via align. RMSD=...
pymollm: Commands executed:
  fetch 1A19, ...
  spectrum b, rainbow, 1A19
  ...
PyMOL> llm_export barstar_session.pml
PyMOL> llm_undo
PyMOL> llm_status
PyMOL> llm_clear
```

### Commands

| Command | Purpose |
|---------|---------|
| `llm <prompt>` | Run the agent |
| `llm_answer <text>` | Answer a pending clarification |
| `llm_config ...` | Set provider / key / model |
| `llm_status` | Provider, pending ask, history size |
| `llm_clear` | Clear conversation |
| `llm_undo` | Restore pre-turn session snapshot |
| `llm_export [path]` | Write last commands as `.pml` |

## Safety

Blocked by default: `quit`, `reinitialize`, `delete all`, `remove all`, shell/system escapes, `run` / `@` scripts, Python `exec`/`eval` patterns.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT
