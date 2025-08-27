# src/dspsim/core.py
"""Functional (fast) DSP simulator.

This model executes one instruction per cycle and is used as the
reference/fast engine for correctness tests. It uses the Bus abstraction
(so MMIO works the same as the cycle model).
"""
from __future__ import annotations

import struct
from typing import List

from .isa import INSTRUCTION_SET
from .bus import Bus
from .bitutil import s32, u32


class FunctionalSimulator:
    def __init__(self, mem_size: int = 16 * 1024 * 1024):
        self.regs: List[int] = [0] * 32
        self.pred: List[bool] = [True] * 4  # predicate state (kept for compatibility)
        self.pc: int = 0x1000
        self.cycle_count: int = 0
        self.running: bool = False
        self.bus = Bus(size=mem_size)

    # -------------------------
    # Memory helpers
    # -------------------------
    def load_words(self, addr: int, words: List[int]) -> None:
        """Load list of 32-bit words into memory at addr (little-endian)."""
        for i, w in enumerate(words):
            self.bus.write32(addr + 4 * i, u32(w))

    def fetch_word(self) -> int:
        w = self.bus.read32(self.pc)
        return w

    # -------------------------
    # Execution
    # -------------------------
    def run(self, entry: int | None = None, max_cycles: int | None = None) -> None:
        """Run starting from entry (or current pc). Stops on HALT or invalid opcode.

        max_cycles: optional safeguard to avoid infinite loops in tests.
        """
        if entry is not None:
            self.pc = entry
        self.running = True
        executed = 0
        while self.running:
            if max_cycles is not None and executed >= max_cycles:
                raise RuntimeError("Max cycles reached")
            try:
                word = self.fetch_word()
            except Exception as e:
                raise RuntimeError(f"Fetch fault at PC=0x{self.pc:X}: {e}") from e

            # Advance PC early (simple, deterministic flow)
            self.pc += 4
            self.cycle_count += 1
            executed += 1

            maj = (word >> 28) & 0xF

            # find matching instruction via INSTRUCTION_SET (small loop; fine for tests)
            matched = False
            for mnem, (fn, argtypes, majcode) in INSTRUCTION_SET.items():
                if majcode == maj:
                    matched = True
                    try:
                        self._dispatch(fn, argtypes, word)
                    except Exception as e:
                        raise RuntimeError(f"Execution error at PC=0x{self.pc-4:X} ({mnem}): {e}") from e
                    break

            if not matched:
                raise RuntimeError(f"Unknown opcode 0x{maj:X} at PC=0x{self.pc-4:X}")

    def _dispatch(self, fn, argtypes, word: int):
        """Decode fields from word according to canonical formats and call instruction semantics."""
        # 3-register form: rd[23:19], rs1[18:14], rs2[13:9]
        if argtypes == ('reg', 'reg', 'reg'):
            rd = (word >> 19) & 0x1F
            rs1 = (word >> 14) & 0x1F
            rs2 = (word >> 9) & 0x1F
            fn(self, rd, rs1, rs2)
            return

        # register, reg, imm (RI): rd[23:19], rs1[18:14], imm[13:0] (14-bit signed)
        if argtypes == ('reg', 'reg', 'imm'):
            rd = (word >> 19) & 0x1F
            rs1 = (word >> 14) & 0x1F
            imm = word & 0x3FFF
            imm = s32(imm) if (imm & 0x2000) else imm  # keep sign
            fn(self, rd, rs1, imm)
            return

        # store form uses rs2 in rs2 field, base in rs1
        if argtypes == ('reg', 'reg', 'imm') and fn.__name__.startswith("instr_st"):
            rs2 = (word >> 9) & 0x1F
            rs1 = (word >> 14) & 0x1F
            imm = word & 0x3FFF
            imm = s32(imm) if (imm & 0x2000) else imm
            fn(self, rs2, rs1, imm)
            return
        
            # immediate-only form: imm[23:0] (for jumps, using 14 bits)
        if argtypes == ('imm',):
            imm = word & 0x3FFF
            imm = s32(imm) if (imm & 0x2000) else imm # sign extend
            fn(self, imm)
            return
        
        # HALT / no-arg
        if argtypes == ():
            fn(self)
            return

        # fallback: try to be helpful
        raise RuntimeError(f"Unsupported argtypes {argtypes}")

    # -------------------------
    # Debugging helpers
    # -------------------------
    def dump_regs(self) -> None:
        for i in range(0, 32, 4):
            r = self.regs[i:i+4]
            print(f"R{i:02d}-R{i+3:02d}: " + " ".join(f"{v:08X}" for v in r))
