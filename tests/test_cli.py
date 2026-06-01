"""End-to-end CLI tests via click's CliRunner.

Guards the user-facing surface the README documents: assembling, running on
both engines, disassembling, and -- specifically -- that address options
accept hex literals like ``--base 0x1000`` (which plain ``click.INT`` rejects;
this was a real quick-start bug).
"""
from __future__ import annotations

import pathlib

from click.testing import CliRunner

from dspsim.cli import cli

_EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"
_LOOP = _EXAMPLES / "loop_example.asm"


def _run(*args: str):
    return CliRunner().invoke(cli, list(args), catch_exceptions=False)


def test_asm_to_hex_stdout() -> None:
    res = _run("asm", str(_LOOP))
    assert res.exit_code == 0
    assert "0x" in res.output


def test_run_hex_base_fast() -> None:
    # --base 0x1000 must be accepted (regression: hex address parsing).
    res = _run("run", "--asm", str(_LOOP), "--base", "0x1000", "--engine", "fast")
    assert res.exit_code == 0, res.output
    assert "Final Registers" in res.output


def test_run_hex_base_cycle() -> None:
    res = _run("run", "--asm", str(_LOOP), "--base", "0x1000", "--engine", "cycle")
    assert res.exit_code == 0, res.output
    assert "CPI" in res.output


def test_run_decimal_base_still_works() -> None:
    res = _run("run", "--asm", str(_LOOP), "--base", "4096", "--engine", "fast")
    assert res.exit_code == 0, res.output


def test_run_rejects_bad_base() -> None:
    res = CliRunner().invoke(cli, ["run", "--asm", str(_LOOP), "--base", "nope"])
    assert res.exit_code != 0


def test_run_requires_a_source() -> None:
    res = CliRunner().invoke(cli, ["run"])
    assert res.exit_code != 0


def test_asm_then_disasm_roundtrip(tmp_path: pathlib.Path) -> None:
    out = tmp_path / "loop.bin"
    assert _run("asm", str(_LOOP), "-o", str(out)).exit_code == 0
    res = _run("disasm", str(out), "--base", "0x1000")
    assert res.exit_code == 0
    assert "0x1000:" in res.output
