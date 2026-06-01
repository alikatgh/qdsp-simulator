# DSPsim ISA Reference

This is the authoritative specification of the DSPsim educational instruction
set. It is a **clean-room, Hexagon-*inspired*** ISA — it is not Qualcomm Hexagon
and shares no encodings with it. The goal is transparency: every instruction
has a single documented encoding and a single documented side effect, and both
execution engines (see below) are tested to agree on all of them.

> Source of truth in code: opcodes and semantics live in
> [`src/dspsim/isa.py`](../src/dspsim/isa.py); field encodings in
> [`src/dspsim/encoder.py`](../src/dspsim/encoder.py) and
> [`src/dspsim/decoder.py`](../src/dspsim/decoder.py). If this document and the
> code ever disagree, the code wins and this file is the bug.

---

## 1. Machine state

| State | Description |
|-------|-------------|
| `R0`–`R31` | 32 general-purpose registers, 32-bit. `R0` is an ordinary register (not hardwired to zero), but examples use it as a zero source after `ADDI Rx, R0, #k`. |
| `P0`–`P3` | 4 predicate (1-bit) registers. Written by `CMPI`, read by predicated instructions. |
| `PC` | Program counter, byte address. Default reset/base value `0x1000`. |
| Memory | Flat little-endian byte-addressable RAM (default 16 MiB) plus MMIO regions. 32-bit accesses must be 4-byte aligned. |

All arithmetic is modulo 2³² (wrapping). Values are stored unsigned; signed
operations (`CMPI`, immediate sign-extension) interpret the 32-bit value as
two's complement.

---

## 2. Instruction word format

Every instruction is a single 32-bit little-endian word. All instructions
share a common 8-bit header:

```
 31    28 27   26  25 24 23                                    0
+--------+---+------+---+--------------------------------------+
|  MAJ   | P | Pidx |EOP|            format-specific           |
+--------+---+------+---+--------------------------------------+
```

| Field | Bits | Meaning |
|-------|------|---------|
| `MAJ`  | `[31:28]` | Major opcode (4 bits, 16 possible). |
| `P`    | `[27]`    | Predicated flag. If 1, the instruction is guarded by `Pidx`. |
| `Pidx` | `[26:25]` | Which predicate register guards this instruction (0–3). |
| `EOP`  | `[24]`    | End-of-packet bit (see §6). |

---

## 3. Formats

The low 24 bits `[23:0]` are interpreted per the instruction's format.

### 3R — three registers (`ADD SUB AND OR XOR SHL SHR MUL MAC`)
```
[23:19] rd    [18:14] rs1    [13:9] rs2    [8:0] unused
```

### 2R — two registers (`NOT`)
```
[23:19] rd    [18:14] rs1
```

### RI — register + immediate (`ADDI LD ST`)
```
[23:19] rd    [18:14] rs1    [13:0] imm14 (signed, two's complement)
```
For `ST`, the `[23:19]` field holds the **source data register**, not a
destination (store writes memory, not a register).

### I — immediate only (`J`)
```
[13:0] imm14 (signed word offset)
```

### CMPI — compare immediate, writes a predicate
```
[23:19] Pdst    [18:14] rs1    [13:10] cmp_code    [9:0] imm10 (signed)
```

### Register-only (`JR`) and no-operand (`HALT`)
```
JR:   [18:14] rs1
HALT: all of MAJ=0xF with rd=0, rs1=0, [13:0]=0
```

---

## 4. Opcode table

| Mnemonic | MAJ | Format | Operation |
|----------|-----|--------|-----------|
| `ADD`  | `0x0` | 3R | `R[rd] = R[rs1] + R[rs2]` |
| `ADDI` | `0x1` | RI | `R[rd] = R[rs1] + sext(imm14)` |
| `SUB`  | `0x2` | 3R | `R[rd] = R[rs1] - R[rs2]` |
| `AND`  | `0x3` | 3R | `R[rd] = R[rs1] & R[rs2]` |
| `OR`   | `0x4` | 3R | `R[rd] = R[rs1] \| R[rs2]` |
| `XOR`  | `0x5` | 3R | `R[rd] = R[rs1] ^ R[rs2]` |
| `SHL`  | `0x6` | 3R | `R[rd] = R[rs1] << (R[rs2] & 31)` |
| `SHR`  | `0x7` | 3R | `R[rd] = R[rs1] >> (R[rs2] & 31)` (logical) |
| `MUL`  | `0x8` | 3R | `R[rd] = (R[rs1] * R[rs2]) & 0xFFFFFFFF` |
| `MAC`  | `0x9` | 3R | `R[rd] = R[rd] + R[rs1] * R[rs2]` (reads `rd`) |
| `NOT`  | `0xA` | 2R | `R[rd] = ~R[rs1]` |
| `LD`   | `0xB` | RI | `R[rd] = Mem32[R[rs1] + sext(imm14)]` |
| `ST`   | `0xC` | RI | `Mem32[R[rs1] + sext(imm14)] = R[rd]` |
| `J`    | `0xD` | I  | `PC = PC_next + (sext(imm14) << 2)` |
| `JR`   | `0xE` | reg| `PC = R[rs1]` |
| `CMPI` | `0xF` | CMPI | `P[Pdst] = (s32(R[rs1]) <cmp> sext(imm10))` |
| `HALT` | `0xF` | none | Stop execution |

