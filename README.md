# PSU UART Test Suite

This repository contains test suites for a Power Supply Unit (PSU) UART interface. The tests validate the communication protocol between a host system and a PSU device over a UART connection.

## Files

### `test_psu_uart.py`
- **Purpose**: Tests against the real PSU hardware via UART
- **Features**:
  - Tests power ON/OFF commands
  - Tests voltage setting functionality with boundary validation
  - Tests invalid command handling
  - Includes latency checks
  - Uses real serial communication with the PSU device

### `test_psu_uart_sim.py`
- **Purpose**: Tests against a simulated PSU interface (no hardware required)
- **Features**:
  - Simulates PSU behavior without physical hardware
  - Supports fault simulation modes (slow response, no reply, bad status)
  - All tests from `test_psu_uart.py` are available in simulation mode
  - Enables offline testing and faster test runs

## Environment Variables

Both test files support the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PSU_PORT` | `COM3` | UART port to connect to |
| `PSU_BAUD` | `115200` | Baud rate for UART communication |
| `PSU_SIM` | Not set | Set to `1` to enable simulation mode |
| `PSU_SIM_FAULT` | Not set | Set to `slow`, `noreply`, or `badstatus` for fault simulation |

## Test Coverage

### Basic Commands
- `CMD_OFF` (0x00): Turn PSU output off
- `CMD_ON` (0x01): Turn PSU output on
- `CMD_SET_VOLTAGE` (0x02): Set output voltage (0-1500 V)

### Voltage Validation
- Valid ranges: 0-1500 V
- Invalid ranges: >1500 V (returns error status)

### Fault Conditions
- Invalid commands (0x03, 0x7F, 0xFF) return error status

## Running Tests

### With Real Hardware
```bash
pytest test_psu_uart.py
```

### With Simulation (No Hardware Required)
```bash
PSU_SIM=1 pytest test_psu_uart_sim.py
```

### With Fault Simulation
```bash
PSU_SIM=1 PSU_SIM_FAULT=slow pytest test_psu_uart_sim.py
```

## Test Structure

Each test:
1. Sends a command packet to the PSU
2. Waits for a response (echo + status byte)
3. Validates the response matches expected format
4. Checks response latency is within acceptable limits
5. Records test properties for reporting

## Requirements

- Python 3.x
- pytest
- pyserial (for real hardware tests)
- pytest-reportportal (for advanced reporting)