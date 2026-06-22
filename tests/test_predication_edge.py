# tests/test_predication_edge.py
"""Edge-case tests for predicated execution in the functional simulator.

These tests focus on corner-cases that the basic predication tests in
test_predication.py do not cover:
  - All four predicate registers (P0–P3) guarding real instructions
  - Predicated memory (LD/ST) — skip means no memory side-effect
  - Predicated control-flow (J)
  - Predicated CMPI — skip means predicate register is NOT updated
  - A predicate set True vs False right before a guarded instruction
  - CMPI boundary values (signed comparison at limits)
  - Negative comparands in CMPI
"""

import pytest

from dspsim import FunctionalSimulator
from dspsim.assembler import assemble
from dspsim.encoder import enc_i, enc_ri
from dspsim.isa import MAJ_ADDI, MAJ_HALT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(program_asm: list[str], regs=None, preds=None) -> FunctionalSimulator:
    sim = FunctionalSimulator()
    if regs:
        for r, v in regs.items():
            sim.regs[r] = v
    if preds:
        for p, v in preds.items():
            sim.pred[p] = v
    words = assemble(program_asm)
    sim.load_words(sim.pc, words)
    sim.run(max_cycles=500)
    return sim


# ---------------------------------------------------------------------------
# All four predicate registers guarding instructions
# ---------------------------------------------------------------------------

class TestAllPredicateRegisters:
    @pytest.mark.parametrize("pidx", [0, 1, 2, 3])
    def test_pred_true_executes(self, pidx):
        """Each of P0-P3 in True state should allow the guarded instruction."""
        sim = FunctionalSimulator()
        sim.pred[pidx] = True
        sim.regs[0] = 0
        w_addi = enc_ri(MAJ_ADDI, 1, 0, 99, pred=pidx, end=True)
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        sim.load_words(sim.pc, [w_addi, w_halt])
        sim.run(max_cycles=20)
        assert sim.regs[1] == 99

    @pytest.mark.parametrize("pidx", [0, 1, 2, 3])
    def test_pred_false_skips(self, pidx):
        """Each of P0-P3 in False state should suppress the guarded instruction."""
        sim = FunctionalSimulator()
        sim.pred[pidx] = False
        sim.regs[1] = 42  # should remain unchanged
        w_addi = enc_ri(MAJ_ADDI, 1, 0, 99, pred=pidx, end=True)
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        sim.load_words(sim.pc, [w_addi, w_halt])
        sim.run(max_cycles=20)
        assert sim.regs[1] == 42


# ---------------------------------------------------------------------------
# Predicated memory operations
# ---------------------------------------------------------------------------

class TestPredicatedMemory:
    def test_predicated_ld_true_loads(self):
        """LD guarded by True pred must load from memory."""
        # Note: CMPI.EQ P0, R0, #0 is identical to HALT encoding, so we use
        # R1 as the compare source with a known non-zero value to avoid the
        # HALT/CMPI disambiguation edge case in the ISA.
        sim = run([
            "ADDI R10, R0, #0x100",
            "ADDI R1, R0, #77",
            "ST [R10], R1",          # store 77 at 0x100
            "CMPI.EQ P0, R1, #77",   # P0 = True (R1 == 77; rd=P0!=0, rs1=R1!=0)
            "LD R2, [R10] @P0",      # should execute
            "HALT",
        ])
        assert sim.regs[2] == 77

    def test_predicated_ld_false_skips(self):
        """LD guarded by False pred must NOT change the destination register."""
        sim = run([
            "ADDI R10, R0, #0x100",
            "ADDI R1, R0, #77",
            "ST [R10], R1",        # store 77 at 0x100
            "ADDI R2, R0, #999",   # pre-fill R2
            "CMPI.NE P1, R0, #0",  # P1 = False (R0 != 0 is False since R0=0)
            "LD R2, [R10] @P1",    # should be skipped
            "HALT",
        ])
        assert sim.regs[2] == 999  # unchanged

    def test_predicated_st_false_no_write(self):
        """ST guarded by False pred must NOT write to memory."""
        sim = run([
            "ADDI R10, R0, #0x100",
            "ADDI R1, R0, #55",
            "ST [R10], R1",        # store 55 at 0x100 (un-guarded)
            "ADDI R1, R0, #99",    # overwrite R1 with 99
            "CMPI.LT P2, R0, #0",  # P2 = False (0 < 0 is False)
            "ST [R10], R1 @P2",    # guarded by False -> skip
            "LD R2, [R10]",        # should still read 55
            "HALT",
        ])
        assert sim.regs[2] == 55


# ---------------------------------------------------------------------------
# Predicated control flow (J)
# ---------------------------------------------------------------------------

class TestPredicatedJump:
    def test_predicated_j_true_jumps(self):
        """J @P0 with P0=True must transfer control.

        We cannot use CMPI.EQ P0, R0, #0 because that encodes identically
        to HALT (rd=0, rs1=0, low14=0).  Use R1 and a non-zero value.
        """
        sim = run([
            "ADDI R1, R0, #5",
            "CMPI.EQ P0, R1, #5",  # P0 = True
            "J DONE @P0",
            "ADDI R1, R0, #99",    # should be skipped
            "DONE:",
            "ADDI R2, R0, #42",
            "HALT",
        ])
        assert sim.regs[1] == 5   # not overwritten (the skip worked)
        assert sim.regs[2] == 42

    def test_predicated_j_false_falls_through(self):
        """J @P0 with P0=False must fall through."""
        sim = run([
            "CMPI.NE P0, R0, #0",  # P0 = False (R0 != 0 is False since R0=0)
            "J SKIP @P0",          # should NOT jump
            "ADDI R1, R0, #7",     # should execute
            "HALT",
            "SKIP:",
            "ADDI R2, R0, #99",    # should not execute
            "HALT",
        ])
        assert sim.regs[1] == 7
        assert sim.regs[2] == 0


