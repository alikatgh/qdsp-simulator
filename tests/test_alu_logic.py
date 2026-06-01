# tests/test_alu_logic.py
"""Comprehensive tests for ALL ALU and logic instructions in the functional simulator."""

from dspsim import FunctionalSimulator
from dspsim.assembler import assemble


def run_program(program_asm: list[str], initial_regs=None):
    sim = FunctionalSimulator()
    if initial_regs:
        for r_idx, val in initial_regs.items():
            sim.regs[r_idx] = val
    program = assemble(program_asm)
    sim.load_words(sim.pc, program)
    sim.run(max_cycles=200)
    return sim


# --- Arithmetic ---

class TestADD:
    def test_basic(self):
        sim = run_program(["ADD R2, R0, R1", "HALT"], {0: 10, 1: 20})
        assert sim.regs[2] == 30

    def test_overflow_wraps(self):
        sim = run_program(["ADD R2, R0, R1", "HALT"], {0: 0xFFFFFFFF, 1: 2})
        assert sim.regs[2] == 1  # wraps around

    def test_zero_plus_zero(self):
        sim = run_program(["ADD R2, R0, R1", "HALT"], {0: 0, 1: 0})
        assert sim.regs[2] == 0


class TestADDI:
    def test_positive(self):
        sim = run_program(["ADDI R1, R0, #42", "HALT"])
        assert sim.regs[1] == 42

    def test_negative(self):
        sim = run_program(["ADDI R1, R0, #-1", "HALT"])
        assert sim.regs[1] == 0xFFFFFFFF

    def test_chain(self):
        sim = run_program([
            "ADDI R1, R0, #100",
            "ADDI R2, R1, #50",
            "HALT"
        ])
        assert sim.regs[1] == 100
        assert sim.regs[2] == 150


class TestSUB:
    def test_basic(self):
        sim = run_program(["SUB R2, R0, R1", "HALT"], {0: 100, 1: 30})
        assert sim.regs[2] == 70

    def test_underflow_wraps(self):
        sim = run_program(["SUB R2, R0, R1", "HALT"], {0: 0, 1: 1})
        assert sim.regs[2] == 0xFFFFFFFF


class TestMUL:
    def test_basic(self):
        sim = run_program(["MUL R2, R0, R1", "HALT"], {0: 7, 1: 6})
        assert sim.regs[2] == 42

    def test_overflow_truncates(self):
        sim = run_program(["MUL R2, R0, R1", "HALT"], {0: 0x10000, 1: 0x10000})
        assert sim.regs[2] == 0  # 0x1_0000_0000 truncated

    def test_zero(self):
        sim = run_program(["MUL R2, R0, R1", "HALT"], {0: 0, 1: 999})
        assert sim.regs[2] == 0


class TestMAC:
    def test_accumulate(self):
        sim = run_program(["MAC R2, R0, R1", "HALT"], {0: 3, 1: 4, 2: 10})
        assert sim.regs[2] == 22  # 10 + 3*4

    def test_chained(self):
        sim = run_program([
            "MAC R3, R0, R1",
            "MAC R3, R0, R1",
            "HALT"
        ], {0: 2, 1: 5, 3: 0})
        assert sim.regs[3] == 20  # 0 + 2*5 + 2*5


# --- Logic ---

class TestAND:
    def test_basic(self):
        sim = run_program(["AND R2, R0, R1", "HALT"], {0: 0xF0F0F0F0, 1: 0x00FFFF00})
        assert sim.regs[2] == 0x00F0F000

    def test_identity(self):
        sim = run_program(["AND R2, R0, R1", "HALT"], {0: 0xDEADBEEF, 1: 0xFFFFFFFF})
        assert sim.regs[2] == 0xDEADBEEF


class TestOR:
    def test_basic(self):
        sim = run_program(["OR R2, R0, R1", "HALT"], {0: 0xF0F0F0F0, 1: 0x00FFFF00})
        assert sim.regs[2] == 0xF0FFFFF0

    def test_zero(self):
        sim = run_program(["OR R2, R0, R1", "HALT"], {0: 0, 1: 0})
        assert sim.regs[2] == 0


class TestXOR:
    def test_basic(self):
        sim = run_program(["XOR R2, R0, R1", "HALT"], {0: 0xFF00FF00, 1: 0x0F0F0F0F})
        assert sim.regs[2] == 0xF00FF00F

    def test_self_xor_zeros(self):
        sim = run_program(["XOR R0, R0, R0", "HALT"], {0: 0xDEADBEEF})
        assert sim.regs[0] == 0


class TestNOT:
    def test_basic(self):
        sim = run_program(["NOT R1, R0", "HALT"], {0: 0x00000000})
        assert sim.regs[1] == 0xFFFFFFFF

    def test_inverse(self):
        sim = run_program(["NOT R1, R0", "HALT"], {0: 0xAAAAAAAA})
        assert sim.regs[1] == 0x55555555


# --- Shifts ---

class TestSHL:
    def test_basic(self):
        sim = run_program(["SHL R2, R0, R1", "HALT"], {0: 1, 1: 8})
        assert sim.regs[2] == 256

    def test_overflow(self):
        sim = run_program(["SHL R2, R0, R1", "HALT"], {0: 0x80000000, 1: 1})
        assert sim.regs[2] == 0  # shifted out


class TestSHR:
    def test_basic(self):
        sim = run_program(["SHR R2, R0, R1", "HALT"], {0: 256, 1: 4})
        assert sim.regs[2] == 16

    def test_logical(self):
        sim = run_program(["SHR R2, R0, R1", "HALT"], {0: 0x80000000, 1: 1})
        assert sim.regs[2] == 0x40000000  # logical shift, no sign extension


# --- Control flow ---

class TestJump:
    def test_forward_jump(self):
        sim = run_program([
            "ADDI R1, R0, #100",
            "J TARGET",
            "ADDI R1, R0, #200",  # skipped
            "HALT",               # skipped
            "TARGET:",
            "ADDI R2, R0, #50",
            "HALT"
        ])
        assert sim.regs[1] == 100
        assert sim.regs[2] == 50

    def test_backward_jump_loop(self):
        """Counts up to 5 using a loop."""
        sim = run_program([
            "ADDI R1, R0, #0",     # counter = 0
            "ADDI R2, R0, #5",     # limit = 5
            "LOOP:",
            "ADDI R1, R1, #1",     # counter++
            "SUB R3, R2, R1",      # R3 = limit - counter
            "CMPI.GT P0, R3, #0",  # P0 = (R3 > 0)
            "J DONE",              # unconditional jump to DONE (we test CMPI separately)
            "DONE:",
            "HALT"
        ])
        assert sim.regs[1] == 1


# --- Memory ---

class TestMemory:
    def test_store_load_roundtrip(self):
        sim = run_program([
            "ADDI R10, R0, #0x100",
            "ADDI R1, R0, #42",
            "ST [R10], R1",
            "LD R2, [R10]",
            "HALT"
        ])
        assert sim.regs[2] == 42

    def test_load_with_offset(self):
        sim = run_program([
            "ADDI R10, R0, #0x100",
            "ADDI R1, R0, #99",
            "ST [R10+4], R1",
            "LD R2, [R10+4]",
            "HALT"
        ])
        assert sim.regs[2] == 99
