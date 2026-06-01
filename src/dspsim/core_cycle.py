# src/dspsim/core_cycle.py
"""Cycle-accurate DSP simulator with pipeline, hazard detection, and perf counters."""

from __future__ import annotations

from .bitutil import s32, u32
from .bus import Bus
from .decoder import decode_word
from .fu import ALU, LSU, VEC
from .inst import Inst
from .trace import TraceSink


class RegFile:
    def __init__(self):
        self.R = [0] * 32
        self.P = [True] * 4  # predicate registers

    def read(self, idx: int) -> int:
        return self.R[idx]

    def write(self, idx: int, val: int) -> None:
        self.R[idx] = val & 0xFFFFFFFF

    def read_pred(self, idx: int) -> bool:
        return self.P[idx]

    def write_pred(self, idx: int, val: bool) -> None:
        self.P[idx] = val


class PerfCounters:
    """Hardware performance counters for cycle-accurate analysis."""

    def __init__(self):
        self.cycles = 0
        self.instructions = 0
        self.stall_cycles = 0
        self.packets_fetched = 0
        self.alu_ops = 0
        self.mem_ops = 0
        self.branch_ops = 0
        self.predicated_nops = 0

    @property
    def cpi(self) -> float:
        return self.cycles / self.instructions if self.instructions else 0.0

    @property
    def ipc(self) -> float:
        return self.instructions / self.cycles if self.cycles else 0.0

    def summary(self) -> str:
        return (
            f"Cycles: {self.cycles}  |  Instructions: {self.instructions}  |  "
            f"CPI: {self.cpi:.2f}  |  IPC: {self.ipc:.2f}\n"
            f"Stalls: {self.stall_cycles}  |  Packets: {self.packets_fetched}\n"
            f"ALU: {self.alu_ops}  Mem: {self.mem_ops}  Branch: {self.branch_ops}  "
            f"Pred-NOP: {self.predicated_nops}"
        )


