# core_cycle.py
from typing import List, Dict
from .inst import Inst
from .decoder import decode_word
from .fu import ALU, LSU, VEC
from .trace import TraceSink
import struct

class RegFile:
    def __init__(self):
        self.R = [0]*32
        self.P = [True]*4

    def read(self, idx):
        return self.R[idx]

    def write(self, idx, val):
        self.R[idx] = val & 0xFFFFFFFF

class Memory:
    def __init__(self, size=16*1024*1024):
        self.mem = bytearray(size)
    def load32(self, addr):
        return struct.unpack_from('<I', self.mem, addr)[0]
    def store32(self, addr, val):
        struct.pack_into('<I', self.mem, addr, val & 0xFFFFFFFF)
    def load_blob(self, addr, data: bytes):
        self.mem[addr:addr+len(data)] = data

class Core:
    def __init__(self, mem: Memory, trace: TraceSink=None):
        self.mem = mem
        self.regs = RegFile()
        self.pc = 0x1000
        self.cycle = 0
        self.alus = [ALU("ALU0", latency=1), ALU("ALU1", latency=1)]
        self.lsus = [LSU("LSU0", latency=3)]
        self.vecs = [VEC("VEC0", latency=2, lanes=4)]
        self.rob = []  # simple list of pending completions
        self.trace = trace
        self.halted = False

    def fetch_packet(self):
        # fetch one word (later: multiple words up to packet limit)
        w = self.mem.load32(self.pc)
        inst = decode_word(w, self.pc)
        self.pc += 4
        return [inst]

    def regs_snapshot(self):
        return {f"R{i}": self.regs.read(i) for i in range(8)}  # small snapshot for perf

    def step(self):
        if self.halted:
            return False
        packet = self.fetch_packet()
        # decode done in fetch; now try to issue
        for inst in packet:
            # predicate check
            if inst.pred is not None and not self.regs.P[inst.pred]:
                # treat as NOP
                if self.trace:
                    self.trace.emit_inst(self.cycle, inst, {}, {}, [])
                continue
            # choose FU
            fu = None
            if inst.op in ("ADD","ADDI","SUB"):
                for a in self.alus:
                    if a.can_accept(self.cycle):
                        fu = a; break
            elif inst.op in ("LD32","ST32"):
                for l in self.lsus:
                    if l.can_accept(self.cycle):
                        fu = l; break
            elif inst.op.startswith("V"):
                for v in self.vecs:
                    if v.can_accept(self.cycle):
                        fu = v; break
            elif inst.op == "HALT":
                self.halted = True
                if self.trace:
                    self.trace.emit_inst(self.cycle, inst, {}, {}, [])
                return False
            else:
                # default ALU
                for a in self.alus:
                    if a.can_accept(self.cycle):
                        fu = a; break
            if not fu:
                # stall: can't issue this cycle; bump cycle and try again
                self.cycle += 1
                # tick FUs to finish ready insts
                self._tick_fus()
                return True
            # execute: capture reg states
            regs_before = self.regs_snapshot()
            # materialize execution immediate effect for single-cycle ALU or schedule for multi-cycle
            fu.start(inst, self.cycle)
            # we register completion record in ROB for writeback at end cycle
            self.rob.append((fu, inst, self.cycle + fu.latency))
        # advance time by one cycle and tick FUs
        self._tick_fus()
        self.cycle += 1
        return True

    def _tick_fus(self):
        finished = []
        for fu in (self.alus + self.lsus + self.vecs):
            inst = fu.tick(self.cycle)
            if inst:
                finished.append((fu, inst))
        # commit finished insts
        for fu, inst in finished:
            regs_before = self.regs_snapshot()
            memops = []
            # simple semantics: implement core ops here
            if inst.op == "ADD":
                a = self.regs.read(inst.rs1); b = self.regs.read(inst.rs2)
                self.regs.write(inst.rd, (a + b) & 0xFFFFFFFF)
            elif inst.op == "ADDI":
                a = self.regs.read(inst.rs1)
                self.regs.write(inst.rd, (a + (inst.imm or 0)) & 0xFFFFFFFF)
            elif inst.op == "SUB":
                a = self.regs.read(inst.rs1); b = self.regs.read(inst.rs2)
                self.regs.write(inst.rd, (a - b) & 0xFFFFFFFF)
            elif inst.op == "LD32":
                addr = (self.regs.read(inst.rs1) + (inst.imm or 0)) & 0xFFFFFFFF
                val = self.mem.load32(addr)
                self.regs.write(inst.rd, val)
                memops.append({"type":"LD","addr":hex(addr),"value":hex(val)})
            elif inst.op == "ST32":
                addr = (self.regs.read(inst.rs1) + (inst.imm or 0)) & 0xFFFFFFFF
                val = self.regs.read(inst.rs2)
                self.mem.store32(addr, val)
                memops.append({"type":"ST","addr":hex(addr),"value":hex(val)})
            # vector ops, branch, etc: implement later
            regs_after = self.regs_snapshot()
            if self.trace:
                self.trace.emit_inst(self.cycle, inst, regs_before, regs_after, memops)
