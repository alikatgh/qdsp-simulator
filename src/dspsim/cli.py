from __future__ import annotations

import logging
import pathlib
import struct
import sys

import click

from . import __version__, assembler, disassembler
from .bus import Bus
from .core import FunctionalSimulator
from .core_cycle import Core as CycleSimulator
from .logging_setup import setup_logging
from .trace import TraceSink

try:
    from rich.console import Console
    from rich.table import Table
    HAVE_RICH = True
except ImportError:
    HAVE_RICH = False

log = logging.getLogger("dspsim.cli")

# Reused click parameter type: an existing, readable file path argument.
_EXISTING_FILE = click.Path(exists=True, dir_okay=False, path_type=pathlib.Path)


def _parse_addr(tok: str) -> int:
    """Parse an address token as hex (0x...) or decimal."""
    return int(tok, 16) if tok.lower().startswith("0x") else int(tok)


class _IntType(click.ParamType):
    """A click int parameter that accepts both decimal and 0x-hex literals.

    Addresses are naturally written in hex (``--base 0x1000``); plain
    ``click.INT`` rejects that. ``min`` optionally enforces a lower bound.
    """

    name = "integer"

    def __init__(self, min: int | None = None):
        self.min = min

    def convert(self, value, param, ctx):
        if isinstance(value, int):
            parsed = value
        else:
            try:
                parsed = int(value, 0)  # base 0 -> honors 0x / 0o / 0b prefixes
            except ValueError:
                self.fail(f"{value!r} is not a valid integer", param, ctx)
        if self.min is not None and parsed < self.min:
            self.fail(f"{parsed} is less than the minimum {self.min}", param, ctx)
        return parsed


INT = _IntType()
ADDR = _IntType(min=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_text_file(path: pathlib.Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        raise click.ClickException(f"Failed to read '{path}': {e}") from e


def _load_program(asm_file, bin_file):
    """Return list of 32-bit words from either an asm or bin source."""
    if asm_file:
        lines = _read_text_file(asm_file)
        try:
            return assembler.assemble(lines)
        except assembler.AsmError as e:
            raise click.ClickException(f"Assembly failed: {e}") from e
    else:
        data = pathlib.Path(bin_file).read_bytes()
        if len(data) % 4 != 0:
            raise click.ClickException("Binary size is not a multiple of 4 bytes.")
        return [struct.unpack_from("<I", data, i)[0] for i in range(0, len(data), 4)]


def _print_regs(regs_32: list[int], pretty: bool = False):
    if HAVE_RICH and pretty:
        console = Console()
        table = Table(title="Register File (R0..R31)")
        table.add_column("Range", justify="right")
        table.add_column("Values")
        for i in range(0, 32, 4):
            chunk = regs_32[i:i + 4]
            table.add_row(f"R{i:02d}-R{i+3:02d}", " ".join(f"{r:08X}" for r in chunk))
        console.print(table)
    else:
        for i in range(0, 32, 4):
            chunk = regs_32[i:i + 4]
            click.echo(f"R{i:02d}-R{i+3:02d}: " + " ".join(f"{r:08X}" for r in chunk))


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(__version__, prog_name="dspsim")
@click.option("--log-level", default="WARNING", show_default=True,
              type=click.Choice(
                  ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                  case_sensitive=False,
              ),
              help="Set log verbosity.")
def cli(log_level: str):
    """DSPsim \u2014 educational DSP simulator and tools."""
    setup_logging(log_level)
    log.debug("CLI started")


# ---------------------------------------------------------------------------
# asm
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("asm_file", type=_EXISTING_FILE)
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=pathlib.Path),
              help="Output binary file (.bin). If omitted, prints hex words.")
def asm(asm_file: pathlib.Path, output: pathlib.Path | None):
    """Assemble ASM_FILE into binary words."""
    lines = _read_text_file(asm_file)
    try:
        program_words = assembler.assemble(lines)
    except assembler.AsmError as e:
        raise click.ClickException(f"Assembly failed: {e}") from e

    if output:
        with output.open("wb") as f:
            for w in program_words:
                f.write(struct.pack("<I", w))
        click.echo(f"Wrote {len(program_words)} words to {output}")
    else:
        for w in program_words:
            click.echo(f"0x{w:08X}")


# ---------------------------------------------------------------------------
# disasm
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("bin_file", type=_EXISTING_FILE)
@click.option("--base", default=0, show_default=True, type=ADDR,
              help="Base PC for address display.")
def disasm(bin_file: pathlib.Path, base: int):
    """Disassemble a binary (.bin) of 32-bit words (little-endian)."""
    data = bin_file.read_bytes()
    if len(data) % 4:
        raise click.ClickException("Binary size is not a multiple of 4 bytes.")
    words = [struct.unpack_from("<I", data, i)[0] for i in range(0, len(data), 4)]
    lines = disassembler.disassemble(words, base_pc=base)
    for ln in lines:
        click.echo(ln)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--asm", "asm_file", type=_EXISTING_FILE,
              help="Assemble and run this assembly file.")
