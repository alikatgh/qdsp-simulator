import pytest
from dspsim.simulator import Simulator

def test_add():
    sim = Simulator()
    sim.regs.write(0, 2)
    sim.regs.write(1, 3)
    sim.program = [["ADD", "2", "0", "1"]]
    sim.run()
    assert sim.regs.read(2) == 5
