# tests/test_packet_boundaries.py
"""Tests for packet boundary (EOP / end-of-packet) behaviour.

The ISA encodes each instruction word with a 1-bit EOP flag at bit 24.
The cycle-accurate Core's fetch_packet() uses this bit to decide how many
words to collect into a packet: it keeps fetching until it sees EOP=1 or
reaches PACKET_WIDTH (4).

Coverage goals:
  - EOP=1 on a single-word packet terminates fetch immediately.
  - Multi-word packets (EOP=0 on first N-1, EOP=1 on last) are fetched
    as one packet.
  - Packets larger than PACKET_WIDTH are split: only PACKET_WIDTH words
    per fetch cycle.
  - The perf counter `packets_fetched` increments correctly.
  - Functional correctness: results produced inside a packet are correct.
  - EOP on every instruction (single-issue) vs grouped.
  - fetch_packet() returns an empty-ish packet when it hits an unknown/None
    decode at the packet boundary.
"""

import struct

from dspsim.assembler import assemble
from dspsim.bus import Bus
from dspsim.core_cycle import Core
from dspsim.decoder import decode_word
from dspsim.encoder import enc_i, enc_ri
from dspsim.isa import MAJ_ADDI, MAJ_HALT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_core(words: list[int], base: int = 0x1000) -> Core:
    """Load raw words into memory and return a Core pointing at base."""
    bus = Bus()
    blob = b"".join(struct.pack("<I", w) for w in words)
    bus.load_blob(base, blob)
    core = Core(bus=bus)
    core.pc = base
    return core


def _run_core(words: list[int], base: int = 0x1000, max_steps: int = 500) -> Core:
    """Run until halted or max_steps."""
    core = _make_core(words, base)
    for _ in range(max_steps):
        if not core.step():
            break
    return core


def _asm_core(lines: list[str]) -> Core:
    """Assemble ASM text, load into a Core and return it (not yet run)."""
    words = assemble(lines)
    return _make_core(words)


def _run_asm_core(lines: list[str], max_steps: int = 500) -> Core:
    words = assemble(lines)
    return _run_core(words, max_steps=max_steps)


# ---------------------------------------------------------------------------
# EOP bit helpers — build words with explicit EOP control
# ---------------------------------------------------------------------------

def _set_eop(word: int, eop: bool) -> int:
    """Set or clear bit 24 (EOP) of an instruction word."""
    if eop:
        return word | (1 << 24)
    return word & ~(1 << 24)


# ---------------------------------------------------------------------------
# fetch_packet unit tests (direct calls, no full run)
# ---------------------------------------------------------------------------

class TestFetchPacket:
    def test_single_word_eop1_terminates_fetch(self):
        """A word with EOP=1 should produce a 1-instruction packet."""
        w_addi = enc_ri(MAJ_ADDI, 1, 0, 42, None, True)  # EOP=1
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        core = _make_core([w_addi, w_halt])
        pkt = core.fetch_packet()
        assert len(pkt) == 1
        assert pkt[0].op == "ADDI"

    def test_two_word_packet_eop_on_second(self):
        """EOP=0 on first, EOP=1 on second => 2-word packet."""
        w1 = _set_eop(enc_ri(MAJ_ADDI, 1, 0, 1), False)   # EOP=0
        w2 = _set_eop(enc_ri(MAJ_ADDI, 2, 0, 2), True)    # EOP=1
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        core = _make_core([w1, w2, w_halt])
        pkt = core.fetch_packet()
        assert len(pkt) == 2
        assert pkt[0].op == "ADDI"
        assert pkt[1].op == "ADDI"
        # EOP flags
        assert pkt[0].endpkt is False
        assert pkt[1].endpkt is True

    def test_packet_width_cap(self):
        """If EOP never fires, fetch stops at PACKET_WIDTH words (4)."""
        # 6 ADDIs with EOP=0, then HALT with EOP=1
        words = [_set_eop(enc_ri(MAJ_ADDI, i % 32, 0, i), False) for i in range(6)]
        words.append(enc_i(MAJ_HALT, 0, None, True))
        core = _make_core(words)
        pkt = core.fetch_packet()
        assert len(pkt) == Core.PACKET_WIDTH  # 4

    def test_eop_flag_on_inst(self):
        """Decoded Inst.endpkt should mirror the EOP bit in the word."""
        w_eop = _set_eop(enc_ri(MAJ_ADDI, 1, 0, 10), True)
        w_no_eop = _set_eop(enc_ri(MAJ_ADDI, 1, 0, 10), False)
        inst_eop = decode_word(w_eop)
        inst_no = decode_word(w_no_eop)
        assert inst_eop.endpkt is True
        assert inst_no.endpkt is False

    def test_perf_packets_increments(self):
        """packets_fetched counter increases by 1 per call to fetch_packet."""
        w_addi = enc_ri(MAJ_ADDI, 1, 0, 5, None, True)
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        core = _make_core([w_addi, w_halt])
        assert core.perf.packets_fetched == 0
        core.fetch_packet()
        assert core.perf.packets_fetched == 1
        core.fetch_packet()
        assert core.perf.packets_fetched == 2


# ---------------------------------------------------------------------------
# Functional correctness across packet boundaries
# ---------------------------------------------------------------------------