@click.option("--bin", "bin_file", type=_EXISTING_FILE,
              help="Load and run this raw .bin file of 32-bit words.")
@click.option("--elf", "elf_file", type=_EXISTING_FILE,
              help="Load and run an ELF binary (requires pyelftools).")
@click.option("--base", default=0x1000, show_default=True, type=ADDR,
              help="Base load address (for asm/bin). Accepts hex (0x...).")
@click.option("--entry", default=None, type=ADDR,
              help="Entry PC address (default: base or ELF entry). Accepts hex.")
@click.option("--engine", type=click.Choice(["fast", "cycle"]), default="fast", show_default=True,
              help="Select execution engine: functional fast model or cycle/timing model.")
@click.option("--max-cycles", default=100_000, show_default=True, type=INT,
              help="Safety limit on executed instructions/cycles.")
@click.option("--trace/--no-trace", default=False, show_default=True,
              help="Enable instruction trace.")
@click.option("--pretty/--no-pretty", default=False, show_default=True,
              help="Pretty print output (requires rich).")
def run(asm_file, bin_file, elf_file, base, entry, engine, max_cycles, trace, pretty):
    """Run a program (from ASM, BIN, or ELF) on the simulator."""
    sources = sum(1 for x in (asm_file, bin_file, elf_file) if x)
    if sources == 0:
        raise click.ClickException("Provide one of --asm, --bin, or --elf.")
    if sources > 1:
        raise click.ClickException("Provide only one of --asm, --bin, or --elf.")

    # ELF path: load directly into bus, get entry from ELF header
    if elf_file:
        from .elf_loader import load_elf
        bus = Bus()
        try:
            elf_entry, nbytes = load_elf(str(elf_file), bus)
        except ImportError as e:
            raise click.ClickException(str(e)) from e
        except RuntimeError as e:
            raise click.ClickException(f"ELF load failed: {e}") from e
        start_pc = entry if entry is not None else elf_entry
        click.echo(f"Loaded ELF: {nbytes} bytes, entry=0x{elf_entry:X}")
        # Run on cycle engine with pre-loaded bus
        trace_sink = TraceSink() if trace else None
        core = CycleSimulator(bus=bus, trace=trace_sink)
        core.pc = start_pc
        safety = 0
        while not core.halted and safety < max_cycles:
            core.step()
            safety += 1
        if not core.halted:
            click.echo(f"Warning: max-cycles ({max_cycles}) reached without HALT.", err=True)
        if trace_sink:
            trace_sink.close()
        click.echo(core.perf.summary())
        click.echo("\nFinal Registers:")
        _print_regs([core.regs.read(i) for i in range(32)], pretty)
        return

    words = _load_program(asm_file, bin_file)
    start_pc = entry if entry is not None else base

    if engine == "fast":
        sim = FunctionalSimulator()
        sim.load_words(base, words)
        sim.pc = start_pc
        try:
            sim.run(max_cycles=max_cycles)
        except RuntimeError as e:
            raise click.ClickException(str(e)) from e
        click.echo(f"Executed {sim.cycle_count} instructions.\n")
        click.echo("Final Registers:")
        _print_regs(sim.regs, pretty)

    else:  # cycle
        bus = Bus()
        bus.load_blob(base, b"".join(struct.pack("<I", w) for w in words))
        trace_sink = TraceSink() if trace else None
        core = CycleSimulator(bus=bus, trace=trace_sink)
        core.pc = start_pc

        safety = 0
        while not core.halted and safety < max_cycles:
            core.step()
            safety += 1
        if not core.halted:
            click.echo(f"Warning: max-cycles ({max_cycles}) reached without HALT.", err=True)

        if trace_sink:
            trace_sink.close()

        click.echo(core.perf.summary())
        click.echo("\nFinal Registers:")
        final_regs = [core.regs.read(i) for i in range(32)]
        _print_regs(final_regs, pretty)


# ---------------------------------------------------------------------------
# debug (interactive debugger)
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--asm", "asm_file", type=_EXISTING_FILE,
              help="Assembly source file.")
@click.option("--bin", "bin_file", type=_EXISTING_FILE,
              help="Raw .bin file.")
