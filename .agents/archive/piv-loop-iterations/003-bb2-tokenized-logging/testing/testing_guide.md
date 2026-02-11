# BB2 — Tokenized Logging Subsystem: Testing Guide

**Date**: 2026-02-10
**Test Type**: Manual Testing / Integration Testing
**Purpose**: Validate the complete BB2 tokenized logging pipeline from firmware to host decoder

---

## 🎯 Testing Objective

Verify that the tokenized logging subsystem correctly:
1. Initializes RTT Channel 1 with a binary buffer
2. Encodes log messages as FNV-1a hashed tokens with varint-encoded arguments
3. Transmits packets via SMP-safe critical sections
4. Generates a correct token database via gen_tokens.py
5. Decodes binary packets to JSON via log_decoder.py

---

## Prerequisites

- Docker image `ai-freertos-build` available (built in PIV-002)
- Raspberry Pi Pico W + Pico Probe (for hardware tests only)
- Python 3.8+ installed on host
- OpenOCD with RTT support (for hardware tests only)

---

### **Test 1: File Structure Validation**

**Location**: Project root

**Steps**:
1. Run the file structure validation command:
   ```bash
   test -f firmware/components/logging/include/ai_log.h && \
   test -f firmware/components/logging/include/ai_log_config.h && \
   test -f firmware/components/logging/include/log_varint.h && \
   test -f firmware/components/logging/include/tokens_generated.h && \
   test -f firmware/components/logging/src/log_core.c && \
   test -f firmware/components/logging/src/log_varint.c && \
   test -f firmware/components/logging/CMakeLists.txt && \
   test -f tools/logging/gen_tokens.py && \
   test -f tools/logging/log_decoder.py && \
   test -f tools/logging/requirements.txt && \
   test -f tools/hil/openocd/pico-probe.cfg && \
   test -f tools/hil/openocd/rtt.cfg && \
   echo "ALL FILES PRESENT"
   ```

**Expected Result**:
- ✅ Output: `ALL FILES PRESENT`
- ✅ 12 new files exist in correct locations

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 2: Docker Build Compilation**

**Location**: Project root

**Steps**:
1. Run full clean build inside Docker:
   ```bash
   docker run --rm -v $(pwd):/workspace -w /workspace ai-freertos-build bash -c '
     cd /workspace && rm -rf build && mkdir build && cd build &&
     cmake .. -G Ninja && ninja
   '
   ```
2. Observe the build output for "Generating token database (gen_tokens.py)..." message
3. Verify firmware.elf and firmware.uf2 are produced

**Expected Result**:
- ✅ Build completes with zero errors
- ✅ `gen_tokens.py` runs during build: "Generating token database..."
- ✅ `build/firmware/app/firmware.elf` exists
- ✅ `build/firmware/app/firmware.uf2` exists
- ✅ Binary text size < 500KB

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 3: Symbol Verification**

**Location**: Docker container

**Steps**:
1. Check that logging + RTT symbols are linked into the firmware:
   ```bash
   docker run --rm -v $(pwd):/workspace ai-freertos-build bash -c '
     arm-none-eabi-nm /workspace/build/firmware/app/firmware.elf | \
     grep -i "ai_log_init\|_ai_log_write\|SEGGER_RTT_WriteNoLock\|_SEGGER_RTT\|log_varint"
   '
   ```

**Expected Result**:
- ✅ `ai_log_init` — in .text section
- ✅ `_ai_log_write` — in .text section
- ✅ `SEGGER_RTT_WriteNoLock` — in .text section
- ✅ `_SEGGER_RTT` — in .bss section (RTT control block)
- ✅ `log_varint_encode_i32` — in .text section
- ✅ At least 5 symbols matched

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 4: Token Database Generation**

**Location**: Project root

**Steps**:
1. Run gen_tokens.py manually:
   ```bash
   python3 tools/logging/gen_tokens.py \
     --scan-dirs firmware/ \
     --header firmware/components/logging/include/tokens_generated.h \
     --csv tools/logging/token_database.csv
   ```
2. Inspect the CSV:
   ```bash
   cat tools/logging/token_database.csv
   ```
3. Inspect the generated header:
   ```bash
   cat firmware/components/logging/include/tokens_generated.h
   ```

**Expected Result**:
- ✅ gen_tokens.py completes without errors
- ✅ CSV contains entries for "BUILD_ID: %x" and "LED toggled, state=%d, core=%d"
- ✅ tokens_generated.h has non-zero BUILD_ID (not 0x00000000)
- ✅ AI_LOG_TOKEN_COUNT matches number of unique format strings
- ✅ Running gen_tokens.py twice produces identical output (idempotent)

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 5: Log Decoder Help**