class TestPacketFunctional:
    def test_single_issue_basic(self):
        """Standard assembled code (EOP=1 per instruction) runs correctly."""
        core = _run_asm_core(["ADDI R1, R0, #42", "HALT"])
        assert core.halted
        assert core.regs.read(1) == 42

    def test_multi_instruction_arithmetic(self):
        """Multi-issue: several ADDI in a single packet, then HALT."""
        w1 = _set_eop(enc_ri(MAJ_ADDI, 1, 0, 10), False)
        w2 = _set_eop(enc_ri(MAJ_ADDI, 2, 0, 20), False)
        w3 = _set_eop(enc_ri(MAJ_ADDI, 3, 0, 30), True)   # end of packet
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        core = _run_core([w1, w2, w3, w_halt])
        assert core.regs.read(1) == 10
        assert core.regs.read(2) == 20
        assert core.regs.read(3) == 30
        assert core.halted

    def test_two_packets_sequential(self):
        """Two separate 1-word packets produce the same result as one 2-word packet."""
        # Two separate packets (each EOP=1)
        words_single = [
            enc_ri(MAJ_ADDI, 1, 0, 5, None, True),   # packet 1
            enc_ri(MAJ_ADDI, 2, 1, 3, None, True),   # packet 2 (R2 = R1 + 3)
            enc_i(MAJ_HALT, 0, None, True),
        ]
        core = _run_core(words_single)
        assert core.regs.read(2) == 8
        assert core.halted

    def test_packet_perf_count_two_packets(self):
        """Two separate 1-word packets => packets_fetched >= 2 after full run."""
        words = [
            enc_ri(MAJ_ADDI, 1, 0, 1, None, True),  # packet 1
            enc_i(MAJ_HALT, 0, None, True),          # packet 2
        ]
        core = _run_core(words)
        # At minimum two packets were fetched (ADDI + HALT)
        assert core.perf.packets_fetched >= 2

    def test_three_word_packet(self):
        """Three instructions in a single packet all execute."""
        w1 = _set_eop(enc_ri(MAJ_ADDI, 1, 0, 1), False)
        w2 = _set_eop(enc_ri(MAJ_ADDI, 2, 0, 2), False)
        w3 = _set_eop(enc_ri(MAJ_ADDI, 3, 0, 3), True)
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        core = _run_core([w1, w2, w3, w_halt])
        assert core.regs.read(1) == 1
        assert core.regs.read(2) == 2
        assert core.regs.read(3) == 3

    def test_max_width_packet(self):
        """Four instructions (= PACKET_WIDTH) in one packet all execute."""
        w1 = _set_eop(enc_ri(MAJ_ADDI, 1, 0, 1), False)
        w2 = _set_eop(enc_ri(MAJ_ADDI, 2, 0, 2), False)
        w3 = _set_eop(enc_ri(MAJ_ADDI, 3, 0, 3), False)
        w4 = _set_eop(enc_ri(MAJ_ADDI, 4, 0, 4), True)
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        core = _run_core([w1, w2, w3, w4, w_halt])
        for r in range(1, 5):
            assert core.regs.read(r) == r

    def test_overflow_beyond_packet_width_splits(self):
        """5 ADDIs without EOP: first fetch grabs 4, second fetch starts on 5th."""
        w_noend = [_set_eop(enc_ri(MAJ_ADDI, i, 0, i * 10), False) for i in range(1, 6)]
        # Put EOP on the last ADDI to stop
        w_noend[-1] = _set_eop(w_noend[-1], True)
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        core = _make_core(w_noend + [w_halt])
        pkt1 = core.fetch_packet()
        pkt2 = core.fetch_packet()
        # First packet: up to PACKET_WIDTH=4
        assert len(pkt1) == 4
        # Second packet: remaining 1
        assert len(pkt2) == 1


# ---------------------------------------------------------------------------
# EOP and predication interaction
# ---------------------------------------------------------------------------

class TestPacketPredicationInteraction:
    def test_predicated_nop_in_packet_still_counted(self):
        """A predicated-false instruction inside a packet should increment
        predicated_nops but not change registers."""
        # P0 starts True; first ADDI runs; P0 is set False by CMPI;
        # the @P0-guarded second ADDI is skipped.
        core = _run_asm_core([
            "ADDI R1, R0, #10",
            "CMPI.NE P0, R1, #10",   # P0 = False (10 != 10 is False)
            "ADDI R2, R0, #99 @P0",  # guarded by False => predicated NOP
            "HALT",
        ])
        assert core.regs.read(2) == 0  # not written
        assert core.perf.predicated_nops >= 1

    def test_mixed_packet_pred_true_executes(self):
        """In a mixed packet, predicated-true instruction must execute."""
        # Build a 2-instruction packet: [ADDI R1, #5 (no-pred), ADDI R2, #7 @P0 (pred-true)]
        # P0 starts as True in the RegFile.
        w1 = _set_eop(enc_ri(MAJ_ADDI, 1, 0, 5), False)
        w2 = _set_eop(enc_ri(MAJ_ADDI, 2, 0, 7, pred=0), True)  # @P0
        w_halt = enc_i(MAJ_HALT, 0, None, True)
        core = _make_core([w1, w2, w_halt])
        # RegFile.P starts all True (per RegFile.__init__)
        while not core.halted:
            core.step()
        assert core.regs.read(1) == 5
        assert core.regs.read(2) == 7


# ---------------------------------------------------------------------------
# Packet boundary with store/load across packet edges
# ---------------------------------------------------------------------------

class TestPacketMemoryAcrossBoundary:
    def test_store_in_packet1_load_in_packet2(self):
        """ST at end of packet 1, LD at start of packet 2 — result must be correct."""
        core = _run_asm_core([
            "ADDI R10, R0, #0x200",
            "ADDI R1, R0, #55",
            "ST [R10], R1",         # end of implicit packet
            "LD R2, [R10]",         # start of next packet
            "HALT",
        ])
        assert core.regs.read(2) == 55
