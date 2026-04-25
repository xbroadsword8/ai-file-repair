"""
Disk Recovery Module
磁碟資料recover核心模組
跳過 MBR/分區表，直接讀取磁碟數據
"""

import os
import sys
import struct
from pathlib import Path
from typing import List, Optional, Tuple
import hashlib


class DiskRecovery:
    """
    磁碟資料recover工具
    直接讀取磁碟 sectors， bypass MBR 和分區表
    """
    
    # 文件類型簽名 (Magic Numbers)
    FILE_SIGNATURES = {
        'jpg': (b'\xFF\xD8\xFF', 0),
        'jpeg': (b'\xFF\xD8\xFF', 0),
        'png': (b'\x89PNG\r\n\x1a\n', 0),
        'gif': (b'GIF87a', 0),
        'gif2': (b'GIF89a', 0),
        'mp3': (b'\xFF\xFB', 0),
        'mp4': (b'\x00\x00\x00\x1f\x66\x74\x79\x70', 0),
        'avi': (b'RIFF', 0),
        'wav': (b'RIFF', 0),
        'pdf': (b'%PDF', 0),
        'docx': (b'PK\x03\x04', 0),  # ZIP format
        'xlsx': (b'PK\x03\x04', 0),
        'pptx': (b'PK\x03\x04', 0),
        'zip': (b'PK\x03\x04', 0),
        'rar': (b'Rar!', 0),
        'tar': (b'ustar', 257),
        'gz': (b'\x1F\x8B', 0),
        'bmp': (b'BM', 0),
        'tiff': (b'II\x2A\x00', 0),
        'tiff2': (b'MM\x00\x2A', 0),
        'exe': (b'MZ', 0),
        'dll': (b'MZ', 0),
        'py': (b'#', 0),
        'txt': (None, 0),  # Plain text - no magic header
        'json': (None, 0),  # JSON - no magic header
        'xml': (b'<?xml', 0),
        'html': (b'<!DOCTYPE', 0),
        'css': (None, 0),
        'js': (None, 0),
    }
    
    # 文件類型擴展
    FILE_EXTENSIONS = {
        'jpg': ['jpg', 'jpeg', 'jpe', 'jif'],
        'png': ['png'],
        'gif': ['gif'],
        'mp3': ['mp3'],
        'mp4': ['mp4', 'm4v'],
        'avi': ['avi'],
        'wav': ['wav'],
        'pdf': ['pdf'],
        'docx': ['docx'],
        'xlsx': ['xlsx'],
        'pptx': ['pptx'],
        'zip': ['zip', 'jar'],
        'rar': ['rar'],
        'tar': ['tar'],
        'gz': ['gz', 'gzip'],
        'bmp': ['bmp'],
        'tiff': ['tiff', 'tif'],
        'exe': ['exe', 'dll', 'sys'],
        'py': ['py'],
        'txt': ['txt', 'log', 'cfg', 'ini', 'conf'],
        'json': ['json'],
        'xml': ['xml'],
        'html': ['html', 'htm'],
        'css': ['css'],
        'js': ['js'],
    }
    
    # 內存映射緩衝區大小
    BUFFER_SIZE = 64 * 1024 * 1024  # 64MB
    
    def __init__(self, disk_path: str):
        """
        初始化磁碟recover
        
        Args:
            disk_path: 磁碟路徑 (e.g., '\\.\PhysicalDrive0' 或 'C:')
        """
        self.disk_path = disk_path
        self.disk_handle = None
        self.sector_size = 512
        self.disk_size = 0
        self.file_system_type = None
        
    def open_disk(self) -> bool:
        """
        打開磁碟
        使用 Windows API 直接訪問物理磁碟
        """
        try:
            if sys.platform == 'win32':
                # Windows - 使用 CreateFileA
                import ctypes
                from ctypes import wintypes
                
                # 嘗試打開物理磁碟
                if not self.disk_path.startswith('\\\\.\\'):
                    path = f"\\\\.\\{self.disk_path}" if self.disk_path != 'C' else '\\\\.\\PhysicalDrive0'
                else:
                    path = self.disk_path
                
                self.disk_handle = ctypes.windll.kernel32.CreateFileA(
                    path.encode(),
                    0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
                    0,  # No sharing
                    None,
                    3,  # OPEN_EXISTING
                    0,
                    None
                )
                
                if self.disk_handle == -1:
                    print(f"❌ 無法打開磁碟: {path}")
                    print("   請以管理員權限運行")
                    return False
                
                # 獲取磁碟大小
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
                
                if result:
                    self.disk_size = struct.unpack('Q', geometry[16:24])[0]
                    print(f"✅ 磁碟大小: {self.disk_size:,} bytes")
                    return True
                else:
                    print("❌ 無法獲取磁碟大小")
                    return False
                    
            else:
                # Linux - 直接打開文件
                self.disk_handle = os.open(self.disk_path, os.O_RDONLY)
                self.disk_size = os.fstat(self.disk_handle).st_size
                print(f"✅ 磁碟大小: {self.disk_size:,} bytes")
                return True
                
        except PermissionError:
            print(f"❌ 無權限訪問: {self.disk_path}")
            print("   請以管理員/root權限運行")
            return False
        except Exception as e:
            print(f"❌ 打開磁碟失敗: {e}")
            return False
    
    def read_sector(self, sector_number: int, count: int = 1) -> bytes:
        """
        讀取指定扇區
        
        Args:
            sector_number: 扇區號
            count: 扇區數量
            
        Returns:
            扇區數據
        """
        try:
            if sys.platform == 'win32':
                import ctypes
                
                offset = sector_number * self.sector_size
                position = ctypes.windll.kernel32.SetFilePointer(
                    self.disk_handle,
                    offset,
                    None,
                    0  # FILE_BEGIN
                )
                
                if position == -1:
                    raise Exception("SetFilePointer failed")
                
                buffer = ctypes.create_string_buffer(count * self.sector_size)
                bytes_read = ctypes.c_ulong()
                
                result = ctypes.windll.kernel32.ReadFile(
                    self.disk_handle,
                    buffer,
                    count * self.sector_size,
                    ctypes.byref(bytes_read),
                    None
                )
                
                if not result:
                    raise Exception("ReadFile failed")
                
                return buffer.raw[:bytes_read.value]
            else:
                # Linux
                os.lseek(self.disk_handle, offset, 0)
                return os.read(self.disk_handle, count * self.sector_size)
                
        except Exception as e:
            print(f"❌ 讀取扇區 {sector_number} 失敗: {e}")
            return b''
    
    def scan_for_files(self) -> List[dict]:
        """
        掃描磁碟尋找文件
        通过 Magic Numbers 和文件大小推測
        """
        print("\n🔍 開始掃描磁碟尋找文件...")
        
        found_files = []
        buffer = b''
        offset = 0
        sector_offset = 0
        
        # 讀取磁碟到緩衝區
        sectors_to_read = min(10000, self.disk_size // self.sector_size)
        
        for sector in range(0, sectors_to_read, 100):
            data = self.read_sector(sector, 100)
            if not data:
                continue
            
            buffer += data
            
            # 搜尋文件簽名
            for file_type, (magic, skip) in self.FILE_SIGNATURES.items():
                if magic is None:
                    continue  # 無簽名文件跳過
                
                search_start = max(0, len(buffer) - 100000)
                search_area = buffer[search_start:]
                
                idx = 0
                while True:
                    pos = search_area.find(magic, idx)
                    if pos == -1:
                        break
                    
                    # 檢查文件大小
                    file_start = search_start + pos
                    estimated_size = self.estimate_file_size(buffer, file_start, file_type)
                    
                    if estimated_size > 0 and estimated_size < 100 * 1024 * 1024:  # < 100MB
                        found_files.append({
                            'type': file_type,
                            'offset': file_start,
                            'estimated_size': estimated_size,
                            'path': f"sector_{sector}_{pos}"
                        })
                        print(f"  ✓ 找到 {file_type} 文件: {estimated_size:,} bytes")
                    
                    idx = pos + 1
        
        print(f"\n✅ 共找到 {len(found_files)} 個可能的文件")
        return found_files
    
    def estimate_file_size(self, data: bytes, start: int, file_type: str) -> int:
        """
        評估文件大小
        根據文件類型推測大小
        """
        try:
            if file_type in ['jpg', 'jpeg']:
                # JPEG: 從 D9 號標記結束
                end_marker = data[start:].find(b'\xFF\xD9')
                if end_marker != -1:
                    return start + end_marker + 2
                return 0
            
            elif file_type in ['png']:
                # PNG: 從 IEND 標記結束
                end_marker = data[start:].find(b'IEND\x00\x42\x60\x82')
                if end_marker != -1:
                    return start + end_marker + 8
                return 0
            
            elif file_type in ['gif']:
                # GIF: 從 ; 結束
                end_marker = data[start:].find(b';')
                if end_marker != -1:
                    return start + end_marker + 1
                return 0
            
            elif file_type in ['mp3']:
                # MP3: 讀取 frame header
                frame_start = start
                frame_size = 0
                count = 0
                while count < 10:
                    if frame_start + 4 > len(data):
                        break
                    frame_header = struct.unpack('>I', data[frame_start:frame_start+4])[0]
                    if (frame_header & 0xFFE00000) != 0xFFE00000:
                        break
                    # Calculate frame size
                    version = (frame_header >> 19) & 3
                    layer = (frame_header >> 17) & 3
                    bitrate_index = (frame_header >> 12) & 15
                    sample_rate_index = (frame_header >> 10) & 3
                    
                    bitrate = [32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448][bitrate_index]
                    sample_rate = [44100, 48000, 32000, 0][sample_rate_index]
                    
                    if version == 3:  # MP3 v1
                        frame_size = (144 * bitrate * 1000) // sample_rate
                    else:  # MP3 v2
                        frame_size = (72 * bitrate * 1000) // sample_rate
                    
                    frame_start += frame_size
                    count += 1
                
                return frame_start - start
            
            elif file_type in ['pdf']:
                # PDF: 從 %%EOF
                end_marker = data[start:].find(b'%%EOF')
                if end_marker != -1:
                    return start + end_marker + 5
                return 0
            
            elif file_type in ['docx', 'xlsx', 'pptx', 'zip', 'jar']:
                # ZIP-based: 從 local file header
                # 從中央目錄記錄推測
                central_dir = data[start:].find(b'PK\x01\x02')
                if central_dir != -1:
                    return central_dir + 46  # Central directory record size
                return 0
            
            elif file_type in ['mp4', 'mov']:
                # MP4: 從 moov box
                moov_pos = data[start:].find(b'moov')
                if moov_pos != -1:
                    return moov_pos + 8
                return 0
            
            elif file_type in ['avi']:
                # AVI: 從 RIFF + AVI
                riff_pos = data[start:].find(b'RIFF')
                if riff_pos != -1:
                    return riff_pos + 12  # RIFF header
                return 0
            
            elif file_type in ['wav']:
                # WAV: 從 RIFF + WAVE
                riff_pos = data[start:].find(b'RIFF')
                if riff_pos != -1:
                    return riff_pos + 12
                return 0
            
            elif file_type in ['bmp']:
                # BMP: 從 BMP header
                return start + struct.unpack('<I', data[start+2:start+6])[0]
            
            elif file_type in ['exe', 'dll']:
                # PE: 從 PE header
                pe_pos = data[start:].find(b'PE\x00\x00')
                if pe_pos != -1:
                    return pe_pos + 4
                return 0
            
            return 0
            
        except Exception as e:
            print(f" 估算大小失敗: {e}")
            return 0
    
    def extract_file(self, offset: int, size: int) -> bytes:
        """
        提取文件數據
        
        Args:
            offset: 文件在磁碟上的偏移
            size: 文件大小
            
        Returns:
            文件數據
        """
        try:
            # 讀取磁碟數據
            sectors = self.read_sector(offset // self.sector_size, 
                                       (size + self.sector_size - 1) // self.sector_size)
            return sectors[offset % self.sector_size:size + (offset % self.sector_size)]
        except Exception as e:
            print(f"❌ 提取文件失敗: {e}")
            return b''
    
    def recover_all_files(self, output_dir: str) -> List[str]:
        """
        recover所有找到的文件
        
        Args:
            output_dir: 輸出目錄
            
        Returns:
            recover的文件路徑列表
        """
        import shutil
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        found_files = self.scan_for_files()
        recovered_files = []
        
        for file_info in found_files:
            print(f"\n📦 recover {file_info['type']} 文件...")
            
            # 提取文件
            data = self.extract_file(file_info['offset'], file_info['estimated_size'])
            
            if not data:
                continue
            
            # 根據文件類型決定擴展名
            ext = self.get_extension(file_info['type'])
            if ext:
                filename = f"recovered_{file_info['type']}_{file_info['offset']}.{ext}"
            else:
                filename = f"recovered_{file_info['type']}_{file_info['offset']}"
            
            output_file = output_path / filename
            
            try:
                # 如果是壓縮文件，直接寫入
                if file_info['type'] in ['zip', 'rar', 'tar', 'gz']:
                    with open(output_file, 'wb') as f:
                        f.write(data)
                
                # 如果是文本文件，嘗試解碼
                elif file_info['type'] in ['txt', 'json', 'xml', 'html', 'css', 'js', 'py']:
                    try:
                        text = data.decode('utf-8')
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(text)
                    except:
                        with open(output_file, 'wb') as f:
                            f.write(data)
                
                # 其他二進制文件
                else:
                    with open(output_file, 'wb') as f:
                        f.write(data)
                
                recovered_files.append(str(output_file))
                print(f"  ✓ 已保存: {output_file}")
                
            except Exception as e:
                print(f"  ❌ 保存失敗: {e}")
        
        return recovered_files
    
    def get_extension(self, file_type: str) -> Optional[str]:
        """獲取文件擴展名"""
        return self.FILE_EXTENSIONS.get(file_type, [None])[0]
    
    def close_disk(self):
        """關閉磁碟"""
        if self.disk_handle:
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.disk_handle)
            else:
                os.close(self.disk_handle)
            self.disk_handle = None
            print("磁碟已關閉")


def main():
    """主程式"""
    print("=" * 60)
    print("磁碟資料recover工具")
    print("=" * 60)
    print("\n此工具將直接讀取磁碟，跳過 MBR 和分區表")
    print("適合用於 MBR損壞、分區表損壞等情況")
    
    # 磁碟路徑
    disk_path = input("\n輸入磁碟路徑 (例如: C: 或 PhysicalDrive0): ")
    
    # 輸出目錄
    output_dir = input("輸入recover輸出目錄: ")
    
    # 初始化recover工具
    recovery = DiskRecovery(disk_path)
    
    if not recovery.open_disk():
        print("\n❌ 無法打開磁碟")
        return
    
    try:
        # recover文件
        recovered = recovery.recover_all_files(output_dir)
        
        if recovered:
            print(f"\n✅ 成功 recover {len(recovered)} 個文件")
            print(f"輸出目錄: {output_dir}")
            
            # 顯示recover的文件
            print("\nrecover的文件:")
            for f in recovered:
                print(f"  - {f}")
        else:
            print("\n❌ 未找到任何文件")
            
    except Exception as e:
        print(f"\n❌ recover失敗: {e}")
    finally:
        recovery.close_disk()


if __name__ == "__main__":
    main()