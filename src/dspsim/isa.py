# src/dspsim/isa.py
# Instruction Set Architecture definitions.

# === Opcode constants (encoding layer) ===

# ALU
MAJ_ADD   = 0x0
MAJ_ADDI  = 0x1
MAJ_SUB   = 0x2
MAJ_AND   = 0x3
MAJ_OR    = 0x4
MAJ_XOR   = 0x5
MAJ_SHL   = 0x6
MAJ_SHR   = 0x7
MAJ_MUL   = 0x8
MAJ_MAC   = 0x9
MAJ_NOT   = 0xA

# Memory (using legacy names for assembler compatibility)
MAJ_LD32  = 0xB
MAJ_ST32  = 0xC
MAJ_LD = MAJ_LD32
MAJ_ST = MAJ_ST32

# Control flow
MAJ_J     = 0xD
MAJ_JR    = 0xE
MAJ_CMPI  = 0xF  # Note: CMPI shares a major opcode with HALT in this simplified model.
MAJ_HALT  = 0xF  # A sub-opcode would distinguish them in a real ISA.


# === Functional semantics (executed by simulator) ===

def instr_add(sim, rd, rs1, rs2):
    """R[rd] = R[rs1] + R[rs2]"""
    sim.regs[rd] = (sim.regs[rs1] + sim.regs[rs2]) & 0xFFFFFFFF

def instr_addi(sim, rd, rs1, imm):
    """R[rd] = R[rs1] + imm"""
    sim.regs[rd] = (sim.regs[rs1] + imm) & 0xFFFFFFFF

def instr_sub(sim, rd, rs1, rs2):
    """R[rd] = R[rs1] - R[rs2]"""
    sim.regs[rd] = (sim.regs[rs1] - sim.regs[rs2]) & 0xFFFFFFFF

def instr_ld(sim, rd, rs1, imm):
    """R[rd] = Mem[R[rs1] + imm]"""
    addr = sim.regs[rs1] + imm
    sim.regs[rd] = sim.bus.read32(addr)

def instr_st(sim, rs2, rs1, imm):
    """Mem[R[rs1] + imm] = R[rs2]"""
    addr = sim.regs[rs1] + imm
    sim.bus.write32(addr, sim.regs[rs2])

def instr_halt(sim):
    """Stop simulation"""
    sim.running = False


# === Lookup table: mnemonic -> (executor, arg types, opcode) ===

INSTRUCTION_SET = {
    'ADD':  (instr_add,  ('reg', 'reg', 'reg'), MAJ_ADD),
    'ADDI': (instr_addi, ('reg', 'reg', 'imm'), MAJ_ADDI),
    'SUB':  (instr_sub,  ('reg', 'reg', 'reg'), MAJ_SUB),
    'LD':   (instr_ld,   ('reg', 'reg', 'imm'), MAJ_LD),
    'ST':   (instr_st,   ('reg', 'reg', 'imm'), MAJ_ST),
    'HALT': (instr_halt, (),                   MAJ_HALT),
}