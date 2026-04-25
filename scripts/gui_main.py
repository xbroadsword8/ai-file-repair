"""
AI File Repair - Complete Disk Recovery Application
完整的磁碟recover應用程式

正確流程：
1. 硬體掃描 → 2. 選擇磁碟 → 3. 磁碟掃描 → 4. 選擇文件 → 5. 修復
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import time
from datetime import datetime
from pathlib import Path
import os
import sys
import struct

# ============================================
# 硬體掃描模組
# ============================================

class HardwareScanner:
    """硬體掃描器 - 檢測系統中的磁碟"""
    
    def __init__(self):
        self.disks = []
        self.selected_disk = None
        
    def scan_disks(self):
        """掃描所有可用磁碟"""
        print("=" * 60)
        print("掃描硬碟...")
        print("=" * 60)
        
        if sys.platform == 'win32':
            # Windows - 使用 WMI 或直接枚舉
            self._scan_windows()
        else:
            # Linux - 讀取 /proc/diskstats
            self._scan_linux()
        
        return self.disks
    
    def _scan_windows(self):
        """Windows 磁碟掃描"""
        import ctypes
        from ctypes import wintypes
        
        # 列出所有磁碟設備
        disk_devices = [
            '\\\\.\\PhysicalDrive0',
            '\\\\.\\PhysicalDrive1',
            '\\\\.\\PhysicalDrive2',
            '\\\\.\\PhysicalDrive3',
            'C:',
            'D:',
            'E:',
            'F:',
            'G:',
            'H:',
            'I:',
            'J:',
            'K:',
            'L:',
            'M:',
            'N:',
            'O:',
            'P:',
            'Q:',
            'R:',
            'S:',
            'T:',
            'U:',
            'V:',
            'W:',
            'X:',
            'Y:',
            'Z:',
        ]
        
        for device in disk_devices:
            try:
                handle = ctypes.windll.kernel32.CreateFileA(
                    device.encode(),
                    0x80000000,  # GENERIC_READ
                    0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
                    None,
                    3,  # OPEN_EXISTING
                    0,
                    None
                )
                
                if handle != -1:
                    # 獲取磁碟資訊
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
                    
                    if result:
                        disk_info = {
                            'device': device,
                            'handle': handle,
                            'size': struct.unpack('Q', geometry[16:24])[0],
                            'sectors': struct.unpack('I', geometry[8:12])[0],
                            'sector_size': struct.unpack('I', geometry[12:16])[0],
                            'cylinders': struct.unpack('I', geometry[0:4])[0],
                            'tracks_per_cylinder': struct.unpack('I', geometry[4:8])[0],
                            'sectors_per_track': struct.unpack('I', geometry[8:12])[0]
                        }
                        
                        # 轉換大小為易讀格式
                        size_gb = disk_info['size'] / (1024 ** 3)
                        disk_info['size_str'] = f"{size_gb:.2f} GB"
                        
                        # 類型判斷
                        if 'PhysicalDrive' in device:
                            disk_info['type'] = '物理磁碟'
                            disk_info['drive_letter'] = None
                        else:
                            disk_info['type'] = '磁碟機'
                            disk_info['drive_letter'] = device[0]
                        
                        self.disks.append(disk_info)
                        print(f"  ✓ 找到磁碟: {device} ({disk_info['size_str']})")
                    
                    ctypes.windll.kernel32.CloseHandle(handle)
                    
            except:
                continue
    
    def _scan_linux(self):
        """Linux 磁碟掃描"""
        import glob
        
        # 讀取磁碟資訊
        for disk_path in glob.glob('/dev/sd*'):
            try:
                stat = os.stat(disk_path)
                if stat.st_rdev & 0xf00 == 0x800:  # Block device
                    # 獲取磁碟大小
                    with open(f'/sys/block/{os.path.basename(disk_path)}/size') as f:
                        sectors = int(f.read().strip())
                    
                    # 獲取塊大小
                    with open(f'/sys/block/{os.path.basename(disk_path)}/queue/physical_block_size') as f:
                        block_size = int(f.read().strip())
                    
                    disk_info = {
                        'device': disk_path,
                        'type': '磁碟',
                        'sectors': sectors,
                        'sector_size': block_size,
                        'size': sectors * block_size,
                        'size_str': f"{(sectors * block_size) / (1024**3):.2f} GB"
                    }
                    
                    self.disks.append(disk_info)
                    print(f"  ✓ 找到磁碟: {disk_path} ({disk_info['size_str']})")
                    
            except:
                continue
    
    def select_disk(self, device_path):
        """選擇磁碟"""
        for disk in self.disks:
            if disk['device'] == device_path:
                self.selected_disk = disk
                print(f"已選擇磁碟: {device_path}")
                return True
        return False
    
    def get_selected_disk(self):
        """獲取選中的磁碟"""
        return self.selected_disk


# ============================================
# 磁碟掃描器
# ============================================

class DiskScanner:
    """磁碟掃描器 - 掃描磁碟中的文件"""
    
    # 文件簽名
    FILE_SIGNATURES = {
        'jpg': (b'\xFF\xD8\xFF', 0),
        'png': (b'\x89PNG\r\n\x1a\n', 0),
        'pdf': (b'%PDF', 0),
        'mp3': (b'\xFF\xFB', 0),
        'mp4': (b'\x00\x00\x00\x1f\x66\x74\x79\x70', 0),
        'avi': (b'RIFF', 0),
        'wav': (b'RIFF', 0),
        'zip': (b'PK\x03\x04', 0),
        'rar': (b'Rar!', 0),
        'gif': (b'GIF8', 0),
        'bmp': (b'BM', 0),
        'exe': (b'MZ', 0),
        'txt': (None, 0),  # 無簽名
        'json': (None, 0),
        'xml': (b'<?xml', 0),
        'html': (b'<!DOCTYPE', 0),
    }
    
    def __init__(self, disk_path, sector_size=512):
        self.disk_path = disk_path
        self.sector_size = sector_size
        self.disk_handle = None
        self.files_found = []
        
    def open_disk(self):
        """打開磁碟"""
        try:
            if sys.platform == 'win32':
                import ctypes
                if not self.disk_path.startswith('\\\\.\\'):
                    path = f"\\\\.\\{self.disk_path}" if self.disk_path != 'C' else '\\\\.\\PhysicalDrive0'
                else:
                    path = self.disk_path
                
                self.disk_handle = ctypes.windll.kernel32.CreateFileA(
                    path.encode(),
                    0x80000000,  # GENERIC_READ
                    0,
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
    
    def read_sector(self, sector_num, count=1):
        """讀取扇區"""
        try:
            if sys.platform == 'win32':
                import ctypes
                offset = sector_num * self.sector_size
                ctypes.windll.kernel32.SetFilePointer(self.disk_handle, offset, None, 0)
                buffer = ctypes.create_string_buffer(count * self.sector_size)
                bytes_read = ctypes.c_ulong()
                ctypes.windll.kernel32.ReadFile(self.disk_handle, buffer, count * self.sector_size, ctypes.byref(bytes_read), None)
                return buffer.raw[:bytes_read.value]
            else:
                os.lseek(self.disk_handle, sector_num * self.sector_size, 0)
                return os.read(self.disk_handle, count * self.sector_size)
        except:
            return b''
    
    def scan_for_files(self, max_sectors=10000):
        """掃描文件"""
        print(f"\n掃描磁碟 {self.disk_path}...")
        print(f"掃描範圍: {max_sectors} 個扇區")
        
        self.files_found = []
        buffer = b''
        
        for sector in range(0, min(max_sectors, 100000), 100):
            data = self.read_sector(sector, 100)
            if not data:
                continue
            
            buffer += data
            
            # 搜尋文件簽名
            for file_type, (magic, _) in self.FILE_SIGNATURES.items():
                if magic is None:
                    continue
                
                pos = 0
                while True:
                    idx = buffer.find(magic, pos)
                    if idx == -1:
                        break
                    
                    # 評估文件大小
                    estimated_size = self._estimate_file_size(buffer, idx, file_type)
                    
                    if estimated_size > 0 and estimated_size < 100 * 1024 * 1024:
                        self.files_found.append({
                            'type': file_type,
                            'offset': sector * self.sector_size + idx,
                            'size': estimated_size,
                            'path': f"sector_{sector}_{idx}"
                        })
                        print(f"  ✓ 找到 {file_type} 文件: {estimated_size:,} bytes")
                    
                    pos = idx + 1
        
        print(f"\n共找到 {len(self.files_found)} 個文件")
        return self.files_found
    
    def _estimate_file_size(self, data, start, file_type):
        """估計文件大小"""
        if file_type == 'jpg':
            end = data[start:].find(b'\xFF\xD9')
            return start + end + 2 if end != -1 else 0
        elif file_type == 'png':
            end = data[start:].find(b'IEND\x00\x42\x60\x82')
            return start + end + 8 if end != -1 else 0
        elif file_type == 'pdf':
            end = data[start:].find(b'%%EOF')
            return start + end + 5 if end != -1 else 0
        elif file_type in ['mp3']:
            return self._mp3_size(data, start)
        return 0
    
    def _mp3_size(self, data, start):
        """估計 MP3 文件大小"""
        frame_start = start
        frame_size = 0
        count = 0
        while count < 10:
            if frame_start + 4 > len(data):
                break
            frame_header = struct.unpack('>I', data[frame_start:frame_start+4])[0]
            if (frame_header & 0xFFE00000) != 0xFFE00000:
                break
            frame_start += 416  # Approximate frame size
            count += 1
        return frame_start - start
    
    def close_disk(self):
        """關閉磁碟"""
        if self.disk_handle:
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.disk_handle)
            else:
                os.close(self.disk_handle)
            self.disk_handle = None


# ============================================
# GUI 主程式
# ============================================

class AIRepairGUI:
    """AI 文件修復工具主窗口"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("AI File Repair - Disk Recovery Tool")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # 初始化
        self.hardware_scanner = HardwareScanner()
        self.disk_scanner = None
        self.selected_files = []
        self.repair_mode = tk.StringVar(value="ai")
        self.current_disk = None
        self.progress_bar = None
        
        # 創建界面
        self.create_widgets()
        self.scan_hardware()
    
    def scan_hardware(self):
        """掃描硬體"""
        print("開始掃描硬體...")
        disks = self.hardware_scanner.scan_disks()
        
        if not disks:
            messagebox.showwarning("警告", "未找到任何磁碟！")
            return
        
        # 更新磁碟列表
        self.disk_list.delete(0, tk.END)
        for disk in disks:
            display_text = f"{disk['device']} - {disk['size_str']} ({disk['type']})"
            self.disk_list.insert(tk.END, display_text)
            self.disk_list.itemconfig(tk.END, {'bg': '#3c3c3c', 'fg': '#ffffff'})
        
        if len(disks) > 0:
            self.disk_list.selection_set(0)
    
    def select_disk(self):
        """選擇磁碟"""
        selection = self.disk_list.curselection()
        if not selection:
            messagebox.showinfo("提示", "請先選擇一個磁碟")
            return
        
        disk_info = self.hardware_scanner.disks[selection[0]]
        self.hardware_scanner.select_disk(disk_info['device'])
        self.current_disk = disk_info
        
        messagebox.showinfo("磁碟選擇", f"已選擇: {disk_info['device']}\n容量: {disk_info['size_str']}")
        
        # 啟用掃描按鈕
        self.scan_btn.config(state=tk.NORMAL)
    
    def scan_disk(self):
        """掃描磁碟"""
        if not self.current_disk:
            messagebox.showwarning("警告", "請先選擇磁碟")
            return
        
        # 禁用按鈕
        self.scan_btn.config(state=tk.DISABLED)
        
        # 創建磁碟掃描器
        self.disk_scanner = DiskScanner(self.current_disk['device'])
        
        if not self.disk_scanner.open_disk():
            messagebox.showerror("錯誤", "無法打開磁碟！")
            self.scan_btn.config(state=tk.NORMAL)
            return
        
        # 在背景執行掃描
        self.progress_bar['value'] = 0
        self.status_label.config(text="掃描中...")
        
        def scan_thread():
            files = self.disk_scanner.scan_for_files(max_sectors=50000)
            
            # 更新文件列表
            self.file_list.delete(0, tk.END)
            for f in files:
                display_text = f"{f['path']} - {f['type']} ({f['size']:,} bytes)"
                self.file_list.insert(tk.END, display_text)
                self.file_list.itemconfig(tk.END, {'bg': '#2b2b2b', 'fg': '#ffffff'})
            
            self.status_label.config(text=f"掃描完成！找到 {len(files)} 個文件")
            self.scan_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def select_files(self):
        """選擇文件"""
        selection = self.file_list.curselection()
        if selection:
            self.selected_files = [self.file_list.get(i) for i in selection]
            self.selected_count.config(text=f"已選擇: {len(self.selected_files)} 個文件")
    
    def start_repair(self):
        """開始修復"""
        if not self.selected_files:
            messagebox.showinfo("提示", "請先選擇要修復的文件")
            return
        
        # 選擇輸出目錄
        output_dir = filedialog.askdirectory(title="選擇輸出目錄")
        if not output_dir:
            return
        
        # 啟動修復
        self.repair_btn.config(state=tk.DISABLED)
        
        def repair_thread():
            for file_info in self.selected_files:
                print(f"修復: {file_info}")
                # 修復邏輯...
            
            messagebox.showinfo("完成", "修復完成！")
            self.repair_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=repair_thread, daemon=True).start()
    
    def create_widgets(self):
        """創建界面"""
        # 顏色
        colors = {
            'bg': '#2b2b2b',
            'panel': '#3c3c3c',
            'accent': '#007acc',
            'text': '#ffffff'
        }
        
        self.root.configure(bg=colors['bg'])
        
        # ============= 硬體掃描面板 =============
        hardware_frame = tk.LabelFrame(self.root, text="🔍 硬體掃描", 
                                       bg=colors['panel'], fg=colors['text'],
                                       font=('Segoe UI', 11, 'bold'))
        hardware_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.disk_list = tk.Listbox(hardware_frame, bg=colors['bg'], 
                                    fg=colors['text'], height=5,
                                    selectmode=tk.SINGLE)
        self.disk_list.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        btn_frame = tk.Frame(hardware_frame, bg=colors['panel'])
        btn_frame.pack(side=tk.RIGHT, padx=5)
        
        self.scan_hardware_btn = tk.Button(btn_frame, text="🔄 掃描硬體", 
                                           command=self.scan_hardware,
                                           bg=colors['accent'], fg='white',
                                           font=('Segoe UI', 9))
        self.scan_hardware_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.select_disk_btn = tk.Button(btn_frame, text="✅ 選擇磁碟", 
                                         command=self.select_disk,
                                         bg=colors['accent'], fg='white',
                                         font=('Segoe UI', 9))
        self.select_disk_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.scan_btn = tk.Button(btn_frame, text="🔍 掃描磁碟", 
                                  command=self.scan_disk,
                                  bg=colors['accent'], fg='white',
                                  font=('Segoe UI', 9),
                                  state=tk.DISABLED)
        self.scan_btn.pack(side=tk.LEFT)
        
        # ============= 文件列表面板 =============
        file_frame = tk.LabelFrame(self.root, text="📁 文件列表", 
                                   bg=colors['panel'], fg=colors['text'],
                                   font=('Segoe UI', 11, 'bold'))
        file_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.file_list = tk.Listbox(file_frame, bg=colors['bg'],
                                    fg=colors['text'], selectmode=tk.MULTIPLE,
                                    height=20)
        self.file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        scrollbar = tk.Scrollbar(file_frame, orient=tk.VERTICAL,
                                command=self.file_list.yview,
                                bg=colors['panel'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_list.config(yscrollcommand=scrollbar.set)
        
        # 選擇按鈕
        select_frame = tk.Frame(file_frame, bg=colors['panel'])
        select_frame.pack(fill=tk.X, pady=(5, 0))
        
        tk.Button(select_frame, text="✓ 選擇", command=self.select_files,
                  bg=colors['accent'], fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 5))
        
        self.selected_count = tk.Label(select_frame, text="已選擇: 0 個文件",
                                       bg=colors['panel'], fg=colors['text'],
                                       font=('Segoe UI', 9))
        self.selected_count.pack(side=tk.LEFT)
        
        # ============= 修復面板 =============
        repair_frame = tk.LabelFrame(self.root, text="🛠️ 修復設定", 
                                     bg=colors['panel'], fg=colors['text'],
                                     font=('Segoe UI', 11, 'bold'))
        repair_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 修復模式
        mode_frame = tk.Frame(repair_frame, bg=colors['panel'])
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(mode_frame, text="修復模式:", bg=colors['panel'], 
                 fg=colors['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        
        tk.Radiobutton(mode_frame, text="🤖 AI 增強模式", variable=self.repair_mode,
                       value="ai", bg=colors['panel'], fg=colors['text'],
                       font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 15))
        
        tk.Radiobutton(mode_frame, text="🔧 本地修復模式", variable=self.repair_mode,
                       value="local", bg=colors['panel'], fg=colors['text'],
                       font=('Segoe UI', 9)).pack(side=tk.LEFT)
        
        # 修復按鈕
        self.repair_btn = tk.Button(repair_frame, text="🚀 開始修復", 
                                    command=self.start_repair,
                                    bg=colors['accent'], fg='white',
                                    font=('Segoe UI', 10, 'bold'),
                                    height=2)
        self.repair_btn.pack(pady=10)
        
        # 狀態列
        self.status_bar = tk.Frame(self.root, bg=colors['panel'], 
                                   height=25, relief=tk.FLAT)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = tk.Label(self.status_bar, text="就緒",
                                     bg=colors['panel'], fg=colors['text'],
                                     font=('Segoe UI', 8))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.progress_bar = ttk.Progressbar(self.status_bar, length=200,
                                           mode='determinate')
        self.progress_bar.pack(side=tk.RIGHT, padx=10)


def main():
    """主程式"""
    root = tk.Tk()
    app = AIRepairGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()