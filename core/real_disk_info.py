"""
Real Disk Information Acquisition
真實磁碟資訊獲取 - 要能實際運作的程式碼

使用方法:
1. python real_disk_info.py
2. 或 import 後使用 DiskInfoCollector
"""

import os
import sys
import struct
import subprocess
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# ============================================
# 磁碟資訊類別 - 完整資訊
# ============================================

@dataclass
class DiskInfo:
    """完整的磁碟資訊"""
    device_path: str
    device_name: str
    size_bytes: int
    sector_size: int
    num_sectors: int
    
    # Manufacturer/Model info
    model: str = ""
    serial: str = ""
    vendor: str = ""
    firmware: str = ""
    
    # Interface info
    interface: str = ""
    bus_type: str = ""
    
    # Health info
    health: str = "Unknown"
    smart_status: str = "Unknown"
    
    # Partition info
    partition_table: str = "Unknown"
    partitions: List['PartitionInfo'] = field(default_factory=list)
    
    # Time info
    scan_time: str = ""
    
    def size_human(self) -> str:
        """人體可讀的大小"""
        if self.size_bytes >= 1024**3:
            return f"{self.size_bytes / (1024**3):.2f} GB"
        elif self.size_bytes >= 1024**2:
            return f"{self.size_bytes / (1024**2):.2f} MB"
        else:
            return f"{self.size_bytes} bytes"
    
    def to_dict(self) -> Dict:
        """轉換為字典"""
        return {
            'device_path': self.device_path,
            'device_name': self.device_name,
            'size_bytes': self.size_bytes,
            'sector_size': self.sector_size,
            'num_sectors': self.num_sectors,
            'model': self.model,
            'serial': self.serial,
            'vendor': self.vendor,
            'firmware': self.firmware,
            'interface': self.interface,
            'bus_type': self.bus_type,
            'health': self.health,
            'smart_status': self.smart_status,
            'partition_table': self.partition_table,
            'partitions': [p.to_dict() for p in self.partitions],
            'scan_time': self.scan_time,
        }


@dataclass
class PartitionInfo:
    """分區資訊"""
    number: int
    device_path: str
    start_sector: int
    end_sector: int
    size_bytes: int
    partition_type: int
    type_name: str
    filesystem: str
    label: str = ""
    mount_point: str = ""
    health: str = "Unknown"
    
    def size_human(self) -> str:
        if self.size_bytes >= 1024**3:
            return f"{self.size_bytes / (1024**3):.2f} GB"
        elif self.size_bytes >= 1024**2:
            return f"{self.size_bytes / (1024**2):.2f} MB"
        else:
            return f"{self.size_bytes} bytes"
    
    def to_dict(self) -> Dict:
        return {
            'number': self.number,
            'device_path': self.device_path,
            'start_sector': self.start_sector,
            'end_sector': self.end_sector,
            'size_bytes': self.size_bytes,
            'partition_type': self.partition_type,
            'type_name': self.type_name,
            'filesystem': self.filesystem,
            'label': self.label,
            'mount_point': self.mount_point,
            'health': self.health,
        }


# ============================================
# 磁碟資訊收集器 - 使用多種方法
# ============================================

