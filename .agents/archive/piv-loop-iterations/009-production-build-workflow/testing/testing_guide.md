# PIV-009 Testing Guide — Production Build Workflow

## Test Matrix

| Test | Command | Expected Result |
|------|---------|----------------|
| File guards exist | `grep -l 'BUILD_PRODUCTION' CMakeLists.txt firmware/CMakeLists.txt firmware/app/CMakeLists.txt firmware/app/main.c firmware/core/FreeRTOSConfig.h` | All 5 files listed |
| Dev build regression | `cmake -B build -G Ninja && ninja -C build` | Zero errors |
| Production configure | `cmake -B build-production -DBUILD_PRODUCTION=ON -DCMAKE_BUILD_TYPE=MinSizeRel -G Ninja` | Shows `>>> PRODUCTION BUILD` |
| Production compile | `ninja -C build-production` | Zero errors, zero warnings |
| UF2 exists | `ls build-production/firmware/app/firmware.uf2` | File exists |
| ELF valid | `file build-production/firmware/app/firmware.elf` | `ELF 32-bit LSB executable, ARM` |
| Size smaller | `arm-none-eabi-size build/firmware/app/firmware.elf build-production/firmware/app/firmware.elf` | Production text+bss < dev |
| No lib/ changes | `git diff --name-only \| grep '^lib/'` | Empty |
