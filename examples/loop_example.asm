; simple loop that writes ascii letters to memory and halts
ADDI R1, R0, 0x2000       ; base pointer
ADDI R2, R0, 65           ; 'A'
ADDI R3, R0, 90           ; 'Z'+1
LOOP_START:
CMPI.LT P0, R2, 0x5B      ; set P0 if R2 < 0x5B (91)
J 2                       ; if not taken, skip body (we don't have conditional-j encode here; keep simple)
ST32 [R1+0], R2
ADDI R2, R2, 1
J -3
HALT
