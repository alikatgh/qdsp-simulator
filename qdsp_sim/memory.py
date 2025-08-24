# Memory and MMIO Bus simulation.

class Memory:
    """Represents a simple, flat memory space."""
    def __init__(self, size_bytes=1024 * 4):
        if size_bytes % 4 != 0:
            raise ValueError("Memory size must be a multiple of 4.")
        self.size = size_bytes
        self.data = bytearray(size_bytes)

    def read_word(self, address: int) -> int:
        if not (0 <= address < self.size and address % 4 == 0):
            raise ValueError(f"Invalid memory read at address 0x{address:X}")
        return int.from_bytes(self.data[address:address+4], 'little')

    def write_word(self, address: int, value: int):
        if not (0 <= address < self.size and address % 4 == 0):
            raise ValueError(f"Invalid memory write at address 0x{address:X}")
        self.data[address:address+4] = value.to_bytes(4, 'little')
