from __future__ import annotations


def u32(x: int) -> int: return x & 0xFFFFFFFF


def s32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x if x < 0x80000000 else x - 0x100000000


def get_bits(x: int, hi: int, lo: int) -> int:
    return (x >> lo) & ((1 << (hi - lo + 1)) - 1)