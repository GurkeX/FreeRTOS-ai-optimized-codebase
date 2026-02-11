#!/usr/bin/env python3
"""
openocd_utils.py — BB3: Shared OpenOCD Utility Layer

Provides OpenOCD path discovery, process management, and TCL RPC client
for all HIL tools. Works in both host (~/.pico-sdk/) and Docker (/opt/openocd/)
environments.

Key components:
    - find_openocd()         — Locate the OpenOCD binary
    - find_openocd_scripts() — Locate the scripts directory (interface/, target/)
    - run_openocd_command()  — Execute OpenOCD one-shot commands
    - start_openocd_server() — Launch persistent OpenOCD server
    - OpenOCDTclClient       — TCL RPC client (port 6666)
"""

import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


# ===========================================================================
# Default Configuration
# ===========================================================================

DEFAULT_PROBE_CFG = "tools/hil/openocd/pico-probe.cfg"
DEFAULT_RTT_CFG = "tools/hil/openocd/rtt.cfg"
DEFAULT_FLASH_CFG = "tools/hil/openocd/flash.cfg"
DEFAULT_ELF_PATH = "build/firmware/app/firmware.elf"
DEFAULT_ADAPTER_SPEED = 5000
TCL_RPC_PORT = 6666
GDB_PORT = 3333
TELNET_PORT = 4444


# ===========================================================================
# Project Root Discovery
# ===========================================================================

