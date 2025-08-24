# Q-DSP Simulator (Educational)

An educational instruction set simulator for a clean-room, Hexagon-inspired VLIW DSP architecture.

## Goal

To provide a working, instrumentable simulator for learning about VLIW packets, hazard detection, and DSP architecture.

## How to Run

1.  **Install dependencies:**
    ```bash
    pip install pytest
    ```

2.  **Run an example:**
    ```bash
    python3 run_sim.py examples/basic_alu.asm --trace
    ```

3.  **Run tests:**
    ```bash
    pytest
    ```
