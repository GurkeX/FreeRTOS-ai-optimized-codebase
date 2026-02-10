#ifndef AI_LOG_CONFIG_H
#define AI_LOG_CONFIG_H

/* =========================================================================
 * RTT Channel Configuration
 * ========================================================================= */

/** RTT channel for binary tokenized log data.
 *  Channel 0 is reserved for text stdio (printf via pico_stdio_rtt).
 *  Channel 1 is our binary tokenized log channel. */
#define AI_LOG_RTT_CHANNEL          1

/** Size of the RTT up-buffer for tokenized logs (bytes).
 *  Each packet is 5-15 bytes → 2048B holds ~150-400 messages before
 *  the host must drain. Larger = more crash-resilient black box. */
#define AI_LOG_RTT_BUFFER_SIZE      2048

/** RTT buffer mode.
 *  NO_BLOCK_SKIP = drop entire message if buffer full (zero latency).
 *  NO_BLOCK_TRIM = write partial message if buffer full (not recommended).
 *  BLOCK_IF_FIFO_FULL = block until space (NEVER use in RT system). */
#define AI_LOG_RTT_MODE             SEGGER_RTT_MODE_NO_BLOCK_SKIP

/* =========================================================================
 * Log Levels
 * ========================================================================= */

/** Log levels — higher number = more verbose.
 *  Level filtering is compile-time via AI_LOG_LEVEL_MIN. */
#define AI_LOG_LEVEL_ERROR          0
#define AI_LOG_LEVEL_WARN           1
#define AI_LOG_LEVEL_INFO           2
#define AI_LOG_LEVEL_DEBUG          3

/** Minimum log level to compile in. Messages below this are compiled out.
 *  Override in CMakeLists.txt: target_compile_definitions(... AI_LOG_LEVEL_MIN=0) */
#ifndef AI_LOG_LEVEL_MIN
#define AI_LOG_LEVEL_MIN            AI_LOG_LEVEL_DEBUG  /* Include all levels by default */
#endif

/* =========================================================================
 * Packet Format Constants
 * ========================================================================= */

/** Maximum number of arguments per log call.
 *  Each arg is varint-encoded (1-5 bytes for int32, 4 bytes for float).
 *  Max packet size = 4 (token) + 1 (level) + 1 (arg count) + 8*5 = 46 bytes. */
#define AI_LOG_MAX_ARGS             8

/** Maximum packet size in bytes (stack-allocated per log call). */
#define AI_LOG_MAX_PACKET_SIZE      64

#endif /* AI_LOG_CONFIG_H */
