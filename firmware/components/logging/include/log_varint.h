#ifndef LOG_VARINT_H
#define LOG_VARINT_H

#include <stdint.h>

/**
 * @brief ZigZag-encode a signed 32-bit integer to unsigned.
 *
 * Maps signed values to unsigned so small magnitudes produce small varints:
 *   0 → 0, -1 → 1, 1 → 2, -2 → 3, 2 → 4, ...
 *
 * @param n Signed 32-bit value
 * @return ZigZag-encoded unsigned value
 */
static inline uint32_t log_varint_zigzag_encode(int32_t n) {
    return (uint32_t)((n << 1) ^ (n >> 31));
}

/**
 * @brief Encode an unsigned 32-bit value as a varint into a buffer.
 *
 * Uses Protocol Buffers varint encoding: 7 bits per byte, MSB = continuation.
 * Maximum output: 5 bytes for uint32.
 *
 * @param value  Unsigned value to encode
 * @param buf    Output buffer (must have space for at least 5 bytes)
 * @return Number of bytes written (1-5)
 */
unsigned log_varint_encode_u32(uint32_t value, uint8_t *buf);

/**
 * @brief Encode a signed 32-bit value as a ZigZag varint.
 *
 * Combines ZigZag encoding + varint encoding.
 * Small magnitudes (positive or negative) produce fewer bytes.
 *
 * @param value  Signed value to encode
 * @param buf    Output buffer (must have space for at least 5 bytes)
 * @return Number of bytes written (1-5)
 */
unsigned log_varint_encode_i32(int32_t value, uint8_t *buf);

/**
 * @brief Write a raw 32-bit float (IEEE 754) to buffer, little-endian.
 *
 * No compression — 4 bytes always. Saves CPU cycles vs. varint for floats.
 *
 * @param value  Float to encode
 * @param buf    Output buffer (must have space for 4 bytes)
 * @return Always 4
 */
unsigned log_varint_encode_float(float value, uint8_t *buf);

#endif /* LOG_VARINT_H */
