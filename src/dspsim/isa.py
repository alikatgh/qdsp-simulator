# src/dspsim/isa.py
# Instruction Set Architecture definitions.

from .bitutil import s32, u32

# === Opcode constants (The Single Source of Truth) ===

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

# Memory
MAJ_LD    = 0xB
MAJ_ST    = 0xC
MAJ_LD32 = MAJ_LD # Alias for assembler
MAJ_ST32 = MAJ_ST # Alias for assembler

# Control flow
MAJ_J     = 0xD
MAJ_JR    = 0xE
MAJ_CMPI  = 0xF # Shares opcode with HALT for this example
MAJ_HALT  = 0xF


# === Functional semantics (executed by simulator) ===

def instr_add(sim, rd, rs1, rs2):
    """R[rd] = R[rs1] + R[rs2]"""
    sim.regs[rd] = u32(sim.regs[rs1] + sim.regs[rs2])

def instr_addi(sim, rd, rs1, imm):
    """R[rd] = R[rs1] + imm"""
    sim.regs[rd] = u32(sim.regs[rs1] + imm)

def instr_sub(sim, rd, rs1, rs2):
    """R[rd] = R[rs1] - R[rs2]"""
    sim.regs[rd] = u32(sim.regs[rs1] - sim.regs[rs2])

def instr_and(sim, rd, rs1, rs2):
    """R[rd] = R[rs1] & R[rs2]"""
    sim.regs[rd] = u32(sim.regs[rs1] & sim.regs[rs2])

def instr_or(sim, rd, rs1, rs2):
    """R[rd] = R[rs1] | R[rs2]"""
    sim.regs[rd] = u32(sim.regs[rs1] | sim.regs[rs2])

def instr_ld(sim, rd, rs1, imm):
    """R[rd] = Mem[R[rs1] + imm]"""
    addr = u32(sim.regs[rs1] + imm)
    sim.regs[rd] = sim.bus.read32(addr)

def instr_st(sim, rs2, rs1, imm):
    """Mem[R[rs1] + imm] = R[rs2]"""
    addr = u32(sim.regs[rs1] + imm)
    sim.bus.write32(addr, sim.regs[rs2])

def instr_j(sim, imm):
    """PC += signed_offset"""
    # PC is already advanced to next instruction, so we add the offset.
    offset = s32(imm << 2)
    sim.pc += offset

def instr_halt(sim):
    """Stop simulation"""
    sim.running = False


# === Lookup table: mnemonic -> (executor, arg types, opcode) ===

INSTRUCTION_SET = {
    'ADD':  (instr_add,  ('reg', 'reg', 'reg'), MAJ_ADD),
    'ADDI': (instr_addi, ('reg', 'reg', 'imm'), MAJ_ADDI),
    'SUB':  (instr_sub,  ('reg', 'reg', 'reg'), MAJ_SUB),
    'AND':  (instr_and,  ('reg', 'reg', 'reg'), MAJ_AND),
    'OR':   (instr_or,   ('reg', 'reg', 'reg'), MAJ_OR),
    'LD':   (instr_ld,   ('reg', 'reg', 'imm'), MAJ_LD),
    'ST':   (instr_st,   ('reg', 'reg', 'imm'), MAJ_ST),
    'J':    (instr_j,    ('imm',),              MAJ_J),
    'HALT': (instr_halt, (),                   MAJ_HALT),
}