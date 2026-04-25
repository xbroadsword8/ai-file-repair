"""
Disk Recovery - Based on Research
根據研究實作的磁碟recover工具

參考：
- PhotoRec
- TestDisk  
- Foremost
- The Sleuth Kit (pytsk3)
"""

import os
import sys
import struct
import subprocess
import tempfile
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


# ============================================
# MBR/Partition Table Parsing
# ============================================

@dataclass
class PartitionEntry:
    """分區條目"""
    status: int  # 0x00 inactive, 0x80 active/bootable
    start_chs: tuple  # Cylinder-Head-Sector
    partition_type: int
    end_chs: tuple
    lba_start: int  # Logical Block Address
    num_sectors: int


@dataclass
class DiskInfo:
    """磁碟資訊"""
    device_path: str
    size_bytes: int
    sector_size: int
    num_sectors: int
    model: str = ""
    serial: str = ""
    vendor: str = ""
    partitions: List[PartitionEntry] = None
    
    def __post_init__(self):
        if self.partitions is None:
            self.partitions = []


class MBRParser:
    """MBR 解析器"""
    
    # Partition type codes
    PARTITION_TYPES = {
        0x00: "Empty",
        0x01: "FAT12",
        0x04: "FAT16",
        0x05: "Extended",
        0x06: "FAT16B",
        0x07: "NTFS",
        0x0B: "FAT32",
        0x0C: "FAT32(LBA)",
        0x0E: "FAT16(LBA)",
        0x0F: "Extended(LBA)",
        0x83: "Linux",
        0x82: "Linux Swap",
        0x85: "Linux Extended",
        0xAF: "HFS+",
        0xAB: "APFS",
        0xC7: "Solaris",
        0xFE: "Windows NT",
        0xFB: "VMware",
    }
    
    def __init__(self, disk_path: str):
        self.disk_path = disk_path
        self.disk_handle = None
        self.mbr_data = None
        
    def open_disk(self) -> bool:
        """打開磁碟"""
        try:
            if sys.platform == 'win32':
                import ctypes
                
                if not self.disk_path.startswith('\\\\.\\'):
                    if self.disk_path == 'C':
                        path = '\\\\.\\PhysicalDrive0'
                    else:
                        path = f"\\\\.\\{self.disk_path}"
                else:
                    path = self.disk_path
                
                self.disk_handle = ctypes.windll.kernel32.CreateFileA(
                    path.encode(),
                    0x80000000,  # GENERIC_READ
                    0x00000001 | 0x00000002,
                    None,
                    3,  # OPEN_EXISTING
                    0,
                    None
                )
                
                return self.disk_handle != -1
            else:
                self.disk_handle = os.open(self.disk_path, os.O_RDONLY)
                return True
        except:
            return False
    
    def read_mbr(self) -> bool:
        """讀取 MBR (sector 0)"""
        try:
            if sys.platform == 'win32':
                import ctypes
                
                # Read sector 0
                offset = 0
                ctypes.windll.kernel32.SetFilePointer(
                    self.disk_handle, offset, None, 0
                )
                
                buffer = ctypes.create_string_buffer(512)
                bytes_read = ctypes.c_ulong()
                
                result = ctypes.windll.kernel32.ReadFile(
                    self.disk_handle,
                    buffer,
                    512,
                    ctypes.byref(bytes_read),
                    None
                )
                
                if not result or bytes_read.value != 512:
                    return False
                
                self.mbr_data = buffer.raw
                return True
            else:
                os.lseek(self.disk_handle, 0, 0)
                self.mbr_data = os.read(self.disk_handle, 512)
                return len(self.mbr_data) == 512
        except:
            return False
    
    def parse_partitions(self) -> List[PartitionEntry]:
        """解析分區表"""
        if not self.mbr_data:
            return []
        
        partitions = []
        
        # Partition table starts at offset 446
        # 4 entries, each 16 bytes
        for i in range(4):
            offset = 446 + i * 16
            entry = self.mbr_data[offset:offset + 16]
            
            if len(entry) < 16:
                continue
            
            # Parse entry
            status = entry[0]
            
            # CHS (Cylinder-Head-Sector) - legacy
            chs_start = struct.unpack('<HBB', entry[1:4])
            partition_type = entry[4]
            chs_end = struct.unpack('<HBB', entry[5:8])
            
            # LBA (Logical Block Address)
            lba_start = struct.unpack('<I', entry[8:12])[0]
            num_sectors = struct.unpack('<I', entry[12:16])[0]
            
            # Skip empty entries
            if num_sectors == 0:
                continue
            
            partition = PartitionEntry(
                status=status,
                start_chs=chs_start,
                partition_type=partition_type,
                end_chs=chs_end,
                lba_start=lba_start,
                num_sectors=num_sectors
            )
            
            partitions.append(partition)
        
        return partitions
    
    def get_disk_info(self) -> Optional[DiskInfo]:
        """獲取磁碟資訊"""
        try:
            if sys.platform == 'win32':
                import ctypes
                
                # Get drive geometry
                geometry = ctypes.create_string_buffer(24)
                bytes_returned = ctypes.c_ulong()
                
                result = ctypes.windll.kernel32.DeviceIoControl(
                    self.disk_handle,
                    0x70000,  # IOCTL_DISK_GET_DRIVE_GEOMETRY
                    None,
                    0,
                    geometry,
                    24,
                    ctypes.byref(bytes_returned),
                    None
                )
                
                if not result:
                    return None
                
                # Parse geometry
                size_bytes = struct.unpack('Q', geometry[16:24])[0]
                sector_size = struct.unpack('I', geometry[16:20])[0]
                num_sectors = struct.unpack('I', geometry[8:12])[0]
                
                # Get serial/model (via WMI or registry)
                # This is a simplified version
                model = ""
                serial = ""
                
                # Try to get serial via registry
                try:
                    import winreg
                    # This is platform-specific and may vary
                    pass
                except:
                    pass
                
                return DiskInfo(
                    device_path=self.disk_path,
                    size_bytes=size_bytes,
                    sector_size=sector_size,
                    num_sectors=num_sectors,
                    model=model,
                    serial=serial
                )
            else:
                # Linux - read from /sys
                device_name = os.path.basename(self.disk_path)
                
                # Read size
                with open(f'/sys/block/{device_name}/size') as f:
                    sectors = int(f.read().strip())
                
                # Read sector size
                with open(f'/sys/block/{device_name}/queue/physical_block_size') as f:
                    sector_size = int(f.read().strip())
                
                # Read model
                try:
                    with open(f'/sys/block/{device_name}/device/model') as f:
                        model = f.read().strip()
                except:
                    model = ""
                
                # Read serial
                try:
                    with open(f'/sys/block/{device_name}/device/serial') as f:
                        serial = f.read().strip()
                except:
                    serial = ""
                
                return DiskInfo(
                    device_path=self.disk_path,
                    size_bytes=sectors * sector_size,
                    sector_size=sector_size,
                    num_sectors=sectors,
                    model=model,
                    serial=serial
                )
        except Exception as e:
            print(f"Error getting disk info: {e}")
            return None
    
    def close(self):
        """關閉磁碟"""
        if sys.platform == 'win32' and self.disk_handle:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(self.disk_handle)
            self.disk_handle = None
        elif self.disk_handle:
            os.close(self.disk_handle)
            self.disk_handle = None


