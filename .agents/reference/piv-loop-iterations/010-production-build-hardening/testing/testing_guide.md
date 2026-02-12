# PIV-010 Testing Guide — Production Build Hardening

## Quick Reference

All validation for this iteration is **compilation-based** + **binary inspection**. No unit test framework is required.

## Test Phases

### Phase 1: Pre-Flight (Before Any Changes)
```bash
# Verify dev build still works before making changes
docker compose -f tools/docker/docker-compose.yml run --rm build
```

### Phase 2: FreeRTOSConfig.h Verification
```bash
# After Task 1: Confirm guard count increased
grep -n "BUILD_PRODUCTION" firmware/core/FreeRTOSConfig.h
# Expected: Lines in sections 1 (task name), 2 (heap), 5 (observability), 9 (queue registry)
# Section 8 (Event Groups) should NOT have BUILD_PRODUCTION — it's unconditionally enabled
```

### Phase 3: CMake LTO Verification
```bash
# After Task 2: Confirm LTO flag is present
grep "INTERPROCEDURAL_OPTIMIZATION" CMakeLists.txt
# Expected: 1 match inside `if(BUILD_PRODUCTION)` block
```

### Phase 4: Docker Compose Verification
```bash
# After Task 3: YAML syntax check
docker compose -f tools/docker/docker-compose.yml config --quiet && echo "YAML OK"

# New service exists
docker compose -f tools/docker/docker-compose.yml config --services | grep build-production

# User mapping present
grep "user:" tools/docker/docker-compose.yml
# Expected: 3 occurrences (build, flash, build-production)
```

### Phase 5: Full Build Verification
```bash
# Dev profile (must not regress)
docker compose -f tools/docker/docker-compose.yml run --rm build

# Production profile
docker compose -f tools/docker/docker-compose.yml run --rm build-production
# Output must include: ">>> PRODUCTION BUILD"

# LTO fallback: If production build fails with "multiple definition" errors,
# remove CMAKE_INTERPROCEDURAL_OPTIMIZATION from CMakeLists.txt and rebuild
```

### Phase 6: Binary Inspection
```bash
# Symbol verification — all must return empty (no matches)
arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep "ai_log_\|telemetry_\|fs_manager_\|watchdog_manager_"

# Size check — UF2 should be < 550 KB
ls -la build-production/firmware/app/firmware.uf2
arm-none-eabi-size build-production/firmware/app/firmware.elf

# Comparison
arm-none-eabi-size build/firmware/app/firmware.elf
```

### Phase 7: Cleanup Verification
```bash
rm -rf build-production
ls build-production/ 2>/dev/null && echo "FAIL" || echo "Clean"
```

## Pass/Fail Criteria

| Check | Pass | Fail |
|-------|------|------|
| Dev builds | Exit 0 | Any error |
| Production builds | Exit 0 + status message | Any error |
| No observability symbols in prod ELF | Empty grep output | Any match |
| UF2 < 550 KB | Size check passes | Over limit |
| Docker YAML valid | `config --quiet` exits 0 | Parse error |
| Event Groups in prod ELF | Present (xEventGroup*) | Absent (would mean SMP broken) |
