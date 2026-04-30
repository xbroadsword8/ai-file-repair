"""
AI File Repair - Data Recovery Tool
=================================
Windows executable entry point for the disk recovery tool.

Usage:
    python main.py                          # Run in headless mode
    python main.py --gui                   # Run GUI mode
    python main.py --disk C:             # Scan disk C:
    python main.py --disk PhysicalDrive0 # Scan physical drive
"""

import sys
import os

# Add project root to path so imports from core/gui work
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="AI File Repair - Data Recovery Tool",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--disk", "-d",
        type=str,
        default=None,
        help="Disk path (e.g. C: or PhysicalDrive0)",
    )
    parser.add_argument(
        "--gui", "-g",
        action="store_true",
        help="Launch GUI mode",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless/headless mode",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./recovered",
        help="Output directory for recovered files",
    )

    args = parser.parse_args()

    if args.gui:
        # GUI mode
        from gui.gui_main import main as gui_main
        gui_main()
    else:
        # Headless / CLI mode
        from core.disk_recovery import DiskRecovery
        from pathlib import Path

        if not args.disk:
            print("🔍 Headless mode")
            print(f"   Disk: {args.disk or 'C:'}")
            print(f"   Output: {args.output}")

            recovery = DiskRecovery(args.disk or "C:")
            if recovery.open_disk():
                recovered = recovery.recover_all_files(args.output)
                print(f"\n✅ Recovered {len(recovered)} files")
                print(f"   Output: {args.output}")
            else:
                print("❌ Failed to open disk")
        else:
            print("🔍 Headless mode")
            print(f"   Disk: {args.disk}")
            print(f"   Output: {args.output}")

            recovery = DiskRecovery(args.disk)
            if recovery.open_disk():
                recovered = recovery.recover_all_files(args.output)
                print(f"\n✅ Recovered {len(recovered)} files")
                print(f"   Output: {args.output}")
            else:
                print("❌ Failed to open disk")


if __name__ == "__main__":
    main()
