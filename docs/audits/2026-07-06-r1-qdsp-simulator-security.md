# qdsp-simulator (dspsim) — Security Audit (Round 1)

**Audit ID:** `2026-07-06-r1`  
**Date:** 2026-07-06  
**Scope:** CLI entrypoints (`src/dspsim/cli.py`), assembler, ELF loader, bus memory model  
**Mode:** Read-only (no code changes)  
**Cross-reference:** `docs/BUG_JOURNAL.md` — engine drift, alignment, CLI hex parsing (remediated).

---

## Executive summary

dspsim is an **educational offline DSP simulator** invoked via CLI. There is no network service. Security concerns are limited to **local DoS** (memory/CPU exhaustion from large inputs) and **memory model edge cases** when loading binaries. No `eval`, `pickle`, or shell invocation found.

### Finding counts

| Severity | Count |
|----------|------:|
| High | 0 |
| Medium | 4 |
| Low | 3 |
| **Total** | **7** |

---

## Confirmed findings

### Medium

#### M1 — No file size cap when loading ASM/BIN programs

- **Location:** `src/dspsim/cli.py:68-72`, `src/dspsim/cli.py:84-87`, `src/dspsim/cli.py:229`
- **Category:** DoS / resource exhaustion
- **What:** `_read_text_file` and `read_bytes()` load entire files into memory. `_load_program` builds a Python list of all 32-bit words with no maximum.
- **Trigger:** `dspsim run --bin huge.bin` where file is gigabytes.
- **Impact:** OOM; long CPU in assembler/disassembler.
- **Suggested fix:** `MAX_PROGRAM_BYTES` / `MAX_PROGRAM_WORDS` constants; reject before read.

#### M2 — ELF loader accumulates unbounded `memsz` per segment

- **Location:** `src/dspsim/elf_loader.py:42-57`, `src/dspsim/bus.py:59-61`
- **Category:** DoS
- **What:** Each `PT_LOAD` segment calls `bus.load_blob(paddr, data)` and zero-fills BSS up to `memsz` with no total cap across segments.
- **Trigger:** Crafted ELF with large `p_memsz` or overlapping segments.
- **Impact:** Memory exhaustion; simulator slowdown.
- **Suggested fix:** Cap total loaded bytes; validate segment ranges do not overlap excessively.

#### M3 — `Bus.load_blob` / `Bus.write` do not bounds-check (unlike `read32`/`write32`)

- **Location:** `src/dspsim/bus.py:59-61`, `src/dspsim/bus.py:105-107`
- **Category:** Memory safety (simulator integrity)
- **What:** `load_blob` and `write` slice-assign into `bytearray` without `_check_access`. Python extends `bytearray` if slice end exceeds length — loads can **grow** memory beyond `size` constructor default (16 MiB).
- **Trigger:** `load_blob(0xFFFF0000, data)` or ELF high addresses.
- **Impact:** Unbounded host memory growth; bypass intended 16 MiB limit.
- **Contrast:** `read32`/`write32` enforce alignment and bounds (`bus.py:90-99`).
- **Suggested fix:** Reject `addr + len > len(self.mem)` in `load_blob`/`write`; no silent extend.

#### M4 — Interactive `debug` command has no instruction step limit

- **Location:** `src/dspsim/cli.py:278-291`, `src/dspsim/cli.py:354-360`
- **Category:** DoS (interactive)
- **What:** `continue` runs until HALT/breakpoint with no `--max-cycles` guard (unlike `run` at `cli.py:186-187`).
- **Trigger:** `dspsim debug --bin infinite_loop.bin` then `continue`.
- **Impact:** Hung CLI session consuming CPU.
- **Suggested fix:** Share `max_cycles` safety from `run` command.

### Low

#### L1 — Trace sink writes to arbitrary user-specified path

- **Location:** `src/dspsim/trace.py:9`, `src/dspsim/cli.py:213-223`
- **Category:** Local file write
- **What:** `--trace` opens user-controlled output path for write (when trace path option used).
- **Impact:** Overwrite files if combined with symlink tricks on shared systems.
- **Suggested fix:** Refuse symlinks; default to cwd-only.

#### L2 — Assembler label dictionary unbounded

- **Location:** `src/dspsim/assembler.py:75-91`, `src/dspsim/assembler.py:99-103`
- **Category:** DoS
- **What:** `first_pass` / `assemble` grow `labels` and `out_words` lists proportional to input lines without cap.
- **Trigger:** Megabyte `.asm` with millions of labels/instructions.
- **Suggested fix:** Tie to M1 file size limits.

#### L3 — Optional ELF dependency expands attack surface slightly

- **Location:** `src/dspsim/elf_loader.py:24-32`
- **Category:** Supply chain
- **What:** `pyelftools` parses binary formats; historical parser bugs exist in any ELF library.
- **Impact:** Low for local-only educational tool.
- **Suggested fix:** Pin dependency version; fuzz ELF loader.

---

## Good practices observed

- CLI file args use `click.Path(exists=True)` (`cli.py:27`).
- `run` has default `--max-cycles 100_000` (`cli.py:186-187`).
- `read32`/`write32` enforce alignment + OOB checks (`bus.py:90-99`).
- No subprocess/shell/`eval` in simulator core.
- BUG_JOURNAL alignment/CLI hex issues previously fixed.

---

## Project paths

| Path | Purpose |
|------|---------|
| `/Users/s_avelova/Documents/projects/qdsp-simulator/` | Project root |
| `/Users/s_avelova/Documents/projects/qdsp-simulator/docs/BUG_JOURNAL.md` | Bug patterns |
| `/Users/s_avelova/Documents/projects/qdsp-simulator/docs/audits/` | Audit reports |