"""
Disk Repair Module
磁碟修復工具 - 處理 MBR 和分區表問題
"""

import os
import sys
import struct
from pathlib import Path


class DiskRepair:
    """磁碟修復器"""
    
    def __init__(self, disk_path: str):
        self.disk_path = disk_path
        self.disk = None
        self.mbr = None
        self.partition_table = None
    
    def open_disk(self, mode='rb'):
        """打開磁碟"""
        try:
            self.disk = open(self.disk_path, mode)
            return True
        except PermissionError:
            print(f"❌ 無法打開 {self.disk_path}")
            print("   需要管理員權限")
            return False
        except Exception as e:
            print(f"❌ 開啟失敗: {e}")
            return False
    
    def read_mbr(self):
        """讀取 MBR (512 bytes)"""
        if not self.disk:
            return False
        
        try:
            self.disk.seek(0)
            mbr_data = self.disk.read(512)
            
            if len(mbr_data) < 512:
                print("❌ 磁碟太小或無法完整讀取")
                return False
            
            # 解析 MBR
            self.mbr = {
                'boot_code': mbr_data[:446],
                'partition_table': mbr_data[446:512],
                'signature': mbr_data[510:512]
            }
            
            # 檢查 MBR 簽名
            if self.mbr['signature'] != b'\x55\xAA':
                print("⚠️  MBR 簽名無效 (應該是 0xAA55)")
                return False
            
            print("✅ 成功讀取 MBR")
            return True
            
        except Exception as e:
            print(f"❌ 讀取 MBR 失敗: {e}")
            return False
    
    def parse_partition_table(self):
        """解析分區表"""
        if not self.mbr:
            return False
        
        partition_data = self.mbr['partition_table']
        
        # 每個分區條目 16 bytes, 共 4 個分區
        partitions = []
        for i in range(4):
            entry = partition_data[i*16:(i+1)*16]
            if entry[0] != 0x00 and entry[0] != 0x80:  # Active flag
                continue
            
            # 解析分區資訊
            partition = {
                'active': entry[0] == 0x80,
                'start_chs': entry[1:4],
                'type': entry[4],
                'end_chs': entry[5:8],
                'lba_start': struct.unpack('<I', entry[8:12])[0],
                'num_sectors': struct.unpack('<I', entry[12:16])[0]
            }
            partitions.append(partition)
        
        self.partition_table = partitions
        return True
    
    def fix_mbr_signature(self):
        """修復 MBR 簽名"""
        if not self.mbr:
            return False
        
        try:
            # 重新寫入 MBR
            self.disk.seek(0)
            fixed_mbr = self.mbr['boot_code'] + self.mbr['partition_table'] + b'\x55\xAA'
            self.disk.write(fixed_mbr)
            self.disk.flush()
            print("✅ MBR 簽名已修復")
            return True
        except Exception as e:
            print(f"❌ 修復失敗: {e}")
            return False
    
    def repair_disk(self):
        """完整的磁碟修復流程"""
        print("=" * 60)
        print("磁碟修復流程")
        print("=" * 60)
        
        # Step 1: Open disk
        if not self.open_disk():
            return False
        
        # Step 2: Read MBR
        if not self.read_mbr():
            print("\n⚠️  MBR 讀取失敗，嘗試重建...")
            if not self.rebuild_mbr():
                return False
        
        # Step 3: Parse partition table
        if not self.parse_partition_table():
            print("\n⚠️  分區表解析失敗，嘗試重建...")
            if not self.rebuild_partition_table():
                return False
        
        # Step 4: Fix MBR signature if needed
        if self.mbr['signature'] != b'\x55\xAA':
            if not self.fix_mbr_signature():
                return False
        
        print("\n" + "=" * 60)
        print("✅ 磁碟修復完成！")
        print("=" * 60)
        return True
    
    def rebuild_mbr(self):
        """重建 MBR"""
        try:
            # 建立新的 MBR
            new_mbr = bytearray(512)
            
            # 0x55AA signature at end
            new_mbr[510] = 0x55
            new_mbr[511] = 0xAA
            
            # 寫入新 MBR
            self.disk.seek(0)
            self.disk.write(bytes(new_mbr))
            self.disk.flush()
            
            print("✅ MBR 已重建")
            return True
        except Exception as e:
            print(f"❌ 重建 MBR 失敗: {e}")
            return False
    
    def rebuild_partition_table(self):
        """重建分區表"""
        try:
            # 讀取現有分區資訊
            current_partitions = []
            if self.partition_table:
                current_partitions = self.partition_table
            
            # 建立新的分區表
            partition_data = bytearray(64)  # 4 entries × 16 bytes
            
            for i, part in enumerate(current_partitions):
                if i >= 4:
                    break
                
                entry = bytearray(16)
                entry[0] = 0x80 if part.get('active', False) else 0x00
                entry[4] = part.get('type', 0x07)  # NTFS default
                entry[8:12] = struct.pack('<I', part.get('lba_start', 2048))
                entry[12:16] = struct.pack('<I', part.get('num_sectors', 100000))
                
                partition_data[i*16:(i+1)*16] = entry
            
            # 寫入分區表
            self.disk.seek(446)
            self.disk.write(bytes(partition_data))
            self.disk.flush()
            
            print("✅ 分區表已重建")
            return True
        except Exception as e:
            print(f"❌ 重建分區表失敗: {e}")
            return False
    
    def check_disk_health(self):
        """檢查磁碟健康狀態"""
        try:
            # 檢查磁碟大小
            self.disk.seek(0, 2)  # Seek to end
            disk_size = self.disk.tell()
            
            print(f"磁碟大小: {disk_size:,} bytes ({disk_size / (1024**3):.2f} GB)")
            
            # 檢查 MBR
            self.disk.seek(0)
            mbr = self.disk.read(512)
            
            if len(mbr) < 512:
                print("❌ 磁碟太小")
                return False
            
            if mbr[510:512] != b'\x55\xAA':
                print("❌ MBR 簽名無效")
                return False
            
            print("✅ 磁碟健康檢查通過")
            return True
            
        except Exception as e:
            print(f"❌ 檢查失敗: {e}")
            return False
    
    def close_disk(self):
        """關閉磁碟"""
        if self.disk:
            self.disk.close()
            print("磁碟已關閉")


def main():
    """主程式"""
    print("=" * 60)
    print("磁碟修復工具")
    print("=" * 60)
    
    # 檢查是否以管理員權限運行
    if sys.platform == 'win32':
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            if not is_admin:
                print("\n⚠️  警告: 程式未以管理員權限運行")
                print("   某些操作可能需要管理員權限")
                input("按 Enter 繼續...")
        except:
            pass
    
    # 磁碟路徑 (需要根據實際情況修改)
    disk_path = "C:"  # 或 "D:", "E:" 等
    
    print(f"\n目標磁碟: {disk_path}")
    print("注意: 這將修復磁碟的 MBR 和分區表")
    print("      進行此操作前請務必備份重要資料")
    
    confirm = input("\n是否繼續? (y/n): ")
    if confirm.lower() != 'y':
        print("已取消")
        return
    
    # 建立磁碟修復器
    disk_repair = DiskRepair(disk_path)
    
    # 執行修復
    success = disk_repair.repair_disk()
    
    if success:
        print("\n✅ 磁碟修復完成！")
        print("請重新啟動電腦以套用變更")
    else:
        print("\n❌ 磁碟修復失敗")
        print("可能的原因:")
        print("  1. 磁碟物理損壞")
        print("  2. 需要更高權限")
        print("  3. 磁碟已損壞過度，無法修復")
    
    disk_repair.close_disk()


if __name__ == "__main__":
    main()