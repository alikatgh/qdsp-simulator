; Predicated Max — find the maximum of 4 values using predication
; Demonstrates CMPI + predicated ADDI (conditional move pattern)
;
; Values: 17, 42, 8, 35 → expected max = 42 in R5

ADDI R1, R0, #17       ; val[0]
ADDI R2, R0, #42       ; val[1]
ADDI R3, R0, #8        ; val[2]
ADDI R4, R0, #35       ; val[3]

; R5 = max, start with val[0]
ADD R5, R0, R1         ; max = 17

; if val[1] > max: max = val[1]
SUB R6, R2, R5         ; R6 = val[1] - max
CMPI.GT P0, R6, #0     ; P0 = (val[1] - max > 0)
ADD R5, R0, R2 @P0     ; if P0: max = val[1]

; if val[2] > max: max = val[2]
SUB R6, R3, R5
CMPI.GT P0, R6, #0
ADD R5, R0, R3 @P0

; if val[3] > max: max = val[3]
SUB R6, R4, R5
CMPI.GT P0, R6, #0
ADD R5, R0, R4 @P0

; R5 should now be 42
HALT
