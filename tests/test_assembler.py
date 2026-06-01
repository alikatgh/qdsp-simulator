# tests/test_assembler.py
"""Tests for the assembler: encoding, labels, error handling."""

import pytest

from dspsim.assembler import AsmError, assemble, parse_imm, parse_reg
from dspsim.decoder import decode_word


class TestParseReg:
    def test_valid(self):
        assert parse_reg("R0") == 0
        assert parse_reg("r31") == 31

    def test_invalid(self):
        with pytest.raises(AsmError):
            parse_reg("X5")

    def test_out_of_range(self):
        with pytest.raises(AsmError):
            parse_reg("R32")


class TestParseImm:
    def test_decimal(self):
        assert parse_imm("42", {}, 0) == 42

    def test_hex(self):
        assert parse_imm("0xFF", {}, 0) == 255

    def test_hash_prefix(self):
        assert parse_imm("#10", {}, 0) == 10

    def test_label_lookup(self):
        assert parse_imm("LOOP", {"LOOP": 0x20}, 0) == 0x20

    def test_bad(self):
        with pytest.raises(AsmError):
            parse_imm("xyz", {}, 0)


class TestAssemble:
    def test_add(self):
        words = assemble(["ADD R2, R0, R1", "HALT"])
        assert len(words) == 2
        inst = decode_word(words[0])
        assert inst.op == "ADD"

    def test_all_3r_ops(self):
        for op in ("ADD", "SUB", "AND", "OR", "XOR", "SHL", "SHR", "MUL", "MAC"):
            words = assemble([f"{op} R3, R1, R2", "HALT"])
            inst = decode_word(words[0])
            assert inst.op == op, f"Failed for {op}"

    def test_addi(self):
        words = assemble(["ADDI R1, R0, #100", "HALT"])
        inst = decode_word(words[0])
        assert inst.op == "ADDI"
        assert inst.imm == 100

    def test_not(self):
        words = assemble(["NOT R1, R0", "HALT"])
        inst = decode_word(words[0])
        assert inst.op == "NOT"

    def test_ld_st(self):
        words = assemble(["LD R1, [R10+4]", "ST [R10], R1", "HALT"])
        ld = decode_word(words[0])
        assert ld.op == "LD"
        assert ld.imm == 4

    def test_jump_label(self):
        words = assemble([
            "J TARGET",
            "HALT",
            "TARGET:",
            "HALT"
        ])
        assert len(words) == 3  # 2 instructions + 1 at target (label is not an instruction)
        # Actually: J, HALT, HALT = 3 words
        inst = decode_word(words[0])
        assert inst.op == "J"

    def test_cmpi(self):
        words = assemble(["CMPI.EQ P0, R1, #10", "HALT"])
        inst = decode_word(words[0])
        assert "CMPI" in inst.op

    def test_halt(self):
        words = assemble(["HALT"])
        inst = decode_word(words[0])
        assert inst.op == "HALT"

    def test_unknown_op_raises(self):
        with pytest.raises(AsmError):
            assemble(["FOOBAR R0, R1"])

    def test_comments_ignored(self):
        words = assemble([
            "; this is a comment",
            "ADDI R1, R0, #5  ; inline comment",
            "HALT"
        ])
        assert len(words) == 2

    def test_labels(self):
        words = assemble([
            "START:",
            "ADDI R1, R0, #1",
            "END:",
            "HALT"
        ])
        assert len(words) == 2

    def test_ld32_alias(self):
        words = assemble(["LD32 R1, [R10]", "HALT"])
        assert len(words) == 2

    def test_st32_alias(self):
        words = assemble(["ST32 [R10], R1", "HALT"])
        assert len(words) == 2
