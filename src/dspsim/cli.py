from __future__ import annotations

import sys
import pathlib
import logging
import click
import struct

from .logging_setup import setup_logging
from . import __version__
from . import assembler
from . import disassembler
from .core import FunctionalSimulator
from .core_cycle import Core as CycleSimulator, Memory as CycleMemory
from .trace import TraceSink

try:
    from rich.console import Console
    from rich.table import Table
    HAVE_RICH = True
except ImportError:
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
        program_words = assembler.assemble(lines)
    except assembler.AsmError as e:
        raise click.ClickException(f"Assembly failed: {e}") from e
    except Exception as e:
        raise click.ClickException(f"Assembly crashed: {e}") from e

    if output:
        with output.open("wb") as f:
            for w in program_words:
                f.write(struct.pack("<I", w))
        click.echo(f"Wrote {len(program_words)} words to {output}")
    else:
        for w in program_words:
            click.echo(f"0x{w:08X}")

@cli.command()
@click.argument("bin_file", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path))
def disasm(bin_file: pathlib.Path):
    """Disassemble a binary (.bin) of 32-bit words (little-endian)."""
    data = bin_file.read_bytes()
    if len(data) % 4:
        raise click.ClickException("Binary size is not a multiple of 4 bytes.")
    words = [struct.unpack_from("<I", data, i)[0] for i in range(0, len(data), 4)]
    # Assuming disassembler.disassemble exists and works
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

    if asm_file:
        lines = _read_text_file(asm_file)
        try:
            words = assembler.assemble(lines)
        except assembler.AsmError as e:
            raise click.ClickException(f"Assembly failed: {e}") from e
    else:
        data = pathlib.Path(bin_file).read_bytes()
        if len(data) % 4 != 0:
            raise click.ClickException("Binary size is not a multiple of 4 bytes.")
        words = [struct.unpack_from("<I", data, i)[0] for i in range(0, len(data), 4)]

    start_pc = entry if entry is not None else base

    if engine == "fast":
        sim = FunctionalSimulator()
        sim.load_words(base, words)
        sim.pc = start_pc
        
        if trace and pretty and not HAVE_RICH:
            click.echo("Warning: --pretty requested but 'rich' not installed.", err=True)
        
        sim.run()
        
        click.echo("Final Registers:")
        if HAVE_RICH and pretty:
            _print_registers_rich(sim.regs)
        else:
            sim.dump_regs()

    else: # engine == "cycle"
        mem = CycleMemory()
        program_bytes = b"".join(struct.pack("<I", w) for w in words)
        mem.load_blob(base, program_bytes)
        
        trace_sink = TraceSink() if trace else None
        core = CycleSimulator(mem=mem, trace=trace_sink)
        core.pc = start_pc

        while not core.halted:
            core.step()
        
        if trace_sink:
            trace_sink.close()

        click.echo("Final Registers:")
        final_regs = [core.regs.read(i) for i in range(32)]
        if HAVE_RICH and pretty:
            _print_registers_rich(final_regs)
        else:
            for i in range(0, 32, 4):
                chunk = final_regs[i:i+4]
                click.echo(f"R{i:02d}-R{i+3:02d}: " + " ".join(f"{r:08X}" for r in chunk))

def _print_registers_rich(regs_32: list[int]):
    """Prints the register file state using a rich Table."""
    console = Console()
    table = Table(title="Register File (R0..R31)")
    table.add_column("Range", justify="right")
    table.add_column("Values")
    for i in range(0, 32, 4):
        chunk = regs_32[i:i+4]
        table.add_row(f"R{i:02d}-R{i+3:02d}", " ".join(f"{r:08X}" for r in chunk))
    console.print(table)

def main():
    try:
        cli(prog_name="dspsim")
    except click.ClickException as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nInterrupted.", err=True)
        sys.exit(130)