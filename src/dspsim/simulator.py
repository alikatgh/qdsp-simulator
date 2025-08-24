import sys
from .registers import RegisterFile
from .memory import Memory
from .instructions import INSTRUCTION_SET

class Simulator:
    def __init__(self):
        self.regs = RegisterFile()
        self.mem = Memory()
        self.pc = 0
        self.program = []

    def load_program(self, lines):
        self.program = [line.strip().split() for line in lines if line.strip()]

    def run(self):
        while self.pc < len(self.program):
            parts = self.program[self.pc]
            instr_name = parts[0].upper()
            args = list(map(int, parts[1:]))
            if instr_name in INSTRUCTION_SET:
                INSTRUCTION_SET[instr_name].execute(self.regs, self.mem, args)
            else:
                print(f"Unknown instruction: {instr_name}")
            self.pc += 1

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m dsp_sim.simulator <program.dspasm>")
        sys.exit(1)

    filename = sys.argv[1]
    with open(filename) as f:
        lines = f.readlines()

    sim = Simulator()
    sim.load_program(lines)
    sim.run()
    print("Registers:", sim.regs.dump())
