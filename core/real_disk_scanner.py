"""
Real Disk Scanner - 真正的磁碟掃描器
不使用任何範例/假資料，直接從磁碟讀實際資料
"""

import os
import sys
import struct
import ctypes
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiskInfo:
    """真實磁碟資訊"""
    device_id: str
    drive_letter: Optional[str]
    total_size_bytes: int
    total_size_gb: float
    sector_size: int
    num_sectors: int
    disk_type: str
    model_number: str  # 廠牌型号
    serial_number: str


@dataclass
class FileInfo:
    """真實文件資訊"""
    path: str
    name: str
    extension: str
    size_bytes: int
    size_kb: float
    size_mb: float
    size_gb: float
    file_type: str
    sector_offset: int
    is_recoverable: bool


class RealDiskScanner:
    """
    真正的磁碟掃描器
    - 使用 Windows API 獲取真實磁碟資訊
    - 實際讀取 sectors
    - 從實際資料中識別文件
    """
    
    # 實際的文件簽名 (從真實文件提取)
    REAL_FILE_SIGNATURES = {
        # 图像文件
        'jpg': (b'\xFF\xD8\xFF\xE0', 0, 200 * 1024, 100 * 1024 * 1024),
        'jpeg': (b'\xFF\xD8\xFF\xE0', 0, 200 * 1024, 100 * 1024 * 1024),
        'png': (b'\x89PNG\r\n\x1a\n', 0, 100 * 1024, 500 * 1024 * 1024),
        'gif': (b'GIF87a', 0, 100 * 1024, 100 * 1024 * 1024),
        'bmp': (b'BM', 0, 100 * 1024, 500 * 1024 * 1024),
        'tiff': (b'\x49\x49\x2A\x00', 0, 100 * 1024, 500 * 1024 * 1024),
        # 音訊文件
        'mp3': (b'\xFF\xFB', 0, 100 * 1024, 100 * 1024 * 1024),
        'wav': (b'RIFF', 0, 100 * 1024, 500 * 1024 * 1024),
        'flac': (b'\x66\x4C\x61\x43', 0, 100 * 1024, 100 * 1024 * 1024),
        'aac': (b'\xFF\xF1', 0, 100 * 1024, 100 * 1024 * 1024),
        # 影片文件
        'mp4': (b'\x00\x00\x00\x1f\x66\x74\x79\x70', 0, 100 * 1024, 10 * 1024 * 1024 * 1024),
        'avi': (b'RIFF', 0, 100 * 1024, 10 * 1024 * 1024 * 1024),
        'mov': (b'\x00\x00\x00\x14\x66\x74\x79\x70\x6D\x6F\x6F\x76', 0, 100 * 1024, 10 * 1024 * 1024 * 1024),
        'mkv': (b'\x1A\x45\xDF\xA3', 0, 100 * 1024, 10 * 1024 * 1024 * 1024),
        # 文档文件
        'pdf': (b'%PDF', 0, 10 * 1024, 500 * 1024 * 1024),
        'doc': (b'\xD0\xCF\x11\xE0', 0, 10 * 1024, 100 * 1024 * 1024),
        'docx': (b'PK\x03\x04', 0, 10 * 1024, 100 * 1024 * 1024),
        'xls': (b'\xD0\xCF\x11\xE0', 0, 10 * 1024, 100 * 1024 * 1024),
        'xlsx': (b'PK\x03\x04', 0, 10 * 1024, 100 * 1024 * 1024),
        'ppt': (b'\xD0\xCF\x11\xE0', 0, 10 * 1024, 100 * 1024 * 1024),
        'pptx': (b'PK\x03\x04', 0, 10 * 1024, 100 * 1024 * 1024),
        # 壓縮文件
        'zip': (b'PK\x03\x04', 0, 10 * 1024, 100 * 1024 * 1024),
        'rar': (b'Rar!', 0, 10 * 1024, 100 * 1024 * 1024),
        '7z': (b'\x37\x7A\xBC\xAF\x27\x1C', 0, 10 * 1024, 100 * 1024 * 1024),
        'tar': (b'ustar', 257, 10 * 1024, 100 * 1024 * 1024),
        'gz': (b'\x1F\x8B', 0, 10 * 1024, 100 * 1024 * 1024),
        # 程式文件
        'exe': (b'MZ', 0, 100 * 1024, 1 * 1024 * 1024 * 1024),
        'dll': (b'MZ', 0, 100 * 1024, 1 * 1024 * 1024 * 1024),
        'sys': (b'MZ', 0, 100 * 1024, 1 * 1024 * 1024 * 1024),
        'ini': (b'\xEF\xBB\xBF', 0, 100, 10 * 1024 * 1024),
        # 文本文件
        'txt': (None, 0, 100, 100 * 1024 * 1024),
        'json': (b'{', 0, 100, 50 * 1024 * 1024),
        'xml': (b'<?xml', 0, 100, 50 * 1024 * 1024),
        'html': (b'<!DOCTYPE', 0, 100, 50 * 1024 * 1024),
        'css': (b'/*', 0, 100, 10 * 1024 * 1024),
        'js': (None, 0, 100, 10 * 1024 * 1024),
        'py': (None, 0, 100, 10 * 1024 * 1024),
        'log': (None, 0, 100, 100 * 1024 * 1024),
    }
    
    def __init__(self, progress_callback=None, file_callback=None):
        """
        初始化磁碟掃描器
        
        Args:
            progress_callback: 進度回調函數 (sector_num, total_sectors)
            file_callback: 文件發現回調函數 (file_info)
        """
        self.progress_callback = progress_callback
        self.file_callback = file_callback
        self.disk_handle = None
        self.disk_info = None
        self.files_found = []
        self.scan_interrupted = False
        
    def get_disk_info(self, device_path: str) -> Optional[DiskInfo]:
        """
        獲取真實磁碟資訊（不使用假資料）
        
        Args:
            device_path: 磁碟路徑 (e.g., 'C:', '\\\\.\\PhysicalDrive0')
            
        Returns:
            DiskInfo 物件或 None
        """
        try:
            if sys.platform == 'win32':
                # Windows - 使用 CreateFile 和 DeviceIoControl
                import ctypes
                from ctypes import wintypes
                
                # 打開磁碟
                if not device_path.startswith('\\\\.\\'):
                    if device_path == 'C':
                        path = '\\\\.\\PhysicalDrive0'
                    else:
                        path = f"\\\\.\\{device_path}"
                else:
                    path = device_path
                
                handle = ctypes.windll.kernel32.CreateFileA(
                    path.encode(),
                    0x80000000,  # GENERIC_READ
                    0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
                    None,
                    3,  # OPEN_EXISTING
                    0,
                    None
                )
                
                if handle == -1:
                    return None
                
                # 獲取磁碟幾何資訊
                geometry = ctypes.create_string_buffer(24)
                bytes_returned = ctypes.c_ulong()
                
                result = ctypes.windll.kernel32.DeviceIoControl(
                    handle,
                    0x70000,  # IOCTL_DISK_GET_DRIVE_GEOMETRY
                    None,
                    0,
                    geometry,
                    24,
                    ctypes.byref(bytes_returned),
                    None
                )
                
                if not result:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    return None
                
                # 解析幾何資訊
                cylinders = struct.unpack('I', geometry[0:4])[0]
                tracks_per_cylinder = struct.unpack('I', geometry[4:8])[0]
                sectors_per_track = struct.unpack('I', geometry[8:12])[0]
                total_sectors = struct.unpack('I', geometry[12:16])[0]
                sector_size = struct.unpack('I', geometry[16:20])[0]
                total_size = struct.unpack('Q', geometry[16:24])[0]
                
                # 獲取磁碟型號和序列號
                model_number = ""
                serial_number = ""
                try:
                    # 嘗試獲取磁碟描述
                    import win32com.client
                    wmi = win32com.client.Dispatch("WMI")
                    disks = wmi.Win32_DiskDrive()
                    for disk in disks:
                        if disk.DeviceID == path.replace('\\\\.\\', ''):
                            model_number = disk.Model or ""
                            serial_number = disk.SerialNumber or ""
                            break
                except:
                    pass
                
                ctypes.windll.kernel32.CloseHandle(handle)
                
                # 計算大小
                total_size_gb = total_size / (1024 ** 3)
                
                # 確定磁碟類型
                if 'PhysicalDrive' in path:
                    disk_type = '物理磁碟'
                    drive_letter = None
                else:
                    disk_type = '磁碟機'
                    drive_letter = device_path[0]
                
                return DiskInfo(
                    device_id=path,
                    drive_letter=drive_letter,
                    total_size_bytes=total_size,
                    total_size_gb=total_size_gb,
                    sector_size=sector_size,
                    num_sectors=total_sectors,
                    disk_type=disk_type,
                    model_number=model_number,
                    serial_number=serial_number
                )
            else:
                # Linux - 讀取 /proc/diskstats
                return None
                
        except Exception as e:
            print(f"Error getting disk info: {e}")
            return None
    
    def scan_disk(self, device_path: str, max_sectors: int = 100000) -> List[FileInfo]:
        """
        真正掃描磁碟（從實際 sector 讀取資料）
        
        Args:
            device_path: 磁碟路徑
            max_sectors: 最多掃描的 sector 數量
            
        Returns:
            FileInfo 列表
        """
        print(f"開始掃描磁碟: {device_path}")
        
        # 獲取磁碟資訊
        self.disk_info = self.get_disk_info(device_path)
        if not self.disk_info:
            print("❌ 無法獲取磁碟資訊")
            return []
        
        print(f"磁碟: {self.disk_info.device_id}")
        print(f"容量: {self.disk_info.total_size_gb:.2f} GB")
        print(f"Sector Size: {self.disk_info.sector_size} bytes")
        print(f"Total Sectors: {self.disk_info.num_sectors}")
        
        # 打開磁碟
        if not self._open_disk(device_path):
            print("❌ 無法打開磁碟")
            return []
        
        self.files_found = []
        buffer = b''
        sector_size = self.disk_info.sector_size
        sectors_to_read = min(max_sectors, self.disk_info.num_sectors)
        
        print(f"掃描範圍: 0 ~ {sectors_to_read} sectors")
        
        # 讀取並掃描
        for sector_num in range(0, sectors_to_read, 100):
            if self.scan_interrupted:
                print("掃描已中斷")
                break
            
            # 讀取 100 個 sectors
            data = self._read_sectors(sector_num, 100)
            if not data:
                continue
            
            buffer += data
            
            # 在 buffer 中搜尋文件
            self._scan_buffer_for_files(buffer, sector_num * sector_size)
            
            # 更新進度
            if self.progress_callback:
                self.progress_callback(sector_num, sectors_to_read)
            
            # 顯示進度
            progress_pct = (sector_num / sectors_to_read) * 100
            print(f"掃描進度: {progress_pct:.1f}% ({sector_num}/{sectors_to_read})")
        
        self._close_disk()
        
        print(f"\n掃描完成！找到 {len(self.files_found)} 個文件")
        return self.files_found
    
    def _open_disk(self, device_path: str) -> bool:
        """打開磁碟（內部使用）"""
        try:
            if sys.platform == 'win32':
                import ctypes
                
                if not device_path.startswith('\\\\.\\'):
                    if device_path == 'C':
                        path = '\\\\.\\PhysicalDrive0'
                    else:
                        path = f"\\\\.\\{device_path}"
                else:
                    path = device_path
                
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
                return False
        except:
            return False
    
    def _read_sectors(self, sector_num: int, count: int) -> bytes:
        """讀取 sectors（內部使用）"""
        try:
            import ctypes
            
            offset = sector_num * self.disk_info.sector_size
            ctypes.windll.kernel32.SetFilePointer(
                self.disk_handle, offset, None, 0
            )
            
            buffer = ctypes.create_string_buffer(count * self.disk_info.sector_size)
            bytes_read = ctypes.c_ulong()
            
            result = ctypes.windll.kernel32.ReadFile(
                self.disk_handle,
                buffer,
                count * self.disk_info.sector_size,
                ctypes.byref(bytes_read),
                None
            )
            
            if not result:
                return b''
            
            return buffer.raw[:bytes_read.value]
        except:
            return b''
    
    def _scan_buffer_for_files(self, buffer: bytes, base_offset: int):
        """從 buffer 中搜尋文件（內部使用）"""
        for file_type, (magic, skip, min_size, max_size) in self.REAL_FILE_SIGNATURES.items():
            if magic is None:
                continue
            
            pos = 0
            while True:
                idx = buffer.find(magic, pos)
                if idx == -1:
                    break
                
                # 評估文件大小
                file_size = self._estimate_file_size(buffer, idx, file_type)
                
                if file_size >= min_size and file_size <= max_size:
                    # 構建文件資訊
                    file_info = FileInfo(
                        path=f"sector_{base_offset // self.disk_info.sector_size}_{idx}",
                        name=f"recovered_{file_type}_{base_offset // self.disk_info.sector_size}_{idx}",
                        extension=file_type,
                        size_bytes=file_size,
                        size_kb=file_size / 1024,
                        size_mb=file_size / (1024 ** 2),
                        size_gb=file_size / (1024 ** 3),
                        file_type=file_type,
                        sector_offset=base_offset + idx,
                        is_recoverable=True
                    )
                    
                    self.files_found.append(file_info)
                    
                    # 回調
                    if self.file_callback:
                        self.file_callback(file_info)
                
                pos = idx + 1
    
    def _estimate_file_size(self, data: bytes, start: int, file_type: str) -> int:
        """估計文件大小（內部使用）"""
        try:
            if file_type in ['jpg', 'jpeg']:
                end = data[start:].find(b'\xFF\xD9')
                return start + end + 2 if end != -1 else 0
            
            elif file_type == 'png':
                end = data[start:].find(b'IEND\x00\x42\x60\x82')
                return start + end + 8 if end != -1 else 0
            
            elif file_type == 'pdf':
                end = data[start:].find(b'%%EOF')
                return start + end + 5 if end != -1 else 0
            
            elif file_type in ['mp3']:
                # MP3 frame scanning
                frame_start = start
                count = 0
                while count < 10:
                    if frame_start + 4 > len(data):
                        break
                    header = struct.unpack('>I', data[frame_start:frame_start+4])[0]
                    if (header & 0xFFE00000) != 0xFFE00000:
                        break
                    frame_start += 416
                    count += 1
                return frame_start - start
            
            elif file_type in ['mp4', 'mov']:
                # MOOV box scanning
                moov_pos = data[start:].find(b'moov')
                return start + moov_pos + 8 if moov_pos != -1 else 0
            
            elif file_type in ['avi']:
                riff_pos = data[start:].find(b'RIFF')
                return start + riff_pos + 12 if riff_pos != -1 else 0
            
            elif file_type in ['zip', 'rar', '7z', 'tar', 'gz']:
                return min(100 * 1024 * 1024, len(data) - start)
            
            elif file_type in ['exe', 'dll', 'sys']:
                return min(1 * 1024 * 1024 * 1024, len(data) - start)
            
            elif file_type in ['txt', 'json', 'xml', 'html', 'css', 'js', 'py', 'log']:
                return min(100 * 1024 * 1024, len(data) - start)
            
            return 0
            
        except:
            return 0
    
    def _close_disk(self):
        """關閉磁碟（內部使用）"""
        try:
            if sys.platform == 'win32' and self.disk_handle:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.disk_handle)
                self.disk_handle = None
        except:
            pass
    
    def stop_scan(self):
        """停止掃描"""
        self.scan_interrupted = True


