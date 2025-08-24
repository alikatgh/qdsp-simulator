# DSPsim — Educational, Clean-Room Qualcomm-Style DSP Simulator


**DSPsim** is a from-scratch, learn-by-instrumentation simulator for a packeted, predicated DSP core. It is **not** Qualcomm Hexagon, and includes only an original instructional ISA that is Hexagon-inspired at the concept level.


## Highlights
- 32 GPRs (R0..R31), 4 predicate bits (P0..P3), PC, cycle counter
- **Packets**: fetch multiple 32-bit words per packet (end via EOP bit)
- **Predication**: `@P#` guards most instructions
- **MMIO**: UART + Timer examples
- **Assembler/Disassembler** for the educational ISA
- **ELF loader** (optional, via `pyelftools`)
- **Tracing**: CSV/JSON instruction/memory traces
- Basic **timing model** w/ functional-unit latencies


## Install
```bash
pip install -e .
```

## Run Examples
```bash
# assemble and run
dspsim asm examples/hello_packet.asm -o hello.bin
dspsim run --load hello.bin --base 0x1000 --entry 0x1000 --trace


# pretty trace (requires rich)
dspsim run --load hello.bin --trace --pretty


# load ELF (optional)
dspsim run --elf build/program.elf --trace
```

## Educational ISA (Summary)

- Word = 32b, little-endian. All instructions are 32b.
- Format (common header):
    - [31:28] MAJ (major opcode)
    - [27] P? (predicated flag)
    - [26:25] Pidx for predicate
    - [24] EOP (end-of-packet)
    - Remaining bits vary per MAJ.

- Core ops: ADD, ADDI, SUB, AND, OR, XOR, SHL, SHR, MUL, MAC, NOT
- Mem ops: LD, ST (base+imm14), alignment required to 4B for LD/ST32
- Control: J (PC += imm<<2), JR (PC = Rs1), CMPI.{EQ,NE,LT,GE,LE,GT}
- Predication: @P# applies to most ops (skips side-effects if false)
- HALT: stop core

The goal is transparency: you can instrument every side-effect.

## License

```text
MIT License


Copyright (c) 2025 Your Name


Permission is hereby granted, free of charge, to any person obtaining a copy
... (standard MIT text) ...
```