# tests/test_disassembler.py
"""Tests for the disassembler — round-trip assemble -> disassemble."""

from dspsim.assembler import assemble
from dspsim.disassembler import disassemble, disassemble_word
from dspsim.encoder import enc_3r, enc_cmpi, enc_i, enc_ri
from dspsim.isa import (
    MAJ_ADD,
    MAJ_ADDI,
    MAJ_AND,
    MAJ_HALT,
    MAJ_LD32,
    MAJ_MUL,
    MAJ_NOT,
    MAJ_OR,
    MAJ_SUB,
    MAJ_XOR,
)


class TestDisassembleWord:
    def test_add(self):
        w = enc_3r(MAJ_ADD, 2, 0, 1)
        text = disassemble_word(w)
        assert "ADD" in text
        assert "R2" in text and "R0" in text and "R1" in text

    def test_sub(self):
        w = enc_3r(MAJ_SUB, 5, 3, 4)
        text = disassemble_word(w)
        assert "SUB" in text
        assert "R5" in text

    def test_addi(self):
        w = enc_ri(MAJ_ADDI, 1, 0, 123)
        text = disassemble_word(w)
        assert "ADDI" in text
        assert "R1" in text
        assert "123" in text or "0x7B" in text

    def test_halt(self):
        w = enc_i(MAJ_HALT, 0)
        text = disassemble_word(w)
        assert "HALT" in text

    def test_and(self):
        w = enc_3r(MAJ_AND, 2, 0, 1)
        assert "AND" in disassemble_word(w)

    def test_or(self):
        w = enc_3r(MAJ_OR, 2, 0, 1)
        assert "OR" in disassemble_word(w)

    def test_xor(self):
        w = enc_3r(MAJ_XOR, 2, 0, 1)
        assert "XOR" in disassemble_word(w)

    def test_mul(self):
        w = enc_3r(MAJ_MUL, 2, 0, 1)
        assert "MUL" in disassemble_word(w)

    def test_not(self):
        w = enc_3r(MAJ_NOT, 1, 0, 0)
        assert "NOT" in disassemble_word(w)

    def test_ld(self):
        w = enc_ri(MAJ_LD32, 1, 10, 8)
        text = disassemble_word(w)
        assert "LD" in text
        assert "R1" in text

    def test_cmpi(self):
        w = enc_cmpi(0, 1, 10, 0)  # CMPI.EQ P0, R1, #10
        text = disassemble_word(w)
        assert "CMPI" in text
        assert "EQ" in text

    def test_predicated(self):
        w = enc_3r(MAJ_ADD, 2, 0, 1, pred=2)
        text = disassemble_word(w)
        assert "@P2" in text


class TestDisassembleList:
    def test_basic_program(self):
        words = assemble([
            "ADDI R1, R0, #100",
            "ADDI R2, R1, #50",
            "HALT"
        ])
        lines = disassemble(words, base_pc=0)
        assert len(lines) == 3
        assert "ADDI" in lines[0]
        assert "HALT" in lines[2]
