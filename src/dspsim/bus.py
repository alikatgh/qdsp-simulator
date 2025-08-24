from __future__ import annotations

import struct
from typing import List, Optional, Tuple

from .bitutil import u32


class MMIO:
    """Abstract base class for a Memory-Mapped I/O device."""

    def read32(self, addr: int) -> int:
        """Reads a 32-bit value from the device at the given address."""
        raise NotImplementedError

    def write32(self, addr: int, value: int) -> None:
        """Writes a 32-bit value to the device at the given address."""
        raise NotImplementedError

# -----------------------------------------------------------------------------

class Bus:
    """
    Simulates a system bus with main memory and support for memory-mapped I/O.
    """

    def __init__(self, size: int = 16 * 1024 * 1024):
        """
        Initializes the bus.

        Args:
            size: The total size of the main memory in bytes.
        """
        self.mem = bytearray(size)
        # Each entry is a tuple: (start_addr, end_addr_inclusive, device_obj)
        self.mmio: List[Tuple[int, int, MMIO]] = []

    def map_mmio(self, start: int, size: int, dev: MMIO):
        """
        Maps a device to a specific memory address range.

        Args:
            start: The starting address of the MMIO region.
            size: The size of the region in bytes.
            dev: The MMIO device object to map.
        """
        self.mmio.append((start, start + size - 1, dev))

    def _mmio(self, addr: int) -> Optional[MMIO]:
        """Finds the MMIO device responsible for a given address, if any."""
        for start, end, device in self.mmio:
            if start <= addr <= end:
                return device
        return None

    def load_blob(self, addr: int, data: bytes):
        """Loads a binary blob (bytes) into main memory at a specific address."""
        self.mem[addr : addr + len(data)] = data

    def read32(self, addr: int) -> int:
        """
        Reads a 32-bit little-endian value from the bus.

        Delegates to an MMIO device if the address is mapped;
        otherwise, reads from main memory.
        """
        if dev := self._mmio(addr):
            return u32(dev.read32(addr))
        else:
            return struct.unpack_from('<I', self.mem, addr)[0]

    def write32(self, addr: int, val: int):
        """
        Writes a 32-bit little-endian value to the bus.

        Delegates to an MMIO device if the address is mapped;
        otherwise, writes to main memory.
        """
        if dev := self._mmio(addr):
            dev.write32(addr, val)
        else:
            struct.pack_into('<I', self.mem, addr, u32(val))

    def read(self, addr: int, size: int) -> bytes:
        """Reads a raw block of bytes directly from main memory."""
        return bytes(self.mem[addr : addr + size])

    def write(self, addr: int, data: bytes) -> None:
        """Writes a raw block of bytes directly to main memory."""
        self.mem[addr : addr + len(data)] = data