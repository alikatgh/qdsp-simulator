# src/dspsim/decoder.py

from __future__ import annotations

from .bitutil import get_bits, s32, sign_extend
from .inst import Inst  # Import the correct dataclass
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
    """Extracts a 14-bit signed immediate from an instruction word."""
    imm = get_bits(word, 13, 0)
    # Sign extend for 14 bits
    return s32(imm | 0xFFFFC000) if imm & 0x2000 else imm

def _common(word: int) -> tuple:
    """Extracts common fields from a 32-bit instruction word as per the ISA."""
    maj = get_bits(word, 31, 28)
    pbit = get_bits(word, 27, 27) != 0
    pidx = get_bits(word, 26, 25)
    end = get_bits(word, 24, 24) != 0
    rd = get_bits(word, 23, 19)
    rs1 = get_bits(word, 18, 14)
    rs2 = get_bits(word, 13, 9)
    
    predicate_index = pidx if pbit else None
    
    return maj, predicate_index, end, rd, rs1, rs2

def decode_word(word: int, pc: int = 0) -> Inst | None:
    """
    Decodes a 32-bit instruction word into an Inst object.
    
    Returns None if the major opcode is unrecognized.
    """
    maj, pred, end, rd, rs1, rs2 = _common(word)
    
    # Helper to create Inst with common params
    def make_inst(op, rd=rd, rs1=rs1, rs2=rs2, imm=None):
        return Inst(raw=word, pc=pc, op=op, rd=rd, rs1=rs1, rs2=rs2, imm=imm, pred=pred, endpkt=end)

    if maj == MAJ_ADD:
        return make_inst("ADD")
    if maj == MAJ_ADDI:
        return make_inst("ADDI", rs2=None, imm=_imm14s(word))
    if maj == MAJ_SUB:
        return make_inst("SUB")
    if maj == MAJ_AND:
        return make_inst("AND")
    if maj == MAJ_OR:
        return make_inst("OR")
    if maj == MAJ_XOR:
        return make_inst("XOR")
    if maj == MAJ_SHL:
        return make_inst("SHL")
    if maj == MAJ_SHR:
        return make_inst("SHR")
    if maj == MAJ_MUL:
        return make_inst("MUL")
    if maj == MAJ_MAC:
        return make_inst("MAC")
    if maj == MAJ_NOT:
        return make_inst("NOT", rs2=None)
    if maj == MAJ_LD32:
        return make_inst("LD", rs2=None, imm=_imm14s(word))
    if maj == MAJ_ST32:
        # ST: rd field [23:19] = source register, rs1 = base, imm = offset
        return make_inst("ST", rd=rd, rs1=rs1, rs2=None, imm=_imm14s(word))
    if maj == MAJ_J:
        return make_inst("J", rd=None, rs1=None, rs2=None, imm=_imm14s(word))
    if maj == MAJ_JR:
        return make_inst("JR", rd=None, rs2=None)
    if maj == MAJ_HALT:  # MAJ_HALT == MAJ_CMPI == 0xF
        # Distinguish HALT from CMPI: HALT has rd=0, rs1=0, and all lower bits=0
        if rd == 0 and rs1 == 0 and (word & 0x3FFF) == 0:
            return make_inst("HALT", rd=None, rs1=None, rs2=None)
        # CMPI: cmp_code in [13:10], imm10 in [9:0]
        cmp_code = get_bits(word, 13, 10)
        imm10 = sign_extend(get_bits(word, 9, 0), 10)
        cmp_names = {0: "EQ", 1: "NE", 2: "LT", 3: "GE", 4: "LE", 5: "GT"}
        cmp_name = cmp_names.get(cmp_code, str(cmp_code))
        return make_inst(f"CMPI.{cmp_name}", rd=rd, rs1=rs1, rs2=None, imm=imm10)

    return None