**Location**: Project root

**Steps**:
1. Verify log_decoder.py launches without errors:
   ```bash
   python3 tools/logging/log_decoder.py --help
   ```

**Expected Result**:
- ✅ Usage message printed with --host, --port, --csv options
- ✅ No import errors or exceptions

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 6: FNV-1a Hash Consistency (Python ↔ C)**

**Location**: Project root

**Steps**:
1. Verify Python FNV-1a hash matches expected values:
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, 'tools/logging')
   from gen_tokens import fnv1a_hash
   # Empty string
   assert fnv1a_hash('') == 0x811c9dc5, f'Empty: {fnv1a_hash(\"\"):08x}'
   # Known test strings
   h1 = fnv1a_hash('BUILD_ID: %x')
   h2 = fnv1a_hash('LED toggled, state=%d, core=%d')
   print(f'BUILD_ID hash: 0x{h1:08x}')
   print(f'LED toggled hash: 0x{h2:08x}')
   # Verify these match the CSV
   import csv
   with open('tools/logging/token_database.csv') as f:
       reader = csv.reader(f)
       next(reader)  # skip header
       for row in reader:
           if row[0].startswith('#'):
               continue
           token_hash = int(row[0], 16)
           fmt = row[2]
           expected = fnv1a_hash(fmt)
           assert token_hash == expected, f'Mismatch: {fmt} -> CSV={token_hash:08x} Python={expected:08x}'
   print('All hashes match!')
   "
   ```

**Expected Result**:
- ✅ Empty string hash = 0x811c9dc5 (FNV-1a init value)
- ✅ All CSV hashes match Python computation
- ✅ "All hashes match!" printed

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 7: Hardware RTT Verification (Requires Pico Probe)**

**Location**: Physical hardware setup

**Prerequisites**:
- Pico W connected to Pico Probe via SWD
- firmware.uf2 flashed to Pico W

**Steps**:
1. Flash firmware:
   - Hold BOOTSEL, connect USB, release BOOTSEL
   - Copy `build/firmware/app/firmware.uf2` to the RPI-RP2 drive
2. Start OpenOCD:
   ```bash
   openocd -f tools/hil/openocd/pico-probe.cfg -f tools/hil/openocd/rtt.cfg
   ```
3. In terminal 2, connect to RTT Channel 0 (text):
   ```bash
   nc localhost 9090
   ```
4. In terminal 3, view RTT Channel 1 (binary):
   ```bash
   nc localhost 9091 | xxd | head -20
   ```
5. In terminal 4, run the decoder:
   ```bash
   python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv
   ```

**Expected Result**:
- ✅ Channel 0: Text output including "=== AI-Optimized FreeRTOS v0.1.0 ==="
- ✅ Channel 1: Binary data (4-byte token IDs visible in hex dump)
- ✅ Decoder: JSON lines with "BUILD_ID: ..." as first message
- ✅ Decoder: Periodic "LED toggled, state=..." messages
- ✅ LED still blinks at ~1Hz (no regression)

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 8: Varint Encoding Edge Cases**

**Location**: Project root

**Steps**:
1. Verify varint encoding with known test values:
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, 'tools/logging')
   from log_decoder import decode_varint, zigzag_decode

   # Test varint decoding
   assert decode_varint(bytes([0x00]), 0) == (0, 1)
   assert decode_varint(bytes([0x7F]), 0) == (127, 1)
   assert decode_varint(bytes([0x80, 0x01]), 0) == (128, 2)
   assert decode_varint(bytes([0xAC, 0x02]), 0) == (300, 2)

   # Test zigzag decoding
   assert zigzag_decode(0) == 0
   assert zigzag_decode(1) == -1
   assert zigzag_decode(2) == 1
   assert zigzag_decode(3) == -2
   assert zigzag_decode(4) == 2

   print('All varint tests passed!')
   "
   ```

**Expected Result**:
- ✅ All assertions pass
- ✅ "All varint tests passed!" printed

**Status**: [ ] PASS / [ ] FAIL

---

## 📊 Summary Checklist

| # | Test | Requires HW | Status |
|---|------|-------------|--------|
| 1 | File Structure | No | [ ] |
| 2 | Docker Build | No | [ ] |
| 3 | Symbol Verification | No | [ ] |
| 4 | Token Database | No | [ ] |
| 5 | Decoder Help | No | [ ] |
| 6 | Hash Consistency | No | [ ] |
| 7 | Hardware RTT | Yes | [ ] |
| 8 | Varint Edge Cases | No | [ ] |

**Overall Status**: [ ] ALL PASS / [ ] ISSUES FOUND
