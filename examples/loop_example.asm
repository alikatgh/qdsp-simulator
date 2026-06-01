; Counting loop: sum 1+2+3+4+5 = 15
; Uses CMPI + predicated jump for loop control
;
; R1 = counter (starts at 1)
; R3 = accumulator
; Expected: R3 = 15

ADDI R1, R0, #1        ; counter = 1
ADDI R3, R0, #0        ; sum = 0

LOOP:
ADD R3, R3, R1          ; sum += counter
ADDI R1, R1, #1        ; counter++
CMPI.LE P0, R1, #5     ; P0 = (counter <= 5)
J LOOP @P0              ; if P0: loop back
HALT
; Result: R3 = 1+2+3+4+5 = 15 = 0x0F
