# Future test for Read-After-Write hazards.
# LD should cause a stall before the ADD can use R1.
LD r1, r10, #0
ADD r2, r1, r3
HALT
