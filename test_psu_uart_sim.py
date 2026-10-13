import os
import time

import pytest

try:
    import serial
except ImportError:          # pyserial not installed (fine in simulation mode)
    serial = None

PORT = os.getenv("PSU_PORT", "COM3")
BAUD_RATE = int(os.getenv("PSU_BAUD", "115200"))
MAX_LATENCY_MS = 10
DEBUG = True

# PSU_SIM=1 -> fake PSU, no hardware.  PSU_SIM_FAULT = slow | noreply | badstatus
SIMULATE = True  #os.getenv("PSU_SIM") == "1"
SIM_FAULT = ""   #os.getenv("PSU_SIM_FAULT", "")

CMD_OFF, CMD_ON, CMD_SET_VOLTAGE = 0x00, 0x01, 0x02
STATUS_OK, STATUS_ERROR = 0xAA, 0xFF
MAX_VOLTAGE = 1500

VOLTAGE_CASES = [
    pytest.param(0,     STATUS_OK,      id="min_0"),
    pytest.param(100,   STATUS_OK,      id="normal_100"),
    pytest.param(1500,  STATUS_OK,      id="max_1500"),
    pytest.param(1501,  STATUS_ERROR,   id="above_max_1501"),
]
INVALID_COMMANDS = [0x03, 0x7F, 0xFF]


# ---------------------------------------------------------------- PSU simulator
class FakePSU:
    """Fake serial port with the same methods the tests use."""

    def __init__(self):
        self.output_on = False
        self.voltage = 0
        self._rx = b""

    def close(self):
        pass

    def reset_input_buffer(self):
        self._rx = b""

    def flush(self):
        pass

    def write(self, packet):
        packet = bytes(packet)
        status = self._process(packet)

        if SIM_FAULT == "noreply":
            return
        if SIM_FAULT == "slow":
            time.sleep(0.020)
        if SIM_FAULT == "badstatus":
            status = STATUS_ERROR if status == STATUS_OK else STATUS_OK

        self._rx = packet + bytes([status])      # echo + status

    def read(self, size):
        data, self._rx = self._rx[:size], self._rx[size:]
        return data

    def _process(self, packet):
        if packet == bytes([CMD_OFF]):
            self.output_on = False
            return STATUS_OK
        if packet == bytes([CMD_ON]):
            self.output_on = True
            return STATUS_OK
        if len(packet) == 3 and packet[0] == CMD_SET_VOLTAGE:
            value = int.from_bytes(packet[1:], "little")
            if value <= MAX_VOLTAGE:
                self.voltage = value
                return STATUS_OK
        return STATUS_ERROR


def open_uart():
    """Return the fake PSU in simulation mode, otherwise the real serial port."""
    if SIMULATE:
        return FakePSU()
    if serial is None:
        raise RuntimeError("pyserial is not installed (pip install pyserial)")
    return serial.Serial(PORT, BAUD_RATE, timeout=0.1, write_timeout=1)


# ---------------------------------------------------------------------- helpers
def debug_print(message):
    if DEBUG:
        print(message)


def hex_str(data):
    return data.hex(" ").upper() if data else "NO REPLY"


def voltage_packet(value):
    """0x02, LSB, MSB. to_bytes raises OverflowError if value is not 0..65535."""
    return bytes([CMD_SET_VOLTAGE]) + value.to_bytes(2, "little")


def transact(uart, packet):
    """Send one packet, return (reply, latency_ms)."""
    uart.reset_input_buffer()
    start = time.perf_counter()
    uart.write(packet)
    uart.flush()
    reply = uart.read(len(packet) + 1)  # echo + status byte
    return reply, (time.perf_counter() - start) * 1000


def send_packet(uart, packet, expected_status, record_property):
    expected = packet + bytes([expected_status])
    reply, latency_ms = transact(uart, packet)

    debug_print(f"TX {hex_str(packet)} | RX {hex_str(reply)} | {latency_ms:.3f} ms")
    record_property("tx", hex_str(packet))
    record_property("rx", hex_str(reply))
    record_property("latency_ms", round(latency_ms, 3))

    assert reply == expected, f"Expected {hex_str(expected)}, got {hex_str(reply)}"
    assert latency_ms <= MAX_LATENCY_MS, f"Latency {latency_ms:.3f} ms > {MAX_LATENCY_MS} ms"


def to_safe_state(uart):
    """Output OFF, then 0 V."""
    for packet in (bytes([CMD_OFF]), voltage_packet(0)):
        transact(uart, packet)


# ---------------------------------------------------------------------- fixture
@pytest.fixture(scope="module")
def uart():
    try:
        port = open_uart()
    except Exception as error:
        pytest.exit(f"Cannot open {PORT}: {error}", returncode=2)

    debug_print(f"UART: {'SIMULATION' if SIMULATE else PORT}")
    try:
        to_safe_state(port)
        yield port
    finally:
        to_safe_state(port)
        port.close()


# ------------------------------------------------------------------------ tests
def test_set_on(uart, record_property):
    send_packet(uart, bytes([CMD_ON]), STATUS_OK, record_property)


def test_set_off(uart, record_property):
    send_packet(uart, bytes([CMD_OFF]), STATUS_OK, record_property)


@pytest.mark.parametrize("value, expected_status", VOLTAGE_CASES)
def test_set_voltage(uart, record_property, value, expected_status):
    send_packet(uart, voltage_packet(value), expected_status, record_property)


@pytest.mark.parametrize("command", INVALID_COMMANDS, ids=lambda c: f"cmd_{c:02X}")
def test_invalid_command_returns_ff(uart, record_property, command):
    send_packet(uart, bytes([command]), STATUS_ERROR, record_property)
