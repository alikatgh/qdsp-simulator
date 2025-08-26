from __future__ import annotations

import sys
import pathlib
import logging
import click

from .logging_setup import setup_logging
from . import __version__
from . import assembler
from . import disassembler
from .core import Simulator as FunctionalSimulator
from .core_cycle import Core as CycleSimulator
from .memory import Memory

try:
    from rich.console import Console
    from rich.table import Table
    HAVE_RICH = True
except Exception:
    HAVE_RICH = False

log = logging.getLogger("dspsim.cli")

def _read_text_file(path: pathlib.Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        raise click.ClickException(f"Failed to read '{path}': {e}") from e

@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(__version__, prog_name="dspsim")
@click.option("--log-level", default="WARNING", show_default=True,
              type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
              help="Set log verbosity.")
def cli(log_level: str):
    """DSPsim — educational DSP simulator and tools."""
    setup_logging(log_level)
    log.debug("CLI started")

@cli.command()
@click.argument("asm_file", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path))
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=pathlib.Path),
              help="Output binary file (.bin). If omitted, prints hex words.")
def asm(asm_file: pathlib.Path, output: pathlib.Path | None):
    """Assemble ASM_FILE into binary words."""
    lines = _read_text_file(asm_file)
    try:
        program = assembler.assemble(lines)
    except assembler.AsmError as e:
        raise click.ClickException(f"Assembly failed: {e}") from e
    except Exception as e:
        raise click.ClickException(f"Assembly crashed: {e}") from e

    if output:
        # Each instruction is a 32-bit word. Write little-endian.
        import struct
        with output.open("wb") as f:
            for w in program:
                f.write(struct.pack("<I", w))
        click.echo(f"Wrote {len(program)} words to {output}")
    else:
        # Print as hex, one per line.
        for w in program:
            click.echo(f"0x{w:08X}")

@cli.command()
@click.argument("bin_file", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path))
def disasm(bin_file: pathlib.Path):
    """Disassemble a binary (.bin) of 32-bit words (little-endian)."""
    data = bin_file.read_bytes()
    if len(data) % 4:
        raise click.ClickException("Binary size is not a multiple of 4 bytes.")
    import struct
    words = [struct.unpack_from("<I", data, i)[0] for i in range(0, len(data), 4)]
    lines = disassembler.disassemble(words)
    for ln in lines:
        click.echo(ln)

@cli.command()
@click.option("--asm", "asm_file", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
              help="Assemble and run this assembly file.")
@click.option("--bin", "bin_file", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
              help="Load and run this raw .bin file of 32-bit words.")
@click.option("--base", default=0x1000, show_default=True, type=click.IntRange(min=0),
              help="Base load address.")
@click.option("--entry", default=None, type=int, help="Entry PC address (default: base).")
@click.option("--engine", type=click.Choice(["fast", "cycle"]), default="fast", show_default=True,
              help="Select execution engine: functional fast model or cycle/timing model.")
@click.option("--trace/--no-trace", default=False, show_default=True, help="Enable instruction trace.")
@click.option("--pretty/--no-pretty", default=False, show_default=True,
              help="Pretty print trace (requires rich).")
def run(asm_file: pathlib.Path | None,
        bin_file: pathlib.Path | None,
        base: int,
        entry: int | None,
        engine: str,
        trace: bool,
        pretty: bool):
    """Run a program (from ASM or BIN) on the simulator."""
    if not asm_file and not bin_file:
        raise click.ClickException("Provide either --asm or --bin.")
    if asm_file and bin_file:
        raise click.ClickException("Provide only one of --asm or --bin.")

    # Load instructions
    if asm_file:
        lines = _read_text_file(asm_file)
        try:
            words = assembler.assemble(lines)
        except assembler.AsmError as e:
            raise click.ClickException(f"Assembly failed: {e}") from e
    else:
        data = pathlib.Path(bin_file).read_bytes()
        if len(data) % 4:
            raise click.ClickException("Binary size is not a multiple of 4 bytes.")
        import struct
        words = [struct.unpack_from("<I", data, i)[0] for i in range(0, len(data), 4)]

    # Select engine
    if engine == "fast":
        sim = FunctionalSimulator()
        mem = sim.mem  # Memory instance inside fast model
        # Load words into memory at base
        for i, w in enumerate(words):
            mem.store_u32(base + 4*i, w)
        start_pc = entry if entry is not None else base
        sim.pc = start_pc
        if trace and pretty and not HAVE_RICH:
            click.echo("Warning: --pretty requested but 'rich' not installed.", err=True)
        # The functional model already prints/dumps in some places; keep quiet unless trace toggled:
        sim.run()  # (Extend: add trace hooks in functional model as you consolidate)
        # After run, show registers in a friendly way:
        if HAVE_RICH and pretty:
            _print_registers_rich(sim.regs)
        else:
            click.echo("Final Registers:")
            for i in range(0, 32, 4):
                chunk = sim.regs[i:i+4]
                click.echo(f"R{i:02d}-R{i+3:02d}: " + " ".join(f"{r:08X}" for r in chunk))
    else:
        # Cycle/timing model path
        core = CycleSimulator()
        # Load words into memory via core.mem / bus:
        for i, w in enumerate(words):
            core.mem.store_u32(base + 4*i, w)
        core.pc = entry if entry is not None else base
        core.trace_enable(trace)
        finished = True
        while core.step():
            pass
        if HAVE_RICH and pretty:
            _print_registers_rich([core.regs.read(i) for i in range(32)])
        else:
            click.echo("Final Registers:")
            for i in range(0, 32, 4):
                chunk = [core.regs.read(j) for j in range(i, i+4)]
                click.echo(f"R{i:02d}-R{i+3:02d}: " + " ".join(f"{r:08X}" for r in chunk))

def _print_registers_rich(regs_32):
    console = Console()
    table = Table(title="Register File (R0..R31)")
    table.add_column("Range")
    table.add_column("Values")
    for i in range(0, 32, 4):
        chunk = regs_32[i:i+4]
        table.add_row(f"R{i:02d}-R{i+3:02d}", " ".join(f"{r:08X}" for r in chunk))
    console.print(table)

def main():
    try:
        cli(prog_name="dspsim")
    except click.ClickException as e:
        # Clean error to stderr with proper code
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    except KeyboardInterrupt:
        click.echo("Interrupted.", err=True)
        sys.exit(130)