def find_project_root() -> str:
    """Find the project root by looking for CMakeLists.txt + firmware/ directory.

    Searches from this file's location upward.
    Returns absolute path to the project root.
    Raises FileNotFoundError if not found.
    """
    current = Path(__file__).resolve().parent
    for _ in range(10):  # Max 10 levels up
        if (current / "CMakeLists.txt").exists() and (current / "firmware").is_dir():
            return str(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise FileNotFoundError(
        "Cannot find project root (expected CMakeLists.txt + firmware/ directory). "
        "Are you running from within the project tree?"
    )


# ===========================================================================
# OpenOCD Path Discovery
# ===========================================================================

def find_openocd() -> str:
    """Find the OpenOCD binary.

    Search order:
        1. OPENOCD_PATH environment variable
        2. shutil.which('openocd') — system PATH (works inside Docker)
        3. ~/.pico-sdk/openocd/*/openocd — Pico VS Code extension
        4. Raise FileNotFoundError with helpful message

    Returns:
        Absolute path to the OpenOCD executable.
    """
    # 1. Environment variable override
    env_path = os.environ.get("OPENOCD_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return os.path.abspath(env_path)

    # 2. System PATH (Docker: /opt/openocd/bin/openocd)
    which_path = shutil.which("openocd")
    if which_path:
        return os.path.abspath(which_path)

    # 3. Pico SDK extension (host): ~/.pico-sdk/openocd/*/openocd
    home = os.path.expanduser("~")
    pico_sdk_pattern = os.path.join(home, ".pico-sdk", "openocd", "*", "openocd")
    matches = sorted(glob.glob(pico_sdk_pattern), reverse=True)
    for match in matches:
        if os.path.isfile(match) and os.access(match, os.X_OK):
            return os.path.abspath(match)

    raise FileNotFoundError(
        "Cannot find OpenOCD binary. Tried:\n"
        "  1. $OPENOCD_PATH environment variable (not set or invalid)\n"
        "  2. 'openocd' in system PATH (not found)\n"
        "  3. ~/.pico-sdk/openocd/*/openocd (not found)\n"
        "\n"
        "Solutions:\n"
        "  - Set OPENOCD_PATH=/path/to/openocd\n"
        "  - Install OpenOCD: sudo apt install openocd\n"
        "  - Use Pico SDK VS Code extension (installs to ~/.pico-sdk/)\n"
        "  - Use Docker: docker compose -f tools/docker/docker-compose.yml run --rm build"
    )


def find_openocd_scripts(openocd_path: str) -> str:
    """Find the OpenOCD scripts directory (contains interface/, target/).

    Search order:
        1. OPENOCD_SCRIPTS environment variable
        2. <openocd_dir>/scripts/ (Pico SDK extension layout)
        3. <openocd_dir>/../share/openocd/scripts/ (standard install layout)
        4. /opt/openocd/share/openocd/scripts/ (Docker layout)
        5. /usr/share/openocd/scripts/ (system install)

    Args:
        openocd_path: Absolute path to the OpenOCD binary.

    Returns:
        Absolute path to the scripts directory.
    """
    # 1. Environment variable override
    env_scripts = os.environ.get("OPENOCD_SCRIPTS")
    if env_scripts and os.path.isdir(env_scripts):
        return os.path.abspath(env_scripts)

    openocd_dir = os.path.dirname(os.path.abspath(openocd_path))

    # 2. Pico SDK extension layout: <dir>/scripts/
    pico_scripts = os.path.join(openocd_dir, "scripts")
    if os.path.isdir(pico_scripts) and os.path.isdir(os.path.join(pico_scripts, "interface")):
        return pico_scripts

    # 3. Standard install layout: <dir>/../share/openocd/scripts/
    standard_scripts = os.path.join(openocd_dir, "..", "share", "openocd", "scripts")
    if os.path.isdir(standard_scripts):
        return os.path.abspath(standard_scripts)

    # 4. Docker layout
    docker_scripts = "/opt/openocd/share/openocd/scripts"
    if os.path.isdir(docker_scripts):
        return docker_scripts

    # 5. System install
    system_scripts = "/usr/share/openocd/scripts"
    if os.path.isdir(system_scripts):
        return system_scripts

    raise FileNotFoundError(
        f"Cannot find OpenOCD scripts directory for binary: {openocd_path}\n"
        "Tried: $OPENOCD_SCRIPTS, <bin>/scripts/, <bin>/../share/openocd/scripts/, "
        "/opt/openocd/share/openocd/scripts/, /usr/share/openocd/scripts/\n"
        "\n"
        "Set OPENOCD_SCRIPTS=/path/to/scripts to override."
    )

def find_arm_toolchain(tool_name: str = "arm-none-eabi-addr2line") -> str:
    """Find an ARM cross-toolchain binary.

    Search order:
        1. ARM_TOOLCHAIN_PATH environment variable + tool_name
        2. shutil.which(tool_name) — system PATH (works inside Docker)
        3. ~/.pico-sdk/toolchain/*/bin/tool_name — Pico VS Code extension
        4. Raise FileNotFoundError with helpful message

    Args:
        tool_name: Binary name to find (default: arm-none-eabi-addr2line).

    Returns:
        Absolute path to the toolchain binary.
    """
    # 1. Environment variable override
    env_path = os.environ.get("ARM_TOOLCHAIN_PATH")
    if env_path:
        candidate = os.path.join(env_path, tool_name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return os.path.abspath(candidate)

    # 2. System PATH
    which_path = shutil.which(tool_name)
    if which_path:
        return os.path.abspath(which_path)

    # 3. Pico SDK extension (host): ~/.pico-sdk/toolchain/*/bin/
    home = os.path.expanduser("~")
    pattern = os.path.join(home, ".pico-sdk", "toolchain", "*", "bin", tool_name)
    matches = sorted(glob.glob(pattern), reverse=True)
    for match in matches:
        if os.path.isfile(match) and os.access(match, os.X_OK):
            return os.path.abspath(match)

    raise FileNotFoundError(
        f"Cannot find {tool_name}. Tried:\n"
        f"  1. $ARM_TOOLCHAIN_PATH + {tool_name} (not set or invalid)\n"
        f"  2. '{tool_name}' in system PATH (not found)\n"
        f"  3. ~/.pico-sdk/toolchain/*/bin/{tool_name} (not found)\n"
        f"\n"
        f"Solutions:\n"
        f"  - Set ARM_TOOLCHAIN_PATH=/path/to/bin\n"
        f"  - Add toolchain to PATH: export PATH=~/.pico-sdk/toolchain/*/bin:$PATH\n"
        f"  - Use Pico SDK VS Code extension (installs to ~/.pico-sdk/)\n"
        f"  - Use Docker (includes arm-none-eabi-gcc suite)"
    )


# ===========================================================================
# Pre-Flight Hardware Diagnostics
# ===========================================================================

def preflight_check(elf_path: str = None, check_elf_age: int = None,
                    verbose: bool = False) -> dict:
    """Run pre-flight hardware checks before HIL operations.

    Validates:
        1. No stale OpenOCD process running on TCL port
        2. Debug Probe connected and RP2040 responding
        3. ELF file exists and is valid (if path provided)
        4. ELF file is fresh (if check_elf_age provided)

    Args:
        elf_path: Optional path to ELF file to validate.
        check_elf_age: Optional max age in seconds for ELF staleness check.
        verbose: Include raw OpenOCD output.

    Returns:
        dict with status, checks passed/failed, and actionable errors.
    """
    start_time = time.monotonic()
    checks = {}
    failed_checks = []

    # Check 1: OpenOCD TCL port status
    if is_openocd_running():
        checks["openocd_clear"] = {
            "pass": False,
            "detail": f"OpenOCD already running on port {TCL_RPC_PORT} (may be intentional)",
            "advisory": True,  # Not a hard failure
        }
        # Don't add to failed_checks — this is advisory only
    else:
        checks["openocd_clear"] = {
            "pass": True,
            "detail": f"No stale OpenOCD on port {TCL_RPC_PORT}",
        }

    # Check 2: Probe connectivity (USB → CMSIS-DAP → SWD → RP2040)
    # Use deferred import to avoid circular dependency
    try:
        from probe_check import check_probe_connectivity
        probe_result = check_probe_connectivity(verbose=False)
        
        if probe_result.get("connected"):
            cores = probe_result.get("cores", [])
            checks["probe_connected"] = {
                "pass": True,
                "detail": f"CMSIS-DAP → RP2040 OK, {len(cores)} cores",
            }
        else:
            checks["probe_connected"] = {
                "pass": False,
                "detail": probe_result.get("error", "Unknown probe error"),
                "suggestions": probe_result.get("suggestions", []),
            }
            failed_checks.append("probe_connected")
    except Exception as e:
        checks["probe_connected"] = {
            "pass": False,
            "detail": f"Probe check failed: {e}",
            "suggestions": ["Verify debug probe is connected", "Check USB cable"],
        }
        failed_checks.append("probe_connected")

    # Check 3: ELF file existence and validity (if path provided)
    if elf_path:
        if not os.path.isfile(elf_path):
            checks["elf_valid"] = {
                "pass": False,
                "detail": f"ELF not found: {elf_path}",
                "suggestions": ["Build firmware first", "Check path is correct"],
            }
            failed_checks.append("elf_valid")
        else:
            # Get ELF file info
            elf_stat = os.stat(elf_path)
            elf_size_mb = elf_stat.st_size / (1024 * 1024)
            elf_age_s = time.time() - elf_stat.st_mtime
            
            detail = f"{os.path.basename(elf_path)}, {elf_size_mb:.1f}MB, age {int(elf_age_s)}s"
            
            # Check ELF age if threshold provided
            if check_elf_age and elf_age_s > check_elf_age:
                checks["elf_valid"] = {
                    "pass": False,
                    "detail": f"{detail} (STALE: >{check_elf_age}s)",
                    "suggestions": [
                        "Rebuild firmware",
                        f"ELF is {int(elf_age_s)}s old, threshold is {check_elf_age}s",
                    ],
                }
                failed_checks.append("elf_valid")
            else:
                checks["elf_valid"] = {
                    "pass": True,
                    "detail": detail,
                }

    duration_ms = int((time.monotonic() - start_time) * 1000)

    # Determine overall status
    status = "pass" if not failed_checks else "fail"

    result = {
        "status": status,
        "tool": "preflight_check",
        "checks": checks,
        "failed_checks": failed_checks,
        "duration_ms": duration_ms,
    }

    return result


# ===========================================================================
# RTT Utilities
# ===========================================================================

# Boot markers from firmware/app/main.c
BOOT_MARKER_INIT = "[system_init]"
BOOT_MARKER_VERSION = "=== AI-Optimized FreeRTOS"
BOOT_MARKER_SCHEDULER = "Starting FreeRTOS scheduler"


def wait_for_rtt_ready(tcl_port: int = TCL_RPC_PORT,
                       timeout: int = 15,
                       poll_interval: float = 0.5,
                       verbose: bool = False) -> dict:
    """Wait for OpenOCD to discover the SEGGER RTT control block.

    Polls the OpenOCD TCL RPC with 'rtt channels' until channels are
    reported (indicating the control block was found in SRAM), or timeout.

    The RTT control block is placed in SRAM by firmware during early
    initialization. OpenOCD scans the range configured in rtt.cfg
    (0x20000000-0x20042000) for the "SEGGER RTT" magic string.

    Args:
        tcl_port: OpenOCD TCL RPC port (default: 6666).
        timeout: Maximum wait time in seconds (default: 15).
        poll_interval: Time between polls in seconds (default: 0.5).
        verbose: Print polling progress to stderr.

    Returns:
        dict with:
            ready (bool): True if RTT channels were discovered.
            channels (list): List of channel info if discovered.
            elapsed_seconds (float): Time spent waiting.
            error (str or None): Error message if failed.
    """
    start_time = time.monotonic()
    deadline = start_time + timeout
    
    # First check if OpenOCD is even running
    if not is_openocd_running(tcl_port):
        return {
            "ready": False,
            "channels": [],
            "elapsed_seconds": 0.0,
            "error": f"OpenOCD not running on port {tcl_port}",
        }
    
    # Create TCL client (reuse across polls)
    try:
        client = OpenOCDTclClient(port=tcl_port, timeout=5)
    except Exception as e:
        return {
            "ready": False,
            "channels": [],
            "elapsed_seconds": time.monotonic() - start_time,
            "error": f"Failed to connect to OpenOCD TCL: {e}",
        }
    
    try:
        while time.monotonic() < deadline:
            try:
                # Query RTT channels
                response = client.send("rtt channels")
                
                # Check if response indicates channels are available
                # Responses look like:
                #   "Terminal Logger Telemetry" (channel names)
                #   or empty/error if not found yet
                if response and "error" not in response.lower():
                    # Parse channel info (simple check: non-empty response)
                    channels = response.split()
                    if channels:
                        elapsed = time.monotonic() - start_time
                        if verbose:
                            print(f"\n  RTT: Control block found! ({elapsed:.1f}s)", file=sys.stderr)
                        client.close()
                        return {
                            "ready": True,
                            "channels": channels,
                            "elapsed_seconds": elapsed,
                            "error": None,
                        }
                
                # Not ready yet
                if verbose:
                    elapsed = time.monotonic() - start_time
                    print(f"\r  RTT: Scanning for control block... ({elapsed:.1f}s)", 
                          end="", file=sys.stderr)
                
            except Exception as e:
                # TCL command failed — RTT not ready
                if verbose:
                    elapsed = time.monotonic() - start_time
                    print(f"\r  RTT: Scanning for control block... ({elapsed:.1f}s)", 
                          end="", file=sys.stderr)
            
            time.sleep(poll_interval)
        
        # Timeout
        client.close()
        elapsed = time.monotonic() - start_time
        if verbose:
            print(f"\n  RTT: Timeout after {elapsed:.1f}s", file=sys.stderr)
        
        return {
            "ready": False,
            "channels": [],
            "elapsed_seconds": elapsed,
            "error": f"RTT control block not found within {timeout}s",
        }
    
    except Exception as e:
        client.close()
        return {
            "ready": False,
            "channels": [],
            "elapsed_seconds": time.monotonic() - start_time,
            "error": f"RTT polling error: {e}",
        }


def wait_for_boot_marker(rtt_port: int = 9090,
                         marker: str = BOOT_MARKER_SCHEDULER,
                         timeout: int = 15,
                         verbose: bool = False) -> dict:
    """Wait for a specific boot log marker on RTT Channel 0.

    Connects to RTT Channel 0 (text/printf) and reads until the
    specified marker string appears in the output, indicating the
    firmware has reached that initialization stage.

    Default marker is "Starting FreeRTOS scheduler" which is the
    last printf before the scheduler starts — indicating full boot.

    Args:
        rtt_port: RTT Channel 0 TCP port (default: 9090).
        marker: String to search for in the output stream.
        timeout: Maximum wait time in seconds (default: 15).
        verbose: Print captured output to stderr in real-time.

    Returns:
        dict with:
            found (bool): True if marker was found.
            boot_log (str): All captured text up to and including the marker.
            elapsed_seconds (float): Time spent waiting.
            error (str or None): Error message if failed.
    """
    start_time = time.monotonic()
    deadline = start_time + timeout
    boot_log = ""
    sock = None
    
    # Retry connection (port may not be ready immediately)
    connection_timeout = min(5, timeout)
    conn_deadline = start_time + connection_timeout
    
    while time.monotonic() < conn_deadline:
        try:
            sock = socket.create_connection(("localhost", rtt_port), timeout=2)
            sock.settimeout(1.0)
            break
        except (ConnectionRefusedError, OSError, socket.timeout):
            time.sleep(0.5)
    
    if sock is None:
        return {
            "found": False,
            "boot_log": "",
            "elapsed_seconds": time.monotonic() - start_time,
            "error": f"Failed to connect to RTT Channel 0 (port {rtt_port})",
        }
    
    try:
        # Read and accumulate data until marker is found or timeout
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    # Connection closed
                    break
                
                # Decode as UTF-8 text
                text = chunk.decode("utf-8", errors="replace")
                boot_log += text
                
                if verbose:
                    print(text, end="", file=sys.stderr)
                
                # Check if marker is in the accumulated log
                if marker in boot_log:
                    sock.close()
                    elapsed = time.monotonic() - start_time
                    return {
                        "found": True,
                        "boot_log": boot_log,
                        "elapsed_seconds": elapsed,
                        "error": None,
                    }
            
            except socket.timeout:
                # No data received in this iteration, continue
                continue
            except Exception as e:
                sock.close()
                return {
                    "found": False,
                    "boot_log": boot_log,
                    "elapsed_seconds": time.monotonic() - start_time,
                    "error": f"Socket error: {e}",
                }
        
        # Timeout or connection closed
        sock.close()
        elapsed = time.monotonic() - start_time
        
        # Advisory note if we got no data
        advisory = None
        if not boot_log.strip():
            advisory = "No data received — firmware may have already booted before capture started"
        
        return {
            "found": False,
            "boot_log": boot_log,
            "elapsed_seconds": elapsed,
            "error": f"Boot marker '{marker}' not found within {timeout}s",
            "advisory": advisory,
        }
    
    except Exception as e:
        if sock:
            sock.close()
        return {
            "found": False,
            "boot_log": boot_log,
            "elapsed_seconds": time.monotonic() - start_time,
            "error": f"Unexpected error: {e}",
        }


# ===========================================================================
# OpenOCD Process Management
# ===========================================================================

def run_openocd_command(args: list, timeout: int = 30,
                        openocd_path: str = None, scripts_dir: str = None) -> dict:
    """Run OpenOCD as a one-shot command (e.g., program ... exit).

    Args:
        args: Additional arguments for OpenOCD (e.g., ['-c', 'init; targets; shutdown']).
        timeout: Maximum execution time in seconds.
        openocd_path: Path to OpenOCD binary (auto-detected if None).
        scripts_dir: Path to scripts directory (auto-detected if None).

    Returns:
        dict with keys: exit_code, stdout, stderr, duration_ms
    """
    if openocd_path is None:
        openocd_path = find_openocd()
    if scripts_dir is None:
        scripts_dir = find_openocd_scripts(openocd_path)

    cmd = [openocd_path, "-s", scripts_dir] + args

    start_time = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.monotonic() - start_time) * 1000)
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"OpenOCD timed out after {timeout}s",
            "duration_ms": duration_ms,
        }
    except FileNotFoundError:
        return {
            "exit_code": -2,
            "stdout": "",
            "stderr": f"OpenOCD binary not found: {openocd_path}",
            "duration_ms": 0,
        }


