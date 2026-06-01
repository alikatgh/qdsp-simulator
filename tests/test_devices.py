# tests/test_devices.py
"""Tests for MMIO peripherals: UART and Timer."""

from dspsim.bus import Bus
from dspsim.devices import UART, Timer


class TestUART:
    def test_transmit(self):
        uart = UART()
        uart.write32(0x00, ord('H'))
        uart.write32(0x00, ord('i'))
        assert uart.tx_string == "Hi"

    def test_receive(self):
        uart = UART()
        uart.inject_rx(b"AB")
        assert uart.read32(0x04) == ord('A')
        assert uart.read32(0x04) == ord('B')
        assert uart.read32(0x04) == 0  # empty

    def test_status_rx_available(self):
        uart = UART()
        status = uart.read32(0x08)
        assert status & 1  # TX always ready
        assert not (status & 2)  # no RX data
        uart.inject_rx(b"X")
        status = uart.read32(0x08)
        assert status & 2  # RX data available

    def test_mmio_on_bus(self):
        bus = Bus()
        uart = UART()
        bus.map_mmio(0xFFFF0000, 16, uart)
        bus.write32(0xFFFF0000, ord('Z'))
        assert uart.tx_string == "Z"
        uart.inject_rx(b"Q")
        assert bus.read32(0xFFFF0004) == ord('Q')


class TestTimer:
    def test_countdown(self):
        t = Timer()
        t.write32(0x04, 5)  # LOAD = 5
        t.write32(0x00, 1)  # CTRL = enable
        for _ in range(5):
            assert not t.expired
            t.tick()
        assert t.expired
        assert t.read32(0x0C) == 1

    def test_clear_expired(self):
        t = Timer()
        t.write32(0x04, 1)
        t.write32(0x00, 1)
        t.tick()
        assert t.expired
        t.write32(0x0C, 1)  # clear
        assert not t.expired

    def test_auto_reload(self):
        t = Timer()
        t.write32(0x04, 3)  # LOAD = 3
        t.write32(0x00, 3)  # CTRL = enable + auto-reload
        for _ in range(3):
            t.tick()
        assert t.expired
        assert t.read32(0x08) == 3  # reloaded

    def test_disabled_no_count(self):
        t = Timer()
        t.write32(0x04, 5)
        # don't enable
        for _ in range(10):
            t.tick()
        assert not t.expired
        assert t.read32(0x08) == 0
