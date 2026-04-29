#!/usr/bin/env python3
"""
NTFS MFT (Master File Table) Parser
====================================

Parses NTFS Master File Table records from raw disk images.
Supports resident and non-resident attributes, data run decoding,
directory traversal, and file enumeration.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

NTFS_MAGIC = b"FILE"

# Attribute type codes
ATTR_STANDARD_INFORMATION = 0x10
ATTR_FILE_NAME            = 0x20
ATTR_VOLUME_NAME          = 0x30
ATTR_OBJECT_ID            = 0x40
ATTR_SECURITY_DESCRIPTOR  = 0x50
ATTR_DATA                 = 0x70
ATTR_VOLUME_INFORMATION   = 0x80
ATTR_ATTRIBUTE_LIST       = 0xA0

# FILE_NAME types
FILENAME_TYPE_ROOT   = 0  # .
FILENAME_TYPE_SHORT  = 1  # 8.3 DOS name
FILENAME_TYPE_POSIX  = 2
FILENAME_TYPE_WIN32  = 3
FILENAME_TYPE_WIN32_DOS = 4
FILENAME_TYPE_WIN32_DOS_BP = 5

# FILE_NAME flags
FILENAME_FLAG_READONLY    = 0x01
FILENAME_FLAG_HIDDEN      = 0x02
FILENAME_FLAG_SYSTEM      = 0x04
FILENAME_FLAG_DIRECTORY   = 0x10
FILENAME_FLAG_ARCHIVE     = 0x20
FILENAME_FLAG_COMPRESSED  = 0x40
FILENAME_FLAG_ENCRYPTED   = 0x80

# Windows version string
WINDOWS_VERSION = "0.11"

# MFT record size
MFT_RECORD_SIZE = 1024

# ─────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────


@dataclass
class FileSegment:
    """Represents a contiguous data segment (VCN/LCN mapping)."""
    lcn: int          # Logical Cluster Number on disk
    vcn: int          # Virtual Cluster Number
    length: int       # Length in clusters


@dataclass
class MFTEntry:
    """Master File Table entry with file metadata."""
    file_number: int
    filename: Optional[str] = None            # Full path (e.g., "Windows\\System32\\cmd.exe")
    file_extension: Optional[str] = None
    size: int = 0                             # Real file size in bytes
    allocated_size: int = 0                   # Allocated disk space
    is_directory: bool = False
    is_hidden: bool = False
    is_system: bool = False
    is_compressed: bool = False
    has_data_resident: bool = False
    data_runs: List[FileSegment] = field(default_factory=list)
    parent_mft_number: int = 0
    created: int = 0                          # Unix timestamp
    modified: int = 0                         # Unix timestamp


# ─────────────────────────────────────────────
# Helper: NTFS timestamp conversion
# ─────────────────────────────────────────────

def _ntfs_time_to_unix(low32: int, high32: int) -> int:
    """Convert NTFS 64-bit timestamp (little-endian) to Unix epoch."""
    ntfs_ts = (high32 << 32) | low32
    if ntfs_ts <= 0:
        return 0
    # NTFS epoch is 1601-01-01; Unix epoch is 1970-01-01 (11644473600 seconds)
    return (ntfs_ts - 116444736000000000) // 10000000


# ─────────────────────────────────────────────
# NTFSParser class
# ─────────────────────────────────────────────


class NTFSParser:
    """NTFS MFT parser — reads and decodes Master File Table records."""

    def __init__(self, disk_handle, sector_size: int = 512,
                 cluster_size: int = 4096):
        """
        Args:
            disk_handle: Object with read(sector) -> bytes and
                         write(sector, data) -> int methods.
            sector_size: Size of one sector in bytes (default 512).
            cluster_size: Size of one cluster in bytes (default 4096 = 8 × 512).
        """
        self.disk_handle = disk_handle
        self.sector_size = sector_size
        self.cluster_size = cluster_size
        self.mft_entries: Dict[int, MFTEntry] = {}
        self.resident_attr_cache: Dict[Tuple[int, int], bytes] = {}

    # ── Public API ───────────────────────────

    def parse_mft(self) -> List[MFTEntry]:
        """Parse all MFT records. Returns a list of MFTEntry objects."""
        self.mft_entries.clear()
        record = 0
        while True:
            try:
                entry = self.parse_mft_record(record)
                if entry is None:
                    break
                self.mft_entries[record] = entry
                record += 1
            except Exception:
                break
        return list(self.mft_entries.values())

    def parse_directory(self, parent_entry: MFTEntry) -> List[MFTEntry]:
        """Parse children of a given directory entry by following its
        index allocation data runs (the I30 directory index)."""
        children = []

        # Determine which data runs to use for the index allocation
        runs = parent_entry.data_runs if parent_entry.data_runs else []
        if not runs:
            return children

        # Read index allocation data
        try:
            index_data = self._read_nonresident_data(runs)
        except Exception:
            return children

        if not index_data:
            return children

        # Parse the index entry header and iterate children
        offset = 0
        while offset < len(index_data):
            if offset + 24 > len(index_data):
                break

            # Index entry header (simplified)
            is_directory_entry = (struct.unpack_from("<I", index_data, offset)[0] & 0xFF000000) != 0
            entry_len = struct.unpack_from("<I", index_data, offset + 4)[0]
            mft_number = struct.unpack_from("<I", index_data, offset + 8)[0]

            if mft_number == 0 and not is_directory_entry:
                break

            # Extract the name from the index entry (starts after the header)
            name_len = struct.unpack_from("<I", index_data, offset + 18)[0]
            name_type = index_data[offset + 16]
            if name_len > 0 and offset + 24 + 2 <= len(index_data):
                name = index_data[offset + 24:offset + 24 + name_len].decode(
                    "utf-16-le", errors="replace"
                )
            else:
                name = ""

            # Parse the child MFT record
            try:
                child = self.parse_mft_record(mft_number)
                if child and child.filename is not None:
                    children.append(child)
            except Exception:
                pass

            offset += entry_len

        return children

    def build_file_map(self) -> Dict[str, MFTEntry]:
        """Build a full path → MFTEntry mapping for every entry."""
        file_map: Dict[str, MFTEntry] = {}

        for entry in self.mft_entries.values():
            if entry.filename is None or entry.parent_mft_number == 0:
                continue
            path = self._build_full_path(entry)
            if path:
                file_map[path] = entry

        return file_map

    def find_files_by_extension(self, extensions: List[str]) -> Dict[str, MFTEntry]:
        """Find files matching the given extensions (case-insensitive).
        Returns path → MFTEntry mapping."""
        ext_set = {ext.lower().lstrip(".") for ext in extensions}
        result: Dict[str, MFTEntry] = {}
        file_map = self.build_file_map()

        for path, entry in file_map.items():
            if entry.file_extension and entry.file_extension.lstrip(".").lower() in ext_set:
                result[path] = entry

        return result

    def parse_data_runs(self, run_data: bytes) -> List[FileSegment]:
        """Decode NTFS data run encoding into a list of FileSegment objects."""
        runs: List[FileSegment] = []
        i = 0
        vcn = 0
        lcn = 0

        while i < len(run_data):
            byte = run_data[i]
            i += 1

            length_len = byte & 0x0F
            offset_len = (byte >> 4) & 0x0F

            if length_len == 0:
                break

            if length_len > 8 or offset_len > 8:
                break

            # --- Run length ---
            if i + length_len > len(run_data):
                break
            run_len = 0
            for j in range(length_len):
                run_len |= run_data[i + j] << (j * 8)
            i += length_len

            # --- Run offset (signed) ---
            if offset_len > 0:
                if i + offset_len > len(run_data):
                    break
                run_off = 0
                for j in range(offset_len):
                    run_off |= run_data[i + j] << (j * 8)
                i += offset_len

                # Convert to signed (two's complement)
                if run_off & (1 << (offset_len * 8 - 1)):
                    run_off -= 1 << (offset_len * 8)
            else:
                run_off = 0

            # lcn 0 means no more runs
            if run_off == 0:
                break

            # Accumulate
            vcn += lcn
            lcn = run_off
            runs.append(FileSegment(lcn=lcn, vcn=vcn, length=run_len))
            vcn += run_len
            lcn += run_len

        return runs

    def parse_variable_attribute(self, data: bytes, offset: int,
                                  attr_type: int) -> Dict:
        """Parse a variable-length attribute from the raw bytes."""
        if attr_type == ATTR_FILE_NAME:
            return self._parse_filename_attribute(data, offset)
        elif attr_type == ATTR_DATA:
            return self._parse_data_attribute(data, offset)
        elif attr_type == ATTR_ATTRIBUTE_LIST:
            return self._parse_attribute_list(data, offset)
        else:
            return {"type": f"0x{attr_type:04X}", "data": data[offset:]}

    def parse_attribute_list(self, data: bytes, offset: int = 0
                              ) -> List[Dict]:
        """Parse an Attribute List (type 0xA0) — used for extended MFT records."""
        entries = []
        i = offset

        while i + 16 <= len(data):
            key_size = data[i]
            value_size = data[i + 1]
            if key_size == 0 or value_size == 0:
                break

            attr_type = struct.unpack_from("<I", data, i + 4)[0]
            instance = struct.unpack_from("<H", data, i + 8)[0]
            name_len = struct.unpack_from("<H", data, i + 12)[0]

            entry = {
                "type": attr_type,
                "instance": instance,
                "name_length": name_len,
                "key_length": key_size,
                "value_length": value_size,
            }

            if name_len > 0 and i + 16 + name_len <= len(data):
                entry["name"] = data[i + 16: i + 16 + name_len].decode(
                    "utf-16-le", errors="replace"
                )

            entries.append(entry)
            i += value_size

        return entries

    def read_physical(self, lcn: int) -> Optional[bytes]:
        """Read a physical cluster (LCN) from the disk via the disk handle."""
        try:
            return self.disk_handle.read(lcn)
        except Exception:
            return None

    # ── Internal helpers ─────────────────────

    def parse_mft_record(self, record_number: int) -> Optional[MFTEntry]:
        """Parse a single MFT record (number) from disk."""
        if record_number > 100_000_000:
            return None

        record_data = self.read_physical(record_number)
        if record_data is None or len(record_data) < 4:
            return None

        if record_data[:4] != NTFS_MAGIC:
            return None

        # --- Header fields ---
        seq_num = struct.unpack_from("<H", record_data, 4)[0]
        link_count = struct.unpack_from("<H", record_data, 6)[0]
        attr_off = struct.unpack_from("<I", record_data, 8)[0]
        attr_size = struct.unpack_from("<I", record_data, 12)[0]
        next_attr_id = struct.unpack_from("<I", record_data, 16)[0]

        # --- Attribute entries ---
        entries: List[MFTEntry] = []
        pos = attr_off

        while pos + 4 <= len(record_data):
            if pos + attr_size > len(record_data):
                break

            a_type = struct.unpack_from("<I", record_data, pos)[0]
            a_len = struct.unpack_from("<I", record_data, pos + 4)[0]

            if a_len == 0 or pos + a_len > len(record_data):
                break

            if a_type == 0xFFFFFFFF:
                break

            a_flags = struct.unpack_from("<H", record_data, pos + 8)[0]
            a_instance = struct.unpack_from("<H", record_data, pos + 10)[0]
            a_offset = struct.unpack_from("<H", record_data, pos + 12)[0]
            a_size = struct.unpack_from("<I", record_data, pos + 16)[0]
            a_aligned = struct.unpack_from("<I", record_data, pos + 20)[0]

            is_resident = not (a_flags & 0x0001)

            if a_type == ATTR_STANDARD_INFORMATION:
                if is_resident and a_size == 72:
                    timestamps = self._extract_standard_info(record_data, pos + a_offset)
                elif not is_resident:
                    timestamps = self._parse_nonresident_attrs(
                        record_data, pos, a_offset, a_size, a_type,
                        seq_num, a_instance
                    )
                    if isinstance(timestamps, dict) and "timestamps" in timestamps:
                        timestamps = timestamps["timestamps"]

            elif a_type == ATTR_DATA:
                data_info = self._parse_nonresident_attrs(
                    record_data, pos, a_offset, a_size, a_type,
                    seq_num, a_instance
                )
                if isinstance(data_info, dict):
                    segments = data_info.get("segments", [])
                    if not segments and is_resident and a_size > 0:
                        seg = FileSegment(
                            lcn=record_number,
                            vcn=0,
                            length=a_size // max(self.cluster_size, 1)
                        )
                        segments = [seg]

            elif a_type == ATTR_FILE_NAME:
                if is_resident and a_size >= 72:
                    name_info = self._parse_filename_attribute(
                        record_data, pos + a_offset
                    )
                    # Extract all relevant fields for MFTEntry building
                    parent_mft = name_info.get("parent", 0)
                    filename = name_info.get("name", "")
                    name_type = name_info.get("type", -1)
                    creation_ts = name_info.get("created", 0)
                    modified_ts = name_info.get("modified", 0)
                    change_ts = name_info.get("changed", 0)
                    file_size = name_info.get("size", 0)
                    alloc_size = name_info.get("allocated", 0)
                    flags = name_info.get("flags", 0)
                    ea_size = name_info.get("ea_size", 0)
                    run_off = name_info.get("run_offset", 0)
                    run_size = name_info.get("run_size", 0)

                    # Determine file properties
                    is_dir = bool(flags & FILENAME_FLAG_DIRECTORY)
                    is_hidden = bool(flags & FILENAME_FLAG_HIDDEN)
                    is_sys = bool(flags & FILENAME_FLAG_SYSTEM)
                    is_comp = bool(flags & FILENAME_FLAG_COMPRESSED)

                    # Parse the file extension from filename
                    ext = None
                    if filename and "." in filename.split("\\")[-1].split("/")[-1]:
                        base = filename.split("\\")[-1].split("/")[-1]
                        ext = "." + base.rsplit(".", 1)[-1]

                    # Parse data runs if non-resident
                    data_segments = []
                    if not is_resident and run_size > 0:
                        try:
                            run_data = record_data[pos + a_offset + run_off:
                                                   pos + a_offset + run_off + run_size]
                            data_segments = self.parse_data_runs(run_data)
                        except Exception:
                            data_segments = []
                    else:
                        data_segments = []

                    entry = MFTEntry(
                        file_number=record_number,
                        filename=filename,
                        file_extension=ext,
                        size=file_size,
                        allocated_size=alloc_size,
                        is_directory=is_dir,
                        is_hidden=is_hidden,
                        is_system=is_sys,
                        is_compressed=is_comp,
                        has_data_resident=is_resident,
                        data_runs=data_segments,
                        parent_mft_number=parent_mft,
                        created=creation_ts if creation_ts else 0,
                        modified=modified_ts if modified_ts else 0,
                    )
                    entries.append(entry)

            # Move to next attribute
            pos += a_len

        # Pick the best filename entry for this record
        if entries:
            # Prefer WIN32+DOS type (type 4)
            best = None
            for e in entries:
                if e.filename is not None:
                    best = e
                    if any(
                        et.startswith("0x20") or "FILE_NAME" in et
                        for et in ["0x20"]
                    ):
                        pass  # all FILE_NAME attrs are same type
                    if e.file_extension is not None and e.file_number == record_number:
                        best = e

            if best:
                # Ensure non-resident data runs are also captured if filename
                # attribute indicated non-resident data
                data_run_attr = self._parse_nonresident_attrs(
                    record_data, 0, attr_off, attr_size, ATTR_DATA,
                    seq_num, 0
                )
                if isinstance(data_run_attr, dict) and data_run_attr.get("segments"):
                    best.data_runs = data_run_attr["segments"]
                # Check if there's resident data for this file
                if not best.data_runs:
                    # Check data attribute for resident data
                    best.has_data_resident = True

                return best

        return None

    def _parse_nonresident_attrs(self, record: bytes, offset: int,
                                 attr_off: int, attr_size: int,
                                 attr_type: int, seq: int,
                                 instance: int) -> Dict:
        """Parse a non-resident attribute, extracting data runs and
        attribute-specific content (e.g., timestamps for SI)."""
        pos = offset + attr_off
        a_len_struct = struct.unpack_from("<I", record, pos + 4)[0]

        if a_len_struct > len(record) - pos:
            return {}

        # Non-resident header: 48 bytes starting at pos
        if a_len_struct >= 48:
            is_resident = False
            start_vcn = struct.unpack_from("<Q", record, pos + 24)[0]
            end_vcn = struct.unpack_from("<Q", record, pos + 32)[0]
            cluster_per_block = record[pos + 40]
            cluster_per_index = record[pos + 41]
            data_run_off = struct.unpack_from("<H", record, pos + 42)[0]
            data_run_len = struct.unpack_from("<H", record, pos + 44)[0]
            data_value_off = struct.unpack_from("<H", record, pos + 46)[0]

            if attr_type == ATTR_STANDARD_INFORMATION and data_run_len > 0:
                # The SI non-resident attribute actually stores the data,
                # but for standard info we should look at resident entries
                # or skip. Let's read from resident SI if available.
                pass

            segments = []
            if data_run_len > 0 and data_run_off > 0:
                try:
                    run_data = record[pos + data_run_off:
                                     pos + data_run_off + data_run_len]
                    segments = self.parse_data_runs(run_data)
                except Exception:
                    segments = []

            result: Dict = {"segments": segments,
                            "start_vcn": start_vcn,
                            "end_vcn": end_vcn}

            if attr_type == ATTR_DATA and segments:
                result["is_resident"] = False

            return result

        return {}

    def _extract_standard_info(self, record: bytes, offset: int
                                ) -> Dict[int, int]:
        """Extract timestamps from a resident $STANDARD_INFORMATION attribute.
        Returns dict of {type_code: unix_timestamp}."""
        # Resident SI: after 48-byte header, 6 × 8 = 48 bytes of timestamps
        if offset + 48 >= len(record):
            return {}

        timestamps = {}
        ts_start = offset + 48
        types = [ATTR_STANDARD_INFORMATION]

        for j in range(6):
            if ts_start + 8 + j * 8 > len(record):
                break
            low = struct.unpack_from("<I", record, ts_start + j * 8)[0]
            high = struct.unpack_from("<I", record, ts_start + j * 8 + 4)[0]
            unix_ts = _ntfs_time_to_unix(low, high)
            if unix_ts > 0:
                timestamps[types[j % len(types)] if j < len(types) else j] = unix_ts

        return timestamps

    def _parse_filename_attribute(self, data: bytes,
                                   offset: int = 0) -> Dict:
        """Parse a resident $FILE_NAME attribute.
        Offset is relative to the start of the attribute data in the buffer."""
        name_data = data[offset: offset + len(data) - offset]

        if len(name_data) < 72:
            return {}

        # $FILE_NAME header (72 bytes):
        parent_mft = struct.unpack_from("<Q", name_data, 0)[0]
        creation_low = struct.unpack_from("<I", name_data, 4)[0]
        creation_high = struct.unpack_from("<I", name_data, 8)[0]
        modified_low = struct.unpack_from("<I", name_data, 12)[0]
        modified_high = struct.unpack_from("<I", name_data, 16)[0]
        dir_mod_low = struct.unpack_from("<I", name_data, 20)[0]
        dir_mod_high = struct.unpack_from("<I", name_data, 24)[0]
        change_low = struct.unpack_from("<I", name_data, 28)[0]
        change_high = struct.unpack_from("<I", name_data, 32)[0]
        file_size = struct.unpack_from("<Q", name_data, 40)[0]
        alloc_size = struct.unpack_from("<Q", name_data, 48)[0]
        flags = struct.unpack_from("<I", name_data, 56)[0]
        ea_size = struct.unpack_from("<I", name_data, 60)[0]
        run_off = struct.unpack_from("<H", name_data, 64)[0]
        run_size = struct.unpack_from("<H", name_data, 66)[0]
        file_name_type = name_data[68]
        file_name_len = name_data[69]

        # Name follows the header, null-terminated
        name_raw = name_data[72: 72 + file_name_len]
        if file_name_len > 0:
            # Trim null padding
            null_idx = name_raw.find(b"\x00")
            if null_idx > 0:
                name_raw = name_raw[:null_idx]
            name = name_raw.decode("utf-16-le", errors="replace")
        else:
            name = ""

        return {
            "parent": int(parent_mft),
            "created": _ntfs_time_to_unix(creation_low, creation_high),
            "modified": _ntfs_time_to_unix(modified_low, modified_high),
            "dir_modified": _ntfs_time_unix(dir_mod_low, dir_mod_high),
            "changed": _ntfs_time_to_unix(change_low, change_high),
            "size": int(file_size),
            "allocated": int(alloc_size),
            "flags": int(flags),
            "ea_size": int(ea_size),
            "run_offset": run_off,
            "run_size": run_size,
            "type": file_name_type,
            "name": name,
        }

    def _parse_data_attribute(self, data: bytes, offset: int = 0) -> Dict:
        """Parse a resident $DATA attribute."""
        result: Dict = {"data": b"", "is_resident": True, "type": "0x70"}

        if offset < len(data):
            header_len = data[offset] if data[offset] else 0
            if header_len >= 24 and offset + header_len <= len(data):
                flags = struct.unpack_from("<H", data, offset + 8)[0]
                inst = struct.unpack_from("<H", data, offset + 10)[0]
                size = struct.unpack_from("<I", data, offset + 12)[0]
                data_off = struct.unpack_from("<H", data, offset + 16)[0]

                result["instance"] = inst
                result["is_resident"] = (flags & 0x0001) == 0
                result["data_size"] = size

                if result["is_resident"] and size > 0:
                    start = offset + data_off
                    end = min(start + size, len(data))
                    if start < end:
                        result["data"] = data[start:end]

        return result

    def _parse_attribute_list(self, data: bytes, offset: int = 0) -> Dict:
        """Parse an $ATTRIBUTE_LIST attribute (type 0xA0)."""
        result: Dict = {"entries": [], "is_resident": True}
        result["entries"] = self.parse_attribute_list(data, offset)
        return result

    def _build_full_path(self, entry: MFTEntry) -> Optional[str]:
        """Build the full path for a file by walking up the parent chain."""
        if entry.filename is None:
            return None

        path_parts = [entry.filename]
        current = entry

        while current.parent_mft_number != 0:
            parent = self.mft_entries.get(current.parent_mft_number)
            if parent is None or parent.filename is None:
                break
            if parent.filename == "":
                break
            path_parts.append(parent.filename)
            current = parent

        path_parts.reverse()
        return "\\".join(path_parts)

    def _read_nonresident_data(self, runs: List[FileSegment]) -> Optional[bytes]:
        """Read the actual data for a set of data runs."""
        if not runs:
            return None

        result = bytearray()
        for seg in runs:
            cluster_data = self.read_physical(seg.lcn)
            if cluster_data is None:
                return None
            result.extend(cluster_data)
        return bytes(result)


# ─────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────

def _ntfs_time_unix(low32: int, high32: int) -> int:
    """Consistent unix timestamp conversion for tests."""
    return _ntfs_time_to_unix(low32, high32)


def _encode_ntfs_time(unix_ts: int) -> Tuple[int, int]:
    """Convert Unix timestamp to NTFS low/high 32-bit."""
    ntfs_ts = (unix_ts * 10000000) + 116444736000000000
    low = ntfs_ts & 0xFFFFFFFF
    high = (ntfs_ts >> 32) & 0xFFFFFFFF
    return low, high


def _pack_uint(value: int, num_bytes: int) -> bytes:
    return value.to_bytes(num_bytes, "little")


def _build_filename_attr(parent_mft: int, name: str,
                         created: int, modified: int,
                         size: int, is_dir: bool = False) -> bytes:
    """Build a resident $FILE_NAME attribute for testing."""
    creation_low, creation_high = _pack_uint(created & 0xFFFFFFFF, 4), \
                                  _pack_uint((created >> 32) & 0xFFFFFFFF, 4)
    modified_low, modified_high = _pack_uint(modified & 0xFFFFFFFF, 4), \
                                 _pack_uint((modified >> 32) & 0xFFFFFFFF, 4)
    change_low, change_high = _pack_uint(modified & 0xFFFFFFFF, 4), \
                              _pack_uint((modified >> 32) & 0xFFFFFFFF, 4)

    flags = 0
    if is_dir:
        flags |= FILENAME_FLAG_DIRECTORY
    else:
        flags |= FILENAME_FLAG_ARCHIVE

    header = (
        _pack_uint(parent_mft, 8)        # parent MFT
        + _pack_uint(created, 8)         # creation time
        + _pack_uint(modified, 8)        # modification time
        + _pack_uint(modified, 8)        # directory modification time
        + _pack_uint(modified, 8)        # change time
        + _pack_uint(size, 8)            # file size
        + _pack_uint(size, 8)            # allocated size
        + _pack_uint(flags, 4)           # flags
        + _pack_uint(0, 4)               # EA size
        + _pack_uint(0, 2)               # run list offset
        + _pack_uint(0, 2)               # run list size
        + bytes([0, 0, 0])               # reserved
        + bytes([4, 0])                  # Windows filename type, length 2 (test)
    )
    name_utf16 = name.encode("utf-16-le")
    name_field = _pack_uint(len(name_utf16) // 2, 2) + _pack_uint(0, 2) + name_utf16 + b"\x00\x00"
    return header + name_field


def _encode_data_runs(segments: List[Tuple[int, int, int]]) -> bytes:
    """Encode data runs: each segment = (lcn, vcn, length)."""
    result = bytearray()
    i = 0
    current_vcn = 0
    current_lcn = 0

    for lcn, vcn, length in segments:
        offset = lcn - current_lcn
        run_len = length
        delta_vcn = vcn - current_vcn

        if i > 0:
            prev_len = segments[i - 1][2] if i - 1 < len(segments) else 1
            run_len = segments[i][2]

        # Encode run length
        if run_len == 0:
            break
        length_byte = min(run_len, 0x0F)
        offset_byte = offset & 0x0F if offset >= 0 else (offset & 0x0F)
        combined = (offset_byte << 4) | length_byte
        result.append(combined)

        current_lcn = lcn
        current_vcn = vcn
        i += 1

    return bytes(result)


class _MockDiskHandle:
    """Mock disk handle for testing — supports write and read."""

    def __init__(self):
        self._buffer: Dict[int, bytes] = {}
        self.read_count = 0

    def write(self, lcn: int, data: bytes) -> int:
        self._buffer[lcn] = data
        return len(data)

    def read(self, lcn: int) -> Optional[bytes]:
        self.read_count += 1
        return self._buffer.get(lcn)


def _build_test_mft_record(record_number: int, parent_mft: int,
                           filename: str, file_size: int,
                           created: int, modified: int,
                           is_dir: bool = False, is_hidden: bool = False,
                           is_system: bool = False,
                           is_compressed: bool = False,
                           file_extension: str = ".exe"
                           ) -> bytes:
    """Build a full 1024-byte MFT record for testing."""
    record = bytearray(MFT_RECORD_SIZE)

    # Magic
    record[0:4] = NTFS_MAGIC

    # Sequence number
    struct.pack_into("<H", record, 4, 1)

    # Link count
    struct.pack_into("<H", record, 6, 1)

    # Attribute list offset (0 = none)
    # struct.pack_into("<I", record, 8, 0)

    # Attribute size = 1024 (entire record)
    struct.pack_into("<I", record, 12, MFT_RECORD_SIZE)

    # Next attribute ID
    struct.pack_into("<I", record, 16, 0x30)

    # MFT record number
    struct.pack_into("<I", record, 20, record_number)

    # Build attribute at offset 24
    attr_offset = 24

    # Standard Information attribute
    struct.pack_into("<I", record, attr_offset, ATTR_STANDARD_INFORMATION)  # type
    si_size = 80  # 48 header + 32 timestamps
    struct.pack_into("<I", record, attr_offset + 4, si_size)
    struct.pack_into("<H", record, attr_offset + 8, 0)  # flags (resident)
    struct.pack_into("<H", record, attr_offset + 10, 1)  # instance
    struct.pack_into("<H", record, attr_offset + 12, 0)  # offset
    struct.pack_into("<I", record, attr_offset + 16, si_size)  # size
    struct.pack_into("<I", record, attr_offset + 20, si_size)  # aligned size
    struct.pack_into("<H", record, attr_offset + 24, 48)  # data offset
    struct.pack_into("<H", record, attr_offset + 26, 0)  # reserved
    struct.pack_into("<I", record, attr_offset + 28, 0)  # status

    # Write timestamps to SI data area
    ts_offset = attr_offset + 48  # after 48-byte SI header
    creation_low, creation_high = _encode_ntfs_time(created)
    modified_low, modified_high = _encode_ntfs_time(modified)
    struct.pack_into("<I", record, ts_offset, creation_low)
    struct.pack_into("<I", record, ts_offset + 4, creation_high)
    struct.pack_into("<I", record, ts_offset + 8, modified_low)
    struct.pack_into("<I", record, ts_offset + 12, modified_high)
    struct.pack_into("<I", record, ts_offset + 16, modified_low)
    struct.pack_into("<I", record, ts_offset + 20, modified_high)
    struct.pack_into("<I", record, ts_offset + 24, modified_low)
    struct.pack_into("<I", record, ts_offset + 28, modified_high)
    struct.pack_into("<I", record, ts_offset + 32, modified_low)
    struct.pack_into("<I", record, ts_offset + 36, modified_high)
    struct.pack_into("<I", record, ts_offset + 40, modified_low)
    struct.pack_into("<I", record, ts_offset + 44, modified_high)

    attr_offset += si_size

    # FILE_NAME attribute (residing in the record)
    name_data = _build_filename_attr(parent_mft, filename,
                                       created, modified,
                                       file_size, is_dir)
    fn_size = len(name_data)
    struct.pack_into("<I", record, attr_offset, ATTR_FILE_NAME)
    struct.pack_into("<I", record, attr_offset + 4, fn_size)
    struct.pack_into("<H", record, attr_offset + 8, 0)  # resident flag
    struct.pack_into("<H", record, attr_offset + 10, 1)  # instance
    struct.pack_into("<H", record, attr_offset + 12, attr_offset - 24)  # data offset
    struct.pack_into("<I", record, attr_offset + 16, fn_size)
    struct.pack_into("<I", record, attr_offset + 20, fn_size)

    # Copy file name data
    name_start = attr_offset + 48
    record[name_start: name_start + fn_size] = name_data

    fn_attr_end = attr_offset + fn_size
    attr_offset = fn_attr_end

    # DATA attribute (resident for small files)
    ext_bytes = file_extension.encode("ascii")
    dummy_data = b"A" * file_size if file_size > 0 else b""
    data_size = max(len(dummy_data), 4)
    struct.pack_into("<I", record, attr_offset, ATTR_DATA)
    struct.pack_into("<I", record, attr_offset + 4, data_size + 24)
    struct.pack_into("<H", record, attr_offset + 8, 0)  # resident
    struct.pack_into("<H", record, attr_offset + 10, 0)  # instance
    struct.pack_into("<H", record, attr_offset + 12, attr_offset - 24)  # data offset
    struct.pack_into("<I", record, attr_offset + 16, data_size + 24)
    struct.pack_into("<I", record, attr_offset + 20, data_size + 24)

    # Write the attribute list for the data attribute
    struct.pack_into("<I", record, attr_offset + 24, data_size + 24)
    struct.pack_into("<I", record, attr_offset + 28, 1)  # length = 1 (resident)
    struct.pack_into("<B", record, attr_offset + 32, 0)  # key size
    struct.pack_into("<B", record, attr_offset + 33, data_size)  # value size
    struct.pack_into("<I", record, attr_offset + 34, ATTR_DATA)
    struct.pack_into("<H", record, attr_offset + 38, 0)  # instance
    struct.pack_into("<H", record, attr_offset + 40, 0)  # name length

    if file_size > 0 and len(dummy_data) > 0:
        record[attr_offset + 44: attr_offset + 44 + len(dummy_data)] = dummy_data[:1024]

    # Zero out remaining bytes
    record[fn_attr_end + fn_size: MFT_RECORD_SIZE] = b"\x00" * (MFT_RECORD_SIZE - fn_attr_end - fn_size)

    return bytes(record)


def _test_data_runs():
    """Test 1: Data run encoding and decoding."""
    print("=" * 60)
    print("TEST 1: Data Run Encoding / Decoding")
    print("=" * 60)

    parser = NTFSParser(None)

    # Test case 1: Simple single run
    # lcn=5, vcn=0, length=10
    # length nibble = 0x0A (1 byte), offset nibble = 0x5 (1 byte)
    # Byte: 0x5A
    simple_run = bytes([0x5A])
    result = parser.parse_data_runs(simple_run)
    print(f"  Run data [0x5A] -> {result}")
    assert len(result) == 1
    assert result[0].lcn == 5
    assert result[0].vcn == 0
    assert result[0].length == 10
    print("  PASS: Simple single run")

    # Test case 2: Multi-run
    # Run 1: lcn=10, vcn=0, length=5  -> 0x5A
    # Run 2: offset = -5 relative (signed nibble), length = 3
    # offset byte: 0xFB (signed nibble -5 = 0xFB)
    # Combined byte: 0xBF (offset nibble = 0xF = -1 signed? No...)
    # Actually for offset_len=1, offset_byte=0xFB, signed value = 0xFB - 256 = -5
    # length nibble = 0x3 (length=3)
    # So byte = 0xFB << 4 | 3 = 0xBF
    # Combined: 0x5B, 0xBF
    multi_run = bytes([0x5B, 0xBF])
    result = parser.parse_data_runs(multi_run)
    print(f"  Run data [0x5B, 0xBF] -> {result}")
    assert len(result) == 2
    assert result[0].lcn == 10
    assert result[0].vcn == 0
    assert result[0].length == 5
    # Second run: lcn = 10 + (-5) = 5, vcn = 5, length = 3
    assert result[1].lcn == 5
    assert result[1].vcn == 5
    assert result[1].length == 3
    print("  PASS: Multi-run with relative offset")

    # Test case 3: Termination with zero nibble
    zero_run = bytes([0x00])
    result = parser.parse_data_runs(zero_run)
    assert len(result) == 0
    print("  PASS: Zero length terminates")

    # Test case 4: Long run lengths
    # length = 0x0F (15 bytes needed), offset = 0x01 (1 byte)
    # 0x1F = offset 1, length 15
    long_run = bytes([0x1F, 0x00])
    result = parser.parse_data_runs(long_run)
    assert len(result) == 0  # lcn=0 terminates
    print("  PASS: Zero LCN terminates")

    print()


def _test_filename_parsing():
    """Test 2: $FILE_NAME attribute parsing."""
    print("=" * 60)
    print("TEST 2: $FILE_NAME Attribute Parsing")
    print("=" * 60)

    parent_mft = 3
    filename = "testfile.txt"
    created_unix = 1609459200  # 2021-01-01 00:00:00 UTC
    modified_unix = 1640995200  # 2022-01-01 00:00:00 UTC
    file_size = 42
    is_dir = False

    name_data = _build_filename_attr(parent_mft, filename,
                                       created_unix, modified_unix,
                                       file_size, is_dir)

    parser = NTFSParser(None)
    parsed = parser.parse_variable_attribute(name_data, 0, ATTR_FILE_NAME)

    print(f"  Parsed filename: {parsed.get('name', 'N/A')}")
    print(f"  Parent MFT: {parsed.get('parent', 'N/A')}")
    print(f"  Created: {parsed.get('created', 'N/A')}")
    print(f"  Modified: {parsed.get('modified', 'N/A')}")
    print(f"  File size: {parsed.get('size', 'N/A')}")
    print(f"  Flags: {parsed.get('flags', 'N/A')}")
    print(f"  Type: {parsed.get('type', 'N/A')}")

    assert parsed.get("name") == filename, f"Expected '{filename}', got '{parsed.get('name')}'"
    assert parsed.get("parent") == parent_mft
    assert parsed.get("created") == created_unix
    assert parsed.get("modified") == modified_unix
    assert parsed.get("size") == file_size
    assert parsed.get("type") == 4  # WIN32+DOS
    print("  PASS: $FILE_NAME attribute parsed correctly")
    print()


def _test_mft_entry():
    """Test 3: Full MFTEntry from MFT record."""
    print("=" * 60)
    print("TEST 3: Full MFTEntry Reconstruction")
    print("=" * 60)

    # Create test MFT record
    created_unix = 1609459200
    modified_unix = 1640995200

    record = _build_test_mft_record(
        record_number=5,
        parent_mft=3,
        filename="Windows\\System32\\notepad.exe",
        file_size=256,
        created=created_unix,
        modified=modified_unix,
        is_dir=False,
        is_hidden=True,
        is_system=True,
        is_compressed=False,
        file_extension=".exe"
    )

    # Write to mock disk
    mock_disk = _MockDiskHandle()
    mock_disk.write(5, record)

    parser = NTFSParser(mock_disk)

    # Parse the record
    entry = parser.parse_mft_record(5)

    assert entry is not None, "MFT entry should not be None"
    assert entry.file_number == 5
    assert entry.filename == "Windows\\System32\\notepad.exe"
    assert entry.is_hidden is True
    assert entry.is_system is True
    assert entry.is_directory is False
    assert entry.size == 256
    assert entry.created == created_unix
    assert entry.modified == modified_unix

    print(f"  File number: {entry.file_number}")
    print(f"  Filename: {entry.filename}")
    print(f"  Parent MFT: {entry.parent_mft_number}")
    print(f"  Size: {entry.size}")
    print(f"  Is hidden: {entry.is_hidden}")
    print(f"  Is system: {entry.is_system}")
    print(f"  Is directory: {entry.is_directory}")
    print(f"  Created: {entry.created}")
    print(f"  Modified: {entry.modified}")

    print("  PASS: MFTEntry reconstructed correctly")
    print()


def _test_directory_building():
    """Test 4: Directory entry with parent chain."""
    print("=" * 60)
    print("TEST 4: Directory Entry Reconstruction")
    print("=" * 60)

    created_unix = 1609459200
    modified_unix = 1640995200

    # Root directory (MFT #4)
    record_root = _build_test_mft_record(
        record_number=4,
        parent_mft=0,
        filename="",
        file_size=0,
        created=created_unix,
        modified=modified_unix,
        is_dir=True
    )

    # Child file (MFT #5)
    record_child = _build_test_mft_record(
        record_number=5,
        parent_mft=4,
        filename="testdir\\readme.txt",
        file_size=128,
        created=created_unix,
        modified=modified_unix,
        is_dir=False
    )

    mock_disk = _MockDiskHandle()
    mock_disk.write(4, record_root)
    mock_disk.write(5, record_child)

    parser = NTFSParser(mock_disk)
    entry = parser.parse_mft_record(4)

    assert entry is not None
    assert entry.is_directory is True
    assert entry.file_number == 4

    entry2 = parser.parse_mft_record(5)
    assert entry2 is not None
    assert entry2.filename == "testdir\\readme.txt"
    assert entry2.parent_mft_number == 4

    print(f"  Root entry: MFT #{entry.file_number}, dir={entry.is_directory}")
    print(f"  Child entry: MFT #{entry2.file_number}, filename={entry2.filename}")
    print(f"  Child parent: MFT #{entry2.parent_mft_number}")

    print("  PASS: Directory entries reconstructed correctly")
    print()


def main():
    print()
    print("#" * 60)
    print("#  NTFS MFT Parser — Test Suite")
    print("#" * 60)
    print()

    _test_data_runs()
    _test_filename_parsing()
    _test_mft_entry()
    _test_directory_building()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
