# src/dspsim/encoder.py

from __future__ import annotations

from .bitutil import u32

# Import opcodes from the central ISA definition
from .isa import MAJ_CMPI


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
    # Corrected encoding: 4-bit MAJ at [31:28], P? at [27], Pidx at [26:25], EOP at [24]
    w = (maj & 0xF) << 28
    if pred is not None:
        w |= (1 << 27) | ((pred & 0x3) << 25)
    if end:
        w |= (1 << 24)
    return w

# -----------------------------------------------------------------------------
# Instruction Encoders
# -----------------------------------------------------------------------------

# (Opcode constants removed from here; they are now imported from isa.py)

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

def enc_cmpi(
    pdst: int, rs1: int, imm: int, cmp_code: int,
    pred: int | None = None, end: bool = True,
) -> int:
    """
    Encode a CMPI instruction that writes a predicate result into pdst.
    Layout:
      - header: maj MAJ_CMPI [31:28], P? [27], Pidx [26:25], EOP [24]
      - rd (bits 23:19) = pdst  (predicate destination)
      - rs1 (bits 18:14) = rs1
      - cmp_code (bits 13:10) = comparison type
      - imm (bits 9:0) = 10-bit signed immediate
    """
    w = _header(MAJ_CMPI, pred, end)
    w |= (pdst & 0x1F) << 19
    w |= (rs1 & 0x1F) << 14
    w |= (cmp_code & 0xF) << 10
    w |= (imm & 0x3FF)
    return u32(w)