# Security Audit Round Status — qdsp-simulator

**Last updated:** 2026-07-06

---

## Round index

| Round ID | Date | Scope | Mode | Report | Findings | Status |
|----------|------|-------|------|--------|----------|--------|
| `2026-07-06-r1` | 2026-07-06 | CLI, assembler, ELF loader, bus | Read-only | [2026-07-06-r1-qdsp-simulator-security.md](./2026-07-06-r1-qdsp-simulator-security.md) | 7 (0 High, 4 Med, 3 Low) | 🟡 Open |

---

## Cross-reference: BUG_JOURNAL patterns

| Pattern | 2026-07-06 status |
|---------|-------------------|
| Fast vs cycle engine drift | ✅ Operational risk — not security; covered by differential tests |
| Bus alignment/bounds on word access | ✅ `read32`/`write32` guarded; ❌ `load_blob`/`write` unguarded (M3) |
| CLI hex address parsing | ✅ Fixed per journal (`cli.py` ADDR/INT types) |

---

## Open findings backlog

### Medium

| ID | Summary | Location |
|----|---------|----------|
| M1 | No program file size cap | `src/dspsim/cli.py:84-87` |
| M2 | ELF unbounded segment load | `src/dspsim/elf_loader.py:42-57` |
| M3 | `load_blob` bypasses memory bound | `src/dspsim/bus.py:59-61` |
| M4 | `debug` no max-cycles | `src/dspsim/cli.py:354-360` |

### Low

| ID | Summary | Location |
|----|---------|----------|
| L1 | Trace path arbitrary write | `src/dspsim/trace.py:9` |
| L2 | Unbounded assembler tables | `src/dspsim/assembler.py:75-91` |
| L3 | pyelftools supply chain | `src/dspsim/elf_loader.py:24-32` |

---

## Project paths

| Path | Purpose |
|------|---------|
| `/Users/s_avelova/Documents/projects/qdsp-simulator/` | Project root |
| `/Users/s_avelova/Documents/projects/qdsp-simulator/docs/BUG_JOURNAL.md` | Bug patterns |
| `/Users/s_avelova/Documents/projects/qdsp-simulator/docs/audits/` | Audit reports |