; Basic ALU operations demo
; Tests ADD, SUB, MUL, AND, OR, XOR, SHL, SHR, NOT

ADDI R1, R0, #100      ; R1 = 100
ADDI R2, R0, #50       ; R2 = 50
ADD  R3, R1, R2        ; R3 = 150
SUB  R4, R1, R2        ; R4 = 50
MUL  R5, R1, R2        ; R5 = 5000
AND  R6, R1, R2        ; R6 = 100 & 50 = 32
OR   R7, R1, R2        ; R7 = 100 | 50 = 118
XOR  R8, R1, R2        ; R8 = 100 ^ 50 = 86
ADDI R9, R0, #4
SHL  R10, R1, R9       ; R10 = 100 << 4 = 1600
SHR  R11, R1, R9       ; R11 = 100 >> 4 = 6
NOT  R12, R1           ; R12 = ~100
HALT
