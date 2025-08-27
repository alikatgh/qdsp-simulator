# tests/test_instructions.py
import pytest
from dspsim import FunctionalSimulator as Simulator
from dspsim.encoder import enc_3r, enc_i
from dspsim.isa import MAJ_ADD, MAJ_HALT

def test_add():
    sim = Simulator()
    # Set up initial register state
    sim.regs[0] = 2
    sim.regs[1] = 3

    # Encode the program: ADD r2, r0, r1; HALT
    program = [
        enc_3r(MAJ_ADD, 2, 0, 1),
        enc_i(MAJ_HALT, 0),
    ]
    # Load and run the program
    sim.load_words(sim.pc, program)
    sim.run()

    # Check the result
    assert sim.regs[2] == 5