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
    print("\n[5/5] Constants verification...")
    assert TCL_RPC_PORT == 6666
    assert GDB_PORT == 3333
    assert DEFAULT_ADAPTER_SPEED == 5000
    assert DEFAULT_ELF_PATH == "build/firmware/app/firmware.elf"
    print(f"  ✓ TCL_RPC_PORT={TCL_RPC_PORT}, GDB_PORT={GDB_PORT}")
    print(f"  ✓ DEFAULT_ADAPTER_SPEED={DEFAULT_ADAPTER_SPEED}")
    print(f"  ✓ DEFAULT_ELF_PATH={DEFAULT_ELF_PATH}")

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
