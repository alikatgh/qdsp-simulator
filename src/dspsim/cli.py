# Command-Line Interface for the simulator.
import argparse
from . import core
from . import assembler

def main():
    parser = argparse.ArgumentParser(description="Educational DSP Simulator")
    parser.add_argument("filename", help="Assembly file to run")
    parser.add_argument("--trace", action="store_true", help="Enable instruction tracing")
    args = parser.parse_args()

    try:
        with open(args.filename, 'r') as f:
            source = f.readlines()
        program = assembler.assemble(source)
    except Exception as e:
        print(f"Error assembling file: {e}")
        return

    sim = core.Simulator()
    sim.load_program(program)
    
    print("--- Simulator starting ---")
    sim.run()
    print("--- Simulation finished ---")
    print(f"Total cycles: {sim.cycle_count}")
    print("Final Register State:")
    sim.dump_regs()