`CMPI` and `HALT` share `MAJ=0xF`; they are distinguished by the all-zero
operand pattern of `HALT`.

### CMPI comparison codes
| `.suffix` | `cmp_code` | Test |
|-----------|-----------|------|
| `EQ` | 0 | `a == b` |
| `NE` | 1 | `a != b` |
| `LT` | 2 | `a < b` |
| `GE` | 3 | `a >= b` |
| `LE` | 4 | `a <= b` |
| `GT` | 5 | `a > b` |

`a = s32(R[rs1])`, `b = sext(imm10)`.

---

## 5. Predication

Any instruction may be guarded by a predicate using the `@P#` suffix in
assembly:

```asm
CMPI.LE P0, R1, #5     ; P0 = (R1 <= 5)
J LOOP @P0             ; branch only if P0 is true
ADDI R2, R2, #1 @P0    ; increment only if P0 is true
```

When the predicate flag `P` is set and `P[Pidx]` is **false**, the instruction
is fetched and decoded but produces **no architectural side effect** (no
register write, no memory write, no branch). In the cycle-accurate engine this
is counted as a *predicated NOP*.

Predicate registers reset to `True`, so an un-guarded program behaves as if
predication were absent.

---

## 6. Packets

The architecture supports VLIW-style **packets**: the cycle-accurate core
fetches up to `PACKET_WIDTH` (= 4) words and issues them together, stopping at
the word whose `EOP` bit is set. This models multi-issue hardware and is where
the performance counters' IPC > 1 would come from.

> **Assembler note:** the bundled assembler currently sets `EOP = 1` on *every*
> instruction, so each instruction forms its own one-word packet. Packet
> grouping is an architectural capability exercised by hand-encoded programs and
> the cycle model; the text assembler does not yet emit multi-instruction
> packets.

---

## 7. Memory model

* Flat, little-endian, byte-addressable. Default size 16 MiB.
* **32-bit loads/stores must be 4-byte aligned.** A misaligned or
  out-of-bounds access raises a `MemoryFault`
  ([`src/dspsim/bus.py`](../src/dspsim/bus.py)); the fast engine surfaces it as a
  `RuntimeError` naming the faulting PC.
* Programs load at `--base` (default `0x1000`) and begin at `--entry` (default
  = base).

### MMIO devices

Devices are mapped into the address space and intercept 32-bit accesses to
their range. Two reference peripherals ship in
[`src/dspsim/devices.py`](../src/dspsim/devices.py):

**UART** (offsets from its base)
| Offset | R/W | Register |
|--------|-----|----------|
| `0x00` | W | `TX_DATA` — write low byte to transmit |
| `0x04` | R | `RX_DATA` — read next received byte (0 if empty) |
| `0x08` | R | `STATUS` — bit0 = TX ready (always 1), bit1 = RX data available |

**Timer** (offsets from its base)
| Offset | R/W | Register |
|--------|-----|----------|
| `0x00` | RW | `CTRL` — bit0 = enable, bit1 = auto-reload |
| `0x04` | RW | `LOAD` — reload / initial count |
| `0x08` | R | `COUNT` — current count |
| `0x0C` | R | `STATUS` — bit0 = expired (write 1 to clear) |

---

## 8. Two execution engines

DSPsim ships two independent implementations of this ISA:

| Engine | Module | Purpose |
|--------|--------|---------|
| **fast** | `dspsim.core.FunctionalSimulator` | Reference model: one instruction per step, simplest possible semantics. |
| **cycle** | `dspsim.core_cycle.Core` | Cycle-approximate: packet fetch, functional units (ALU/LSU/VEC), a scoreboard for data/structural hazards, and performance counters (cycles, stalls, CPI/IPC). |

Because the semantics are written twice, they could drift. They are kept honest
by a **differential harness**
([`scripts/diff_engines.py`](../scripts/diff_engines.py)) and
[`tests/test_differential.py`](../tests/test_differential.py), which run every
example and a battery of edge cases on both engines and assert that all 32
registers, 4 predicates, and the full memory image match. Timing and
instruction-count differences are expected and excluded from the comparison.
