# isa.py
# Instruction Set Architecture definitions.

# === Functional semantics (executed by simulator) ===

from .isa import (
    MAJ_ADD, MAJ_ADDI, MAJ_SUB, MAJ_AND, MAJ_OR, MAJ_XOR,
    MAJ_SHL, MAJ_SHR, MAJ_MUL, MAJ_MAC, MAJ_NOT,
    MAJ_LD32, MAJ_ST32,
    MAJ_J, MAJ_JR, MAJ_HALT
)


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
    sim.regs[rd] = sim.mem.read_word(addr)

def instr_st(sim, rs2, rs1, imm):
    """Mem[R[rs1] + imm] = R[rs2]"""
    addr = sim.regs[rs1] + imm
    sim.mem.write_word(addr, sim.regs[rs2])

def instr_halt(sim):
    """Stop simulation"""
    sim.running = False


# === Opcode constants (encoding layer) ===

# ALU
MAJ_ADD  = 0x0
MAJ_ADDI = 0x1
MAJ_SUB  = 0x2
MAJ_AND  = 0x3
MAJ_OR   = 0x4
MAJ_XOR  = 0x5
MAJ_SHL  = 0x6
MAJ_SHR  = 0x7
MAJ_MUL  = 0x8
MAJ_MAC  = 0x9

# Memory
MAJ_LD   = 0xA
MAJ_ST   = 0xB

# Control flow
MAJ_J    = 0xC
MAJ_JR   = 0xD
MAJ_CMPI = 0xE
MAJ_HALT = 0xF


# === Lookup table: mnemonic → (executor, arg types, opcode) ===

INSTRUCTION_SET = {
    'ADD':  (instr_add,  ('reg', 'reg', 'reg'), MAJ_ADD),
    'ADDI': (instr_addi, ('reg', 'reg', 'imm'), MAJ_ADDI),
    'SUB':  (instr_sub,  ('reg', 'reg', 'reg'), MAJ_SUB),
    'LD':   (instr_ld,   ('reg', 'reg', 'imm'), MAJ_LD),
    'ST':   (instr_st,   ('reg', 'reg', 'imm'), MAJ_ST),
    'HALT': (instr_halt, (),                   MAJ_HALT),
}
