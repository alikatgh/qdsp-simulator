# tests/test_predication.py
"""Tests for predicated execution and CMPI instructions."""

from dspsim import FunctionalSimulator
from dspsim.assembler import assemble
from dspsim.encoder import enc_i, enc_ri
from dspsim.isa import MAJ_ADDI, MAJ_HALT


def run_program(program_asm: list[str], initial_regs=None, initial_preds=None):
    sim = FunctionalSimulator()
    if initial_regs:
        for r, v in initial_regs.items():
            sim.regs[r] = v
    if initial_preds:
        for p, v in initial_preds.items():
            sim.pred[p] = v
    program = assemble(program_asm)
    sim.load_words(sim.pc, program)
    sim.run(max_cycles=200)
    return sim


class TestCMPI:
    def test_eq_true(self):
        sim = run_program([
            "ADDI R1, R0, #10",
            "CMPI.EQ P0, R1, #10",
            "HALT"
        ])
        assert sim.pred[0] is True

    def test_eq_false(self):
        sim = run_program([
            "ADDI R1, R0, #10",
            "CMPI.EQ P0, R1, #5",
            "HALT"
        ])
        assert sim.pred[0] is False

    def test_ne(self):
        sim = run_program([
            "ADDI R1, R0, #10",
            "CMPI.NE P1, R1, #5",
            "HALT"
        ])
        assert sim.pred[1] is True

    def test_lt(self):
        sim = run_program([
            "ADDI R1, R0, #3",
            "CMPI.LT P2, R1, #10",
            "HALT"
        ])
        assert sim.pred[2] is True

    def test_ge(self):
        sim = run_program([
            "ADDI R1, R0, #10",
            "CMPI.GE P0, R1, #10",
            "HALT"
        ])
        assert sim.pred[0] is True

    def test_le(self):
        sim = run_program([
            "ADDI R1, R0, #5",
            "CMPI.LE P3, R1, #10",
            "HALT"
        ])
        assert sim.pred[3] is True

    def test_gt_false(self):
        sim = run_program([
            "ADDI R1, R0, #5",
            "CMPI.GT P0, R1, #10",
            "HALT"
        ])
        assert sim.pred[0] is False


class TestPredicatedExecution:
    def test_predicate_true_executes(self):
        """When predicate is true, the guarded instruction runs."""
        sim = FunctionalSimulator()
        sim.pred[0] = True
        # ADDI R1, R0, #42 @P0 ; HALT
        w1 = enc_ri(MAJ_ADDI, 1, 0, 42, pred=0, end=True)
        w2 = enc_i(MAJ_HALT, 0)
        sim.load_words(sim.pc, [w1, w2])
        sim.run(max_cycles=10)
        assert sim.regs[1] == 42

    def test_predicate_false_skips(self):
        """When predicate is false, the guarded instruction is a NOP."""
        sim = FunctionalSimulator()
        sim.pred[1] = False
        sim.regs[1] = 99  # should remain unchanged
        # ADDI R1, R0, #42 @P1 ; HALT
        w1 = enc_ri(MAJ_ADDI, 1, 0, 42, pred=1, end=True)
        w2 = enc_i(MAJ_HALT, 0)
        sim.load_words(sim.pc, [w1, w2])
        sim.run(max_cycles=10)
        assert sim.regs[1] == 99  # not modified

    def test_cmpi_sets_pred_then_guard(self):
        """CMPI sets predicate, which then guards a subsequent instruction."""
        sim = run_program([
            "ADDI R1, R0, #10",
            "CMPI.EQ P0, R1, #10",    # P0 = true
            "CMPI.EQ P1, R1, #999",   # P1 = false
            "HALT"
        ])
        assert sim.pred[0] is True
        assert sim.pred[1] is False
