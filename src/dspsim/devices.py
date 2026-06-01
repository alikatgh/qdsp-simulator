# src/dspsim/devices.py
"""Memory-mapped I/O peripheral models: UART and Timer."""

from __future__ import annotations

from .bitutil import u32
from .bus import MMIO


class UART(MMIO):
    """Simple memory-mapped UART transmitter/receiver.

    Register map (offsets from base):
        0x00  TX_DATA   (W)  — write a byte to transmit
        0x04  RX_DATA   (R)  — read next received byte (0 if empty)
        0x08  STATUS    (R)  — bit 0: TX ready, bit 1: RX data available
    """

    def __init__(self):
        self.tx_buf: list[int] = []  # transmitted bytes
        self.rx_buf: list[int] = []  # bytes available to read
        self._base = 0  # set when mapped

    def inject_rx(self, data: bytes) -> None:
        """Feed bytes into the receive buffer (for test harnesses)."""
        self.rx_buf.extend(data)

    @property
    def tx_bytes(self) -> bytes:
        return bytes(self.tx_buf)

    @property
    def tx_string(self) -> str:
        return self.tx_bytes.decode("ascii", errors="replace")

    def read32(self, addr: int) -> int:
        off = addr & 0xF
        if off == 0x04:  # RX_DATA
            if self.rx_buf:
                return self.rx_buf.pop(0) & 0xFF
            return 0
        if off == 0x08:  # STATUS
            tx_ready = 1  # always ready (unbuffered sim)
            rx_avail = 1 if self.rx_buf else 0
            return tx_ready | (rx_avail << 1)
        return 0

    def write32(self, addr: int, value: int) -> None:
        off = addr & 0xF
        if off == 0x00:  # TX_DATA
            self.tx_buf.append(value & 0xFF)


class Timer(MMIO):
    """Simple countdown timer with auto-reload.

    Register map (offsets from base):
        0x00  CTRL      (RW) — bit 0: enable, bit 1: auto-reload
        0x04  LOAD      (RW) — reload / initial value
        0x08  COUNT     (R)  — current count
        0x0C  STATUS    (R)  — bit 0: expired flag (write 1 to clear)
    """

    def __init__(self):
        self.ctrl = 0
        self.load_val = 0
        self.count = 0
        self.expired = False

    @property
    def enabled(self) -> bool:
        return bool(self.ctrl & 1)

    @property
    def auto_reload(self) -> bool:
        return bool(self.ctrl & 2)

    def tick(self) -> None:
        """Advance the timer by one cycle. Call once per simulator cycle."""
        if not self.enabled:
            return
        if self.count > 0:
            self.count -= 1
        if self.count == 0:
            self.expired = True
            if self.auto_reload:
                self.count = self.load_val

    def read32(self, addr: int) -> int:
        off = addr & 0xF
        if off == 0x00:
            return self.ctrl
        if off == 0x04:
            return self.load_val
        if off == 0x08:
            return u32(self.count)
        if off == 0x0C:
            return 1 if self.expired else 0
        return 0

    def write32(self, addr: int, value: int) -> None:
        off = addr & 0xF
        if off == 0x00:
            self.ctrl = value & 0x3
            if self.enabled and self.count == 0:
                self.count = self.load_val
        elif off == 0x04:
            self.load_val = u32(value)
        elif off == 0x0C:
            if value & 1:
                self.expired = False
