# src/dspsim/assembler.py
from __future__ import annotations
import re, struct
from typing import Dict, List
from .encoder import (
    enc_3r, enc_ri, enc_i, enc_cmpi
)
from .isa import * # Import all MAJ_ opcodes

_reg_re = re.compile(r'^R(\d+)$', re.IGNORECASE)
_label_re = re.compile(r'^[A-Za-z_]\w*$')

class AsmError(Exception):
    pass

def parse_reg(tok: str) -> int:
    m = _reg_re.match(tok.strip())
    if not m:
        raise AsmError(f"Bad register token: '{tok}'")
    val = int(m.group(1))
    if not (0 <= val < 32):
        raise AsmError(f"Register out of range: '{tok}'")
    return val

# In src/dspsim/assembler.py

def parse_imm(tok: str, labels: Dict[str,int], pc: int) -> int:
    t = tok.strip()
    if t.startswith('#'): # <-- Add this block
        t = t[1:]
    if t in labels:
        return labels[t]
    try:
        if t.lower().startswith('0x'):
            return int(t, 16)
        return int(t, 0)
    except Exception:
        raise AsmError(f"Bad immediate: '{tok}'")

def parse_mem(tok: str, labels: Dict[str,int], pc: int):
    # forms: [R1+16], [R1-8], [R2]
    t = tok.strip()
    if not (t.startswith('[') and t.endswith(']')):
        raise AsmError(f"Bad mem syntax: '{tok}'")
    inner = t[1:-1].strip()
    if '+' in inner:
        base, off = inner.split('+',1)
        return parse_reg(base.strip()), parse_imm(off.strip(), labels, pc)
    if '-' in inner:
        base, off = inner.split('-',1)
        return parse_reg(base.strip()), -parse_imm(off.strip(), labels, pc)
    return parse_reg(inner), 0

def first_pass(lines: List[str]) -> Dict[str,int]:
    labels = {}
    pc = 0
    for ln in lines:
        s = ln.split(';',1)[0].strip()
        if not s:
            continue
        if s.endswith(':'):
            name = s[:-1].strip()
            if not _label_re.match(name):
                raise AsmError(f"Bad label name: '{name}'")
            if name in labels:
                raise AsmError(f"Label multiply defined: '{name}'")
            labels[name] = pc
        else:
            pc += 4
    return labels

def tokenize_args(s: str) -> List[str]:
    # split by commas but allow spaces
    return [p.strip() for p in s.split(',') if p.strip()]

def assemble(lines: List[str]) -> List[int]:
    """Assembles lines of text into a list of 32-bit instruction words."""
    src = "\n".join(lines)
    labels = first_pass(lines)
    pc = 0
    out_words: List[int] = []
    for ln in lines:
        s = ln.split(';',1)[0].strip()
        if not s or s.endswith(':'):
            continue

        pred = None
        if '@P' in s:
            parts = s.split('@',1)
            s = parts[0].strip()
            ptxt = parts[1].strip()
            if not ptxt.upper().startswith('P'):
                raise AsmError(f"Bad predicate: '{ptxt}'")
            pred = int(ptxt[1:])
            if not (0 <= pred <= 3):
                raise AsmError(f"Predicate out of range: {pred}")

        if ' ' in s:
            op, args_text = s.split(None,1)
        else:
            op, args_text = s, ''
        op = op.strip().upper()
        args = tokenize_args(args_text) if args_text else []
        word = None

        if op in ('ADD', 'SUB'):
            if len(args) != 3: raise AsmError(f"{op} needs rd,rs1,rs2")
            rd, rs1, rs2 = parse_reg(args[0]), parse_reg(args[1]), parse_reg(args[2])
            maj = MAJ_ADD if op == 'ADD' else MAJ_SUB
            word = enc_3r(maj, rd, rs1, rs2, pred, True)
        elif op == 'ADDI':
            if len(args) != 3: raise AsmError("ADDI needs rd,rs1,imm")
            rd, rs1 = parse_reg(args[0]), parse_reg(args[1])
            imm = parse_imm(args[2], labels, pc)
            word = enc_ri(MAJ_ADDI, rd, rs1, imm & 0x3FFF, pred, True)
        elif op == 'LD':
            if len(args) != 2: raise AsmError("LD needs rd, [mem]")
            rd = parse_reg(args[0])
            base, off = parse_mem(args[1], labels, pc)
            word = enc_ri(MAJ_LD32, rd, base, off & 0x3FFF, pred, True)
        elif op == 'ST':
            if len(args) != 2: raise AsmError("ST needs [mem], rs")
            base, off = parse_mem(args[0], labels, pc)
            rs = parse_reg(args[1])
            w = enc_ri(MAJ_ST32, 0, base, off & 0x3FFF, pred, True)
            w |= (rs & 0x1F) << 9
            word = w
        elif op == 'J':
            if len(args) != 1: raise AsmError("J needs imm_or_label")
            imm = parse_imm(args[0], labels, pc)
            word = enc_i(MAJ_J, imm & 0x3FFF, pred, True)
        elif op.startswith('CMPI.'):
            _, spec = op.split('.',1)
            mapping = {'EQ':0, 'NE':1, 'LT':2, 'GE':3, 'LE':4, 'GT':5}
            if spec not in mapping: raise AsmError(f"Unknown CMPI spec {spec}")
            code = mapping[spec]
            if len(args) != 3: raise AsmError("CMPI.<X> needs Pdst, Rs1, imm")
            pdst = int(args[0].upper().replace('P',''))
            rs1 = parse_reg(args[1])
            imm = parse_imm(args[2], labels, pc)
            word = enc_cmpi(pdst, rs1, imm & 0x3FFF, code, pred, True)
        elif op == 'HALT':
            word = enc_i(MAJ_HALT, 0, pred, True)
        else:
            raise AsmError(f"Unknown op '{op}'")
        
        out_words.append(word)
        pc += 4
        
    return out_words

def assemble_file(in_path: str, out_path: str):
    with open(in_path,'r') as f:
        lines = f.read().splitlines()
    words = assemble(lines)
    with open(out_path,'wb') as g:
        for w in words:
            g.write(struct.pack('<I', w & 0xFFFFFFFF))