from pathlib import Path

import pytest

from qoin_maker.cli import main
from qoin_maker.scaffold import TokenSpec, write_project
from qoin_maker.validate import SpecError, require_symbol


def test_symbol_normalizes():
    assert require_symbol("hqn") == "HQN"


def test_bad_symbol():
    with pytest.raises(SpecError):
        require_symbol("$$")


def test_write_project(tmp_path: Path):
    root = write_project(
        TokenSpec(
            name="Harbor Qoin",
            symbol="HQN",
            initial_supply=1000,
            burnable=True,
            out_dir=tmp_path / "token",
        )
    )
    source = (root / "src" / "HarborQoin.sol").read_text(encoding="utf-8")
    assert "contract HarborQoin" in source
    assert "function burn" in source
    assert (root / "script" / "Deploy.s.sol").exists()


def test_cli_explain(capsys):
    rc = main(["explain", "--name", "Harbor Qoin", "--symbol", "HQN", "--supply", "100"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"symbol": "HQN"' in out