# ============================================
# File Recovery - Magic Number Based
# ============================================

@dataclass
class RecoveredFile:
    """recover的文件"""
    filename: str
    filepath: str
    size_bytes: int
    file_type: str
    sector_start: int
    sector_end: int
    confidence: float  # 0.0 - 1.0


class FileRecovery:
    """文件recover工具"""
    
    # File signatures (magic numbers)
    SIGNATURES = {
        'jpg': {
            'magic': b'\xFF\xD8\xFF',
            'offset': 0,
            'end_magic': b'\xFF\xD9',
            'type': 'JPEG Image',
        },
        'png': {
            'magic': b'\x89PNG\r\n\x1a\n',
            'offset': 0,
            'end_magic': b'IEND\x00\x42\x60\x82',
            'type': 'PNG Image',
        },
        'jpeg': {
            'magic': b'\xFF\xD8\xFF',
            'offset': 0,
            'end_magic': b'\xFF\xD9',
            'type': 'JPEG Image',
        },
        'gif': {
            'magic': b'GIF87a',
            'offset': 0,
            'end_magic': b'\x00\x3B',
            'type': 'GIF Image',
        },
        'bmp': {
            'magic': b'BM',
            'offset': 0,
            'end_magic': None,
            'type': 'Bitmap Image',
        },
        'pdf': {
            'magic': b'%PDF',
            'offset': 0,
            'end_magic': b'%%EOF',
            'type': 'PDF Document',
        },
        'mp3': {
            'magic': b'\xFF\xFB',
            'offset': 0,
            'end_magic': None,
            'type': 'MP3 Audio',
        },
        'mp4': {
            'magic': b'\x00\x00\x00\x1f\x66\x74\x79\x70',
            'offset': 0,
            'end_magic': None,
            'type': 'MP4 Video',
        },
        'avi': {
            'magic': b'RIFF',
            'offset': 0,
            'end_magic': None,
            'type': 'AVI Video',
        },
        'wav': {
            'magic': b'RIFF',
            'offset': 0,
            'end_magic': None,
            'type': 'WAV Audio',
        },
        'zip': {
            'magic': b'PK\x03\x04',
            'offset': 0,
            'end_magic': None,
            'type': 'ZIP Archive',
        },
        'rar': {
            'magic': b'Rar!',
            'offset': 0,
            'end_magic': None,
            'type': 'RAR Archive',
        },
        'tar': {
            'magic': b'ustar',
            'offset': 257,
            'end_magic': None,
            'type': 'TAR Archive',
        },
        'gz': {
            'magic': b'\x1F\x8B\x08',
            'offset': 0,
            'end_magic': None,
            'type': 'GZIP',
        },
        'bmp': {
            'magic': b'BM',
            'offset': 0,
            'end_magic': None,
            'type': 'Bitmap',
        },
        'doc': {
            'magic': b'\xD0\xCF\x11\xE0',
            'offset': 0,
            'end_magic': None,
            'type': 'Word Document',
        },
        'xls': {
            'magic': b'\xD0\xCF\x11\xE0',
            'offset': 0,
            'end_magic': None,
            'type': 'Excel Document',
        },
        'ppt': {
            'magic': b'\xD0\xCF\x11\xE0',
            'offset': 0,
            'end_magic': None,
            'type': 'PowerPoint Document',
        },
        'mpg': {
            'magic': b'\x00\x00\x01\xB3',
            'offset': 0,
            'end_magic': None,
            'type': 'MPEG Video',
        },
        'flv': {
            'magic': b'FLV',
            'offset': 0,
            'end_magic': None,
            'type': 'FLV Video',
        },
        'swf': {
            'magic': b'FWS',
            'offset': 0,
            'end_magic': None,
            'type': 'Flash SWF',
        },
        'html': {
            'magic': b'<!DOCTYPE',
            'offset': 0,
            'end_magic': None,
            'type': 'HTML',
        },
        'xml': {
            'magic': b'<?xml',
            'offset': 0,
            'end_magic': None,
            'type': 'XML',
        },
        'json': {
            'magic': b'{',
            'offset': 0,
            'end_magic': None,
            'type': 'JSON',
        },
    }
    
    def __init__(self, disk_path: str, sector_size: int = 512):
        self.disk_path = disk_path
        self.sector_size = sector_size
        self.disk_handle = None
        self.recovered_files = []
        
    def open_disk(self) -> bool:
        """打開磁碟"""
        try:
            if sys.platform == 'win32':
                import ctypes
                
                if not self.disk_path.startswith('\\\\.\\'):
                    if self.disk_path == 'C':
                        path = '\\\\.\\PhysicalDrive0'
                    else:
                        path = f"\\\\.\\{self.disk_path}"
                else:
                    path = self.disk_path
                
                self.disk_handle = ctypes.windll.kernel32.CreateFileA(
                    path.encode(),
                    0x80000000,
                    0x00000001 | 0x00000002,
                    None,
                    3,
                    0,
                    None
                )
                
                return self.disk_handle != -1
            else:
                self.disk_handle = os.open(self.disk_path, os.O_RDONLY)
                return True
        except:
            return False
    
    def read_sector(self, sector_num: int) -> Optional[bytes]:
        """讀取sector"""
        try:
            if sys.platform == 'win32':
                import ctypes
                
                offset = sector_num * self.sector_size
                ctypes.windll.kernel32.SetFilePointer(
                    self.disk_handle, offset, None, 0
                )
                
                buffer = ctypes.create_string_buffer(self.sector_size)
                bytes_read = ctypes.c_ulong()
                
                result = ctypes.windll.kernel32.ReadFile(
                    self.disk_handle,
                    buffer,
                    self.sector_size,
                    ctypes.byref(bytes_read),
                    None
                )
                
                if not result:
                    return None
                
                return buffer.raw[:bytes_read.value]
            else:
                os.lseek(self.disk_handle, sector_num * self.sector_size, 0)
                return os.read(self.disk_handle, self.sector_size)
        except:
            return None
    
    def scan_for_files(self, max_sectors: int = 10000) -> List[RecoveredFile]:
        """掃描文件"""
        print(f"開始掃描磁碟 {self.disk_path}...")
        print(f"掃描範圍: 0 到 {max_sectors}")
        
        self.recovered_files = []
        
        # Scan sectors
        for sector in range(0, min(max_sectors, 100000), 100):
            data = self.read_sector(sector)
            
            if not data:
                continue
            
            # Check each signature
            for file_type, sig_info in self.SIGNATURES.items():
                magic = sig_info['magic']
                offset = sig_info['offset']
                
                if offset > len(data):
                    continue
                
                if data[offset:offset + len(magic)] == magic:
                    # Found file signature
                    confidence = self._calculate_confidence(file_type, data, offset)
                    
                    # Estimate file size
                    file_size = self._estimate_file_size(file_type, data, offset)
                    
                    if file_size > 0 and file_size < 100 * 1024 * 1024:  # Max 100MB
                        recovered = RecoveredFile(
                            filename=f"recovered_{sector}_{file_type}.{file_type}",
                            filepath=f"Recover/{file_type}/",
                            size_bytes=file_size,
                            file_type=file_type,
                            sector_start=sector,
                            sector_end=sector + (file_size // self.sector_size) + 1,
                            confidence=confidence
                        )
                        
                        self.recovered_files.append(recovered)
                        print(f"  ✓ 找到 {file_type} 文件: {file_size:,} bytes (sector {sector})")
        
        print(f"\n共找到 {len(self.recovered_files)} 個文件")
        return self.recovered_files
    
    def _calculate_confidence(self, file_type: str, data: bytes, offset: int) -> float:
        """計算confidence"""
        # Check for additional markers
        sig_info = self.SIGNATURES.get(file_type, {})
        end_magic = sig_info.get('end_magic')
        
        if end_magic:
            if end_magic in data[offset:offset + 1000]:
                return 0.9
        return 0.7
    
    def _estimate_file_size(self, file_type: str, data: bytes, offset: int) -> int:
        """估計文件大小"""
        sig_info = self.SIGNATURES.get(file_type, {})
        end_magic = sig_info.get('end_magic')
        
        if end_magic:
            end_pos = data[offset:].find(end_magic)
            if end_pos != -1:
                return offset + end_pos + len(end_magic)
        
        # Default: assume sector-aligned
        return 512 * 10  # 10 sectors minimum
        
    def export_files(self, output_dir: str) -> bool:
        """導出文件"""
        try:
            output_path = Path(output_dir) / "Recover"
            output_path.mkdir(parents=True, exist_ok=True)
            
            for file_info in self.recovered_files:
                # Read data from sectors
                data = b''
                for sector in range(file_info.sector_start, file_info.sector_end):
                    sector_data = self.read_sector(sector)
                    if sector_data:
                        data += sector_data
                
                # Write file
                filename = file_info.filename
                if not filename.endswith(f'.{file_info.file_type}'):
                    filename += f'.{file_info.file_type}'
                
                file_path = output_path / filename
                with open(file_path, 'wb') as f:
                    f.write(data[:file_info.size_bytes])
                
                print(f"  ✓ 匯出: {filename}")
            
            return True
        except Exception as e:
            print(f"Export failed: {e}")
            return False
    
    def close(self):
        """關閉磁碟"""
        if self.disk_handle:
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.disk_handle)
            else:
                os.close(self.disk_handle)
            self.disk_handle = None


