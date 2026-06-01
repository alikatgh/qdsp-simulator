# DSPsim — an educational DSP instruction-set simulator

**DSPsim** is a from-scratch, packeted, predicated DSP core with a full
toolchain (assembler, disassembler, two execution engines, interactive
debugger, and MMIO peripherals). It is **not** Qualcomm Hexagon — it implements
an original, instructional ISA that is Hexagon-*inspired* only at the concept
level. The goal is transparency: every instruction has one documented encoding
and one documented side effect, and you can instrument all of them.

[![CI](https://github.com/alikatgh/qdsp-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/alikatgh/qdsp-simulator/actions/workflows/ci.yml)

## Highlights
- 32 GPRs (`R0`–`R31`), 4 predicate bits (`P0`–`P3`), PC, cycle counter
- **Two engines**: a fast functional reference model and a cycle-approximate
  model with hazard stalling and performance counters — kept in lockstep by a
  [differential test harness](scripts/diff_engines.py)
- **Predication**: `@P#` guards any instruction
- **Packets**: VLIW-style multi-word fetch (end via the EOP bit)
- **MMIO**: UART + Timer peripheral models
- **Assembler / disassembler** for the educational ISA
- **Interactive debugger**: step, breakpoints, memory/register inspection
- **ELF loader** (optional, via `pyelftools`)
- **Tracing**: JSON instruction/memory traces

See [`docs/ISA.md`](docs/ISA.md) for the authoritative instruction-set reference.

## Install

```bash
pip install -e .            # core (just needs click)
pip install -e ".[elf]"     # + ELF loading (pyelftools)
pip install -e ".[pretty]"  # + rich tables for --pretty output
```

This project also supports [uv](https://docs.astral.sh/uv/): `uv sync` creates a
dev environment with the test and lint tooling.

## Quick start

The repository ships several runnable example programs in [`examples/`](examples/).

```bash
# Assemble an example to a .bin of 32-bit little-endian words
dspsim asm examples/loop_example.asm -o loop.bin

# Run it on the fast functional engine (addresses accept hex or decimal)
dspsim run --asm examples/loop_example.asm --base 0x1000

# Run on the cycle-accurate engine to see performance counters
dspsim run --asm examples/loop_example.asm --engine cycle

# Emit a JSON instruction/memory trace (cycle engine)
dspsim run --asm examples/loop_example.asm --engine cycle --trace

# Disassemble a binary
dspsim disasm loop.bin --base 0x1000

# Step through a program interactively (breakpoints, regs, memory)
dspsim debug --asm examples/loop_example.asm

# Load and run an ELF binary (requires the [elf] extra)
dspsim run --elf build/program.elf --engine cycle
```

`loop_example.asm` sums 1+2+3+4+5 using a `CMPI` + predicated branch; it
finishes with `R3 = 0xF`.

## The two engines, and why they agree

The semantics of the ISA are implemented **twice** — once in
[`dspsim.core`](src/dspsim/core.py) (fast reference) and once in
[`dspsim.core_cycle`](src/dspsim/core_cycle.py) (cycle-approximate, with a
scoreboard and functional units). Duplicated semantics can drift, so a
differential harness runs any program on both and asserts that all registers,
predicates, and memory match:

```bash
python scripts/diff_engines.py examples/loop_example.asm
```

[`tests/test_differential.py`](tests/test_differential.py) runs this across
every example plus a battery of edge cases (overflow, shift masking, signed
compares, MAC chains, predicated stores) in CI.

## ISA at a glance

- Word = 32 bits, little-endian; all instructions are 32 bits.
- Common header: `[31:28]` MAJ · `[27]` predicated flag · `[26:25]` Pidx ·
  `[24]` EOP.
- ALU: `ADD ADDI SUB AND OR XOR SHL SHR MUL MAC NOT`
- Memory: `LD` / `ST` (base + signed 14-bit offset); 32-bit accesses must be
  4-byte aligned (a misaligned/out-of-bounds access raises a fault).
- Control: `J` (PC-relative), `JR` (register), `CMPI.{EQ,NE,LT,GE,LE,GT}`
  (writes a predicate), `HALT`.
- Predication: `@P#` on any instruction skips its side effects when the
  predicate is false.

Full details, bitfield layouts, and the MMIO register maps are in
[`docs/ISA.md`](docs/ISA.md).

## Development

```bash
uv sync                 # install dev dependencies (pytest, ruff, mypy, ...)
uv run pytest           # run the test suite
uv run ruff check .     # lint
uv run mypy             # type-check the annotated surface
```

CI runs lint + type-check + tests on Python 3.9–3.12. See
[`docs/BUG_JOURNAL.md`](docs/BUG_JOURNAL.md) for recorded bug patterns.

## License

MIT License — see [LICENSE](LICENSE).
