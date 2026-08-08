import json
from pathlib import Path

from pymollm import config as config_mod


def test_update_and_load(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".pymollm"
    cfg_path = cfg_dir / "config.json"
    monkeypatch.setattr(config_mod, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_mod, "CONFIG_PATH", cfg_path)

    cfg = config_mod.update_config(provider="anthropic", api_key="sk-test-key-123456", model="claude-test")
    assert cfg.provider == "anthropic"
    assert cfg_path.exists()
    data = json.loads(cfg_path.read_text())
    assert data["api_key"] == "sk-test-key-123456"

    loaded = config_mod.load_config()
    assert loaded.model == "claude-test"
    public = loaded.to_public_dict()
    assert "sk-t" in public["api_key"]
    assert "3456" in public["api_key"] or public["api_key"].endswith("3456")
