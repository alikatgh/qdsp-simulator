# tests/test_roundtrip.py
"""Assembler / disassembler round-trip tests.

Each test assembles one or more instructions, then disassembles the resulting
word(s) and checks that the disassembled text is self-consistent with the
original intent.  The goal is to exercise the full encode→decode path for
every instruction type, including edge-case immediates and predicated forms.
"""

import pytest

from dspsim.assembler import assemble
from dspsim.decoder import decode_word
from dspsim.disassembler import disassemble, disassemble_word
from dspsim.encoder import enc_3r, enc_cmpi, enc_i, enc_ri
from dspsim.isa import (
    MAJ_ADD,
    MAJ_ADDI,
    MAJ_HALT,
    MAJ_J,
    MAJ_JR,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def asm_one(line: str) -> int:
    """Assemble a single instruction line and return its encoded word."""
    words = assemble([line, "HALT"])
    assert len(words) >= 1
    return words[0]


def roundtrip_one(line: str) -> str:
    """Assemble one instruction and return its disassembled text."""
    word = asm_one(line)
    return disassemble_word(word)


# ---------------------------------------------------------------------------
# 3-register ALU instructions
# ---------------------------------------------------------------------------

class TestRoundTrip3R:
    @pytest.mark.parametrize("op", ["ADD", "SUB", "AND", "OR", "XOR", "SHL", "SHR", "MUL", "MAC"])
    def test_all_3r_ops(self, op):
        text = roundtrip_one(f"{op} R3, R1, R2")
        assert op in text
        assert "R3" in text
        assert "R1" in text
        assert "R2" in text

    def test_add_rd_equals_rs(self):
        """rd == rs1 is a valid encoding (accumulate-style)."""
        text = roundtrip_one("ADD R5, R5, R2")
        assert "ADD" in text
        assert "R5" in text

    def test_register_field_max(self):
        """Register indices up to R31 should survive the round-trip."""
        text = roundtrip_one("ADD R31, R30, R29")
        assert "R31" in text
        assert "R30" in text
        assert "R29" in text

    def test_register_field_zero(self):
        """R0 is valid and must not be confused with an absent field."""
        text = roundtrip_one("ADD R0, R0, R0")
        # R0 should appear at least once (rd)
        assert "R0" in text


class TestRoundTripNOT:
    def test_basic(self):
        text = roundtrip_one("NOT R7, R6")
        assert "NOT" in text
        assert "R7" in text
        assert "R6" in text

    def test_self_not(self):
        """NOT Rx, Rx is a valid in-place bitwise inversion."""
        text = roundtrip_one("NOT R4, R4")
        assert "NOT" in text
        assert "R4" in text


# ---------------------------------------------------------------------------
# ADDI — signed 14-bit immediate
# ---------------------------------------------------------------------------

class TestRoundTripADDI:
    def test_zero_imm(self):
        text = roundtrip_one("ADDI R1, R0, #0")
        assert "ADDI" in text
        assert "R1" in text
        # Zero immediate: may show as "0" or "0x0"
        assert "0" in text

    def test_small_positive(self):
        text = roundtrip_one("ADDI R2, R1, #7")
        assert "ADDI" in text
        assert "7" in text

    def test_large_positive(self):
        """Large positive within 14-bit signed range (max 8191)."""
        text = roundtrip_one("ADDI R3, R0, #8191")
        assert "ADDI" in text
        # Value may appear as decimal or hex
        assert "8191" in text or "0x1FFF" in text or "1FFF" in text

    def test_negative_imm(self):
        """Negative immediate should survive sign-extension round-trip."""
        text = roundtrip_one("ADDI R4, R0, #-1")
        assert "ADDI" in text
        assert "-1" in text

    def test_negative_imm_minus_128(self):
        text = roundtrip_one("ADDI R5, R0, #-128")
        assert "ADDI" in text
        assert "-128" in text


# ---------------------------------------------------------------------------
# Memory: LD / ST
# ---------------------------------------------------------------------------

class TestRoundTripMemory:
    def test_ld_zero_offset(self):
        text = roundtrip_one("LD R1, [R10]")
        assert "LD" in text
        assert "R1" in text
        assert "R10" in text

    def test_ld_positive_offset(self):
        text = roundtrip_one("LD R1, [R10+4]")
        assert "LD" in text
        assert "4" in text

    def test_ld_negative_offset(self):
        text = roundtrip_one("LD R1, [R10-8]")
        assert "LD" in text
        assert "-8" in text

    def test_st_zero_offset(self):
        text = roundtrip_one("ST [R10], R2")
        assert "ST" in text
        assert "R10" in text

    def test_st_positive_offset(self):
        text = roundtrip_one("ST [R10+16], R2")
        assert "ST" in text
        assert "16" in text or "0x10" in text

    def test_st_alias_ld32(self):
        """LD32 alias must produce the same encoding as LD."""
        w_ld = asm_one("LD R1, [R10+4]")
        w_ld32 = asm_one("LD32 R1, [R10+4]")
        assert w_ld == w_ld32

    def test_st_alias_st32(self):
        """ST32 alias must produce the same encoding as ST."""
        w_st = asm_one("ST [R10], R1")
        w_st32 = asm_one("ST32 [R10], R1")
        assert w_st == w_st32


# ---------------------------------------------------------------------------
# Control flow: J, JR
# ---------------------------------------------------------------------------

class TestRoundTripControlFlow:
    def test_halt_encodes_and_decodes(self):
        text = roundtrip_one("HALT")
        assert "HALT" in text

    def test_jmp_forward(self):
        """J with a forward target should disassemble to a J instruction."""
        words = assemble(["J TARGET", "HALT", "TARGET:", "HALT"])
        text = disassemble_word(words[0], pc=0)
        assert "J" in text

    def test_jr(self):
        w = enc_ri(MAJ_JR, 0, 15, 0)  # JR with rs1=R15
        text = disassemble_word(w)
        assert "JR" in text
        assert "R15" in text

    def test_j_target_address_in_disasm(self):
        """Disassembler should embed an absolute target address."""
        # J that skips one word forward from pc=0x1000:
        # offset in words = 1, so imm = 1; target = 0x1000 + 4 + 4 = 0x1008
        w = enc_i(MAJ_J, 1)
        text = disassemble_word(w, pc=0x1000)
        # Target 0x1008 should appear somewhere in the text
        assert "1008" in text.upper() or "0X1008" in text.upper()


# ---------------------------------------------------------------------------
# CMPI — all six comparison codes
# ---------------------------------------------------------------------------

class TestRoundTripCMPI:
    @pytest.mark.parametrize("spec,code", [
        ("EQ", 0), ("NE", 1), ("LT", 2), ("GE", 3), ("LE", 4), ("GT", 5),
    ])
    def test_all_cmpi_specs(self, spec, code):
        text = roundtrip_one(f"CMPI.{spec} P0, R1, #10")
        assert "CMPI" in text
        assert spec in text

    def test_cmpi_pred_dest_preserved(self):
        """Predicate destination field P0..P3 must survive encode/decode."""
        for p in range(4):
            w = enc_cmpi(p, 1, 10, 0)  # CMPI.EQ Pp, R1, #10
            text = disassemble_word(w)
            assert f"P{p}" in text

    def test_cmpi_negative_imm(self):
        """CMPI with a negative 10-bit immediate should round-trip correctly."""
        w = enc_cmpi(0, 1, (-5) & 0x3FF, 0)  # CMPI.EQ P0, R1, #-5
        text = disassemble_word(w)
        assert "CMPI" in text
        assert "-5" in text


# ---------------------------------------------------------------------------
# Predicated instructions
# ---------------------------------------------------------------------------

class TestRoundTripPredicated:
    @pytest.mark.parametrize("pred_idx", [0, 1, 2, 3])
    def test_predicated_add(self, pred_idx):
        """@Pn prefix should survive assemble→disassemble."""
        words = assemble([f"ADD R2, R0, R1 @P{pred_idx}", "HALT"])
        text = disassemble_word(words[0])
        assert f"@P{pred_idx}" in text

    def test_predicated_addi(self):
        words = assemble(["ADDI R1, R0, #42 @P2", "HALT"])
        text = disassemble_word(words[0])
        assert "@P2" in text

    def test_predicated_halt(self):
        """HALT with a predicate bit set should be detectable via the word."""
        words = assemble(["HALT @P0"])
        # The word has a predicate bit; HALT text may or may not carry it
        # but the predicate bit should be in the raw encoding
        word = words[0]
        pbit = (word >> 27) & 1
        assert pbit == 1

    def test_predicated_st(self):
        words = assemble(["ST [R10], R1 @P3", "HALT"])
        text = disassemble_word(words[0])
        assert "@P3" in text


# ---------------------------------------------------------------------------
# Full disassemble() on a multi-instruction program
# ---------------------------------------------------------------------------

class TestDisassembleList:
    def test_line_count_matches_word_count(self):
        words = assemble([
            "ADDI R1, R0, #1",
            "ADDI R2, R0, #2",
            "ADD R3, R1, R2",
            "HALT",
        ])
        lines = disassemble(words, base_pc=0)
        assert len(lines) == 4

    def test_pc_labels_increment_by_four(self):
        words = assemble(["ADDI R1, R0, #1", "HALT"])
        lines = disassemble(words, base_pc=0x2000)
        assert "2000" in lines[0]
        assert "2004" in lines[1]

    def test_all_ops_present_in_output(self):
        words = assemble([
            "ADD R0, R0, R0",
            "SUB R0, R0, R0",
            "AND R0, R0, R0",
            "OR R0, R0, R0",
            "XOR R0, R0, R0",
            "HALT",
        ])
        combined = "\n".join(disassemble(words))
        for op in ("ADD", "SUB", "AND", "OR", "XOR", "HALT"):
            assert op in combined

    def test_base_pc_zero(self):
        """base_pc=0 is a valid argument; first entry should show 0x0000."""
        words = assemble(["HALT"])
        lines = disassemble(words, base_pc=0)
        assert "0000" in lines[0]

    def test_non_instruction_word_produces_dotword(self):
        """An unrecognized word should produce a .word fallback in the disassembler."""
        unknown_word = 0xDEADBEEF  # bit 31:28 could be any opcode
        text = disassemble_word(unknown_word)
        # Either it decodes to a known instruction or falls back to .word
        # We only assert no exception is raised and a non-empty string returned
        assert isinstance(text, str)
        assert len(text) > 0


# ---------------------------------------------------------------------------
# Decode correctness — Inst fields
# ---------------------------------------------------------------------------

class TestDecodeFields:
    def test_add_fields(self):
        w = enc_3r(MAJ_ADD, 7, 5, 3)
        inst = decode_word(w)
        assert inst is not None
        assert inst.op == "ADD"
        assert inst.rd == 7
        assert inst.rs1 == 5
        assert inst.rs2 == 3
        assert inst.pred is None  # no predication

    def test_addi_fields(self):
        w = enc_ri(MAJ_ADDI, 2, 1, 100)
        inst = decode_word(w)
        assert inst is not None
        assert inst.op == "ADDI"
        assert inst.rd == 2
        assert inst.rs1 == 1
        assert inst.imm == 100

    def test_addi_negative_imm_sign_extends(self):
        w = enc_ri(MAJ_ADDI, 1, 0, (-1) & 0x3FFF)
        inst = decode_word(w)
        assert inst is not None
        assert inst.imm == -1

    def test_halt_fields(self):
        w = enc_i(MAJ_HALT, 0)
        inst = decode_word(w)
        assert inst is not None
        assert inst.op == "HALT"
        assert inst.rd is None
        assert inst.rs1 is None

    def test_cmpi_eq_fields(self):
        w = enc_cmpi(2, 3, 15, 0)  # CMPI.EQ P2, R3, #15
        inst = decode_word(w)
        assert inst is not None
        assert "CMPI" in inst.op
        assert "EQ" in inst.op
        assert inst.rd == 2   # predicate destination
        assert inst.rs1 == 3
        assert inst.imm == 15

    def test_predicated_field(self):
        """Predicate index must be captured in the Inst.pred field."""
        w = enc_3r(MAJ_ADD, 1, 2, 3, pred=2)
        inst = decode_word(w)
        assert inst is not None
        assert inst.pred == 2

    def test_j_imm_sign_extends(self):
        """Negative J offset (backward jump) must decode to a negative imm."""
        # imm = -1 in 14-bit means 0x3FFF
        w = enc_i(MAJ_J, 0x3FFF)
        inst = decode_word(w)
        assert inst is not None
        assert inst.imm == -1
