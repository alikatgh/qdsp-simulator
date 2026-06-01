# src/dspsim/elf_loader.py
"""ELF loader for the DSP simulator.

Loads ELF binaries (compiled for a 32-bit little-endian target) into
the simulator's Bus memory.  Requires `pyelftools` (optional dependency).

Install:  pip install dspsim[elf]
"""
from __future__ import annotations

from .bus import Bus


def load_elf(path: str, bus: Bus) -> tuple[int, int]:
    """Load an ELF file into bus memory.

    Returns:
        (entry_point, total_bytes_loaded)

    Raises:
        ImportError if pyelftools is not installed.
        RuntimeError on malformed or unsupported ELF.
    """
    try:
        from elftools.elf.elffile import ELFFile
    except ImportError as e:
        raise ImportError(
            "ELF loading requires pyelftools. Install with: pip install dspsim[elf]"
        ) from e

    with open(path, "rb") as f:
        elf = ELFFile(f)

        if elf.elfclass != 32:
            raise RuntimeError(f"Expected 32-bit ELF, got {elf.elfclass}-bit")
        if not elf.little_endian:
            raise RuntimeError("Expected little-endian ELF")

        entry = elf.header["e_entry"]
        total = 0

        for seg in elf.iter_segments():
            if seg.header["p_type"] != "PT_LOAD":
                continue
            paddr = seg.header["p_paddr"]
            memsz = seg.header["p_memsz"]
            data = seg.data()

            # Load file data
            bus.load_blob(paddr, data)

            # Zero-fill BSS (memsz > filesz)
            filesz = len(data)
            if memsz > filesz:
                bus.write(paddr + filesz, b"\x00" * (memsz - filesz))

            total += memsz

        return entry, total
