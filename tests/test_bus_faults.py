"""Tests for Bus memory-access faults: 4-byte alignment and bounds enforcement.

The README documents that 32-bit loads/stores require 4-byte alignment; these
tests lock that contract in (it was previously unenforced -- an unaligned or
out-of-range access silently succeeded or raised a raw struct error).
"""
from __future__ import annotations

import pytest

from dspsim.assembler import assemble
from dspsim.bus import Bus, MemoryFault
from dspsim.core import FunctionalSimulator
from dspsim.devices import UART


def test_aligned_in_bounds_roundtrip() -> None:
    bus = Bus(size=64 * 1024)
    bus.write32(0x100, 0xDEADBEEF)
    assert bus.read32(0x100) == 0xDEADBEEF


def test_last_valid_word_ok() -> None:
    bus = Bus(size=4096)  # valid aligned words: 0x000 .. 0xFFC
    bus.write32(4092, 0x12345678)
    assert bus.read32(4092) == 0x12345678


@pytest.mark.parametrize("addr", [1, 2, 3, 0x101, 0x102, 0x103])
def test_unaligned_read_faults(addr: int) -> None:
    bus = Bus(size=64 * 1024)
    with pytest.raises(MemoryFault):
        bus.read32(addr)


@pytest.mark.parametrize("addr", [1, 2, 3, 0x101, 0x102, 0x103])
def test_unaligned_write_faults(addr: int) -> None:
    bus = Bus(size=64 * 1024)
    with pytest.raises(MemoryFault):
        bus.write32(addr, 0)


def test_out_of_bounds_read_faults() -> None:
    bus = Bus(size=4096)
    with pytest.raises(MemoryFault):
        bus.read32(4096)  # first word past the end


def test_out_of_bounds_write_faults() -> None:
    bus = Bus(size=4096)
    with pytest.raises(MemoryFault):
        bus.write32(4096, 0)


def test_mmio_bypasses_bounds_check() -> None:
    # A device mapped beyond RAM size is still reachable; MMIO owns its space.
    bus = Bus(size=4096)
    uart = UART()
    base = 0xE000_0000
    bus.map_mmio(base, 0x10, uart)
    bus.write32(base + 0x00, ord("A"))  # TX_DATA register
    assert uart.tx_bytes == b"A"


def test_mmio_alignment_still_enforced() -> None:
    bus = Bus(size=4096)
    uart = UART()
    base = 0x8000
    bus.map_mmio(base, 0x10, uart)
    with pytest.raises(MemoryFault):
        bus.write32(base + 1, 0)


def test_engine_surfaces_unaligned_access() -> None:
    # An unaligned LD must fault rather than silently returning a value.
    words = assemble(["ADDI R1, R0, #1", "LD R2, [R1+0]", "HALT"])
    sim = FunctionalSimulator(mem_size=64 * 1024)
    sim.load_words(0x1000, words)
    sim.pc = 0x1000
    with pytest.raises(RuntimeError):  # fast engine wraps MemoryFault as RuntimeError
        sim.run(max_cycles=100)
