# Bug Journal — dspsim

Cheap to write, cheap to read, expensive to skip. Before debugging a new
symptom, `grep -i <symptom>` this file — the answer is often already here.

**Update protocol:** when you fix a bug, append a chronological entry **in the
same commit** as the fix. If the lesson generalizes, add a bullet to the
patterns section too. Keep entries to ~5 lines.

---

## Patterns to scan for FIRST

- **Two engines, one ISA → they drift.** Semantics live in BOTH
  `src/dspsim/core.py` (fast) and `src/dspsim/core_cycle.py` (cycle). A fix or a
  new instruction applied to one and not the other is the most likely bug class.
  Always run `python scripts/diff_engines.py <prog>` (or `pytest
  tests/test_differential.py`) after touching instruction semantics.
- **`u32()` / `s32()` discipline.** Every ALU result must be masked back to 32
  bits with `u32()`; every signed comparison must go through `s32()` first.
  Missing wrap = silent giant-integer bug that the differential test catches.
- **Shared `MAJ=0xF` opcode.** `CMPI` and `HALT` share major opcode `0xF`.
  `HALT` is the all-zero-operand special case; anything else is `CMPI`. Both the
  decoder and the fast engine special-case this — change them together.
- **`ST` encodes its source in the `rd` field `[23:19]`.** Stores don't write a
  register; the "rd" slot is the data source. Hazard tracking and disassembly
  must treat `ST` specially (it reads rd, writes none).
- **Addresses are hex; click's `INT` is not.** Any CLI option taking an address
  must use the `ADDR`/`INT` param types in `cli.py` (base-0 parsing), never bare
  `type=int` or `click.IntRange` — those reject `0x1000`.
- **Docs/CLI drift breaks the quick-start.** When you rename a flag or example,
  grep `README.md` and `docs/` for the old name in the same change. A wrong
  first command is the worst first impression.
- **Memory access must be aligned + in-bounds.** 32-bit access goes through
  `Bus.read32`/`write32`, which raise `MemoryFault` on misalignment/OOB. Don't
  reach into `bus.mem` directly for word access and bypass the check.

---

## Chronological log (newest first)

- **2026-06-02 — `--base 0x1000` rejected by CLI.**
  Symptom: `dspsim run --bin x.bin --base 0x1000` errored "not a valid integer
  range". Cause: options used `type=int` / `click.IntRange`, which don't parse
  hex. Fix: added `ADDR`/`INT` click param types (base-0 parsing) in `cli.py`
  and wired them into run/disasm/debug. Lesson: addresses are hex — never type
  an address option as plain int. Covered by `tests/test_cli.py`.

- **2026-06-02 — Bus had no alignment/bounds enforcement.**
  Symptom: README claimed "alignment required to 4B" but unaligned/OOB 32-bit
  access silently succeeded or threw a raw `struct.error`. Fix: added
  `MemoryFault` + `_check_access` in `bus.py`; MMIO regions bypass the bounds
  check but still require alignment. Lesson: enforce the contract the docs
  promise. Covered by `tests/test_bus_faults.py`.

- **2026-06-02 — Engines could silently diverge (latent).**
  Symptom: none yet, but fast and cycle engines re-implement every instruction
  with no cross-check. Fix: added `scripts/diff_engines.py` +
  `tests/test_differential.py` comparing full architectural state across both on
  every example and many edge cases. Lesson: duplicated semantics need a
  differential oracle, not hope.
