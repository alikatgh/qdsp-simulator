# tests/test_alu_logic.py
import pytest
from dspsim import FunctionalSimulator
from dspsim.assembler import assemble

def run_program(program_asm: list[str], initial_regs=None):
    """Helper function to assemble, load, and run a program."""
    sim = FunctionalSimulator()
    if initial_regs:
        for r_idx, val in initial_regs.items():
            sim.regs[r_idx] = val
    
    program = assemble(program_asm)
    sim.load_words(sim.pc, program)
    sim.run()
    return sim

def test_and_instruction():
    """Tests the AND instruction."""
    sim = run_program(
        program_asm=[
            "AND r2, r0, r1",
            "HALT"
        ],
        initial_regs={0: 0xF0F0F0F0, 1: 0x00FFFF00}
    )
    assert sim.regs[2] == 0x00F0F000

def test_or_instruction():
    """Tests the OR instruction."""
    sim = run_program(
        program_asm=[
            "OR r2, r0, r1",
            "HALT"
        ],
        initial_regs={0: 0xF0F0F0F0, 1: 0x00FFFF00}
    )
    assert sim.regs[2] == 0xF0FFFFF0

def test_jump_forward():
    """Tests a forward J instruction with a label."""
    sim = run_program(
        program_asm=[
            "ADDI r1, r0, #100", # This executes, setting R1 to 100.
            "J TARGET",
            "ADDI r1, r0, #200", # This is SKIPPED by the jump.
            "HALT",             # This is also SKIPPED.
            "TARGET:",
            "ADDI r2, r0, #50",  # Execution resumes here.
            "HALT"
        ]
    )
    # Corrected Assertions:
    # 1. Check that the instruction BEFORE the jump was executed.
    assert sim.regs[1] == 100
    # 2. Check that the instruction AT THE TARGET was executed.
    assert sim.regs[2] == 50