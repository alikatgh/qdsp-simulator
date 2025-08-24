# Simple text-based assembler.
from . import isa

def parse_operand(op_str: str):
    """Parses an operand string like 'r5' or '#123' into its type and value."""
    op_str = op_str.lower().strip()
    if op_str.startswith('r'):
        return 'reg', int(op_str[1:])
    if op_str.startswith('#'):
        return 'imm', int(op_str[1:])
    # Default to immediate for bare numbers for convenience
    return 'imm', int(op_str)

def assemble(source_lines):
    """Assembles lines of text assembly into a list of instructions."""
    program = []
    for line in source_lines:
        line = line.split('#')[0].strip() # Remove comments
        if not line:
            continue
        
        parts = line.replace(',', ' ').split()
        mnemonic = parts[0].upper()
        operands = [parse_operand(p) for p in parts[1:]]

        if mnemonic not in isa.INSTRUCTION_SET:
            raise ValueError(f"Unknown instruction: {mnemonic}")
        
        program.append({'mnemonic': mnemonic, 'operands': operands})
    return program
