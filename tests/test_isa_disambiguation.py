# tests/test_isa_disambiguation.py
"""Regression tests for ISA encoding ambiguities and architectural reset state.

1. CMPI.EQ P0,R0,#0 vs HALT disambiguation (ISA §4, shared MAJ=0xF).
   Both encode to the same 32-bit word (rd=0, rs1=0, low14=0).  The ISA
   specifies that this pattern is decoded as HALT — not CMPI.  Both the
   decoder and the disassembler must honour the documented rule.

2. Predicate register reset state (ISA §5).
   All four predicate registers initialise to True.  Predicated-false
   instructions must be NOPs at startup (before any CMPI has run).
"""

from __future__ import annotations

import pytest

from dspsim import FunctionalSimulator
from dspsim.decoder import decode_word
from dspsim.disassembler import disassemble_word
from dspsim.encoder import enc_cmpi, enc_i
from dspsim.isa import MAJ_HALT


# ---------------------------------------------------------------------------
# 1. CMPI.EQ P0,R0,#0 vs HALT disambiguation
# ---------------------------------------------------------------------------

class TestHaltCmpiDisambiguation:
    """The all-zero-operand MAJ=0xF word must always decode as HALT.

    ISA §4 states: "HALT has rd=0, rs1=0, [13:0]=0". CMPI.EQ P0,R0,#0
    would have pdst=0, rs1=0, cmp_code=0 (EQ), imm10=0, which produces
    identical bit patterns in [23:0].  The documented disambiguation rule
    gives HALT priority: if rd==0, rs1==0, and low14==0, the word is HALT.
    """

    # The ambiguous word: MAJ=0xF, EOP set, all operand fields zero.
    # enc_cmpi(pdst=0, rs1=0, imm=0, cmp_code=0) == enc_i(MAJ_HALT, 0)
    AMBIGUOUS_WORD: int = enc_i(MAJ_HALT, 0)

    def test_cmpi_encodes_same_as_halt(self):
        """Verify the ambiguity exists at the encoding level (prerequisite)."""
        cmpi_word = enc_cmpi(pdst=0, rs1=0, imm=0, cmp_code=0)
        halt_word = enc_i(MAJ_HALT, 0)
        assert cmpi_word == halt_word, (
            "Prerequisite failed: CMPI.EQ P0,R0,#0 and HALT must share an encoding"
        )

    def test_decoder_resolves_to_halt(self):
        """decode_word must resolve the ambiguous word to HALT, not CMPI."""
        inst = decode_word(self.AMBIGUOUS_WORD)
        assert inst is not None, "decode_word returned None for HALT word"
        assert inst.op == "HALT", (
            f"Expected HALT, got {inst.op!r}. "
            "Decoder must apply the documented disambiguation rule: "
            "rd=0, rs1=0, low14=0 => HALT, not CMPI."
        )

    def test_disassembler_resolves_to_halt(self):
        """disassemble_word must produce 'HALT', not a CMPI mnemonic."""
        text = disassemble_word(self.AMBIGUOUS_WORD)
        assert "HALT" in text, (
            f"Expected 'HALT' in disassembly, got {text!r}. "
            "Disassembler must honour the HALT/CMPI disambiguation rule."
        )
        assert "CMPI" not in text, (
            f"Disassembly must not produce CMPI for the all-zero-operand word, got {text!r}"
        )

    def test_simulator_halts_not_cmpi(self):
        """The functional simulator must stop (HALT), not write a predicate."""
        sim = FunctionalSimulator()
        # Store the ambiguous word as the first instruction.
        sim.load_words(sim.pc, [self.AMBIGUOUS_WORD])
        # Capture initial pred state (should be all True by reset).
        initial_preds = list(sim.pred)
        sim.run(max_cycles=10)
        # sim.running should be False — HALT stopped execution.
        assert not sim.running, (
            "Simulator should have halted but kept running — "
            "the ambiguous word was not treated as HALT."
        )
        # Predicates must be unchanged (HALT has no side effect on pred).
        assert list(sim.pred) == initial_preds, (
            "HALT must not modify any predicate register, but preds changed."
        )

    @pytest.mark.parametrize("cmp_code, suffix", [
        (1, "NE"), (2, "LT"), (3, "GE"), (4, "LE"), (5, "GT"),
    ])
    def test_non_zero_cmp_code_decodes_as_cmpi(self, cmp_code, suffix):
        """Non-zero cmp_code in MAJ=0xF cannot be HALT — must decode as CMPI."""
        # These words have rd=0, rs1=0 but cmp_code != 0, so low14 != 0.
        # The HALT pattern requires low14==0, so these must be CMPI.
        word = enc_cmpi(pdst=0, rs1=0, imm=0, cmp_code=cmp_code)
        inst = decode_word(word)
        assert inst is not None
        assert inst.op.startswith("CMPI"), (
            f"Expected CMPI.{suffix}, got {inst.op!r}"
        )
        text = disassemble_word(word)
        assert "CMPI" in text and suffix in text, (
            f"Disassembly should contain 'CMPI' and '{suffix}', got {text!r}"
        )

    def test_nonzero_pdst_decodes_as_cmpi(self):
        """CMPI with pdst!=0 cannot be HALT (rd field is non-zero)."""
        # CMPI.EQ P1,R0,#0 — pdst=1, cmp_code=0, rs1=0, imm=0
        word = enc_cmpi(pdst=1, rs1=0, imm=0, cmp_code=0)
        inst = decode_word(word)
        assert inst is not None
        assert inst.op == "CMPI.EQ", (
            f"Expected CMPI.EQ (pdst=1 != 0, so not HALT), got {inst.op!r}"
        )

    def test_nonzero_rs1_decodes_as_cmpi(self):
        """CMPI with rs1!=0 cannot be HALT (rs1 field is non-zero)."""
        # CMPI.EQ P0,R1,#0 — pdst=0, rs1=1, cmp_code=0, imm=0
        word = enc_cmpi(pdst=0, rs1=1, imm=0, cmp_code=0)
        inst = decode_word(word)
        assert inst is not None
        assert inst.op == "CMPI.EQ", (
            f"Expected CMPI.EQ (rs1=1 != 0, so not HALT), got {inst.op!r}"
        )


