# tests/test_functional_core.py
import pytest
from dspsim import FunctionalSimulator
from dspsim.encoder import enc_ri, enc_3r, enc_i
from dspsim.isa import MAJ_ADDI, MAJ_ADD, MAJ_HALT

def u32(v): return v & 0xFFFFFFFF

def test_addi_basic():
    sim = FunctionalSimulator(mem_size=8192) # Changed from 4096
    # Build program: ADDI r1, r0, #123 ; HALT
    w1 = enc_ri(MAJ_ADDI, 1, 0, 123, None, True)
    w2 = enc_i(MAJ_HALT, 0, None, True)
    sim.load_words(0x1000, [w1, w2])
    sim.run(entry=0x1000, max_cycles=100)
    assert sim.regs[1] == 123

def test_add_reg():
    sim = FunctionalSimulator(mem_size=8192) # Changed from 4096
    # r0=2, r1=3 built by writing registers directly
    sim.regs[0] = 2
    sim.regs[1] = 3
    # ADD r2, r0, r1 ; HALT
    w1 = enc_3r(MAJ_ADD, 2, 0, 1, None, True)
    w2 = enc_i(MAJ_HALT, 0, None, True)
    sim.load_words(0x1000, [w1, w2])
    sim.run(entry=0x1000, max_cycles=100)
    assert sim.regs[2] == 5