# src/dspsim/disassembler.py
"""Disassembler: converts 32-bit instruction words back to assembly text."""

from __future__ import annotations

from .bitutil import get_bits, s32, sign_extend
from .isa import (
    MAJ_ADD,
    MAJ_ADDI,
    MAJ_AND,
    MAJ_HALT,
    MAJ_J,
    MAJ_JR,
    MAJ_LD32,
    MAJ_MAC,
    MAJ_MUL,
    MAJ_NOT,
    MAJ_OR,
    MAJ_SHL,
    MAJ_SHR,
    MAJ_ST32,
    MAJ_SUB,
    MAJ_XOR,
)


def _imm14s(word: int) -> int:
    imm = get_bits(word, 13, 0)
    return s32(imm | 0xFFFFC000) if imm & 0x2000 else imm


def _pred_prefix(word: int) -> str:
    pbit = get_bits(word, 27, 27)
    if not pbit:
        return ""
    pidx = get_bits(word, 26, 25)
    return f" @P{pidx}"


def _fmt_imm(v: int) -> str:
    if v < 0:
        return f"-{abs(v)}"
    if v > 9:
        return f"0x{v:X}"
    return str(v)


def disassemble_word(word: int, pc: int = 0) -> str:
    """Disassemble a single 32-bit word into an assembly string."""
    maj = get_bits(word, 31, 28)
    rd = get_bits(word, 23, 19)
    rs1 = get_bits(word, 18, 14)
    rs2 = get_bits(word, 13, 9)
    pred = _pred_prefix(word)

    _3r = {
        MAJ_ADD: "ADD", MAJ_SUB: "SUB", MAJ_AND: "AND", MAJ_OR: "OR",
        MAJ_XOR: "XOR", MAJ_SHL: "SHL", MAJ_SHR: "SHR",
        MAJ_MUL: "MUL", MAJ_MAC: "MAC",
    }

    if maj in _3r:
        return f"{_3r[maj]} R{rd}, R{rs1}, R{rs2}{pred}"

    if maj == MAJ_NOT:
        return f"NOT R{rd}, R{rs1}{pred}"

    if maj == MAJ_ADDI:
        imm = _imm14s(word)
        return f"ADDI R{rd}, R{rs1}, #{imm}{pred}"

    if maj == MAJ_LD32:
        imm = _imm14s(word)
        if imm == 0:
            return f"LD R{rd}, [R{rs1}]{pred}"
        sign = "+" if imm >= 0 else ""
        return f"LD R{rd}, [R{rs1}{sign}{imm}]{pred}"

    if maj == MAJ_ST32:
        imm = _imm14s(word)
        # Source register is in rd field [23:19]
        rs_src = rd
        if imm == 0:
            return f"ST [R{rs1}], R{rs_src}{pred}"
        sign = "+" if imm >= 0 else ""
        return f"ST [R{rs1}{sign}{imm}], R{rs_src}{pred}"

    if maj == MAJ_J:
        imm = _imm14s(word)
        target = pc + 4 + (imm << 2)
        return f"J 0x{target & 0xFFFFFFFF:X}{pred}"

    if maj == MAJ_JR:
        return f"JR R{rs1}{pred}"

    if maj == MAJ_HALT:  # shared with CMPI
        if rd == 0 and rs1 == 0 and (word & 0x3FFF) == 0:
            return f"HALT{pred}"
        # CMPI: cmp_code in [13:10], imm10 in [9:0]
        cmp_code = get_bits(word, 13, 10)
        cmp_names = {0: "EQ", 1: "NE", 2: "LT", 3: "GE", 4: "LE", 5: "GT"}
        cmp_name = cmp_names.get(cmp_code, str(cmp_code))
        imm = sign_extend(get_bits(word, 9, 0), 10)
        return f"CMPI.{cmp_name} P{rd}, R{rs1}, #{imm}{pred}"

    return f".word 0x{word:08X}"


def disassemble(words: list[int], base_pc: int = 0) -> list[str]:
    """Disassemble a list of 32-bit words into assembly lines."""
    lines = []
    for i, w in enumerate(words):
        pc = base_pc + i * 4
        asm = disassemble_word(w, pc)
        lines.append(f"  0x{pc:04X}:  {asm}")
    return lines
