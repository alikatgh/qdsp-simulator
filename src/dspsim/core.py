# The core simulator engine.
from . import isa
from . import memory

class Simulator:
    def __init__(self):
        self.regs = [0] * 32
        self.pc = 0
        self.mem = memory.Memory()
        self.running = False
        self.cycle_count = 0
        self.program = []

    def load_program(self, program_list):
        self.program = program_list
        self.pc = 0

    def run(self, entry_point=0):
        self.pc = entry_point
        self.running = True
        while self.running and self.pc < len(self.program):
            instr = self.program[self.pc]
            mnemonic = instr['mnemonic']
            operands = [op[1] for op in instr['operands']]

            # Basic execution
            instr_func, _ = isa.INSTRUCTION_SET[mnemonic]
            instr_func(self, *operands)

            self.pc += 1
            self.cycle_count += 1
    
    def dump_regs(self):
        for i in range(0, 32, 4):
            r0, r1, r2, r3 = self.regs[i:i+4]
            print(f"R{i:02d}-R{i+3:02d}: {r0:08X} {r1:08X} {r2:08X} {r3:08X}")
