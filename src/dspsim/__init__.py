# src/dspsim/__init__.py
from .core import FunctionalSimulator
from .core_cycle import Core as CycleSimulator

__all__ = ["FunctionalSimulator", "CycleSimulator"]
__version__ = "0.2.1"
