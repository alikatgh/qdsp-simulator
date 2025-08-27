# DSPsim - Educational DSP Simulator

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

**DSPsim** is a clean-room, educational simulator for a packeted, predicated DSP core. Inspired by concepts from Qualcomm's Hexagon DSP (but **not** an actual Hexagon implementation), it features an original instructional ISA designed for transparency and ease of understanding. The goal is to provide a platform where you can instrument every side-effect, making it ideal for learning DSP architecture, assembly, and simulation.

Whether you're a student exploring DSP concepts, a developer prototyping algorithms, or an educator teaching ISA design, DSPsim offers a flexible, extensible toolset with functional and cycle-accurate models.

## Highlights
- **Register File**: 32 general-purpose registers (R0–R31), 4 predicate bits (P0–P3), PC, and cycle counter.
- **Packets**: Fetch multiple 32-bit instructions per packet, terminated by the End-of-Packet (EOP) bit.
- **Predication**: Guard instructions with `@P#` to skip side-effects if the predicate is false.
- **MMIO Support**: Examples for UART and Timer peripherals.
- **Assembler & Disassembler**: Built-in tools for the educational ISA.
- **ELF Loader**: Optional support via `pyelftools` for loading ELF binaries.
- **Tracing**: Generate CSV/JSON traces for instructions and memory operations.
- **Simulation Modes**: Fast functional model and basic timing model with functional-unit latencies.

## Installation

DSPsim is a Python package. Install it in editable mode for development:

```bash
pip install -e .
```

### Dependencies
- Required: `click>=8`
- Optional:
  - ELF support: `pyelftools>=0.31`
  - Pretty tracing: `rich>=13`

Supports Python 3.9+.

## Usage

DSPsim provides a CLI for assembling, disassembling, and running programs. Here are some examples:

### Assemble and Run a Program
```bash
# Assemble an ASM file to binary
dspsim asm examples/basic_alu.asm -o program.bin

# Run the binary with tracing
dspsim run --bin program.bin --base 0x1000 --entry 0x1000 --trace
```

### Run Directly from Assembly
```bash
dspsim run --asm examples/memory_copy.asm --base 0x1000 --entry 0x1000 --trace --pretty
```

### Load and Run an ELF File (Optional)
```bash
dspsim run --elf build/program.elf --trace
```

### Engine Options
- `--engine fast` (default): Quick functional simulation.
- `--engine cycle`: Timing-accurate model showing stalls and latencies.

For full CLI options, run `dspsim --help` or `dspsim run --help`.

## ISA Summary
- **Word Size**: 32-bit, little-endian. All instructions are 32 bits.
- **Common Header**:
  - Bits [31:28]: Major opcode (MAJ).
  - Bit [27]: Predication flag.
  - Bits [26:25]: Predicate index (if flagged).
  - Bit [24]: End-of-Packet (EOP).
- **ALU Operations**: ADD, ADDI, SUB, AND, OR, XOR, SHL, SHR, MUL, MAC, NOT.
- **Memory Operations**: LD/ST (32-bit, base + 14-bit signed imm), 4-byte alignment required.
- **Control Flow**: J (PC-relative, imm << 2), JR (jump to register), CMPI.{EQ,NE,LT,GE,LE,GT}.
- **Predication**: `@P#` skips instructions if predicate is false.
- **HALT**: Stops the simulation.

See `src/dspsim/isa.py` for full semantics and the assembler in `src/dspsim/assembler.py` for syntax details.

## Contributing
Contributions are welcome! To get started:
1. Fork the repository.
2. Create a branch: `git checkout -b feature/your-feature`.
3. Commit your changes: `git commit -am 'Add your feature'`.
4. Push to the branch: `git push origin feature/your-feature`.
5. Open a pull request.

Please include tests (run with `pytest`) and follow PEP 8 style guidelines.

For bugs or feature requests, open an issue.

## License
MIT License

Copyright (c) 2025 [Your Name]

See the [LICENSE](LICENSE) file for details.
