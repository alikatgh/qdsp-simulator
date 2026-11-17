# Grok memo — DSPsim — educational instruction-set simulator

Private local context prepared 2026-11-06T16:11:08+00:00.
Folder: `/Users/s_avelova/Documents/projects/qdsp-simulator`.

[How we work](</Users/s_avelova/Documents/projects/pitches/docs/GROK_OPERATING_MEMO.md>) · [Memo coverage and routing index](</Users/s_avelova/Documents/projects/pitches/docs/GROK_MEMO_INDEX.md>)

## Context

The README defines DSPsim as an original educational DSP instruction-set simulator, conceptually inspired by Hexagon but not Qualcomm Hexagon. It describes an assembler, disassembler, debugger, MMIO models and separate functional/cycle-approximate engines with differential testing.

Preserve the explicit encoding and side-effect model, and keep agreement between engines separate from hardware accuracy or binary compatibility. Some local instructions contain old tool-budget and setup claims; apply the current user request and verify actual available commands before using them.

## Next useful actions

- For a later task, select one instruction, packet rule, peripheral or debugger behavior.
- Use the relevant deterministic test and differential engine check; document any approximation.

## Limits and freshness

- Do not claim Hexagon compatibility or cycle-accurate hardware validation.
- This memo starts no build, broad audit, dependency installation or cloud workload.
- Dated local-document context; no external state independently verified
- Current user instructions and local AGENTS.md remain authoritative. This memo is context, not proof of live state or a new external-action authorization.

## Local sources

- [AGENTS.md](</Users/s_avelova/Documents/projects/AGENTS.md>) (applicable instruction)
- [AGENTS.md](</Users/s_avelova/Documents/projects/qdsp-simulator/AGENTS.md>) (applicable instruction)
- [README.md](</Users/s_avelova/Documents/projects/qdsp-simulator/README.md>) (safe readme)
- [grok-memo-targets-20261106.json](</Users/s_avelova/Documents/projects/pitches/research/grok-memo-targets-20261106.json>) (target inventory metadata)

Source fingerprints are recorded in the reviewed delivery plan; reread current sources before acting.
