#!/usr/bin/env python3
"""Differential tester: run one program on BOTH engines and compare state.

The simulator ships two independent execution engines that re-implement the
ISA separately:

  * ``FunctionalSimulator`` (``dspsim.core``)        -- the fast reference model
  * ``Core``               (``dspsim.core_cycle``)   -- the cycle-accurate model

Because the instruction semantics are duplicated across the two, they can
silently drift apart (a fix applied to one, forgotten in the other). This
harness runs the same program on both and asserts that the *architectural*
state agrees: all 32 GPRs, the 4 predicate bits, and the full memory image.

What it catches:
  * any divergence in computed register / predicate / memory results between
    the two engines (the classic "fixed it in core.py, not core_cycle.py" bug).

What it deliberately does NOT compare:
  * timing / perf counters (cycles, stalls, CPI) -- those are *meant* to differ.
  * instruction COUNT -- the fast model counts a predicate-skipped instruction
    as executed; the cycle model counts it as a predicated NOP. This is a known,
    documented difference and is reported but not treated as a failure.

Usage:
    python scripts/diff_engines.py examples/loop_example.asm
    python scripts/diff_engines.py program.bin --base 0x1000 --entry 0x1000
    python scripts/diff_engines.py prog.asm --quiet   # exit code only
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys
from dataclasses import dataclass

# Make the package importable when run straight from a checkout (no install).
_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dspsim import assembler  # noqa: E402
from dspsim.bus import Bus  # noqa: E402
from dspsim.core import FunctionalSimulator  # noqa: E402
from dspsim.core_cycle import Core  # noqa: E402

DEFAULT_BASE = 0x1000
DEFAULT_MAX_CYCLES = 100_000
# 1 MiB is plenty for every bundled example and keeps the memory compare cheap.
DEFAULT_MEM_SIZE = 1 << 20


@dataclass
class EngineResult:
    """Architectural state captured after a program runs (or faults)."""

    name: str
    regs: list[int]
    pred: list[bool]
    mem: bytes
    halted: bool
    instr_count: int
    error: str | None = None


def assemble_lines(lines: list[str]) -> list[int]:
    """Assemble source lines into a list of 32-bit instruction words."""
    return assembler.assemble(lines)


def _words_to_blob(words: list[int]) -> bytes:
    return b"".join(struct.pack("<I", w & 0xFFFFFFFF) for w in words)


def run_fast(
    words: list[int],
    base: int = DEFAULT_BASE,
    entry: int | None = None,
    max_cycles: int = DEFAULT_MAX_CYCLES,
    mem_size: int = DEFAULT_MEM_SIZE,
) -> EngineResult:
    """Run a program on the functional (fast) engine and snapshot its state."""
    sim = FunctionalSimulator(mem_size=mem_size)
    sim.load_words(base, words)
    sim.pc = base if entry is None else entry
    error = None
    try:
        sim.run(max_cycles=max_cycles)
    except Exception as e:  # noqa: BLE001 -- a fault IS part of the observed state
        error = f"{type(e).__name__}: {e}"
    return EngineResult(
        name="fast",
        regs=list(sim.regs),
        pred=[bool(p) for p in sim.pred],
        mem=bytes(sim.bus.mem),
        halted=not sim.running,
        instr_count=sim.cycle_count,
        error=error,
    )


def run_cycle(
    words: list[int],
    base: int = DEFAULT_BASE,
    entry: int | None = None,
    max_cycles: int = DEFAULT_MAX_CYCLES,
    mem_size: int = DEFAULT_MEM_SIZE,
) -> EngineResult:
    """Run a program on the cycle-accurate engine and snapshot its state."""
    bus = Bus(size=mem_size)
    bus.load_blob(base, _words_to_blob(words))
    core = Core(bus=bus)
    core.pc = base if entry is None else entry
    error = None
    steps = 0
    try:
        while not core.halted and steps < max_cycles:
            core.step()
            steps += 1
    except Exception as e:  # noqa: BLE001 -- a fault IS part of the observed state
        error = f"{type(e).__name__}: {e}"
    return EngineResult(
        name="cycle",
        regs=[core.regs.read(i) for i in range(32)],
        pred=[bool(core.regs.read_pred(i)) for i in range(4)],
        mem=bytes(bus.mem),
        halted=core.halted,
        instr_count=core.perf.instructions,
        error=error,
    )


def diff_states(fast: EngineResult, cycle: EngineResult) -> list[str]:
    """Compare two engine results. Returns a list of human-readable diffs.

    An empty list means the architectural state is identical. Instruction
    count and timing are intentionally excluded (see module docstring).
    """
    diffs: list[str] = []

    if fast.error != cycle.error:
        diffs.append(
            f"fault mismatch: fast={fast.error!r}  cycle={cycle.error!r}"
        )

    if fast.halted != cycle.halted:
        diffs.append(f"halted mismatch: fast={fast.halted}  cycle={cycle.halted}")

    for i in range(32):
        if fast.regs[i] != cycle.regs[i]:
            diffs.append(
                f"R{i}: fast=0x{fast.regs[i]:08X}  cycle=0x{cycle.regs[i]:08X}"
            )

    for i in range(4):
        if fast.pred[i] != cycle.pred[i]:
            diffs.append(f"P{i}: fast={fast.pred[i]}  cycle={cycle.pred[i]}")

    if fast.mem != cycle.mem:
        # Report the first differing word to make the divergence actionable.
        addr = _first_mem_diff(fast.mem, cycle.mem)
        if addr is not None:
            fw = struct.unpack_from("<I", fast.mem, addr)[0]
            cw = struct.unpack_from("<I", cycle.mem, addr)[0]
            diffs.append(
                f"mem@0x{addr:X}: fast=0x{fw:08X}  cycle=0x{cw:08X} (first of more)"
            )
        else:
            diffs.append("mem differs (length mismatch)")

    return diffs


def _first_mem_diff(a: bytes, b: bytes) -> int | None:
    """Return the word-aligned address of the first byte that differs."""
    if len(a) != len(b):
        return None
    for i in range(0, min(len(a), len(b)), 4):
        if a[i : i + 4] != b[i : i + 4]:
            return i
    return None


def run_both(
    words: list[int],
    base: int = DEFAULT_BASE,
    entry: int | None = None,
    max_cycles: int = DEFAULT_MAX_CYCLES,
    mem_size: int = DEFAULT_MEM_SIZE,
):
    """Run a program on both engines. Returns (fast, cycle, diffs)."""
    fast = run_fast(words, base, entry, max_cycles, mem_size)
    cycle = run_cycle(words, base, entry, max_cycles, mem_size)
    return fast, cycle, diff_states(fast, cycle)


def load_program(path: pathlib.Path) -> list[int]:
    """Load words from an assembly source (.asm/.dspasm) or raw .bin file."""
    if path.suffix.lower() == ".bin":
        data = path.read_bytes()
        if len(data) % 4:
            raise ValueError("binary size is not a multiple of 4 bytes")
        return [struct.unpack_from("<I", data, i)[0] for i in range(0, len(data), 4)]
    lines = path.read_text(encoding="utf-8").splitlines()
    return assemble_lines(lines)


def _parse_int(text: str) -> int:
    return int(text, 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("program", type=pathlib.Path, help="asm/dspasm source or .bin")
    parser.add_argument("--base", type=_parse_int, default=DEFAULT_BASE)
    parser.add_argument("--entry", type=_parse_int, default=None)
    parser.add_argument("--max-cycles", type=_parse_int, default=DEFAULT_MAX_CYCLES)
    parser.add_argument("--quiet", action="store_true", help="print nothing; exit code only")
    args = parser.parse_args(argv)

    words = load_program(args.program)
    fast, cycle, diffs = run_both(words, args.base, args.entry, args.max_cycles)

    if args.quiet:
        return 1 if diffs else 0

    print(f"Program: {args.program}  ({len(words)} words)")
    print(
        f"  fast : halted={fast.halted}  instrs={fast.instr_count}"
        f"  error={fast.error or '-'}"
    )
    print(
        f"  cycle: halted={cycle.halted}  instrs={cycle.instr_count}"
        f"  error={cycle.error or '-'}"
    )
    if diffs:
        print(f"\n  DIVERGENCE ({len(diffs)}):")
        for d in diffs:
            print(f"    - {d}")
        return 1
    print("\n  ENGINES AGREE on all registers, predicates, and memory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
