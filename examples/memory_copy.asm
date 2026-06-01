; Memory copy: copies 4 words from address 0x200 to 0x300
; First, initialize source data
ADDI R10, R0, #0x200   ; src base
ADDI R11, R0, #0x300   ; dst base

; Store test values at source
ADDI R1, R0, #0xAA
ST [R10], R1
ADDI R1, R0, #0xBB
ST [R10+4], R1
ADDI R1, R0, #0xCC
ST [R10+8], R1
ADDI R1, R0, #0xDD
ST [R10+12], R1

; Copy: load from src, store to dst
LD R2, [R10]
ST [R11], R2
LD R2, [R10+4]
ST [R11+4], R2
LD R2, [R10+8]
ST [R11+8], R2
LD R2, [R10+12]
ST [R11+12], R2

HALT
