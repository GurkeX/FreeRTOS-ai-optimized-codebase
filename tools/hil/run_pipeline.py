#!/usr/bin/env python3
"""
run_pipeline.py — BB3: End-to-End HIL Pipeline Orchestrator

Chains: Docker build → SWD flash → RTT capture & decode → aggregate JSON report.

This script runs on the HOST (not inside Docker). The build step uses Docker
for hermetic compilation, while flash/RTT steps use the host's OpenOCD with
direct USB access to the Debug Probe.

Usage:
    python3 tools/hil/run_pipeline.py --json
    python3 tools/hil/run_pipeline.py --skip-build --json
    python3 tools/hil/run_pipeline.py --skip-build --skip-flash --rtt-duration 10 --json
"""

import argparse
import atexit
import json
import os
import signal
import socket
import subprocess
import sys
import time

# Allow running from project root or tools/hil/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openocd_utils import (
    DEFAULT_ELF_PATH,
    DEFAULT_PROBE_CFG,
    DEFAULT_RTT_CFG,
    find_openocd,
    find_openocd_scripts,
    find_project_root,
    is_openocd_running,
    start_openocd_server,
    wait_for_openocd_ready,
    wait_for_rtt_ready,
    TCL_RPC_PORT,
)


# ===========================================================================
# Global process tracking (for cleanup)
# ===========================================================================

_openocd_proc = None


def _cleanup():
    """Kill any OpenOCD process we started."""
    global _openocd_proc
    if _openocd_proc is not None:
        try:
            _openocd_proc.terminate()
            _openocd_proc.wait(timeout=5)
        except Exception:
            try:
                _openocd_proc.kill()
            except Exception:
                pass
        _openocd_proc = None


atexit.register(_cleanup)


def _signal_handler(signum, frame):
    _cleanup()
    sys.exit(128 + signum)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ===========================================================================
# Pipeline Stages
# ===========================================================================

def stage_build(project_root: str, verbose: bool = False) -> dict:
    """Build firmware using Docker.

    Runs the hermetic Docker build container.

    Args:
        project_root: Absolute path to the project root.
        verbose: Print build output.

    Returns:
        dict with stage result.
    """
    start = time.monotonic()

    # Check if docker/docker-compose is available
    docker_compose = None
    for cmd in ["docker-compose", "docker"]:
        if cmd == "docker":
            # Try "docker compose" (v2 plugin)
            try:
                subprocess.run(
                    ["docker", "compose", "version"],
                    capture_output=True, timeout=5,
                )
                docker_compose = ["docker", "compose"]
                break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        else:
            try:
                subprocess.run(
                    [cmd, "version"],
                    capture_output=True, timeout=5,
                )
                docker_compose = [cmd]
                break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

    if docker_compose:
        # Use docker compose
        compose_file = os.path.join(project_root, "tools", "docker", "docker-compose.yml")
        cmd = docker_compose + ["-f", compose_file, "run", "--rm", "build"]
    else:
        # Fallback: direct Docker run
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{project_root}:/workspace",
            "ai-freertos-build",
            "bash", "-c",
            "cd /workspace && mkdir -p build && cd build && cmake .. -G Ninja && ninja",
        ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=not verbose,
            text=True,
            timeout=300,  # 5 minute build timeout
            cwd=project_root,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        if result.returncode == 0:
            return {
                "status": "success",
                "duration_ms": duration_ms,
            }
        else:
            stderr = result.stderr if hasattr(result, "stderr") and result.stderr else ""
            return {
                "status": "failure",
                "duration_ms": duration_ms,
                "error": f"Build failed (exit code {result.returncode})",
                "stderr": stderr[:1000] if stderr else None,
            }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "duration_ms": int((time.monotonic() - start) * 1000),
            "error": "Build timed out after 300s",
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "duration_ms": int((time.monotonic() - start) * 1000),
            "error": "Docker not found. Install Docker to use the build pipeline.",
        }


