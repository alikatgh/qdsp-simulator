# Load a value from memory, add to it, and store back
# Let's pretend Mem[100] = 42
ADDI r10, r0, #100    # Set up address in R10
ADDI r1, r0, #42
ST   r1, r10, #0      # Store 42 at address 100

LD   r2, r10, #0      # Load value from Mem[100] into R2
ADDI r3, r2, #8      # Add 8 to it
ST   r3, r10, #4      # Store the result at Mem[104]
HALT
