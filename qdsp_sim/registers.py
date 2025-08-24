class RegisterFile:
    def __init__(self, num_registers=32):
        self.registers = [0] * num_registers

    def read(self, idx: int) -> int:
        return self.registers[idx]

    def write(self, idx: int, value: int):
        self.registers[idx] = value & 0xFFFFFFFF  # 32-bit wraparound

    def dump(self):
        return {f"R{i}": val for i, val in enumerate(self.registers)}
