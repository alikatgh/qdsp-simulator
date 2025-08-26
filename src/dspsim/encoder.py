from __future__ import annotations

from .bitutil import *
from .isa import *


def _header(maj: int, pred: int | None = None, end: bool = True) -> int:
    """
    Constructs the common 32-bit instruction header.

    Args:
        maj: The major opcode (4 bits).
        pred: The predicate register index (2 bits). If None, predication is disabled.
        end: The 'end of packet' bit.

    Returns:
        An integer representing the partially built instruction word.
    """
    w = (maj & 0xF) << 28
    if pred is not None:
        w |= (1 << 27) | ((pred & 0x3) << 25)
    if end:
        w |= (1 << 24)
    return w

# -----------------------------------------------------------------------------
# Instruction Encoders
# -----------------------------------------------------------------------------

# src/dspsim/encoder.py

# Arithmetic / logic
MAJ_ADD   = 0x0
MAJ_ADDI  = 0x1
MAJ_SUB   = 0x2
MAJ_AND   = 0x3
MAJ_OR    = 0x4
MAJ_XOR   = 0x5
MAJ_SHL   = 0x6
MAJ_SHR   = 0x7
MAJ_MUL   = 0x8
MAJ_MAC   = 0x9
MAJ_NOT   = 0xA

# Memory
MAJ_LD32  = 0xB
MAJ_ST32  = 0xC

# Control / compare
MAJ_J     = 0xD
MAJ_JR    = 0xE
MAJ_CMPI  = 0xF   # example (your compare group)

# System
MAJ_HALT  = 0x0F  # ensure unique code

# backwards-compatible aliases used by assembler & tests:
MAJ_LD32 = MAJ_LD
MAJ_ST32 = MAJ_ST


def enc_3r(maj: int, rd: int, rs1: int, rs2: int, pred: int | None = None, end: bool = True) -> int:
    """Encodes a 3-register (3R) format instruction."""
    w = _header(maj, pred, end)
    w |= (rd & 0x1F) << 19
    w |= (rs1 & 0x1F) << 14
    w |= (rs2 & 0x1F) << 9
    return u32(w)


def enc_ri(maj: int, rd: int, rs1: int, imm: int, pred: int | None = None, end: bool = True) -> int:
    """Encodes a register-immediate (RI) format instruction."""
    w = _header(maj, pred, end)
    w |= (rd & 0x1F) << 19
    w |= (rs1 & 0x1F) << 14
    w |= (imm & 0x3FFF)
    return u32(w)


def enc_i(maj: int, imm: int, pred: int | None = None, end: bool = True) -> int:
    """Encodes an immediate-only (I) format instruction."""
    w = _header(maj, pred, end)
    w |= (imm & 0x3FFF)
    return u32(w)

def enc_cmpi(pdst: int, rs1: int, imm: int, cmp_code: int, pred: int | None = None, end: bool = True) -> int:
    """
    Encode a CMPI instruction that writes a predicate result into pdst.
    Layout:
      - header: maj MAJ_CMPI, optional predicate guard bits in header if pred is not None
      - rd (bits 23:19) = pdst  (predicate destination index encoded here)
      - rs1 (bits 18:14) = rs1
      - cmp_code (bits 8:5) = cmp_code
      - imm (bits 13:0) = imm (14-bit immediate)
    """
    w = _header(MAJ_CMPI, pred, end)
    # predicate destination encoded in rd field
    w |= (pdst & 0x1F) << 19
    w |= (rs1 & 0x1F) << 14
    w |= (imm & 0x3FFF)
    w |= (cmp_code & 0xF) << 5
    return u32(w)