def stage_flash(project_root: str, elf_path: str, verbose: bool = False) -> dict:
    """Flash firmware via SWD using flash.py.

    Args:
        project_root: Absolute path to the project root.
        elf_path: Path to ELF file.
        verbose: Print flash output.

    Returns:
        dict with stage result.
    """
    start = time.monotonic()

    flash_script = os.path.join(project_root, "tools", "hil", "flash.py")
    cmd = [sys.executable, flash_script, "--elf", elf_path, "--json"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_root,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            flash_result = json.loads(result.stdout)
            return {
                "status": flash_result.get("status", "error"),
                "duration_ms": duration_ms,
                "details": flash_result,
            }
        except json.JSONDecodeError:
            return {
                "status": "failure" if result.returncode != 0 else "success",
                "duration_ms": duration_ms,
                "error": result.stderr[:500] if result.stderr else "Unknown flash error",
            }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "duration_ms": int((time.monotonic() - start) * 1000),
            "error": "Flash timed out after 60s",
        }


def stage_rtt_capture(project_root: str, duration_secs: int = 5,
                      verbose: bool = False) -> dict:
    """Start OpenOCD with RTT and capture output.

    If OpenOCD is not already running, starts it with pico-probe.cfg + rtt.cfg.
    Captures raw RTT binary data from port 9091 for the specified duration.

    Args:
        project_root: Absolute path to the project root.
        duration_secs: How long to capture RTT data.
        verbose: Print capture progress.

    Returns:
        dict with stage result.
    """
    global _openocd_proc
    start = time.monotonic()

    openocd_was_running = is_openocd_running(TCL_RPC_PORT)

    if not openocd_was_running:
        # Start OpenOCD with RTT configuration
        try:
            probe_cfg = os.path.join(project_root, DEFAULT_PROBE_CFG)
            rtt_cfg = os.path.join(project_root, DEFAULT_RTT_CFG)

            _openocd_proc = start_openocd_server(
                probe_cfg=probe_cfg,
                extra_cfgs=[rtt_cfg],
                post_init_cmds=[
                    "rtt start",
                    "rtt server start 9090 0",
                    "rtt server start 9091 1",
                    "rtt server start 9092 2",
                ],
            )

            if not wait_for_openocd_ready(TCL_RPC_PORT, timeout=10):
                return {
                    "status": "error",
                    "duration_ms": int((time.monotonic() - start) * 1000),
                    "error": "OpenOCD did not become ready within 10s",
                }
        except FileNotFoundError as e:
            return {
                "status": "error",
                "duration_ms": int((time.monotonic() - start) * 1000),
                "error": str(e).split("\n")[0],
            }

    # Wait for OpenOCD to discover RTT control block
    if verbose:
        print("  Waiting for RTT control block...", file=sys.stderr)
    rtt_status = wait_for_rtt_ready(timeout=10, verbose=verbose)
    if not rtt_status.get("ready"):
        # Fallback: brief delay even if polling failed
        if verbose:
            print("  RTT polling timeout, using fallback sleep...", file=sys.stderr)
        time.sleep(2.0)

    # Capture RTT binary data from port 9091
    bytes_received = 0
    rtt_data = b""
    try:
        sock = socket.create_connection(("localhost", 9091), timeout=5)
        sock.settimeout(1.0)

        capture_deadline = time.monotonic() + duration_secs
        while time.monotonic() < capture_deadline:
            try:
                chunk = sock.recv(4096)
                if chunk:
                    rtt_data += chunk
                    bytes_received += len(chunk)
            except socket.timeout:
                continue
        sock.close()
    except (ConnectionRefusedError, OSError) as e:
        # RTT port might not be ready yet — not fatal
        if verbose:
            print(f"  RTT capture warning: {e}", file=sys.stderr)

    duration_ms = int((time.monotonic() - start) * 1000)

    return {
        "status": "success" if bytes_received > 0 else "warning",
        "bytes_received": bytes_received,
        "duration_ms": duration_ms,
        "note": None if bytes_received > 0 else "No RTT data received (target may not be logging yet)",
    }


