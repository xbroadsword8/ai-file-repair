"""
Bad Sector Handler - 輪讀取多數決
當 sector 讀取失敗時，重複讀取 N 次並取多數結果
"""
import os
import struct


class BadSectorHandler:
    """處理 bad sector 的輪讀取策略"""

    def __init__(self, device_path: str, retries: int = 3):
        self.device_path = device_path
        self.retries = retries
        self.file_handle = None
        self.bad_sectors = []
        self.read_errors = []

    def open(self):
        """打開磁碟"""
        try:
            self.file_handle = open(self.device_path, 'rb', buffering=0)
            return True
        except Exception as e:
            self.read_errors.append(f"Open failed: {e}")
            return False

    def read_sector(self, sector_num: int, retry: bool = True) -> tuple[bool, bytes | None]:
        """
        讀取單一 sector
        
        Args:
            sector_num: 要讀取的 sector 編號
            retry: 是否使用 retry 邏輯
            
        Returns:
            (success, data) - success 表示是否成功
        """
        offset = sector_num * 512
        
        if not self.file_handle:
            if not self.open():
                return False, None
        
        max_attempts = self.retries if retry else 1
        
        for attempt in range(max_attempts):
            try:
                self.file_handle.seek(offset)
                data = self.file_handle.read(512)
                
                if len(data) == 512:
                    return True, data
                elif len(data) > 0:
                    # 部分讀取，pad 到 512 bytes
                    padded = data.ljust(512, b'\x00')
                    self.bad_sectors.append(sector_num)
                    self.read_errors.append(
                        f"Sector {sector_num}: partial read ({len(data)} bytes)"
                    )
                    return True, padded
                else:
                    self.read_errors.append(
                        f"Sector {sector_num}: empty read (attempt {attempt + 1})"
                    )
                    
            except Exception as e:
                self.read_errors.append(
                    f"Sector {sector_num}: read error attempt {attempt + 1}: {e}"
                )
                
                if attempt == max_attempts - 1:
                    return False, None
                    
        return False, None

    def read_sector_voter(self, sector_num: int, consensus_threshold: int = 2) -> tuple[bool, bytes | None]:
        """
        輪讀取多數決
        
        讀取 sector N 次，收集結果，投票決定最終值。
        適用於 recover damaged sector 的情境。
        
        Args:
            sector_num: 要讀取的 sector 編號
            consensus_threshold: 共識門檻，預設 2 次相同結果
            
        Returns:
            (success, best_data)
        """
        results = []
        
        for attempt in range(self.retries):
            success, data = self.read_sector(sector_num, retry=False)
            if success and data:
                results.append(data)
        
        if not results:
            self.bad_sectors.append(sector_num)
            return False, None
        
        if len(results) == 1:
            return True, results[0]
        
        # 投票：找出現次數最多的結果
        vote_counts = {}
        for data in results:
            # 用 hash 當 key 來分組
            hash_val = hash(data)
            if hash_val not in vote_counts:
                vote_counts[hash_val] = []
            vote_counts[hash_val].append(data)
        
        # 找最多票的
        best_key = max(vote_counts, key=lambda k: len(vote_counts[k]))
        best_data = vote_counts[best_key][0]
        
        if len(vote_counts[best_key]) >= consensus_threshold:
            return True, best_data
        
        # 如果沒達到 consensus，還是用最多的那組
        return True, best_data

    def scan_for_bad_sectors(self, start_sector: int = 0, sector_count: int = 100) -> list[int]:
        """
        掃描指定範圍的 bad sectors
        
        Args:
            start_sector: 起始 sector
            sector_count: 掃描的 sector 數量
            
        Returns:
            bad sector 列表
        """
        bad = []
        
        for i in range(sector_count):
            sector = start_sector + i
            success, data = self.read_sector(sector, retry=False)
            if not success:
                bad.append(sector)
                self.read_errors.append(f"Bad sector detected: {sector}")
        
        self.bad_sectors.extend(bad)
        return bad

    def close(self):
        """關閉檔案描述符"""
        if self.file_handle:
            try:
                self.file_handle.close()
            except:
                pass
            self.file_handle = None


# Tests
if __name__ == '__main__':
    import tempfile
    import os
    
    # Create test file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.dat') as f:
        # Write 10 sectors of test data
        for i in range(10):
            f.write(bytes([i]) * 512)  # Sector 0 = all 0x00, Sector 1 = all 0x01, etc.
        test_file = f.name
    
    try:
        handler = BadSectorHandler(test_file, retries=2)
        
        # Test normal read
        success, data = handler.read_sector(0)
        assert success, "Should read sector 0 successfully"
        assert len(data) == 512, f"Expected 512 bytes, got {len(data)}"
        assert data[0] == 0, f"Expected 0x00, got 0x{data[0]:02x}"
        print("✓ Normal sector read works")
        
        # Test sector with different value
        success, data = handler.read_sector(5)
        assert success, "Should read sector 5 successfully"
        assert data[0] == 5, f"Expected 0x05, got 0x{data[0]:02x}"
        print("✓ Sector with unique pattern read works")
        
        # Test voter
        success, data = handler.read_sector_voter(3, consensus_threshold=1)
        assert success, "Voter should work"
        assert data[0] == 3, f"Voter got wrong sector data: expected 0x03, got 0x{data[0]:02x}"
        print("✓ Voter sector read works")
        
        # Test partial read (truncated sector)
        # Write a file smaller than 512 bytes
        with open(test_file, 'wb') as f:
            f.write(b'\x42' * 100)  # Only 100 bytes
        
        success, data = handler.read_sector(0)
        assert success, "Should handle truncated file"
        assert data is not None, "Should return data for truncated read"
        assert len(data) == 512, f"Should pad to 512 bytes, got {len(data)}"
        assert data[100:] == b'\x00' * 412, "Should pad with zeros"
        print("✓ Partial/truncated read works")
        
        handler.close()
        print("\n✅ All tests passed!")
        
    finally:
        os.unlink(test_file)
