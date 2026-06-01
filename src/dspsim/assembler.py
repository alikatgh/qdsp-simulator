# src/dspsim/assembler.py
from __future__ import annotations

import re
import struct

from .bitutil import u32
from .encoder import _header, enc_3r, enc_cmpi, enc_i, enc_ri
from .isa import (
    MAJ_ADD,
    MAJ_ADDI,
    MAJ_AND,
    MAJ_HALT,
    MAJ_J,
    MAJ_JR,
    MAJ_LD32,
    MAJ_MAC,
    MAJ_MUL,
    MAJ_NOT,
    MAJ_OR,
    MAJ_SHL,
    MAJ_SHR,
    MAJ_ST32,
    MAJ_SUB,
    MAJ_XOR,
)

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


def parse_imm(tok: str, labels: dict[str, int], pc: int) -> int:
    t = tok.strip()
    if t.startswith('#'):
        t = t[1:]
    if t in labels:
        return labels[t]
    try:
        if t.lower().startswith('0x'):
            return int(t, 16)
        return int(t, 0)
    except ValueError as e:
        raise AsmError(f"Bad immediate: '{tok}'") from e


def parse_mem(tok: str, labels: dict[str, int], pc: int):
    # forms: [R1+16], [R1-8], [R2]
    t = tok.strip()
    if not (t.startswith('[') and t.endswith(']')):
        raise AsmError(f"Bad mem syntax: '{tok}'")
    inner = t[1:-1].strip()
    if '+' in inner:
        base, off = inner.split('+', 1)
        return parse_reg(base.strip()), parse_imm(off.strip(), labels, pc)
    if '-' in inner:
        base, off = inner.split('-', 1)
        return parse_reg(base.strip()), -parse_imm(off.strip(), labels, pc)
    return parse_reg(inner), 0


def first_pass(lines: list[str]) -> dict[str, int]:
    labels: dict[str, int] = {}
    pc = 0
    for ln in lines:
        s = ln.split(';', 1)[0].strip()
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


def tokenize_args(s: str) -> list[str]:
    # split by commas but allow spaces
    return [p.strip() for p in s.split(',') if p.strip()]


def assemble(lines: list[str]) -> list[int]:
    """Assembles lines of text into a list of 32-bit instruction words."""
    labels = first_pass(lines)
    pc = 0
    out_words: list[int] = []
    for ln in lines:
        s = ln.split(';', 1)[0].strip()
        if not s or s.endswith(':'):
            continue

        pred = None
        if '@P' in s:
            parts = s.split('@', 1)
            s = parts[0].strip()
            ptxt = parts[1].strip()
            if not ptxt.upper().startswith('P'):
                raise AsmError(f"Bad predicate: '{ptxt}'")
            pred = int(ptxt[1:])
            if not (0 <= pred <= 3):
                raise AsmError(f"Predicate out of range: {pred}")

        if ' ' in s:
            op, args_text = s.split(None, 1)
        else:
            op, args_text = s, ''
        op = op.strip().upper()
        args = tokenize_args(args_text) if args_text else []
        word = None

        _3r_ops = {
            'ADD': MAJ_ADD, 'SUB': MAJ_SUB, 'AND': MAJ_AND, 'OR': MAJ_OR,
            'XOR': MAJ_XOR, 'SHL': MAJ_SHL, 'SHR': MAJ_SHR,
            'MUL': MAJ_MUL, 'MAC': MAJ_MAC,
        }
        if op in _3r_ops:
            if len(args) != 3:
                raise AsmError(f"{op} needs rd,rs1,rs2")
            rd, rs1, rs2 = parse_reg(args[0]), parse_reg(args[1]), parse_reg(args[2])
            word = enc_3r(_3r_ops[op], rd, rs1, rs2, pred, True)
        elif op == 'ADDI':
            if len(args) != 3:
                raise AsmError("ADDI needs rd,rs1,imm")
            rd, rs1 = parse_reg(args[0]), parse_reg(args[1])
            imm = parse_imm(args[2], labels, pc)
            word = enc_ri(MAJ_ADDI, rd, rs1, imm & 0x3FFF, pred, True)
        elif op == 'NOT':
            if len(args) != 2:
                raise AsmError("NOT needs rd,rs1")
            rd, rs1 = parse_reg(args[0]), parse_reg(args[1])
            word = enc_3r(MAJ_NOT, rd, rs1, 0, pred, True)
        elif op == 'JR':
            if len(args) != 1:
                raise AsmError("JR needs rs1")
            rs1 = parse_reg(args[0])
            w = _header(MAJ_JR, pred, True)
            w |= (rs1 & 0x1F) << 14
            word = u32(w)
        elif op in ('LD', 'LD32'):
            if len(args) != 2:
                raise AsmError("LD needs rd, [mem]")
            rd = parse_reg(args[0])
            base, off = parse_mem(args[1], labels, pc)
            word = enc_ri(MAJ_LD32, rd, base, off & 0x3FFF, pred, True)
        elif op in ('ST', 'ST32'):
            if len(args) != 2:
                raise AsmError("ST needs [mem], rs")
            base, off = parse_mem(args[0], labels, pc)
            rs = parse_reg(args[1])
            # Source register goes in rd field [23:19]
            word = enc_ri(MAJ_ST32, rs, base, off & 0x3FFF, pred, True)
        elif op == 'J':
            if len(args) != 1:
                raise AsmError("J needs an immediate or a label")
            # Jumps are PC-relative. The immediate is a signed word offset.
            target_addr = parse_imm(args[0], labels, pc)
            # Offset is from the instruction *after* the jump
            offset = target_addr - (pc + 4)
            if offset % 4 != 0:
                raise AsmError(f"Jump target {args[0]} is not word-aligned")
            imm = (offset >> 2) & 0x3FFF  # Scale offset and fit into 14 bits
            word = enc_i(MAJ_J, imm, pred, True)
        elif op.startswith('CMPI.'):
            _, spec = op.split('.', 1)
            mapping = {'EQ': 0, 'NE': 1, 'LT': 2, 'GE': 3, 'LE': 4, 'GT': 5}
            if spec not in mapping:
                raise AsmError(f"Unknown CMPI spec {spec}")
            code = mapping[spec]
            if len(args) != 3:
                raise AsmError("CMPI.<X> needs Pdst, Rs1, imm")
            pdst = int(args[0].upper().replace('P', ''))
            rs1 = parse_reg(args[1])
            imm = parse_imm(args[2], labels, pc)
            word = enc_cmpi(pdst, rs1, imm & 0x3FF, code, pred, True)
        elif op == 'HALT':
            word = enc_i(MAJ_HALT, 0, pred, True)
        else:
            raise AsmError(f"Unknown op '{op}'")

        out_words.append(word)
        pc += 4

    return out_words


def assemble_file(in_path: str, out_path: str):
    with open(in_path) as f:
        lines = f.read().splitlines()
    words = assemble(lines)
    with open(out_path, 'wb') as g:
        for w in words:
            g.write(struct.pack('<I', w & 0xFFFFFFFF))