def start_openocd_server(probe_cfg: str = None, extra_cfgs: list = None,
                          gdb_port: int = GDB_PORT, tcl_port: int = TCL_RPC_PORT,
                          telnet_port: int = TELNET_PORT,
                          openocd_path: str = None, scripts_dir: str = None,
                          post_init_cmds: list = None) -> subprocess.Popen:
    """Start OpenOCD as a persistent background server.

    Args:
        probe_cfg: Path to probe config (default: pico-probe.cfg in project).
        extra_cfgs: Additional config files to load (e.g., rtt.cfg).
        gdb_port: GDB server port (default: 3333).
        tcl_port: TCL RPC port (default: 6666).
        telnet_port: Telnet port (default: 4444).
        openocd_path: Path to OpenOCD binary (auto-detected if None).
        scripts_dir: Path to scripts directory (auto-detected if None).
        post_init_cmds: List of OpenOCD commands to run after init
            (e.g., ["rtt start", "rtt server start 9090 0"]).

    Returns:
        subprocess.Popen process. Caller is responsible for termination.
    """
    if openocd_path is None:
        openocd_path = find_openocd()
    if scripts_dir is None:
        scripts_dir = find_openocd_scripts(openocd_path)

    if probe_cfg is None:
        try:
            project_root = find_project_root()
            probe_cfg = os.path.join(project_root, DEFAULT_PROBE_CFG)
        except FileNotFoundError:
            probe_cfg = DEFAULT_PROBE_CFG

    cmd = [
        openocd_path,
        "-s", scripts_dir,
        "-f", probe_cfg,
    ]

    if extra_cfgs:
        for cfg in extra_cfgs:
            cmd.extend(["-f", cfg])

    cmd.extend([
        "-c", f"gdb_port {gdb_port}",
        "-c", f"tcl_port {tcl_port}",
        "-c", f"telnet_port {telnet_port}",
    ])

    # Post-init commands (e.g., rtt start, rtt server) must run after init
    if post_init_cmds:
        init_chain = "init; " + "; ".join(post_init_cmds)
        cmd.extend(["-c", init_chain])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc


