"""Differential tests: the fast and cycle engines must agree on architectural state.

Runs every bundled example plus hand-built edge-case programs through BOTH
engines and asserts identical registers, predicates, and memory. The two
engines implement the ISA independently, so this is what stops them drifting
apart (a fix applied to one, forgotten in the other). See
``scripts/diff_engines.py`` for the comparison harness and its rationale.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import diff_engines as de  # noqa: E402  (path set up just above)

_EXAMPLES_DIR = _ROOT / "examples"
EXAMPLE_FILES = sorted(_EXAMPLES_DIR.glob("*.asm")) + sorted(_EXAMPLES_DIR.glob("*.dspasm"))

# Hand-built programs that stress semantic corners where the two independent
# instruction implementations could plausibly diverge. Immediates stay within
# range (ADDI: 14-bit signed; CMPI: 10-bit signed).
EDGE_PROGRAMS: dict[str, list[str]] = {
    "u32_overflow": [
        "ADDI R1, R0, #-1",   # 0xFFFFFFFF
        "ADD  R2, R1, R1",    # 0xFFFFFFFE (wrap)
        "ADDI R3, R1, #1",    # 0x00000000 (wrap)
        "MUL  R4, R1, R1",    # low32 of (2^32-1)^2 == 1
        "HALT",
    ],
    "shift_mask": [
        "ADDI R1, R0, #1",
        "ADDI R2, R0, #32",   # shift amount & 31 == 0
        "SHL  R3, R1, R2",    # 1
        "ADDI R4, R0, #33",   # & 31 == 1
        "SHL  R5, R1, R4",    # 2
        "ADDI R6, R0, #256",
        "ADDI R7, R0, #36",   # & 31 == 4
        "SHR  R8, R6, R7",    # 0x10
        "HALT",
    ],
    "signed_compare": [
        "ADDI R1, R0, #-5",
        "CMPI.LT P0, R1, #0",     # true
        "CMPI.GE P1, R1, #0",     # false
        "ADDI R2, R0, #111 @P0",  # taken
        "ADDI R3, R0, #222 @P1",  # skipped
        "HALT",
    ],
    "mac_chain": [
        "ADDI R1, R0, #7",
        "ADDI R2, R0, #0",
        "MAC  R2, R1, R1",    # +49
        "MAC  R2, R1, R1",    # +49 -> 98
        "HALT",
    ],
    "ld_st_roundtrip": [
        "ADDI R1, R0, #1024",
        "ADDI R5, R0, #4660",  # 0x1234
        "ST   [R1+0], R5",
        "ST   [R1+8], R5",
        "LD   R6, [R1+0]",
        "LD   R7, [R1+8]",
        "HALT",
    ],
    "pred_skip_store": [
        "ADDI R1, R0, #1280",
        "ADDI R5, R0, #4660",
        "CMPI.EQ P0, R0, #1",     # false: R0(0) != 1
        "ST   [R1+0], R5 @P0",    # skipped -> memory stays zero
        "LD   R6, [R1+0]",        # reads 0
        "HALT",
    ],
    "bitops": [
        "ADDI R1, R0, #240",  # 0xF0
        "ADDI R2, R0, #15",   # 0x0F
        "OR   R3, R1, R2",    # 0xFF
        "AND  R4, R1, R2",    # 0x00
        "XOR  R5, R1, R1",    # 0x00
        "NOT  R6, R0",        # 0xFFFFFFFF
        "HALT",
    ],
    "branch_loop": [
        "ADDI R1, R0, #0",
        "ADDI R2, R0, #3",
        "TOP:",
        "ADDI R1, R1, #1",
        "ADDI R2, R2, #-1",
        "CMPI.GT P0, R2, #0",
        "J TOP @P0",
        "HALT",
    ],
}


def _assert_agree(words: list[int], label: str) -> de.EngineResult:
    """Run a program on both engines; fail with a readable diff if they differ."""
    fast, _cycle, diffs = de.run_both(words)
    assert not diffs, f"{label}: engines diverged:\n  " + "\n  ".join(diffs)
    return fast


def test_examples_present() -> None:
    # Guard: an empty glob would make the parametrized test silently pass.
    assert len(EXAMPLE_FILES) >= 5


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_examples_agree(path: pathlib.Path) -> None:
    _assert_agree(de.load_program(path), path.name)


@pytest.mark.parametrize("name", sorted(EDGE_PROGRAMS))
def test_edge_programs_agree(name: str) -> None:
    _assert_agree(de.assemble_lines(EDGE_PROGRAMS[name]), name)


def test_edge_known_values() -> None:
    # Confirm the edge programs actually compute something (so "agreement"
    # is meaningful and not just two idle engines matching on zeros).
    r = _assert_agree(de.assemble_lines(EDGE_PROGRAMS["u32_overflow"]), "u32_overflow")
    assert r.regs[2] == 0xFFFFFFFE
    assert r.regs[3] == 0x00000000
    assert r.regs[4] == 0x00000001

    r = _assert_agree(de.assemble_lines(EDGE_PROGRAMS["mac_chain"]), "mac_chain")
    assert r.regs[2] == 98

    r = _assert_agree(de.assemble_lines(EDGE_PROGRAMS["bitops"]), "bitops")
    assert r.regs[3] == 0xFF
    assert r.regs[4] == 0x00
    assert r.regs[6] == 0xFFFFFFFF

    r = _assert_agree(de.assemble_lines(EDGE_PROGRAMS["branch_loop"]), "branch_loop")
    assert r.regs[1] == 3
