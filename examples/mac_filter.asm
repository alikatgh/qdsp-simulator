; DSP FIR filter tap — multiply-accumulate demo
; Computes: acc = c0*x0 + c1*x1 + c2*x2 + c3*x3
; Coefficients in R1-R4, samples in R5-R8, accumulator in R9

ADDI R1, R0, #3        ; c0 = 3
ADDI R2, R0, #5        ; c1 = 5
ADDI R3, R0, #7        ; c2 = 7
ADDI R4, R0, #2        ; c3 = 2

ADDI R5, R0, #10       ; x0 = 10
ADDI R6, R0, #20       ; x1 = 20
ADDI R7, R0, #30       ; x2 = 30
ADDI R8, R0, #40       ; x3 = 40

ADDI R9, R0, #0        ; acc = 0
MAC R9, R1, R5          ; acc += c0*x0 = 30
MAC R9, R2, R6          ; acc += c1*x1 = 130
MAC R9, R3, R7          ; acc += c2*x2 = 340
MAC R9, R4, R8          ; acc += c3*x3 = 420
HALT
; Expected: R9 = 3*10 + 5*20 + 7*30 + 2*40 = 30 + 100 + 210 + 80 = 420
