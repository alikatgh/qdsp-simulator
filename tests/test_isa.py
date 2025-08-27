# tests/test_isa.py
from dspsim.assembler import assemble
from dspsim import FunctionalSimulator as Simulator

def test_addi():
    sim = Simulator()
    # Program: ADDI R1, R0, #123; HALT
    program = assemble([
        "ADDI r1, r0, #123",
        "HALT"  # <-- Add this line
    ])
    sim.load_words(sim.pc, program)
    sim.run()
    assert sim.regs[1] == 123