def wait_for_openocd_ready(port: int = TCL_RPC_PORT, timeout: int = 10) -> bool:
    """Wait for OpenOCD TCL RPC port to accept connections.

    Args:
        port: TCP port to poll (default: 6666).
        timeout: Maximum wait time in seconds.

    Returns:
        True if port is accepting connections, False on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection(("localhost", port), timeout=1)
            sock.close()
            return True
        except (ConnectionRefusedError, OSError, socket.timeout):
            time.sleep(0.2)
    return False


def is_openocd_running(port: int = TCL_RPC_PORT) -> bool:
    """Check if OpenOCD is already running by testing the TCL RPC port.

    Args:
        port: TCP port to check (default: 6666).

    Returns:
        True if port is accepting connections.
    """
    try:
        sock = socket.create_connection(("localhost", port), timeout=1)
        sock.close()
        return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


# ===========================================================================
# TCL RPC Client
# ===========================================================================

class OpenOCDTclClient:
    """Lightweight TCL RPC client for OpenOCD.

    Protocol: Send command + \\x1a terminator, receive response + \\x1a.
    Default port: 6666 (OpenOCD TCL RPC).

    Usage:
        client = OpenOCDTclClient()
        client.send("targets")
        values = client.read_memory(0xd0000004, width=32, count=1)
        client.close()
    """

    TERMINATOR = b"\x1a"  # ASCII SUB (Ctrl-Z)

    def __init__(self, host: str = "localhost", port: int = TCL_RPC_PORT,
                 timeout: int = 10):
        """Connect to OpenOCD TCL RPC server.

        Args:
            host: OpenOCD hostname (default: localhost).
            port: TCL RPC port (default: 6666).
            timeout: Socket timeout in seconds.
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = socket.create_connection((host, port), timeout=timeout)

    def send(self, cmd: str) -> str:
        """Send a TCL command and return the response.

        Args:
            cmd: TCL command string (e.g., "targets", "mdw 0xd0000004").

        Returns:
            Response string from OpenOCD (stripped of terminator and whitespace).

        Raises:
            ConnectionError: If OpenOCD closes the connection.
        """
        self.sock.sendall((cmd + "\x1a").encode("utf-8"))
        data = b""
        while not data.endswith(self.TERMINATOR):
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("OpenOCD closed TCL RPC connection")
            data += chunk
        return data[:-1].decode("utf-8").strip()

    def read_memory(self, address: int, width: int = 32, count: int = 1) -> list:
        """Read memory from the target.

        Uses OpenOCD's 'read_memory' TCL command which returns a Tcl list
        of hex values (e.g., "0xdeadbeef 0x12345678").

        Args:
            address: Memory address to read.
            width: Access width in bits (8, 16, or 32).
            count: Number of values to read.

        Returns:
            List of integer values.
        """
        response = self.send(f"read_memory 0x{address:08x} {width} {count}")
        if not response:
            return []
        # Parse Tcl list of hex values
        values = []
        for token in response.split():
            try:
                values.append(int(token, 0))  # Handles 0x prefix and bare hex
            except ValueError:
                continue
        return values

    def write_memory(self, address: int, width: int, values: list) -> None:
        """Write memory on the target.

        Args:
            address: Memory address to write.
            width: Access width in bits (8, 16, or 32).
            values: List of integer values to write.
        """
        # Format values as a Tcl list
        val_str = " ".join(f"0x{v:x}" for v in values)
        self.send(f"write_memory 0x{address:08x} {width} {{{val_str}}}")

    def halt(self) -> str:
        """Halt the target CPU.

        Returns:
            OpenOCD response string.
        """
        return self.send("halt")

    def resume(self) -> str:
        """Resume target CPU execution.

        Returns:
            OpenOCD response string.
        """
        return self.send("resume")

    def reset(self, mode: str = "run") -> str:
        """Reset the target.

        Args:
            mode: Reset mode — 'run' (default), 'halt', or 'init'.

        Returns:
            OpenOCD response string.
        """
        return self.send(f"reset {mode}")

    def close(self) -> None:
        """Close the TCL RPC connection."""
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ===========================================================================
# Self-Test (no hardware needed)
# ===========================================================================

