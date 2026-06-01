; Data hazard test for cycle-accurate model
; LD has 3-cycle latency; ADD depends on the LD result -> stall expected

ADDI R10, R0, #0x100   ; address
ADDI R1, R0, #42
ST [R10], R1            ; Mem[0x100] = 42

LD R2, [R10]            ; R2 = Mem[0x100]  (3-cycle latency)
ADD R3, R2, R1          ; depends on R2 — should stall until LD completes
HALT