class Core:
    """Cycle-accurate core with multi-issue packet fetch, functional units,
    data-hazard stalling, and performance counters."""

    PACKET_WIDTH = 4  # max instructions per packet

    def __init__(self, bus: Bus, trace: TraceSink | None = None):
        self.bus = bus
        self.regs = RegFile()
        self.pc: int = 0x1000
        self.cycle: int = 0
        self.halted: bool = False
        self.trace = trace
        self.perf = PerfCounters()

        # Functional units
        self.alus = [ALU("ALU0", latency=1), ALU("ALU1", latency=1)]
        self.lsus = [LSU("LSU0", latency=3)]
        self.vecs = [VEC("VEC0", latency=2, lanes=4)]

        # In-flight scoreboard: register idx -> ready-at-cycle
        self.scoreboard: dict[int, int] = {}

    # ------------------------------------------------------------------
    # Packet fetch
    # ------------------------------------------------------------------

    def fetch_packet(self) -> list[Inst]:
        """Fetch up to PACKET_WIDTH words, stopping at EOP or decode failure."""
        packet: list[Inst] = []
        for _ in range(self.PACKET_WIDTH):
            w = self.bus.read32(self.pc)
            inst = decode_word(w, self.pc)
            self.pc += 4
            if inst is None:
                break
            packet.append(inst)
            if inst.endpkt:
                break
        self.perf.packets_fetched += 1
        return packet

    # ------------------------------------------------------------------
    # Hazard detection
    # ------------------------------------------------------------------

    def _src_regs(self, inst: Inst) -> list[int]:
        """Return list of source register indices for an instruction."""
        srcs = []
        if inst.rs1 is not None:
            srcs.append(inst.rs1)
        if inst.rs2 is not None:
            srcs.append(inst.rs2)
        # MAC also reads rd (accumulate)
        if inst.op == "MAC" and inst.rd is not None:
            srcs.append(inst.rd)
        # ST reads the source data from rd field
        if inst.op == "ST" and inst.rd is not None:
            srcs.append(inst.rd)
        return srcs

    def _has_hazard(self, inst: Inst) -> bool:
        """True if any source register is still in-flight (not yet written back)."""
        for r in self._src_regs(inst):
            if r in self.scoreboard and self.scoreboard[r] > self.cycle:
                return True
        return False

    def _mark_dest(self, inst: Inst, fu_latency: int) -> None:
        """Mark destination register as busy until writeback completes."""
        # ST doesn't write to a register (rd holds the source data register)
        if inst.op == "ST":
            return
        if inst.rd is not None:
            self.scoreboard[inst.rd] = self.cycle + fu_latency

    def _retire_scoreboard(self) -> None:
        """Remove entries that have completed."""
        done = [r for r, ready in self.scoreboard.items() if ready <= self.cycle]
        for r in done:
            del self.scoreboard[r]

    # ------------------------------------------------------------------
    # Snapshot for tracing
    # ------------------------------------------------------------------

    def regs_snapshot(self) -> dict:
        return {f"R{i}": self.regs.read(i) for i in range(8)}

    # ------------------------------------------------------------------
    # Execute semantics
    # ------------------------------------------------------------------

    def _execute(self, inst: Inst) -> list:
        """Execute an instruction's side effects. Returns list of memops."""
        op = inst.op
        memops = []

        # --- ALU 3-register ---
        if op == "ADD":
            a, b = self.regs.read(inst.rs1), self.regs.read(inst.rs2)
            self.regs.write(inst.rd, u32(a + b))
        elif op == "SUB":
            a, b = self.regs.read(inst.rs1), self.regs.read(inst.rs2)
            self.regs.write(inst.rd, u32(a - b))
        elif op == "AND":
            a, b = self.regs.read(inst.rs1), self.regs.read(inst.rs2)
            self.regs.write(inst.rd, u32(a & b))
        elif op == "OR":
            a, b = self.regs.read(inst.rs1), self.regs.read(inst.rs2)
            self.regs.write(inst.rd, u32(a | b))
        elif op == "XOR":
            a, b = self.regs.read(inst.rs1), self.regs.read(inst.rs2)
            self.regs.write(inst.rd, u32(a ^ b))
        elif op == "SHL":
            a, b = self.regs.read(inst.rs1), self.regs.read(inst.rs2)
            self.regs.write(inst.rd, u32(a << (b & 31)))
        elif op == "SHR":
            a, b = self.regs.read(inst.rs1), self.regs.read(inst.rs2)
            self.regs.write(inst.rd, u32(a >> (b & 31)))
        elif op == "MUL":
            a, b = self.regs.read(inst.rs1), self.regs.read(inst.rs2)
            self.regs.write(inst.rd, u32(a * b))
        elif op == "MAC":
            a, b = self.regs.read(inst.rs1), self.regs.read(inst.rs2)
            acc = self.regs.read(inst.rd)
            self.regs.write(inst.rd, u32(acc + a * b))
        elif op == "NOT":
            a = self.regs.read(inst.rs1)
            self.regs.write(inst.rd, u32(~a))

        # --- ALU immediate ---
        elif op == "ADDI":
            a = self.regs.read(inst.rs1)
            self.regs.write(inst.rd, u32(a + (inst.imm or 0)))

        # --- Memory ---
        elif op == "LD":
            addr = u32(self.regs.read(inst.rs1) + (inst.imm or 0))
            val = self.bus.read32(addr)
            self.regs.write(inst.rd, val)
            memops.append({"type": "LD", "addr": hex(addr), "value": hex(val)})
        elif op == "ST":
            addr = u32(self.regs.read(inst.rs1) + (inst.imm or 0))
            # Source register is encoded in rd field
            val = self.regs.read(inst.rd)
            self.bus.write32(addr, val)
            memops.append({"type": "ST", "addr": hex(addr), "value": hex(val)})

        # --- Control flow ---
        elif op == "J":
            offset = s32((inst.imm or 0) << 2)
            self.pc = u32(self.pc + offset)
            self.perf.branch_ops += 1
        elif op == "JR":
            self.pc = u32(self.regs.read(inst.rs1))
            self.perf.branch_ops += 1

        # --- Compare-immediate (writes predicate) ---
        elif op.startswith("CMPI."):
            cmp_name = op.split(".")[1]
            a = s32(self.regs.read(inst.rs1))
            b = inst.imm or 0
            pdst = inst.rd if inst.rd is not None else 0
            cmp_map = {"EQ": a == b, "NE": a != b, "LT": a < b,
                        "GE": a >= b, "LE": a <= b, "GT": a > b}
            result = cmp_map.get(cmp_name, False)
            if 0 <= pdst < 4:
                self.regs.write_pred(pdst, result)

        elif op == "HALT":
            self.halted = True

        return memops

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------

    def step(self) -> bool:
        """Execute one cycle. Returns False when halted.

        Design: functionally correct, timing approximate.  All instructions
        execute their side-effects at issue time so values are immediately
        visible.  The scoreboard + FU availability model tracks *when*
        results would be ready in a real pipeline and inserts stall cycles
        accordingly.
        """
        if self.halted:
            return False

        self._retire_scoreboard()
        packet = self.fetch_packet()

        for inst in packet:
            # Predicate check
            if inst.pred is not None and not self.regs.read_pred(inst.pred):
                self.perf.predicated_nops += 1
                if self.trace:
                    self.trace.emit_inst(self.cycle, inst, {}, {}, [])
                continue

            # Data hazard check — stall until all sources are ready
            while self._has_hazard(inst):
                self.perf.stall_cycles += 1
                self.cycle += 1
                self._tick_fus()
                self._retire_scoreboard()

            # Structural hazard — stall until an FU is available
            fu = self._pick_fu(inst)
            while not fu:
                self.perf.stall_cycles += 1
                self.cycle += 1
                self._tick_fus()
                self._retire_scoreboard()
                fu = self._pick_fu(inst)

            # Issue: reserve FU, mark destination in scoreboard
            fu.start(inst, self.cycle)
            self._mark_dest(inst, fu.latency)

            # Execute side-effects immediately (functional correctness)
            regs_before = self.regs_snapshot()
            memops = self._execute(inst)
            regs_after = self.regs_snapshot()
            if self.trace:
                self.trace.emit_inst(self.cycle, inst, regs_before, regs_after, memops)

            # Accounting
            self.perf.instructions += 1
            if inst.op in ("LD", "ST"):
                self.perf.mem_ops += 1
            elif inst.op not in ("J", "JR", "HALT") and not inst.op.startswith("CMPI"):
                self.perf.alu_ops += 1

            if self.halted:
                break

        self._tick_fus()
        self.cycle += 1
        self.perf.cycles = self.cycle
        return not self.halted

    def _pick_fu(self, inst: Inst) -> object | None:
        """Select an available functional unit for the instruction."""
        alu_ops = {"ADD", "ADDI", "SUB", "AND", "OR", "XOR", "SHL", "SHR",
                   "MUL", "MAC", "NOT", "HALT", "J", "JR"}
        mem_ops = {"LD", "ST"}

        if inst.op in alu_ops or inst.op.startswith("CMPI"):
            for a in self.alus:
                if a.can_accept(self.cycle):
                    return a
        elif inst.op in mem_ops:
            for lsu in self.lsus:
                if lsu.can_accept(self.cycle):
                    return lsu
        elif inst.op.startswith("V"):
            for v in self.vecs:
                if v.can_accept(self.cycle):
                    return v
        else:
            # fallback to ALU
            for a in self.alus:
                if a.can_accept(self.cycle):
                    return a
        return None

    def _tick_fus(self) -> None:
        """Advance all functional units so they release for new instructions."""
        for fu in self.alus + self.lsus + self.vecs:
            fu.tick(self.cycle)


# ---------------------------------------------------------------------------
# Convenience: legacy Memory wrapper (for backward compatibility with CLI)
# ---------------------------------------------------------------------------
class Memory:
    """Thin wrapper so old CLI code that does `Memory()` + `load_blob()` still works."""

    def __init__(self, size: int = 16 * 1024 * 1024):
        self._bus = Bus(size=size)

    @property
    def bus(self) -> Bus:
        return self._bus

    def load32(self, addr: int) -> int:
        return self._bus.read32(addr)

    def store32(self, addr: int, val: int) -> None:
        self._bus.write32(addr, val)

    def load_blob(self, addr: int, data: bytes) -> None:
        self._bus.load_blob(addr, data)