class DiskInfoCollector:
    """
    使用多種方法獲取磁碟資訊
    Windows: WMI + DeviceIoControl
    Linux: /sys/block + lsblk + smartctl
    """
    
    def __init__(self):
        self.platform = sys.platform
        self.collected_disks: List[DiskInfo] = []
        
    def collect_all_disks(self) -> List[DiskInfo]:
        """收集所有磁碟資訊"""
        self.collected_disks = []
        
        if self.platform == 'win32':
            self._collect_windows()
        elif self.platform.startswith('linux'):
            self._collect_linux()
        else:
            self._collect_generic()
        
        return self.collected_disks
    
    def _collect_windows(self):
        """Windows磁碟資訊收集"""
        try:
            import ctypes
            from ctypes import wintypes
            
            # Method 1: 使用 WMI (最完整)
            wmi_info = self._get_wmi_info()
            
            # Method 2: 使用 DeviceIoControl
            device_info = self._get_device_info()
            
            # Combine results
            for device_name, info in device_info.items():
                disk = DiskInfo(
                    device_path=f"\\\\.\\{device_name}",
                    device_name=device_name,
                    size_bytes=info.get('size_bytes', 0),
                    sector_size=info.get('sector_size', 512),
                    num_sectors=info.get('num_sectors', 0),
                    model=info.get('model', ''),
                    serial=info.get('serial', ''),
                    vendor=info.get('vendor', ''),
                    firmware=info.get('firmware', ''),
                    interface=info.get('interface', ''),
                    bus_type=info.get('bus_type', ''),
                    health=info.get('health', 'Unknown'),
                    smart_status=info.get('smart_status', 'Unknown'),
                    partition_table='Unknown',  # Will be detected later
                    partitions=[],
                    scan_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
                # Add WMI info if available
                if device_name in wmi_info:
                    wmi = wmi_info[device_name]
                    if wmi.get('model'):
                        disk.model = wmi['model']
                    if wmi.get('serial'):
                        disk.serial = wmi['serial']
                    if wmi.get('firmware'):
                        disk.firmware = wmi['firmware']
                    if wmi.get('interface'):
                        disk.interface = wmi['interface']
                
                self.collected_disks.append(disk)
                
        except Exception as e:
            print(f"Windows收集失敗: {e}")
            self._fallback_collect()
    
    def _get_wmi_info(self) -> Dict:
        """透過 PowerShell 獲取磁碟資訊（Windows 11 22H2+ 兼容）"""
        info = {}
        try:
            # Windows 11 22H2+ 移除了 wmic，使用 PowerShell
            result = subprocess.run(
                ['powershell', '-Command', 
                 'Get-CimInstance -ClassName Win32_DiskDrive | Select-Object -Property DeviceID, Model, SerialNumber, FirmwareRevision, InterfaceType, Size | Format-Table -HideTableHeaders'],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 6:
                            device = parts[0].replace('\\.\\', '')
                            info[device] = {
                                'model': parts[1],
                                'serial': parts[2],
                                'firmware': parts[3],
                                'interface': parts[4],
                                'size_bytes': int(parts[5]) if parts[5].isdigit() else 0,
                            }
        except subprocess.TimeoutExpired:
            pass
        except:
            pass
        return info
    
    def _get_device_info(self) -> Dict:
        """使用 DeviceIoControl 獲取磁碟資訊"""
        info = {}
        try:
            import ctypes
            from ctypes import wintypes
            
            # Enumerate physical drives
            for i in range(8):  # Check up to 8 drives
                path = f"\\\\.\\PhysicalDrive{i}"
                
                handle = ctypes.windll.kernel32.CreateFileA(
                    path.encode(),
                    0x80000000,  # GENERIC_READ
                    0x00000001 | 0x00000002,  # SHARE_READ | SHARE_WRITE
                    None,
                    3,  # OPEN_EXISTING
                    0,
                    None
                )
                
                if handle == -1:
                    continue
                
                # Get drive geometry
                # Note: DISK_GEOMETRY is 20 bytes, not 24
                geometry = ctypes.create_string_buffer(48)
                bytes_returned = ctypes.c_ulong()
                
                # Use IOCTL_DISK_GET_DRIVE_GEOMETRY_EX (0x700A0) for proper 24-byte struct
                # Or use standard 0x70000 with 20-byte buffer
                result = ctypes.windll.kernel32.DeviceIoControl(
                    handle,
                    0x700A0,  # IOCTL_DISK_GET_DRIVE_GEOMETRY_EX
                    None, 0,
                    geometry, 48,
                    ctypes.byref(bytes_returned),
                    None
                )
                
                if not result:
                    # Fallback to old IOCTL if EX version fails
                    geometry = ctypes.create_string_buffer(48)
                    result = ctypes.windll.kernel32.DeviceIoControl(
                        handle,
                        0x70000,  # IOCTL_DISK_GET_DRIVE_GEOMETRY (old)
                        None, 0,
                        geometry, 48,
                        ctypes.byref(bytes_returned),
                        None
                    )
                
                if result:
                    # Parse DISK_GEOMETRY_EX (24 bytes) or DISK_GEOMETRY (20 bytes)
                    if bytes_returned.value >= 24:
                        # DISK_GEOMETRY_EX format
                        size_bytes = struct.unpack('Q', geometry[16:24])[0]
                        sector_size = struct.unpack('I', geometry[20:24])[0]
                        num_sectors = size_bytes // sector_size
                    else:
                        # DISK_GEOMETRY format (20 bytes)
                        # Cylinders: 4-11 (8 bytes)
                        # Tracks/Cylinder: 12-15 (4 bytes)  
                        # Sectors/Track: 16-19 (4 bytes)
                        # Bytes/Sector: 20-23 (4 bytes) - but struct is only 20 bytes
                        # Actually, standard DISK_GEOMETRY is:
                        # GeometryType(4) + Cylinders(8) + Tracks(4) + Sectors(4) + Bytes(4) = 24
                        # Wait, the old struct is actually 20 bytes in some versions
                        # Let's use a safer parsing
                        size_bytes = struct.unpack('Q', geometry[16:24])[0] if len(geometry) >= 24 else 0
                        sector_size = struct.unpack('I', geometry[20:24])[0] if len(geometry) >= 24 else 512
                        num_sectors = size_bytes // sector_size if sector_size > 0 else 0
                    
                    info[f"PhysicalDrive{i}"] = {
                        'size_bytes': size_bytes,
                        'sector_size': sector_size,
                        'num_sectors': num_sectors,
                        'model': '',
                        'serial': '',
                        'vendor': '',
                        'firmware': '',
                        'interface': '',
                        'bus_type': '',
                        'health': 'Unknown',
                        'smart_status': 'Unknown',
                    }
                
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception as e:
            print(f"DeviceIoControl error: {e}")
        
        return info
    
    def _collect_linux(self):
        """Linux磁碟資訊收集"""
        try:
            # Use lsblk for block device info
            result = subprocess.run(
                ['lsblk', '-J', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT,LABEL,MODEL,TRAN,STATE'],
                capture_output=True, text=True, shell=True
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                for block in data.get('blockdevices', []):
                    if block.get('type') == 'disk':
                        disk = DiskInfo(
                            device_path=f"/dev/{block['name']}",
                            device_name=block['name'],
                            size_bytes=int(block.get('size', 0)),
                            sector_size=512,  # Default, can be refined
                            num_sectors=int(block.get('size', 0)) // int(block.get('sectors', 8)),
                            model=block.get('model', ''),
                            serial='',  # Need hdparm for this
                            vendor='',  # Need to parse from model
                            firmware='',  # Need hdparm for this
                            interface=block.get('tran', ''),
                            bus_type='PCIe' if block.get('tran') == 'nvme' else 'SATA',
                            health='Unknown',
                            smart_status='Unknown',
                            partition_table='Unknown',
                            partitions=[],
                            scan_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                        
                        # Get more info with hdparm if available
                        hdparm_info = self._get_hdparm_info(f"/dev/{block['name']}")
                        if hdparm_info:
                            disk.model = hdparm_info.get('model', disk.model)
                            disk.serial = hdparm_info.get('serial', disk.serial)
                            disk.firmware = hdparm_info.get('firmware', disk.firmware)
                            disk.sector_size = hdparm_info.get('sector_size', 512)
                        
                        self.collected_disks.append(disk)
                        
        except Exception as e:
            print(f"Linux收集失敗: {e}")
            self._fallback_collect()
    
    def _get_hdparm_info(self, device_path: str) -> Optional[Dict]:
        """使用 hdparm 獲取詳細磁碟資訊"""
        try:
            result = subprocess.run(
                ['hdparm', '-I', device_path],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout
                info = {}
                
                # Parse model
                for line in output.split('\n'):
                    if 'Model Number' in line:
                        info['model'] = line.split(':', 1)[1].strip()
                    elif 'Serial Number' in line:
                        info['serial'] = line.split(':', 1)[1].strip()
                    elif 'Firmware Version' in line:
                        info['firmware'] = line.split(':', 1)[1].strip()
                    elif 'Sector Size' in line:
                        info['sector_size'] = int(line.split(':')[1].strip().split()[0])
                
                return info
        except:
            pass
        return None
    
    def _collect_generic(self):
        """通用磁碟收集 (fallback)"""
        try:
            result = subprocess.run(
                ['df', '-h'],
                capture_output=True, text=True, shell=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 6:
                        device = parts[0]
                        size = parts[1]
                        
                        # Convert size to bytes
                        size_bytes = self._parse_size(size)
                        
                        disk = DiskInfo(
                            device_path=device,
                            device_name=device.split('/')[-1],
                            size_bytes=size_bytes,
                            sector_size=512,
                            num_sectors=size_bytes // 512,
                            model='',
                            serial='',
                            vendor='',
                            firmware='',
                            interface='',
                            bus_type='',
                            health='Unknown',
                            smart_status='Unknown',
                            partition_table='Unknown',
                            partitions=[],
                            scan_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                        self.collected_disks.append(disk)
                        
        except Exception as e:
            print(f"通用收集失敗: {e}")
    
    def _parse_size(self, size_str: str) -> int:
        """解析大小字串為 bytes"""
        size_str = size_str.upper()
        multipliers = {'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
        
        for suffix, mult in multipliers.items():
            if size_str.endswith(suffix):
                return int(float(size_str[:-1]) * mult)
        return int(size_str)
    
    def _fallback_collect(self):
        """Fallback 方法 - 使用最簡單的方式（包含 NVMe）"""
        try:
            # 包含所有 block devices: sd*, nvme*, mmcblk*, etc.
            result = subprocess.run(
                ['ls', '-l', '/dev/{sd,nvme,mmcblk}*'],
                capture_output=True, text=True, shell=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('brw'):
                        parts = line.split()
                        if len(parts) >= 9:
                            device = parts[-1].split('/')[-1]
                            disk = DiskInfo(
                                device_path=f"/dev/{device}",
                                device_name=device,
                                size_bytes=0,
                                sector_size=512,
                                num_sectors=0,
                                model='',
                                serial='',
                                vendor='',
                                firmware='',
                                interface='',
                                bus_type='',
                                health='Unknown',
                                smart_status='Unknown',
                                partition_table='Unknown',
                                partitions=[],
                                scan_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            )
                            self.collected_disks.append(disk)
        except:
            pass
    
    def get_disk_info_json(self) -> str:
        """獲取 JSON 格式的磁碟資訊"""
        return json.dumps([d.to_dict() for d in self.collected_disks], indent=2)
    
    def display_disks(self):
        """顯示磁碟資訊"""
        print("=" * 80)
        print("磁碟資訊列表")
        print("=" * 80)
        
        for i, disk in enumerate(self.collected_disks, 1):
            print(f"\n磁碟 {i}: {disk.device_path}")
            print(f"  型號: {disk.model}")
            print(f"  序列號: {disk.serial}")
            print(f"  容量: {disk.size_human()}")
            print(f"  Sector Size: {disk.sector_size} bytes")
            print(f"  Sectors: {disk.num_sectors}")
            print(f"  介面: {disk.interface}")
            print(f"  狀態: {disk.health}")
            print(f"  分區表: {disk.partition_table}")
            
            if disk.partitions:
                print(f"  分區:")
                for p in disk.partitions:
                    print(f"    Partition {p.number}: {p.start_sector}-{p.end_sector} "
                          f"({p.size_human()}) - {p.type_name}")
        
        print("\n" + "=" * 80)


# ============================================
# 主程式
# ============================================

if __name__ == "__main__":
    collector = DiskInfoCollector()
    disks = collector.collect_all_disks()
    
    if disks:
        collector.display_disks()
        
        # Save to file
        with open('/tmp/disk_info.json', 'w') as f:
            f.write(collector.get_disk_info_json())
        print("磁碟資訊已保存到 /tmp/disk_info.json")
    else:
        print("未找到任何磁碟資訊")
        collector._fallback_collect()
        collector.display_disks()
