# tests/test_hazards.py
"""Tests for the cycle-accurate simulator: hazard detection, pipeline, perf counters."""

import struct

from dspsim.assembler import assemble
from dspsim.bus import Bus
from dspsim.core_cycle import Core


def make_core(asm_lines: list[str], base: int = 0x1000) -> Core:
    """Helper: assemble, load, return a Core ready to run."""
    words = assemble(asm_lines)
    bus = Bus()
    blob = b"".join(struct.pack("<I", w) for w in words)
    bus.load_blob(base, blob)
    core = Core(bus=bus)
    core.pc = base
    return core


def run_core(asm_lines: list[str]) -> Core:
    core = make_core(asm_lines)
    safety = 0
    while not core.halted and safety < 500:
        core.step()
        safety += 1
    return core


class TestCycleBasic:
    def test_addi_halt(self):
        core = run_core(["ADDI R1, R0, #42", "HALT"])
        assert core.regs.read(1) == 42
        assert core.halted

    def test_add(self):
        core = run_core([
            "ADDI R0, R0, #10",
            "ADDI R1, R0, #20",
            "ADD R2, R0, R1",
            "HALT"
        ])
        assert core.regs.read(2) == core.regs.read(0) + core.regs.read(1)

    def test_sub(self):
        core = run_core([
            "ADDI R0, R0, #100",
            "ADDI R1, R0, #30",
            "SUB R2, R0, R1",
            "HALT"
        ])
        # R0=100, R1=130, SUB -> 100 - 130 = -30 wraps to 0xFFFFFFE2
        assert core.regs.read(2) == (core.regs.read(0) - core.regs.read(1)) & 0xFFFFFFFF


class TestMemoryCycle:
    def test_store_load(self):
        core = run_core([
            "ADDI R10, R0, #0x100",
            "ADDI R1, R0, #77",
            "ST [R10], R1",
            "LD R2, [R10]",
            "HALT"
        ])
        assert core.regs.read(2) == 77

    def test_load_stall(self):
        """LD has 3-cycle latency in LSU; reading the result should cause stalls."""
        core = run_core([
            "ADDI R10, R0, #0x100",
            "ADDI R1, R0, #99",
            "ST [R10], R1",
            "LD R2, [R10]",
            "ADD R3, R2, R0",  # depends on LD result — should stall
            "HALT"
        ])
        assert core.regs.read(3) == 99
        assert core.perf.stall_cycles > 0  # stalls expected


class TestPerfCounters:
    def test_counts(self):
        core = run_core([
            "ADDI R1, R0, #1",
            "ADDI R2, R0, #2",
            "ADD R3, R1, R2",
            "HALT"
        ])
        assert core.perf.instructions >= 3
        assert core.perf.cycles > 0
        assert core.perf.alu_ops >= 3

    def test_cpi(self):
        core = run_core(["ADDI R1, R0, #1", "HALT"])
        # CPI should be >= 1.0 (no pipeline is faster than 1 IPC)
        assert core.perf.cpi >= 1.0