def _self_test():
    """Run basic self-tests without hardware.

    Tests path discovery, module imports, and class instantiation.
    """
    print("=" * 60)
    print("openocd_utils.py — Self-Test (no hardware required)")
    print("=" * 60)

    # Test 1: Project root discovery
    print("\n[1/5] Project root discovery...")
    try:
        root = find_project_root()
        print(f"  ✓ Project root: {root}")
    except FileNotFoundError as e:
        print(f"  ✗ {e}")

    # Test 2: OpenOCD binary discovery
    print("\n[2/5] OpenOCD binary discovery...")
    try:
        openocd = find_openocd()
        print(f"  ✓ OpenOCD binary: {openocd}")
    except FileNotFoundError as e:
        print(f"  ✗ Not found (expected in CI/Docker-less environments)")
        print(f"    {e.args[0].split(chr(10))[0]}")
        openocd = None

    # Test 3: Scripts directory discovery
    print("\n[3/5] OpenOCD scripts directory discovery...")
    if openocd:
        try:
            scripts = find_openocd_scripts(openocd)
            print(f"  ✓ Scripts dir: {scripts}")
        except FileNotFoundError as e:
            print(f"  ✗ Not found: {e.args[0].split(chr(10))[0]}")
    else:
        print("  ⊘ Skipped (no OpenOCD binary found)")

    # Test 4: TCL RPC client class
    print("\n[4/5] TCL RPC client class instantiation...")
    try:
        # Just verify the class can be imported and attributes exist
        client_cls = OpenOCDTclClient
        assert hasattr(client_cls, "TERMINATOR")
        assert client_cls.TERMINATOR == b"\x1a"
        assert hasattr(client_cls, "send")
        assert hasattr(client_cls, "read_memory")
        assert hasattr(client_cls, "write_memory")
        assert hasattr(client_cls, "halt")
        assert hasattr(client_cls, "resume")
        assert hasattr(client_cls, "reset")
        assert hasattr(client_cls, "close")
        print("  ✓ OpenOCDTclClient class verified (all methods present)")
    except AssertionError:
        print("  ✗ OpenOCDTclClient class incomplete")

    # Test 5: Constants
    print("\n[5/6] Constants verification...")
    assert TCL_RPC_PORT == 6666
    assert GDB_PORT == 3333
    assert DEFAULT_ADAPTER_SPEED == 5000
    assert DEFAULT_ELF_PATH == "build/firmware/app/firmware.elf"
    print(f"  ✓ TCL_RPC_PORT={TCL_RPC_PORT}, GDB_PORT={GDB_PORT}")
    print(f"  ✓ DEFAULT_ADAPTER_SPEED={DEFAULT_ADAPTER_SPEED}")
    print(f"  ✓ DEFAULT_ELF_PATH={DEFAULT_ELF_PATH}")

    # Test 6: ARM toolchain discovery
    print("\n[6/10] ARM toolchain discovery...")
    try:
        addr2line = find_arm_toolchain("arm-none-eabi-addr2line")
        print(f"  ✓ addr2line binary: {addr2line}")
    except FileNotFoundError as e:
        print(f"  ✗ Not found (expected in CI/Docker-less environments)")
        print(f"    {e.args[0].split(chr(10))[0]}")

    # Test 7: preflight_check function
    print("\n[7/10] preflight_check function...")
    try:
        assert callable(preflight_check)
        print(f"  ✓ preflight_check() function is callable")
    except (AssertionError, NameError):
        print(f"  ✗ preflight_check() function not found")

    # Test 8: wait_for_rtt_ready function
    print("\n[8/10] wait_for_rtt_ready function...")
    try:
        assert callable(wait_for_rtt_ready)
        print(f"  ✓ wait_for_rtt_ready() function is callable")
    except (AssertionError, NameError):
        print(f"  ✗ wait_for_rtt_ready() function not found")

    # Test 9: wait_for_boot_marker function
    print("\n[9/10] wait_for_boot_marker function...")
    try:
        assert callable(wait_for_boot_marker)
        print(f"  ✓ wait_for_boot_marker() function is callable")
    except (AssertionError, NameError):
        print(f"  ✗ wait_for_boot_marker() function not found")

    # Test 10: Boot marker constants
    print("\n[10/10] Boot marker constants verification...")
    try:
        assert BOOT_MARKER_INIT == "[system_init]"
        assert BOOT_MARKER_VERSION == "=== AI-Optimized FreeRTOS"
        assert BOOT_MARKER_SCHEDULER == "Starting FreeRTOS scheduler"
        print(f"  ✓ BOOT_MARKER_INIT={BOOT_MARKER_INIT}")
        print(f"  ✓ BOOT_MARKER_VERSION={BOOT_MARKER_VERSION}")
        print(f"  ✓ BOOT_MARKER_SCHEDULER={BOOT_MARKER_SCHEDULER}")
    except (AssertionError, NameError):
        print(f"  ✗ Boot marker constants not defined correctly")

    print("\n" + "=" * 60)
    print("Self-test complete.")
    print("=" * 60)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print("Usage: python3 tools/hil/openocd_utils.py --self-test")
        print("\nThis module provides shared OpenOCD utilities for HIL tools.")
        print("Run --self-test to verify path discovery and class structure.")
