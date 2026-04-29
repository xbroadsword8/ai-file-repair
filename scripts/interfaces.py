"""
Disk Recovery Core Interfaces
定義各模組之間的介面合約
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum


class BadSectorPolicy(Enum):
    """Bad Sector 處理策略"""
    SKIP = "skip"           # 跳過，用 0xFF 填充
    REREGE = "rereg"        # 重複讀取多次，取多數
    REPORT = "report"       # 標記但不處理


@dataclass
class FileSegment:
    """檔案的一個連續區塊 (VCN/LCN mapping)"""
    lcn: int              # Logical Cluster Number on disk
    vcn: int              # Virtual Cluster Number
    length: int           # 長度 (sectors or clusters)
    
    @property
    def start_lcn(self) -> int:
        return self.lcn
    
    @property
    def end_lcn(self) -> int:
        return self.lcn + self.length - 1


@dataclass
class MFTEntry:
    """MFT (Master File Table) 中的一筆記錄"""
    file_number: int          # MFT record number
    filename: Optional[str]   # Filename (non-ROOT)
    file_extension: Optional[str]
    size: int                 # File size (bytes)
    created: Optional[int]    # Unix timestamp
    modified: Optional[int]   # Unix timestamp
    allocated_size: int       # Allocated disk space
    is_directory: bool
    is_hidden: bool
    is_system: bool
    is_compressed: bool
    is_encrypted: bool
    has_data_resident: bool   # Data resident in MFT (small files)
    data_runs: List[FileSegment] = field(default_factory=list)
    parent_mft_number: Optional[int] = None  # Parent directory MFT number
    attribute_type: str = "FILE"
    
    @property
    def full_name(self) -> str:
        return self.filename or f"unknown_{self.file_number}"
    
    @property
    def size_str(self) -> str:
        if self.size >= 1024**3:
            return f"{self.size / (1024**3):.2f} GB"
        elif self.size >= 1024**2:
            return f"{self.size / (1024**2):.2f} MB"
        elif self.size >= 1024:
            return f"{self.size / 1024:.1f} KB"
        return f"{self.size} bytes"


@dataclass
class RawScanResult:
    """RAW 磁碟掃描結果 (Magic Number Scan)"""
    file_type: str            # jpg, png, pdf, etc.
    offset: int               # Byte offset on disk
    size: int                 # Estimated size
    confidence: float         # 0.0 ~ 1.0
    header_bytes: bytes       # First bytes for verification
    end_marker_found: bool    # Whether end marker was found


@dataclass
class RecoveredFile:
    """最終 recover 的檔案"""
    original_name: str        # Original filename (from MFT or RAW)
    file_type: str            # Type
    size: int                 # Size
    is_mft_recovered: bool    # Recovered via MFT (more reliable)
    mft_entry: Optional[MFTEntry] = None
    raw_result: Optional[RawScanResult] = None
    segments: List[FileSegment] = field(default_factory=list)
    bad_sectors: List[int] = field(default_factory=list)
    confidence: float = 1.0   # 1.0 = complete
    
    @property
    def has_gaps(self) -> bool:
        return len(self.bad_sectors) > 0
    
    @property
    def size_str(self) -> str:
        if self.size >= 1024**3:
            return f"{self.size / (1024**3):.2f} GB"
        elif self.size >= 1024**2:
            return f"{self.size / (1024**2):.2f} MB"
        elif self.size >= 1024:
            return f"{self.size / 1024:.1f} KB"
        return f"{self.size} bytes"


# Interface: NTFS Parser
class NTFSParser:
    """NTFS MFT 解析器介面"""
    def __init__(self, disk_handle, sector_size: int = 512):
        self.disk_handle = disk_handle
        self.sector_size = sector_size
    
    def parse_mft(self) -> List[MFTEntry]:
        raise NotImplementedError
    
    def parse_directory(self, mft_entry: MFTEntry) -> List[MFTEntry]:
        raise NotImplementedError
    
    def build_file_map(self) -> Dict[str, MFTEntry]:
        raise NotImplementedError


# Interface: Disk Scanner (RAW)
class DiskScanner:
    """RAW 磁碟掃描器介面"""
    def __init__(self, disk_handle, sector_size: int = 512,
                 error_mode: BadSectorPolicy = BadSectorPolicy.SKIP):
        self.disk_handle = disk_handle
        self.sector_size = sector_size
        self.error_mode = error_mode
    
    def scan_for_files(self, max_bytes: int = None) -> List[RawScanResult]:
        raise NotImplementedError
    
    def recover_raw_file(self, segment: RawScanResult) -> bytes:
        raise NotImplementedError
    
    def read_sector(self, sector_num: int) -> Optional[bytes]:
        raise NotImplementedError


# Interface: Recovery Engine
class RecoveryEngine:
    """整合 MFT + RAW + Bad Sector 的恢復引擎"""
    def __init__(self, ntfs_parser: NTFSParser, 
                 raw_scanner: DiskScanner,
                 error_mode: BadSectorPolicy = BadSectorPolicy.SKIP):
        self.ntfs_parser = ntfs_parser
        self.raw_scanner = raw_scanner
        self.error_mode = error_mode
    
    def recover_mft_files(self, max_count: int = 1000) -> List[RecoveredFile]:
        raise NotImplementedError
    
    def recover_raw_files(self, min_confidence: float = 0.7) -> List[RecoveredFile]:
        raise NotImplementedError
    
    def recover_file_data(self, file_info: RecoveredFile) -> bytes:
        raise NotImplementedError