def stage_rtt_decode(project_root: str, duration_secs: int = 5,
                     verbose: bool = False) -> dict:
    """Decode RTT output using log_decoder.py.

    Args:
        project_root: Absolute path to the project root.
        duration_secs: How long to capture/decode.
        verbose: Print decode output.

    Returns:
        dict with stage result.
    """
    start = time.monotonic()

    decoder_script = os.path.join(project_root, "tools", "logging", "log_decoder.py")
    csv_path = os.path.join(project_root, "tools", "logging", "token_database.csv")

    if not os.path.isfile(decoder_script):
        return {
            "status": "skipped",
            "duration_ms": int((time.monotonic() - start) * 1000),
            "note": "log_decoder.py not found — skipping RTT decode",
        }

    if not os.path.isfile(csv_path):
        # Try to generate token database
        gen_script = os.path.join(project_root, "tools", "logging", "gen_tokens.py")
        if os.path.isfile(gen_script):
            try:
                subprocess.run(
                    [sys.executable, gen_script,
                     "--scan-dirs", os.path.join(project_root, "firmware"),
                     "--csv", csv_path,
                     "--header", os.path.join(project_root, "firmware", "components",
                                               "logging", "include", "tokens_generated.h"),
                     "--base-dir", project_root],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=project_root,
                )
            except Exception:
                pass

        if not os.path.isfile(csv_path):
            return {
                "status": "skipped",
                "duration_ms": int((time.monotonic() - start) * 1000),
                "note": "token_database.csv not found — skipping RTT decode",
            }

    # Run log_decoder.py with a duration limit
    cmd = [
        sys.executable, decoder_script,
        "--port", "9091",
        "--csv", csv_path,
        "--duration", str(duration_secs),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration_secs + 10,
            cwd=project_root,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        # Count decoded messages (each line of stdout should be a JSON object)
        messages_decoded = 0
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    json.loads(line)
                    messages_decoded += 1
                except json.JSONDecodeError:
                    pass

        return {
            "status": "success" if messages_decoded > 0 else "warning",
            "messages_decoded": messages_decoded,
            "duration_ms": duration_ms,
            "note": None if messages_decoded > 0 else "No messages decoded (check RTT connection)",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "duration_ms": int((time.monotonic() - start) * 1000),
            "error": f"RTT decode timed out after {duration_secs + 10}s",
        }


# ===========================================================================
# Pipeline Orchestrator
# ===========================================================================

def run_pipeline(skip_build: bool = False, skip_flash: bool = False,
                 rtt_duration: int = 5, verbose: bool = False) -> dict:
    """Run the full HIL pipeline.

    Stages:
        1. Docker build (unless --skip-build)
        2. SWD flash (unless --skip-flash)
        3. RTT capture (raw binary data)
        4. RTT decode (tokenized logs → JSON)

    Args:
        skip_build: Skip the Docker build stage.
        skip_flash: Skip the SWD flash stage.
        rtt_duration: RTT capture duration in seconds.
        verbose: Print stage progress.

    Returns:
        dict with aggregate pipeline results.
    """
    pipeline_start = time.monotonic()

    try:
        project_root = find_project_root()
    except FileNotFoundError as e:
        return {
            "status": "error",
            "tool": "run_pipeline.py",
            "error": str(e),
            "duration_ms": 0,
        }

    elf_path = os.path.join(project_root, DEFAULT_ELF_PATH)
    stages = {}

    # Stage 1: Build
    if skip_build:
        stages["build"] = {"status": "skipped"}
        if verbose:
            print("  [1/4] Build: SKIPPED", file=sys.stderr)
    else:
        if verbose:
            print("  [1/4] Build: starting Docker build...", file=sys.stderr)
        stages["build"] = stage_build(project_root, verbose=verbose)
        if verbose:
            print(f"  [1/4] Build: {stages['build']['status']}", file=sys.stderr)
        if stages["build"]["status"] not in ("success", "skipped"):
            total_duration = int((time.monotonic() - pipeline_start) * 1000)
            return {
                "status": "failure",
                "tool": "run_pipeline.py",
                "failed_stage": "build",
                "stages": stages,
                "total_duration_ms": total_duration,
            }

    # Stage 2: Flash
    if skip_flash:
        stages["flash"] = {"status": "skipped"}
        if verbose:
            print("  [2/4] Flash: SKIPPED", file=sys.stderr)
    else:
        if not os.path.isfile(elf_path):
            stages["flash"] = {
                "status": "error",
                "error": f"ELF not found: {elf_path}. Run build first.",
            }
        else:
            if verbose:
                print("  [2/4] Flash: programming via SWD...", file=sys.stderr)
            stages["flash"] = stage_flash(project_root, elf_path, verbose=verbose)
            if verbose:
                print(f"  [2/4] Flash: {stages['flash']['status']}", file=sys.stderr)

        if stages["flash"]["status"] not in ("success", "skipped"):
            total_duration = int((time.monotonic() - pipeline_start) * 1000)
            return {
                "status": "failure",
                "tool": "run_pipeline.py",
                "failed_stage": "flash",
                "stages": stages,
                "total_duration_ms": total_duration,
            }

    # Stage 3: RTT Capture
    if verbose:
        print(f"  [3/4] RTT Capture: {rtt_duration}s...", file=sys.stderr)
    stages["rtt_capture"] = stage_rtt_capture(
        project_root, duration_secs=rtt_duration, verbose=verbose,
    )
    if verbose:
        print(
            f"  [3/4] RTT Capture: {stages['rtt_capture']['status']} "
            f"({stages['rtt_capture'].get('bytes_received', 0)} bytes)",
            file=sys.stderr,
        )

    # Stage 4: RTT Decode
    if verbose:
        print(f"  [4/4] RTT Decode: decoding...", file=sys.stderr)
    stages["rtt_decode"] = stage_rtt_decode(
        project_root, duration_secs=rtt_duration, verbose=verbose,
    )
    if verbose:
        print(
            f"  [4/4] RTT Decode: {stages['rtt_decode']['status']} "
            f"({stages['rtt_decode'].get('messages_decoded', 0)} messages)",
            file=sys.stderr,
        )

    # Cleanup OpenOCD if we started it
    _cleanup()

    # Determine overall status
    stage_statuses = [s.get("status") for s in stages.values()]
    if all(s in ("success", "skipped") for s in stage_statuses):
        overall = "success"
    elif any(s in ("failure", "error") for s in stage_statuses):
        overall = "failure"
    elif any(s == "timeout" for s in stage_statuses):
        overall = "timeout"
    else:
        overall = "success"  # warnings are acceptable

    total_duration = int((time.monotonic() - pipeline_start) * 1000)

    return {
        "status": overall,
        "tool": "run_pipeline.py",
        "stages": stages,
        "total_duration_ms": total_duration,
    }


# ===========================================================================
# CLI Interface
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="End-to-end HIL pipeline: Docker build → SWD flash → RTT verification.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    # Full pipeline (build → flash → RTT):
    python3 tools/hil/run_pipeline.py --json

    # Skip build (use existing build artifacts):
    python3 tools/hil/run_pipeline.py --skip-build --json

    # Skip build and flash (RTT only):
    python3 tools/hil/run_pipeline.py --skip-build --skip-flash --rtt-duration 10 --json

    # Verbose progress output:
    python3 tools/hil/run_pipeline.py --verbose
""",
    )
    parser.add_argument(
        "--skip-build", action="store_true",
        help="Skip the Docker build stage",
    )
    parser.add_argument(
        "--skip-flash", action="store_true",
        help="Skip the SWD flash stage",
    )
    parser.add_argument(
        "--rtt-duration", type=int, default=5, metavar="SECS",
        help="RTT capture duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON only (no human-readable text)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print stage progress to stderr",
    )

    args = parser.parse_args()

    # Run pipeline
    result = run_pipeline(
        skip_build=args.skip_build,
        skip_flash=args.skip_flash,
        rtt_duration=args.rtt_duration,
        verbose=args.verbose,
    )

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status_icon = "✓" if result.get("status") == "success" else "✗"
        print(f"{status_icon} Pipeline: {result.get('status', 'unknown')}")

        stages = result.get("stages", {})
        for name, stage in stages.items():
            s_icon = "✓" if stage.get("status") == "success" else (
                "⊘" if stage.get("status") == "skipped" else "✗"
            )
            extra = ""
            if "bytes_received" in stage:
                extra = f" ({stage['bytes_received']} bytes)"
            elif "messages_decoded" in stage:
                extra = f" ({stage['messages_decoded']} messages)"
            elif "duration_ms" in stage:
                extra = f" ({stage['duration_ms']}ms)"
            print(f"  {s_icon} {name}: {stage.get('status', '?')}{extra}")

            if stage.get("error"):
                print(f"    Error: {stage['error']}")
            if stage.get("note"):
                print(f"    Note: {stage['note']}")

        print(f"\n  Total duration: {result.get('total_duration_ms', 0)}ms")

    sys.exit(0 if result.get("status") == "success" else 1)


if __name__ == "__main__":
    main()
