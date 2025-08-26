from __future__ import annotations
from .bitutil import get_bits, s32
from .isa import *
from dataclasses import dataclass

@dataclass
class Inst:
    op: str
    rd: int | None = None
    rs1: int | None = None
    rs2: int | None = None
    imm: int | None = None
    pred: int | None = None
    endpkt: bool = True



def _imm14s(word: int) -> int:
    """Extracts a 14-bit signed immediate from an instruction word."""
    return s32(get_bits(word, 13, 0))

# -----------------------------------------------------------------------------

def _common(word: int) -> tuple:
    """Extracts common fields from a 32-bit instruction word as per the ISA."""
    maj = get_bits(word, 31, 28)
    pbit = get_bits(word, 27, 27) != 0
    pidx = get_bits(word, 26, 25)
    end = get_bits(word, 24, 24) != 0
    rd = get_bits(word, 23, 19)
    rs1 = get_bits(word, 18, 14)
    rs2 = get_bits(word, 13, 9)
    
    # Use pidx only if the predicate bit is set
    predicate_index = pidx if pbit else None
    
    return maj, predicate_index, end, rd, rs1, rs2

# -----------------------------------------------------------------------------

def decode(word: int) -> Inst | None:
    """
    Decodes a 32-bit instruction word into an Inst object.
    
    Returns None if the major opcode is unrecognized.
    """
    maj, pred, end, rd, rs1, rs2 = _common(word)

    if maj == MAJ_ADD:
        return Inst("ADD", rd, rs1, rs2, None, pred, end, word)
    if maj == MAJ_ADDI:
        return Inst("ADDI", rd, rs1, None, _imm14s(word), pred, end, word)
    if maj == MAJ_SUB:
        return Inst("SUB", rd, rs1, rs2, None, pred, end, word)
    if maj == MAJ_AND:
        return Inst("AND", rd, rs1, rs2, None, pred, end, word)
    if maj == MAJ_OR:
        return Inst("OR", rd, rs1, rs2, None, pred, end, word)
    if maj == MAJ_XOR:
        return Inst("XOR", rd, rs1, rs2, None, pred, end, word)
    if maj == MAJ_SHL:
        return Inst("SHL", rd, rs1, rs2, None, pred, end, word)
    if maj == MAJ_SHR:
        return Inst("SHR", rd, rs1, rs2, None, pred, end, word)
    if maj == MAJ_MUL:
        return Inst("MUL", rd, rs1, rs2, None, pred, end, word)
    if maj == MAJ_MAC:
        return Inst("MAC", rd, rs1, rs2, None, pred, end, word)
    if maj == MAJ_LD:
        return Inst("LD", rd, rs1, None, _imm14s(word), pred, end, word)
    if maj == MAJ_ST:
        return Inst("ST", None, rs1, rs2, _imm14s(word), pred, end, word)
    if maj == MAJ_J:
        return Inst("J", None, None, None, _imm14s(word), pred, end, word)
    if maj == MAJ_JR:
        return Inst("JR", None, rs1, None, None, pred, end, word)
    if maj == MAJ_CMPI:
        sub = get_bits(word, 8, 5)
        return Inst(f"CMPI_{sub}", None, rs1, None, _imm14s(word), pred, end, word)
    if maj == MAJ_HALT:
        return Inst("HALT", None, None, None, None, pred, end, word)
        
    return None

# --- at the bottom of src/dspsim/decoder.py (add these) ---

# Backwards-compatible wrapper expected by other modules:
def decode_word(word: int, pc: int = 0):
    """
    Backwards-compatible wrapper: decode a 32-bit word into an Inst object.
    Kept for modules that call decode_word(word, pc).
    """
    inst = decode(word)
    # if the caller expects 'raw' and 'pc' attributes, attach them when safe
    try:
        inst.raw = word
        inst.pc = pc
    except Exception:
        # inst might be None or not support attribute set — ignore
        pass
    return inst
