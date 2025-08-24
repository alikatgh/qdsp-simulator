# Instruction Set Architecture definitions.

def instr_add(sim, rd, rs1, rs2):
    """ R[rd] = R[rs1] + R[rs2] """
    val1 = sim.regs[rs1]
    val2 = sim.regs[rs2]
    sim.regs[rd] = (val1 + val2) & 0xFFFFFFFF

def instr_addi(sim, rd, rs1, imm):
    """ R[rd] = R[rs1] + imm """
    val1 = sim.regs[rs1]
    sim.regs[rd] = (val1 + imm) & 0xFFFFFFFF

def instr_ld(sim, rd, rs1, imm):
    """ R[rd] = Mem[R[rs1] + imm] """
    addr = sim.regs[rs1] + imm
    sim.regs[rd] = sim.mem.read_word(addr)

def instr_st(sim, rs2, rs1, imm):
    """ Mem[R[rs1] + imm] = R[rs2] """
    addr = sim.regs[rs1] + imm
    value = sim.regs[rs2]
    sim.mem.write_word(addr, value)

def instr_halt(sim):
    """ Stop simulation """
    sim.running = False

INSTRUCTION_SET = {
    # name: (function, argument_types)
    'ADD':  (instr_add,  ('reg', 'reg', 'reg')),
    'ADDI': (instr_addi, ('reg', 'reg', 'imm')),
    'LD':   (instr_ld,   ('reg', 'reg', 'imm')),
    'ST':   (instr_st,   ('reg', 'reg', 'imm')),
    'HALT': (instr_halt, ()),
}
