#include "log_varint.h"
#include <string.h>  /* memcpy */

unsigned log_varint_encode_u32(uint32_t value, uint8_t *buf) {
    unsigned i = 0;
    while (value > 0x7F) {
        buf[i++] = (uint8_t)(value | 0x80);  /* Set continuation bit */
        value >>= 7;
    }
    buf[i++] = (uint8_t)value;  /* Last byte, no continuation bit */
    return i;
}

unsigned log_varint_encode_i32(int32_t value, uint8_t *buf) {
    return log_varint_encode_u32(log_varint_zigzag_encode(value), buf);
}

unsigned log_varint_encode_float(float value, uint8_t *buf) {
    /* Raw IEEE 754 little-endian copy — no compression for floats.
     * RP2040 is little-endian, so memcpy is correct byte order. */
    memcpy(buf, &value, sizeof(float));
    return sizeof(float);
}
