"""Minimal disk sector scanner – read sectors, detect file signatures."""

import os
import sys
from typing import List, Dict, Optional

FILE_SIGNATURES = {
    'jpg': {'magic': b'\xFF\xD8\xFF', 'end': b'\xFF\xD9', 'ext': 'jpg'},
    'png': {'magic': b'\x89PNG\r\n\x1a\n', 'end': b'IEND', 'ext': 'png'},
    'pdf': {'magic': b'%PDF', 'end': b'%%EOF', 'ext': 'pdf'},
    'zip': {'magic': b'PK\x03\x04', 'end': None, 'ext': 'zip'},
    'doc': {'magic': b'\xD0\xCF\x11\xE0', 'end': None, 'ext': 'doc'},
    'mp3': {'magic': b'\xFF\xFB', 'end': None, 'ext': 'mp3'},
}


class DiskSectorScanner:
    """Low-level physical-disk sector reader with magic-number scanning."""

    SECTOR_SIZE = 512

    def __init__(self):
        self._fd: Optional[int] = None

    # ── public API ──────────────────────────────────────────────

    def open_disk(self, device_path: str) -> bool:
        """Open a physical-disk device for raw read access.

        Windows:  \\.\PhysicalDriveN   (requires admin)
        Linux:    /dev/sdX             (requires root)
        """
        try:
            if sys.platform.startswith("win"):
                self._fd = os.open(
                    device_path,
                    os.O_RDONLY | os.O_BINARY,
                )
            else:
                self._fd = os.open(device_path, os.O_RDONLY)
            return True
        except (OSError, TypeError):
            self._fd = None
            return False

    def read_sector(self, sector_num: int) -> Optional[bytes]:
        """Read a single sector (512 bytes) at the given sector offset."""
        if self._fd is None:
            return None
        try:
            os.lseek(self._fd, sector_num * self.SECTOR_SIZE, os.SEEK_SET)
            data = os.read(self._fd, self.SECTOR_SIZE)
            return data if len(data) == self.SECTOR_SIZE else None
        except OSError:
            return None

    def scan_file_types(self, data: bytes, base_offset: int = 0) -> List[Dict]:
        """Scan *data* for known file signatures and return hit list.

        Each result is a dict with keys:
            type, ext, offset (absolute), magic, length (bytes scanned).
        """
        hits: List[Dict] = []
        for ftype, sig in FILE_SIGNATURES.items():
            pos = 0
            while True:
                pos = data.find(sig["magic"], pos)
                if pos == -1:
                    break
                result: Dict = {
                    "type": ftype,
                    "ext": sig["ext"],
                    "offset": base_offset + pos,
                    "magic": sig["magic"].hex(),
                }
                # report data length from magic to end-of-buffer (or end marker)
                if sig["end"] is not None:
                    end_pos = data.find(sig["end"], pos + 1)
                    result["length"] = (
                        (end_pos + len(sig["end"])) - pos if end_pos != -1
                        else len(data) - pos
                    )
                else:
                    result["length"] = len(data) - pos
                hits.append(result)
                pos += 1
        return hits

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


# ── entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    print("Hello from DiskSectorScanner")
    print(f"File signatures loaded: {len(FILE_SIGNATURES)}")
    for name, sig in FILE_SIGNATURES.items():
        print(f"  {name:5s}  magic  {sig['magic'].hex()}")
