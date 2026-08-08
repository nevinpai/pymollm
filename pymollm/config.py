"""Persistent configuration for pymollm (~/.pymollm/config.json)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

CONFIG_DIR = Path.home() / ".pymollm"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_MODELS = {
    "openai": "gpt-4.1",
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.5-flash",
}


@dataclass
class Config:
    provider: str = "openai"  # openai | anthropic | gemini
    api_key: str = ""
    model: str = ""
    base_url: str = ""  # optional OpenAI-compatible base URL
    max_steps: int = 16
    export_dir: str = ""

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        return DEFAULT_MODELS.get(self.provider, "gpt-4.1")

    def to_public_dict(self) -> dict[str, Any]:
        d = asdict(self)
        key = d.get("api_key") or ""
        if len(key) > 8:
            d["api_key"] = key[:4] + "…" + key[-4:]
        elif key:
            d["api_key"] = "***"
        else:
            d["api_key"] = "(not set)"
        d["model"] = self.resolved_model()
        return d


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        cfg = Config()
        # Allow env overrides on first load
        _apply_env(cfg)
        return cfg
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cfg = Config()
        _apply_env(cfg)
        return cfg
    cfg = Config(
        provider=str(data.get("provider") or "openai"),
        api_key=str(data.get("api_key") or ""),
        model=str(data.get("model") or ""),
        base_url=str(data.get("base_url") or ""),
        max_steps=int(data.get("max_steps") or 16),
        export_dir=str(data.get("export_dir") or ""),
    )
    if not cfg.api_key:
        _apply_env(cfg)
    return cfg


def save_config(cfg: Config) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass
    return CONFIG_PATH


def update_config(**kwargs: Any) -> Config:
    cfg = load_config()
    for key, value in kwargs.items():
        if value is None:
            continue
        if not hasattr(cfg, key):
            raise ValueError(f"Unknown config field: {key}")
        setattr(cfg, key, value)
    if "provider" in kwargs and kwargs["provider"] and not kwargs.get("model"):
        # Reset model when switching provider unless explicitly set
        if not cfg.model or cfg.model in DEFAULT_MODELS.values():
            cfg.model = DEFAULT_MODELS.get(cfg.provider, cfg.model)
    save_config(cfg)
    return cfg


def _apply_env(cfg: Config) -> None:
    provider = os.environ.get("PYMOLLM_PROVIDER")
    if provider:
        cfg.provider = provider.strip().lower()
    key = (
        os.environ.get("PYMOLLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    )
    if key and not cfg.api_key:
        cfg.api_key = key
    model = os.environ.get("PYMOLLM_MODEL")
    if model:
        cfg.model = model
    base = os.environ.get("PYMOLLM_BASE_URL")
    if base:
        cfg.base_url = base