# ---------------------------------------------------------------------------
# 2. Predicate register reset state and predicated-false startup behaviour
# ---------------------------------------------------------------------------

class TestPredicateResetState:
    """ISA §5: Predicate registers reset to True.

    "Predicate registers reset to True, so an un-guarded program behaves as if
    predication were absent."
    """

    def test_all_four_predicates_initialize_true(self):
        """A freshly constructed FunctionalSimulator has P0-P3 all True."""
        sim = FunctionalSimulator()
        for idx in range(4):
            assert sim.pred[idx] is True, (
                f"P{idx} should initialise to True, got {sim.pred[idx]!r}"
            )

    def test_pred_is_bool_not_int(self):
        """Predicate values must be Python bool, not int (0/1)."""
        sim = FunctionalSimulator()
        for idx in range(4):
            assert isinstance(sim.pred[idx], bool), (
                f"P{idx} should be bool, got {type(sim.pred[idx]).__name__}"
            )

    @pytest.mark.parametrize("pidx", [0, 1, 2, 3])
    def test_predicated_false_is_nop_at_startup(self, pidx):
        """At startup all predicates are True — explicitly set one to False and
        confirm the guarded instruction is suppressed (predicated-NOP behaviour).

        This validates that the simulator correctly skips instructions when
        the guarding predicate is False, independently of CMPI.
        """
        from dspsim.encoder import enc_ri
        from dspsim.isa import MAJ_ADDI

        sim = FunctionalSimulator()
        # Force exactly one pred to False before loading any program.
        sim.pred[pidx] = False
        sim.regs[1] = 0xDEAD  # sentinel — must survive if guarded instr is skipped

        # ADDI R1, R0, #0xBEEF @Pidx  (guarded by the False predicate)
        # HALT
        w_guarded = enc_ri(MAJ_ADDI, 1, 0, 0xBEEF & 0x1FFF, pred=pidx, end=True)
        w_halt = enc_i(MAJ_HALT, 0)
        sim.load_words(sim.pc, [w_guarded, w_halt])
        sim.run(max_cycles=10)

        assert sim.regs[1] == 0xDEAD, (
            f"Predicated-false (P{pidx}=False) instruction must be a NOP, "
            f"but R1 changed to 0x{sim.regs[1]:X}"
        )

    @pytest.mark.parametrize("pidx", [0, 1, 2, 3])
    def test_predicated_true_executes_at_startup(self, pidx):
        """At startup predicates are True, so a guarded instruction must execute."""
        from dspsim.encoder import enc_ri
        from dspsim.isa import MAJ_ADDI

        sim = FunctionalSimulator()
        # All predicates are True by reset — no forced setup needed.
        sim.regs[1] = 0

        w_guarded = enc_ri(MAJ_ADDI, 1, 0, 42, pred=pidx, end=True)
        w_halt = enc_i(MAJ_HALT, 0)
        sim.load_words(sim.pc, [w_guarded, w_halt])
        sim.run(max_cycles=10)

        assert sim.regs[1] == 42, (
            f"Predicated-true (P{pidx}=True at reset) instruction should execute, "
            f"but R1={sim.regs[1]}"
        )

    def test_all_predicates_true_means_unguarded_behaves_normally(self):
        """With all predicates True, guarded instructions behave like un-guarded ones."""
        from dspsim.assembler import assemble

        sim = FunctionalSimulator()
        # All preds are True; guarding with any Pidx should not suppress anything.
        words = assemble([
            "ADDI R1, R0, #10",     # un-guarded
            "ADDI R2, R0, #20",     # un-guarded
            "HALT",
        ])
        sim.load_words(sim.pc, words)
        sim.run(max_cycles=20)
        assert sim.regs[1] == 10
        assert sim.regs[2] == 20

    def test_predicated_false_does_not_affect_memory(self):
        """Predicated-false ST must not write to memory (no side-effect)."""
        from dspsim.encoder import enc_ri
        from dspsim.isa import MAJ_ST32

        sim = FunctionalSimulator()
        # Use a valid aligned memory address well above the PC area.
        target_addr = 0x2000
        # Pre-fill the target address with a sentinel value.
        sim.bus.write32(target_addr, 0xCAFEBABE)

        # Force P0 = False.
        sim.pred[0] = False
        # ST [R5], R1 @P0  — but P0=False, so no write should happen.
        # Encode: rd field = source register (R1=0), rs1 = R5 (address reg).
        sim.regs[5] = target_addr
        sim.regs[1] = 0x12345678  # value that must NOT be written

        # enc_ri for ST: rd=[23:19]=source, rs1=base, imm=offset
        w_st = enc_ri(MAJ_ST32, 1, 5, 0, pred=0, end=True)
        w_halt = enc_i(MAJ_HALT, 0)
        sim.load_words(sim.pc, [w_st, w_halt])
        sim.run(max_cycles=10)

        stored = sim.bus.read32(target_addr)
        assert stored == 0xCAFEBABE, (
            f"Predicated-false ST must not write memory; "
            f"expected 0xCAFEBABE, got 0x{stored:08X}"
        )
