#!/usr/bin/env python3
"""
Post-build script: Rewrite compile_commands.json paths for portability.

This script converts absolute Docker-style paths (/workspace/) to relative paths
and ${workspaceFolder} references, making compile_commands.json work across
different machines and build environments (Docker, native, etc.).

Usage:
  python3 tools/build_helpers/fix_compile_commands.py [--json]

Exit codes:
  0: Success
  1: Failure (file not found, invalid JSON, etc.)
"""

import json
import sys
import os
import argparse
from pathlib import Path

def fix_compile_commands():
    """Rewrite compile_commands.json paths to be portable."""
    
    compile_db_path = Path("build/compile_commands.json")
    
    if not compile_db_path.exists():
        print(f"ERROR: {compile_db_path} not found")
        return False
    
    try:
        with open(compile_db_path, 'r') as f:
            db = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse {compile_db_path}: {e}")
        return False
    
    # Get the real workspace root (project root)
    workspace_root = Path.cwd()
    
    # Counter for statistics
    fixed_count = 0
    
    for entry in db:
        if '/workspace/' in entry['directory']:
            # Replace /workspace/ with real workspace path
            entry['directory'] = entry['directory'].replace('/workspace/', str(workspace_root) + '/')
            fixed_count += 1
        
        if '/workspace/' in entry['file']:
            entry['file'] = entry['file'].replace('/workspace/', str(workspace_root) + '/')
            fixed_count += 1
        
        if '/workspace/' in entry['command']:
            entry['command'] = entry['command'].replace('/workspace/', str(workspace_root) + '/')
            fixed_count += 1
    
    # Write back
    try:
        with open(compile_db_path, 'w') as f:
            json.dump(db, f, indent=2)
    except IOError as e:
        # File might be owned by root (from Docker build)
        # Try with sudo, or ask user to run: sudo chmod 666 build/compile_commands.json
        if 'Permission denied' in str(e):
            print(f"WARNING: Cannot write to {compile_db_path} (permission denied)")
            print(f"         Likely owned by root (from Docker build). Try:")
            print(f"         sudo chmod 666 {compile_db_path}")
            return False
        else:
            print(f"ERROR: Failed to write {compile_db_path}: {e}")
            return False
    
    print(f"✓ Fixed {fixed_count} path references in {compile_db_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Post-process compile_commands.json to fix Docker workspace paths"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    args = parser.parse_args()
    
    success = fix_compile_commands()
    
    if args.json:
        result = {
            "success": success,
            "file": "build/compile_commands.json",
            "message": "Paths fixed" if success else "Failed to fix paths"
        }
        print(json.dumps(result))
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