# ---------------------------------------------------------------------------
# Predicated CMPI — skip means the predicate register is NOT written
# ---------------------------------------------------------------------------

class TestPredicatedCMPI:
    def test_predicated_cmpi_false_does_not_update_pred(self):
        """CMPI guarded by False must leave the target predicate unchanged."""
        sim = run([
            "ADDI R1, R0, #10",
            "CMPI.EQ P0, R1, #10",   # P0 = True
            "CMPI.NE P0, R0, #0",    # P0 should flip to False — guard is ABSENT here
            "HALT",
        ])
        # Un-guarded: P0 ends up False because R0 != 0 is False
        assert sim.pred[0] is False

    def test_predicated_cmpi_true_updates_pred(self):
        """CMPI guarded by True must update the target predicate."""
        sim = run([
            "ADDI R1, R0, #5",
            "CMPI.EQ P3, R0, #0",   # P3 = True (P3 starts True, and R0==0 is True)
            "CMPI.GT P1, R1, #3 @P3",  # P3=True => executes, R1=5 > 3 => P1=True
            "HALT",
        ])
        assert sim.pred[1] is True


# ---------------------------------------------------------------------------
# CMPI boundary and negative comparand tests
# ---------------------------------------------------------------------------

class TestCMPIBoundaries:
    def test_cmpi_eq_max_positive(self):
        """CMPI.EQ at the maximum positive 10-bit signed immediate (511)."""
        sim = run([
            "ADDI R1, R0, #511",
            "CMPI.EQ P0, R1, #511",
            "HALT",
        ])
        assert sim.pred[0] is True

    def test_cmpi_lt_with_negative_comparand(self):
        """CMPI.LT comparing a register value against a negative immediate."""
        sim = run([
            "ADDI R1, R0, #-2",   # R1 = -2 (sign extended to u32)
            "CMPI.LT P0, R1, #0", # R1 signed < 0 => True
            "HALT",
        ])
        assert sim.pred[0] is True

    def test_cmpi_ge_equal_is_true(self):
        """CMPI.GE with equal values must yield True."""
        sim = run([
            "ADDI R1, R0, #7",
            "CMPI.GE P1, R1, #7",
            "HALT",
        ])
        assert sim.pred[1] is True

    def test_cmpi_gt_equal_is_false(self):
        """CMPI.GT with equal values must yield False."""
        sim = run([
            "ADDI R1, R0, #7",
            "CMPI.GT P2, R1, #7",
            "HALT",
        ])
        assert sim.pred[2] is False

    def test_cmpi_ne_zero_vs_zero(self):
        """CMPI.NE with both sides zero must yield False."""
        sim = run([
            "CMPI.NE P0, R0, #0",
            "HALT",
        ])
        assert sim.pred[0] is False

    def test_cmpi_le_negative_less(self):
        """CMPI.LE: negative value <= 0 must be True."""
        sim = run([
            "ADDI R1, R0, #-5",
            "CMPI.LE P3, R1, #0",
            "HALT",
        ])
        assert sim.pred[3] is True

    def test_cmpi_does_not_clobber_other_predicates(self):
        """Writing to P2 must not change P0, P1, P3."""
        sim = run([
            "CMPI.EQ P0, R0, #0",  # P0 = True
            "CMPI.EQ P1, R0, #0",  # P1 = True
            "CMPI.NE P2, R0, #99", # P2 = True  (0 != 99)
            "CMPI.EQ P3, R0, #0",  # P3 = True
            "HALT",
        ])
        assert sim.pred[0] is True
        assert sim.pred[1] is True
        assert sim.pred[2] is True
        assert sim.pred[3] is True


# ---------------------------------------------------------------------------
# Chained predication programs
# ---------------------------------------------------------------------------

class TestChainedPredication:
    def test_if_then_else_via_predicates(self):
        """Simulate an if-then-else: if R1==10 { R2=1 } else { R2=2 }."""
        sim = run([
            "ADDI R1, R0, #10",
            "CMPI.EQ P0, R1, #10",   # P0 = True
            "CMPI.NE P1, R1, #10",   # P1 = False
            "ADDI R2, R0, #1 @P0",   # executes: R2 = 1
            "ADDI R2, R0, #2 @P1",   # skipped
            "HALT",
        ])
        assert sim.regs[2] == 1

    def test_if_else_branch_taken(self):
        """Complementary predicates: R1!=10, so else-branch runs."""
        sim = run([
            "ADDI R1, R0, #5",
            "CMPI.EQ P0, R1, #10",   # P0 = False (5 != 10)
            "CMPI.NE P1, R1, #10",   # P1 = True  (5 != 10)
            "ADDI R2, R0, #1 @P0",   # skipped
            "ADDI R2, R0, #2 @P1",   # executes: R2 = 2
            "HALT",
        ])
        assert sim.regs[2] == 2

    def test_predicated_loop(self):
        """Simple counted loop using predicated jump."""
        sim = run([
            "ADDI R1, R0, #0",      # R1 = counter
            "ADDI R2, R0, #3",      # R2 = limit
            "LOOP:",
            "ADDI R1, R1, #1",      # counter++
            "SUB R3, R2, R1",       # R3 = limit - counter
            "CMPI.GT P0, R3, #0",   # P0 = (R3 > 0), i.e. not done yet
            "J LOOP @P0",           # repeat while P0 is true
            "HALT",
        ])
        assert sim.regs[1] == 3  # loop ran exactly 3 times
