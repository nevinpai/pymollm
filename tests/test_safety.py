from pymollm.safety import assert_safe, check_commands, split_commands


def test_split_commands():
    assert split_commands("show cartoon; color red\n# comment\nhide lines") == [
        "show cartoon",
        "color red",
        "hide lines",
    ]


def test_blocks_dangerous():
    r = check_commands(["show cartoon", "quit", "fetch 1A19"])
    assert not r.ok
    assert any("quit" in b.lower() for b in r.blocked)


def test_allows_normal():
    cmds = assert_safe(["fetch 1A19", "spectrum b, rainbow, all", "show solvent"])
    assert len(cmds) == 3


def test_blocks_shellish():
    r = check_commands(["system ls", "delete all", "reinitialize"])
    assert len(r.blocked) == 3
