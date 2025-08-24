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


def enc_cmpi(rs1: int, imm: int, cmp_code: int, pred: int = 0, end: bool = True) -> int:
    """
    Encodes a compare-immediate (CMPI) format instruction.
    Note: CMPI is assumed to always be predicated.
    """
    w = _header(MAJ_CMPI, pred, end)
    w |= (rs1 & 0x1F) << 14
    w |= (imm & 0x3FFF)
    w |= (cmp_code & 0xF) << 5
    return u32(w)