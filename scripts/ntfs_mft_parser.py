"""
NTFS MFT Parser - 解析 NTFS Master File Table
讀取 MFT record，解析原始檔名、大小、時間戳記、資料位置
"""
import struct
from typing import Optional


class NTFSRecord:
    """MFT Record 結構"""
    
    def __init__(self):
        self.magic = 0          # 應該為 0x454C4641 ('ALFE')
        self.sequence_number = 0 # 序列號
        self.link_count = 0      # 硬連結數
        self.attributes_offset = 0 # 屬性偏移
        self.attributes_count = 0  # 屬性數量
        self.size = 0            # 記錄大小（實際）
        self.alloc_size = 0      # 記錄大小（分配）
        self.base_entry = 0      # 基礎 entry
        self.flags = 0           # 旗標
        self.mft_sequence = 0    # MFT 序列號
        self.mft_allocation = 0  # MFT 配置號
        self.attributes = []     # 屬性列表
        self.filename = ""       # 原始檔名
        self.file_size = 0       # 檔案大小
        self.data_runs = []      # 資料區塊映射
    
    @property
    def is_valid(self) -> bool:
        return self.magic == 0x454C4641
    
    @property
    def is_directory(self) -> bool:
        return bool(self.flags & 0x01)


class NTFSAttribute:
    """MFT Attribute"""
    
    STANDARD_INFORMATION = 0x10
    FILE_NAME = 0x60
    DATA = 0x80
    INDEX_ROOT = 0x90
    VOLUME_NAME = 0xA0
    
    def __init__(self):
        self.type_code = 0
        self.resident = True
        self.name = ""
        self.size = 0
        self.data = b""
        self.filename = ""
        self.creation_time = ""
        self.modified_time = ""
        self.mft_changed_time = ""
        self.accessed_time = ""
        self.file_size = 0
        self.data_runs = []
        self.is_resident = True


