class Instruction:
    def __init__(self, name, execute_fn):
        self.name = name
        self.execute_fn = execute_fn

    def execute(self, regs, mem, args):
        return self.execute_fn(regs, mem, args)


# Define a few instructions
def instr_add(regs, mem, args):
    rd, rs1, rs2 = args
    regs.write(rd, regs.read(rs1) + regs.read(rs2))

def instr_load(regs, mem, args):
    rd, addr = args
    regs.write(rd, mem.load(addr))

def instr_store(regs, mem, args):
    rs, addr = args
    mem.store(addr, regs.read(rs))

INSTRUCTION_SET = {
    "ADD": Instruction("ADD", instr_add),
    "LOAD": Instruction("LOAD", instr_load),
    "STORE": Instruction("STORE", instr_store),
}