# ============================================
# Main Application
# ============================================

def main():
    """主程式"""
    print("=" * 60)
    print("AI File Repair - Disk Recovery")
    print("=" * 60)
    
    # Scan disks
    print("\n1. 掃描磁碟...")
    
    if sys.platform == 'win32':
        devices = [
            ('C:', '\\\\.\\PhysicalDrive0'),
            ('D:', '\\\\.\\PhysicalDrive1'),
            ('E:', '\\\\.\\PhysicalDrive2'),
            ('F:', '\\\\.\\PhysicalDrive3'),
        ]
    else:
        devices = [
            ('/dev/sda', '/dev/sda'),
            ('/dev/sdb', '/dev/sdb'),
            ('/dev/sdc', '/dev/sdc'),
            ('/dev/sdd', '/dev/sdd'),
        ]
    
    for drive_letter, device_path in devices:
        parser = MBRParser(device_path)
        if parser.open_disk():
            info = parser.get_disk_info()
            if info:
                print(f"  ✓ {drive_letter}: {info.size_bytes / (1024**3):.2f} GB")
                print(f"    Model: {info.model}")
                print(f"    Serial: {info.serial}")
                
                # Parse partitions
                parser.read_mbr()
                partitions = parser.parse_partitions()
                
                for p in partitions:
                    print(f"    Partition: {p.lba_start}-{p.lba_start + p.num_sectors}")
                    print(f"      Type: {MBRParser.PARTITION_TYPES.get(p.partition_type, 'Unknown')} ({p.partition_type:02X})")
            
            parser.close()
    
    # File recovery
    print("\n2. 文件recover...")
    
    recovery = FileRecovery('C:', 512)
    if recovery.open_disk():
        files = recovery.scan_for_files(max_sectors=50000)
        recovery.close()
        
        print(f"\n3. 匯出文件...")
        recovery.export_files('/tmp/recovered')
    
    print("\n完成！")


if __name__ == "__main__":
    main()