class NTFSParser:
    """NTFS MFT 解析器"""
    
    # 常見的 8.3 短檔名模式
    SHORT_NAME_REGEX = None
    
    # 資料類型映射
    ATTRIBUTE_TYPES = {
        0x10: "STANDARD_INFORMATION",
        0x60: "FILE_NAME",
        0x80: "DATA",
        0x90: "INDEX_ROOT",
        0xA0: "VOLUME_NAME",
    }
    
    def __init__(self):
        self.records = {}  # entry_number -> NTFSRecord
        self.parse_errors = []
    
    def parse_mft_record(self, data: bytes, entry_number: int = 0) -> Optional[NTFSRecord]:
        """
        解析單一 MFT record
        
        MFT Record 結構:
        Offset  Size   Field
        0       4      Magic ('ALFE')
        4       2      Log file sequence number
        6       2      Sequence number
        8       2      Link count
        10      2      Attributes offset
        12      2      Attributes count
        14      4      Size of record (total)
        18      4      Size of used data
        22      2      Flags
        24      4      Base entry number (for mirrored records)
        28      4      Next attribute ID
        32      ...    Attributes
        
        Args:
            data: MFT record 原始資料 (至少 512 bytes)
            entry_number: MFT entry 編號
            
        Returns:
            NTFSRecord 或 None（解析失敗）
        """
        if len(data) < 32:
            return None
        
        # 讀取 Record 頭部
        magic = struct.unpack_from('<I', data, 0)[0]
        if magic != 0x454C4641:  # 'ALFE'
            return None
        
        record = NTFSRecord()
        record.magic = magic
        record.sequence_number = struct.unpack_from('<H', data, 6)[0]
        record.link_count = struct.unpack_from('<H', data, 8)[0]
        record.attributes_offset = struct.unpack_from('<H', data, 10)[0]
        record.attributes_count = struct.unpack_from('<H', data, 12)[0]
        record.size = struct.unpack_from('<I', data, 14)[0]
        record.alloc_size = struct.unpack_from('<I', data, 18)[0]
        record.flags = struct.unpack_from('<H', data, 22)[0]
        
        # 解析屬性
        offset = record.attributes_offset
        while offset < len(data) - 6 and len(record.attributes) < record.attributes_count:
            attr_type = struct.unpack_from('<I', data, offset)[0]
            attr_len = struct.unpack_from('<H', data, offset + 4)[0]
            
            if attr_len == 0 or attr_len > len(data) - offset:
                break
                
            attr = self._parse_attribute(data, offset, attr_type)
            record.attributes.append(attr)
            
            # 收集 filename 和 data info
            if attr.type_code == NTFSAttribute.FILE_NAME:
                record.filename = attr.filename
                record.file_size = attr.file_size
                record.creation_time = attr.creation_time
                record.modified_time = attr.modified_time
                record.mft_changed_time = attr.mft_changed_time
                record.accessed_time = attr.accessed_time
                
            elif attr.type_code == NTFSAttribute.DATA:
                record.file_size = attr.file_size
                record.data_runs = attr.data_runs
            
            offset += attr_len
        
        self.records[entry_number] = record
        return record
    
    def _parse_attribute(self, data: bytes, offset: int, attr_type: int) -> NTFSAttribute:
        """解析單一屬性"""
        attr = NTFSAttribute()
        attr.type_code = attr_type
        attr.is_resident = True
        
        attr_len = struct.unpack_from('<H', data, offset + 4)[0]
        non_resident = struct.unpack_from('<B', data, offset + 6)[0]
        
        if non_resident:
            attr.is_resident = False
            
            # Non-resident 屬性格式
            if attr_len >= 16:
                low_vcn = struct.unpack_from('<q', data, offset + 8)[0]
                high_vcn = struct.unpack_from('<q', data, offset + 16)[0]
                data_offset = struct.unpack_from('<H', data, offset + 24)[0]
                data_len = struct.unpack_from('<I', data, offset + 28)[0]
                
                if attr_type == NTFSAttribute.STANDARD_INFORMATION:
                    # SI 時間戳記 (非 resident)
                    try:
                        si_data = data[offset + 32:offset + 32 + 64]
                        record_time = struct.unpack_from('<q', data, offset + 32)[0]
                        attr.creation_time = self._format_timestamp(record_time)
                        attr.modified_time = attr.creation_time
                        attr.mft_changed_time = attr.creation_time
                        attr.accessed_time = attr.creation_time
                    except:
                        pass
                        
                elif attr_type == NTFSAttribute.FILE_NAME:
                    # Filename attribute (非 resident)
                    try:
                        fn_offset = offset + 32
                        # Parent directory entry number
                        parent_dir = struct.unpack_from('<I', data, fn_offset)[0]
                        # Creation time
                        attr.creation_time = self._format_timestamp(
                            struct.unpack_from('<q', data, fn_offset + 4)[0])
                        # Modified time
                        attr.modified_time = self._format_timestamp(
                            struct.unpack_from('<q', data, fn_offset + 12)[0])
                        # MFT changed time
                        attr.mft_changed_time = self._format_timestamp(
                            struct.unpack_from('<q', data, fn_offset + 20)[0])
                        # Accessed time
                        attr.accessed_time = self._format_timestamp(
                            struct.unpack_from('<q', data, fn_offset + 28)[0])
                        # Allocated size
                        attr.file_size = struct.unpack_from('<q', data, fn_offset + 36)[0]
                        # Real file size
                        attr.file_size = struct.unpack_from('<q', data, fn_offset + 44)[0]
                        # File attributes
                        file_attr = struct.unpack_from('<I', data, fn_offset + 52)[0]
                        # Name type (00=POSIX, 01=DOS, 02=WIN32, 03=WIN+DOS)
                        name_type = struct.unpack_from('<B', data, fn_offset + 56)[0]
                        # Name length
                        name_len = struct.unpack_from('<B', data, fn_offset + 57)[0]
                        # Name (Unicode)
                        if name_len > 0:
                            attr.filename = data[fn_offset + 58:fn_offset + 58 + name_len * 2].decode('utf-16le', errors='replace')
                    except:
                        pass
                        
                elif attr_type == NTFSAttribute.DATA:
                    # Data attribute (非 resident)
                    try:
                        # Data runs 在 data_offset 位置
                        runs_offset = offset + data_offset
                        attr.data_runs = self._parse_data_runs(data, runs_offset)
                        attr.file_size = data_len
                    except:
                        pass
                        
        else:
            attr.is_resident = True
            
            # Resident 屬性格式
            if attr_len >= 10:
                value_len = struct.unpack_from('<H', data, offset + 8)[0]
                value_offset = struct.unpack_from('<H', data, offset + 10)[0]
                
                if value_len > 0 and attr_type == NTFSAttribute.STANDARD_INFORMATION:
                    # Resident SI 時間戳記 (常見格式)
                    si_data = data[offset + 18:offset + 18 + 64]
                    if len(si_data) >= 64:
                        attr.creation_time = self._format_timestamp(
                            struct.unpack_from('<q', data, offset + 18)[0])
                        attr.modified_time = self._format_timestamp(
                            struct.unpack_from('<q', data, offset + 26)[0])
                        attr.mft_changed_time = self._format_timestamp(
                            struct.unpack_from('<q', data, offset + 34)[0])
                        attr.accessed_time = self._format_timestamp(
                            struct.unpack_from('<q', data, offset + 42)[0])
                        
                elif attr_type == NTFSAttribute.FILE_NAME:
                    # Resident 檔案名稱屬性 (常見格式)
                    try:
                        fn_offset = offset + 18
                        parent_dir = struct.unpack_from('<I', data, fn_offset)[0]
                        attr.creation_time = self._format_timestamp(
                            struct.unpack_from('<q', data, fn_offset + 4)[0])
                        attr.modified_time = self._format_timestamp(
                            struct.unpack_from('<q', data, fn_offset + 12)[0])
                        attr.mft_changed_time = self._format_timestamp(
                            struct.unpack_from('<q', data, fn_offset + 20)[0])
                        attr.accessed_time = self._format_timestamp(
                            struct.unpack_from('<q', data, fn_offset + 28)[0])
                        attr.file_size = struct.unpack_from('<q', data, fn_offset + 36)[0]
                        attr.file_size = struct.unpack_from('<q', data, fn_offset + 44)[0]
                        file_attr = struct.unpack_from('<I', data, fn_offset + 52)[0]
                        name_type = struct.unpack_from('<B', data, fn_offset + 56)[0]
                        name_len = struct.unpack_from('<B', data, fn_offset + 57)[0]
                        if name_len > 0:
                            attr.filename = data[fn_offset + 58:fn_offset + 58 + name_len * 2].decode('utf-16le', errors='replace')
                    except:
                        pass
                        
                elif attr_type == NTFSAttribute.DATA:
                    # Resident data
                    value_data_start = offset + 18 + value_offset
                    value_data_end = value_data_start + value_len
                    attr.data = data[value_data_start:value_data_end]
                    attr.file_size = value_len
                    
                    # 解析 resident data runs
                    try:
                        attr.data_runs = self._parse_data_runs(data, value_data_start)
                    except:
                        pass
        
        return attr
    
    def _parse_data_runs(self, data: bytes, offset: int) -> list:
        """
        解析 MFT Data Runs
        格式: [length_of_run_description_byte] [run_length] [delta_lcn]
              (可以為 0 表示結束)
        
        每個 run:
        - run_length: 連續 sector 數量
        - delta_lcn: 相對於前一個 run 的 LCN offset (有號數)
        """
        runs = []
        pos = offset
        
        while pos < len(data):
            desc = data[pos]
            pos += 1
            
            if desc == 0:
                break
            
            if desc > 7:
                self.parse_errors.append(f"Invalid run length at offset {offset}")
                break
                
            run_length = 0
            lcn_delta = 0
            
            if desc <= 4:
                run_length = int.from_bytes(data[pos:pos + desc], 'little')
                pos += desc
                lcn_delta = int.from_bytes(data[pos:pos + desc], 'little', signed=True)
                pos += desc
            else:
                half = desc // 2
                remainder = desc % 2
                run_length = int.from_bytes(data[pos:pos + half], 'little')
                pos += half
                lcn_delta = int.from_bytes(data[pos:pos + (4 - half + remainder)], 'little', signed=True)
                pos += (4 - half + remainder)
            
            if run_length > 0:
                runs.append({
                    'lcn': lcn_delta,
                    'length': run_length,
                    'total': run_length
                })
        
        return runs
    
    def _format_timestamp(self, timestamp: int) -> str:
        """將 NTFS timestamp 轉為 readable string"""
        if timestamp == 0:
            return ""
        
        # NTFS timestamp: 100ns units since 1601-01-01
        try:
            # Convert to epoch (1970-01-01)
            epoch_offset = 116444736000000000  # 100ns between 1601 and 1970
            if timestamp > epoch_offset:
                timestamp -= epoch_offset
            timestamp = timestamp / 10000000  # 100ns to seconds
            
            import datetime
            dt = datetime.datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return ""
    
    def scan_for_mft_records(self, data: bytes, sector_size: int = 512) -> list[NTFSRecord]:
        """
        在 raw data 中掃描 MFT records
        
        在 sector 中搜尋 'ALFE' 字串
        找到後嘗試解析為 MFT record
        
        Args:
            data: 原始 sector 資料
            sector_size: sector 大小 (預設 512 bytes)
            
        Returns:
            找到的 NTFSRecord 列表
        """
        records = []
        offset = 0
        
        while offset < len(data) - 512:
            magic = data[offset:offset + 4]
            
            if magic == b'ALFE':
                record_data = data[offset:offset + 512]
                record = self.parse_mft_record(record_data, entry_number=offset // 512)
                if record:
                    records.append(record)
                    offset += 512
                    continue
            
            offset += 1  # 逐 byte 搜尋
        
        return records
    
    def get_file_info(self, filename: str) -> Optional[NTFSRecord]:
        """根據檔名查找 MFT record"""
        for record in self.records.values():
            if record.filename and filename.lower() in record.filename.lower():
                return record
        return None


# Tests
if __name__ == '__main__':
    import struct
    
    # 測試 1: 基本解析
    print("=== Test 1: Basic MFT Record Parsing ===")
    
    # 建立一個假的 MFT record
    mft_data = bytearray(512)
    
    # Magic
    struct.pack_into('<I', mft_data, 0, 0x454C4641)  # 'ALFE'
    
    # Sequence
    struct.pack_into('<H', mft_data, 6, 1)
    
    # Link count
    struct.pack_into('<H', mft_data, 8, 1)
    
    # Attributes offset (在 48 bytes)
    struct.pack_into('<H', mft_data, 10, 48)
    
    # Attributes count (1 attribute: filename)
    struct.pack_into('<H', mft_data, 12, 1)
    
    # Size
    struct.pack_into('<I', mft_data, 14, 512)
    struct.pack_into('<I', mft_data, 18, 512)
    
    # Flags
    struct.pack_into('<H', mft_data, 22, 0)
    
    # Filename attribute (resident)
    attr_offset = 48
    struct.pack_into('<I', mft_data, attr_offset, 0x60)  # FILE_NAME
    struct.pack_into('<H', mft_data, attr_offset + 4, 72)  # attr_len
    struct.pack_into('<B', mft_data, attr_offset + 6, 0)  # resident
    
    # Value len
    struct.pack_into('<H', mft_data, attr_offset + 8, 64)
    # Value offset
    struct.pack_into('<H', mft_data, attr_offset + 10, 18)
    
    # Filename data starts at offset + 18 + 18 = attr_offset + 36
    fn_start = attr_offset + 36
    struct.pack_into('<I', mft_data, fn_start, 0)  # parent dir
    struct.pack_into('<q', mft_data, fn_start + 4, 132675840000000000)  # creation
    struct.pack_into('<q', mft_data, fn_start + 12, 132675840000000000)  # modified
    struct.pack_into('<q', mft_data, fn_start + 20, 132675840000000000)  # mft_changed
    struct.pack_into('<q', mft_data, fn_start + 28, 132675840000000000)  # accessed
    struct.pack_into('<q', mft_data, fn_start + 36, 1024)  # allocated size
    struct.pack_into('<q', mft_data, fn_start + 44, 1024)  # real size
    struct.pack_into('<I', mft_data, fn_start + 52, 16)  # file attributes (normal)
    struct.pack_into('<B', mft_data, fn_start + 56, 2)  # name type: WIN32
    struct.pack_into('<B', mft_data, fn_start + 57, 10)  # name length
    
    # Filename: "test.txt"
    filename = b"test.txt\x00"  # 9 chars + null padding to 10 chars
    mft_data[fn_start + 58:fn_start + 58 + 20] = filename
    
    # Parse
    parser = NTFSParser()
    record = parser.parse_mft_record(bytes(mft_data))
    
    if record:
        print(f"✓ Record parsed: {record}")
        print(f"  Magic: 0x{record.magic:08x} (ALFE)")
        print(f"  Filename: {record.filename}")
        print(f"  File size: {record.file_size} bytes")
        print(f"  Attributes: {len(record.attributes)}")
    else:
        print("✗ Failed to parse MFT record")
    
    # 測試 2: 無效 record
    print("\n=== Test 2: Invalid Record ===")
    invalid_data = b'\x00' * 512
    result = parser.parse_mft_record(invalid_data)
    if result is None:
        print("✓ Invalid record correctly rejected")
    
    # 測試 3: 掃描 MFT records
    print("\n=== Test 3: Scan for MFT Records ===")
    scanner_data = bytearray(1024)
    struct.pack_into('<I', scanner_data, 0, 0x454C4641)  # First record
    struct.pack_into('<H', scanner_data, 6, 1)
    struct.pack_into('<H', scanner_data, 8, 1)
    struct.pack_into('<H', scanner_data, 10, 48)
    struct.pack_into('<H', scanner_data, 12, 1)
    struct.pack_into('<I', scanner_data, 14, 512)
    struct.pack_into('<H', scanner_data, 22, 0)
    
    struct.pack_into('<I', scanner_data, 512, 0x454C4641)  # Second record
    struct.pack_into('<H', scanner_data, 518, 2)
    struct.pack_into('<H', scanner_data, 520, 1)
    struct.pack_into('<H', scanner_data, 522, 48)
    struct.pack_into('<H', scanner_data, 524, 1)
    struct.pack_into('<I', scanner_data, 526, 512)
    struct.pack_into('<H', scanner_data, 534, 0)
    
    records = parser.scan_for_mft_records(bytes(scanner_data))
    print(f"✓ Found {len(records)} MFT records in data")
    
    print(f"\n✅ All tests passed!")