@click.option("--base", default=0x1000, show_default=True, type=ADDR)
@click.option("--entry", default=None, type=ADDR)
def debug(asm_file, bin_file, base, entry):
    """Interactive debugger: step through instructions, set breakpoints, inspect state."""
    if not asm_file and not bin_file:
        raise click.ClickException("Provide either --asm or --bin.")
    if asm_file and bin_file:
        raise click.ClickException("Provide only one of --asm or --bin.")

    words = _load_program(asm_file, bin_file)
    start_pc = entry if entry is not None else base

    bus = Bus()
    bus.load_blob(base, b"".join(struct.pack("<I", w) for w in words))
    core = CycleSimulator(bus=bus)
    core.pc = start_pc

    breakpoints: set[int] = set()
    program_end = base + len(words) * 4

    click.echo("DSPsim interactive debugger. Type 'help' for commands.")
    click.echo(f"Program loaded at 0x{base:X}..0x{program_end:X}, entry=0x{start_pc:X}\n")

    def _show_current():
        """Show the instruction at the current PC."""
        if core.halted:
            click.echo("  [HALTED]")
            return
        try:
            w = bus.read32(core.pc)
            asm_text = disassembler.disassemble_word(w, core.pc)
            click.echo(f"  0x{core.pc:04X}: {asm_text}")
        except Exception:
            click.echo(f"  0x{core.pc:04X}: <unreadable>")

    _show_current()

    while True:
        try:
            line = click.prompt("dbg", type=str, default="").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\nExiting debugger.")
            break

        if not line:
            line = "s"  # default: step

        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("h", "help"):
            click.echo(
                "Commands:\n"
                "  s, step [N]       Step N instructions (default 1)\n"
                "  c, continue       Run until breakpoint or HALT\n"
                "  b, break ADDR     Set breakpoint at hex address\n"
                "  d, delete ADDR    Remove breakpoint\n"
                "  bl                List breakpoints\n"
                "  r, regs           Show registers\n"
                "  p, pred           Show predicate registers\n"
                "  m, mem ADDR [N]   Dump N words at ADDR (default 4)\n"
                "  dis [ADDR] [N]    Disassemble N words at ADDR (default: PC, 8)\n"
                "  perf              Show performance counters\n"
                "  q, quit           Exit debugger"
            )

        elif cmd in ("s", "step"):
            n = int(parts[1]) if len(parts) > 1 else 1
            for _ in range(n):
                if core.halted:
                    click.echo("  [HALTED]")
                    break
                core.step()
                if core.pc in breakpoints:
                    click.echo(f"  ** Breakpoint at 0x{core.pc:04X} **")
                    break
            _show_current()

        elif cmd in ("c", "continue"):
            safety = 0
            while not core.halted and safety < 100_000:
                core.step()
                safety += 1
                if core.pc in breakpoints:
                    click.echo(f"  ** Breakpoint at 0x{core.pc:04X} **")
                    break
            if core.halted:
                click.echo("  [HALTED]")
            elif safety >= 100_000:
                click.echo("  Stopped after 100000 cycles (safety limit).")
            _show_current()

        elif cmd in ("b", "break"):
            if len(parts) < 2:
                click.echo("Usage: break <hex_addr>")
            else:
                addr = _parse_addr(parts[1])
                breakpoints.add(addr)
                click.echo(f"  Breakpoint set at 0x{addr:04X}")

        elif cmd in ("d", "delete"):
            if len(parts) < 2:
                click.echo("Usage: delete <hex_addr>")
            else:
                addr = _parse_addr(parts[1])
                breakpoints.discard(addr)
                click.echo(f"  Breakpoint removed at 0x{addr:04X}")

        elif cmd == "bl":
            if breakpoints:
                for bp in sorted(breakpoints):
                    click.echo(f"  0x{bp:04X}")
            else:
                click.echo("  No breakpoints set.")

        elif cmd in ("r", "regs"):
            regs = [core.regs.read(i) for i in range(32)]
            _print_regs(regs)

        elif cmd in ("p", "pred"):
            for i in range(4):
                click.echo(f"  P{i} = {core.regs.read_pred(i)}")

        elif cmd in ("m", "mem"):
            if len(parts) < 2:
                click.echo("Usage: mem <hex_addr> [count]")
            else:
                addr = _parse_addr(parts[1])
                count = int(parts[2]) if len(parts) > 2 else 4
                for i in range(count):
                    a = addr + i * 4
                    try:
                        val = bus.read32(a)
                        click.echo(f"  0x{a:04X}: 0x{val:08X}")
                    except Exception:
                        click.echo(f"  0x{a:04X}: <fault>")

        elif cmd == "dis":
            addr = core.pc
            count = 8
            if len(parts) > 1:
                addr = _parse_addr(parts[1])
            if len(parts) > 2:
                count = int(parts[2])
            for i in range(count):
                a = addr + i * 4
                try:
                    w = bus.read32(a)
                    text = disassembler.disassemble_word(w, a)
                    marker = " >>>" if a == core.pc else "    "
                    click.echo(f"{marker} 0x{a:04X}: {text}")
                except Exception:
                    click.echo(f"     0x{a:04X}: <fault>")

        elif cmd == "perf":
            click.echo(f"  {core.perf.summary()}")

        elif cmd in ("q", "quit", "exit"):
            click.echo("Exiting debugger.")
            break

        else:
            click.echo(f"  Unknown command: '{cmd}'. Type 'help' for commands.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        cli(prog_name="dspsim")
    except click.ClickException as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nInterrupted.", err=True)
        sys.exit(130)
