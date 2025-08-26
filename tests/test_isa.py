from dspsim.assembler import assemble
from dspsim import FunctionalSimulator as Simulator

def test_addi():
    sim = Simulator()
    # Program: ADDI R1, R0, #123
    program = assemble(["ADDI r1, r0, #123"])
    sim.load_program(program)
    sim.run()
    assert sim.regs[1] == 123