def main():
    """測試函數"""
    print("=" * 60)
    print("Real Disk Scanner Test")
    print("=" * 60)
    
    # 磁碟路徑 - 請根據您的系統修改
    device_path = "C:"  # 或 '\\\\.\\PhysicalDrive0'
    
    # 建立掃描器
    scanner = RealDiskScanner()
    
    # 獲取磁碟資訊
    disk_info = scanner.get_disk_info(device_path)
    
    if disk_info:
        print(f"\n磁碟資訊:")
        print(f"  Device: {disk_info.device_id}")
        print(f"  Size: {disk_info.total_size_gb:.2f} GB")
        print(f"  Sector Size: {disk_info.sector_size} bytes")
        print(f"  Model: {disk_info.model_number}")
        print(f"  Serial: {disk_info.serial_number}")
        
        # 開始掃描
        print("\n開始掃描...")
        files = scanner.scan_disk(device_path, max_sectors=10000)
        
        print(f"\n找到 {len(files)} 個文件:")
        for f in files[:10]:  # 顯示前 10 個
            print(f"  {f.name} ({f.size_mb:.2f} MB) - {f.file_type}")
        
        if len(files) > 10:
            print(f"  ... 以及 {len(files) - 10} 個其他文件")
    else:
        print("❌ 無法獲取磁碟資訊")
        print("請確保以管理員權限運行")


if __name__ == "__main__":
    main()