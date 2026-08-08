# pymollm

Natural-language agent for [PyMOL](https://pymol.org). Type English on the PyMOL command line; an LLM plans with tools, runs real PyMOL commands, asks when information is missing, and can export a replayable `.pml` script.

## Features

- **RCSB resolve** — protein names are looked up before guessing or asking
- **Typed science tools** — B-factor coloring, residue select, align+RMSD, solvents (plus raw `run_pymol` for everything else)
- **Verify / repair** — check objects and selections after mutations; feed errors back to the model
- **CLI ask/answer** — `ask_user` pauses; reply with `llm_answer`
- **Undo + export** — session snapshot undo and `.pml` transcript export
- **OpenAI, Claude, Gemini** — tool-calling for each provider

## Install

Add the repo to PyMOL’s startup file (`~/.pymolrc.py`):

```python
import sys
from pathlib import Path

PYMOLLM_ROOT = Path("/path/to/pymollm")  # your clone
if str(PYMOLLM_ROOT) not in sys.path:
    sys.path.insert(0, str(PYMOLLM_ROOT))

import pymollm
pymollm.__init_plugin__()
```

See [`examples/pymolrc.py`](examples/pymolrc.py).

Or install into the same Python that runs PyMOL:

```bash
python -m pip install -e /path/to/pymollm
```

## Configure

```text
PyMOL> llm_config provider openai key sk-... model gpt-4.1
PyMOL> llm_config provider anthropic key sk-ant-... model claude-sonnet-4-20250514
PyMOL> llm_config provider gemini key AIza... model gemini-2.5-flash
PyMOL> llm_config
```

Config is stored at `~/.pymollm/config.json`.  
Environment variables: `PYMOLLM_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` / `GEMINI_API_KEY`, plus `PYMOLLM_PROVIDER`, `PYMOLLM_MODEL`, `PYMOLLM_BASE_URL`.

OpenAI-compatible proxies:

```text
PyMOL> llm_config provider openai base_url https://openrouter.ai/api/v1 key sk-or-... model openai/gpt-4.1
```

## Usage

```text
PyMOL> llm get BARSTAR, colour by b-factor, select residues 29+33+37, load the mutant, align them, show RMSD and solvents
pymollm: Which BARSTAR structure should I use?
pymollm:   1) 1A19 — ...
pymollm:   2) 1BTA — ...
PyMOL> llm_answer 1
PyMOL> llm_answer /path/to/barstar_mutant.pdb
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

Blocked by default: `quit`, `reinitialize`, `delete all`, `remove all`, shell/system escapes, `run` / `@` scripts, and Python `exec`/`eval` patterns.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT
