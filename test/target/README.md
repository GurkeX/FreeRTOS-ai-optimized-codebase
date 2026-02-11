# HIL Target Tests

> **Status:** PLANNED — not yet implemented

## Overview

Hardware-in-the-loop (HIL) target tests run on a **real RP2040 (Pico W)** connected via a debug probe (CMSIS-DAP). They validate firmware behavior that cannot be tested on the host: boot sequences, crash handling, RTT channel output, watchdog recovery, and flash persistence across reboots.

### Architecture

```
┌─────────────┐  SWD   ┌──────────────┐  TCP   ┌──────────────────┐
│  Pico W     │◄──────►│  Debug Probe  │◄──────►│  Host PC          │
│  (RP2040)   │        │  (CMSIS-DAP)  │        │                   │
│             │        └──────────────┘        │  OpenOCD :3333    │
│  firmware   │                                 │  RTT     :9090-92 │
│  under test │                                 │                   │
└─────────────┘                                 │  tools/hil/       │
                                                │  ├─ run_hw_test.py│
                                                │  ├─ flash.py      │
                                                │  └─ run_pipeline.py│
                                                └──────────────────┘
```

## Relationship to `tools/hil/`

HIL tests leverage the existing host-side scripts in `tools/hil/`:

| Tool | Role in Testing |
|------|-----------------|
| `flash.py` | Deploy test firmware to the device |
| `run_hw_test.py` | GDB-driven breakpoint assertions |
| `probe_check.py` | Pre-test hardware validation |
| `run_pipeline.py` | Full build → flash → capture → decode cycle |

Test scripts in this directory will **orchestrate** those tools with specific test scenarios and pass/fail criteria.

## Planned Test Scenarios

| Test | What It Validates | Method |
|------|-------------------|--------|
| Boot verification | Firmware reaches `vTaskStartScheduler` | GDB breakpoint via `run_hw_test.py` |
| RTT log output | Tokenized logs appear on RTT Channel 1 | Capture + `log_decoder.py` parse |
| Telemetry stream | Vitals packets arrive on RTT Channel 2 | Capture + `telemetry_manager.py` parse |
| Crash injection | HardFault triggers crash reporter | Trigger fault → reboot → decode crash JSON |
| Watchdog recovery | Stalled task causes clean reboot | Block task → wait for WDT reset → verify scratch regs |
| Config persistence | Writes survive power cycle | Write config → reset → read back via RTT |

## Directory Structure

```
test/target/
├── README.md              ← This file
├── test_boot.py           ← (planned) Boot + scheduler verification
├── test_crash.py          ← (planned) Crash injection + decode
├── test_rtt.py            ← (planned) RTT channel validation
└── conftest.py            ← (planned) Shared fixtures (flash, probe, OpenOCD)
```

## Future: Running HIL Tests

```bash
# (planned) Run all HIL tests (requires connected Pico W + probe)
python3 -m pytest test/target/ --json-report --timeout=60

# (planned) Single scenario
python3 -m pytest test/target/test_boot.py -v
```

All tools support `--json` output for CI integration.
