#!/usr/bin/env python3
"""Integration test: verify that all ai-file-repair scripts can be imported."""

import sys
import os

# Ensure the scripts directory is on the path
scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

MODULES = [
    "disk_sector_scanner",
    "file_size_estimator",
    "bad_sector_handler",
    "ntfs_mft_parser",
    "reconstruction",
    "ai_repair_engine",
]

ok_count = 0
fail_count = 0

for mod in MODULES:
    try:
        __import__(mod)
        print(f"✓ {mod} OK")
        ok_count += 1
    except ImportError as e:
        print(f"✗ {mod} FAILED ({e})")
        fail_count += 1

print()
print(f"Results: {ok_count} passed, {fail_count} failed")
print("✅ Integration test complete")
