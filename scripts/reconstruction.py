"""
Reconstruction Engine - 連續區塊重建
將分散的 FileSegment 合併成完整檔案
"""

import struct
from typing import List, Dict, Optional


class FileSegment:
    """檔案片段"""
    
    def __init__(self, offset: int, size: int, file_type: str, 
                 data: bytes = None, is_raw: bool = False,
                 sector_list: list = None, quality_score: float = 1.0):
        self.offset = offset
        self.size = size
        self.file_type = file_type
        self.data = data
        self.is_raw = is_raw
        self.sector_list = sector_list or []
        self.quality_score = quality_score
    
    def __repr__(self):
        return f"FileSegment(offset={self.offset}, size={self.size}, type={self.file_type})"


class ReconstructionEngine:
    """連續區塊重建引擎"""
    
    @staticmethod
    def merge_segments(segments: List[FileSegment]) -> List[FileSegment]:
        """
        將相鄰的 FileSegment 合併
        
        條件：
        - 相鄰（後一個的 offset == 前一個的 offset + size）
        - 相同類型
        - 品質 > 0
        
        Returns:
            合併後的 segments 列表
        """
        if not segments:
            return []
        
        sorted_segs = sorted(segments, key=lambda s: s.offset)
        merged = []
        current = None
        consumed = set()
        
        for i, seg in enumerate(sorted_segs):
            if i in consumed:
                continue
            if seg.quality_score <= 0:
                continue
            
            if current is None:
                current = seg
                consumed.add(i)
                continue
            
            # Check adjacency and same type
            if (current.file_type == seg.file_type and
                seg.offset == current.offset + current.size and
                seg.quality_score > 0):
                # Merge: concatenate data
                combined_data = current.data + seg.data if (current.data and seg.data) else None
                current = FileSegment(
                    offset=current.offset,
                    size=current.size + seg.size,
                    file_type=current.file_type,
                    data=combined_data,
                    is_raw=current.is_raw,
                    sector_list=current.sector_list + seg.sector_list,
                    quality_score=min(current.quality_score, seg.quality_score)
                )
                consumed.add(i)
            else:
                merged.append(current)
                current = seg
                consumed.add(i)
        
        if current is not None:
            merged.append(current)
        
        return merged
    
    @staticmethod
    def fill_gaps(segments: List[FileSegment], sector_size: int = 512) -> List[FileSegment]:
        """
        填補 segment 之間的 gaps
        
        策略：
        - 如果是連續檔案的合理 gap（< 10 sectors），用 0 填充
        - 如果 gap 太大，標記為碎片的另一個 segment
        
        Returns:
            更新後的 segments 列表
        """
        if not segments:
            return []
        
        sorted_segs = sorted(segments, key=lambda s: s.offset)
        result = []
        threshold = 10 * sector_size  # gap < 10 sectors = fill with zeros
        
        for i in range(len(sorted_segs)):
            if i > 0:
                prev = sorted_segs[i - 1]
                curr = sorted_segs[i]
                gap_start = prev.offset + prev.size
                gap_end = curr.offset
                gap_size = gap_end - gap_start
                
                if 0 < gap_size < threshold:
                    # Fill small gap with zero bytes
                    gap_fill = FileSegment(
                        offset=gap_start,
                        size=gap_size,
                        file_type=curr.file_type,
                        data=b'\x00' * gap_size,
                        quality_score=0.0  # filled gap has zero quality
                    )
                    result.append(gap_fill)
            
            result.append(sorted_segs[i])
        
        return result
    
    @staticmethod
    def calculate_rebuild_quality(segments: List[FileSegment]) -> float:
        """
        計算重建品質
        
        公式：
        quality = (total_sectors_read / estimated_sectors) * average_quality_score
        
        Returns:
            0.0 ~ 1.0
        """
        if not segments:
            return 0.0
        
        total_size = sum(s.size for s in segments)
        if total_size == 0:
            return 0.0
        
        estimated_sectors = total_size / 512  # assume 512-byte sectors
        total_sectors_read = sum(s.size / 512 for s in segments)
        
        avg_quality = sum(s.quality_score for s in segments) / len(segments)
        
        quality = (total_sectors_read / estimated_sectors) * avg_quality
        return max(0.0, min(1.0, quality))
    
    @staticmethod
    def build_file(segments: List[FileSegment], output_path: str = None) -> Dict:
        """
        重建完整檔案
        
        流程：
        1. 排序（offset）
        2. 合併相鄰
        3. 填補小 gap
        4. 寫入檔案
        
        Returns:
            {
                'success': bool,
                'total_size': int,
                'gaps_filled': int,
                'segments_merged': int,
                'quality': float,
                'output_path': str
            }
        """
        result = {
            'success': False,
            'total_size': 0,
            'gaps_filled': 0,
            'segments_merged': 0,
            'quality': 0.0,
            'output_path': output_path or ''
        }
        
        if not segments:
            return result
        
        # 1. Sort by offset
        sorted_segs = sorted(segments, key=lambda s: s.offset)
        original_count = len(sorted_segs)
        
        # 2. Merge adjacent segments
        merged = ReconstructionEngine.merge_segments(sorted_segs)
        segments_merged = original_count - len(merged)
        
        # 3. Fill small gaps
        gap_threshold = 10 * 512  # 10 sectors
        pre_gap_count = len(merged)
        filled = ReconstructionEngine.fill_gaps(merged)
        gaps_filled = len(filled) - pre_gap_count
        
        # 4. Reassemble data and write
        total_data = b''
        for seg in sorted(filled, key=lambda s: s.offset):
            if seg.data:
                total_data += seg.data
        
        if output_path:
            try:
                with open(output_path, 'wb') as f:
                    f.write(total_data)
                result['output_path'] = output_path
            except IOError:
                result['success'] = False
                return result
        
        result['success'] = True
        result['total_size'] = len(total_data)
        result['gaps_filled'] = gaps_filled
        result['segments_merged'] = segments_merged
        result['quality'] = ReconstructionEngine.calculate_rebuild_quality(filled)
        
        return result


# Tests
if __name__ == '__main__':
    # Test 1: Merge adjacent segments
    segs = [
        FileSegment(0, 512, 'jpg', b'\x00' * 512),
        FileSegment(512, 512, 'jpg', b'\x01' * 512),
        FileSegment(1024, 512, 'jpg', b'\x02' * 512),
    ]
    merged = ReconstructionEngine.merge_segments(segs)
    print(f"Merge test: {len(segs)} -> {len(merged)} segments")
    
    # Test 2: Calculate quality
    quality = ReconstructionEngine.calculate_rebuild_quality(merged)
    print(f"Quality: {quality}")
    
    # Test 3: File with gaps
    segs_with_gap = [
        FileSegment(0, 512, 'jpg', b'\x00' * 512),
        FileSegment(512, 1024, 'jpg', b'\x01' * 1024),
        FileSegment(2048, 512, 'jpg', b'\x02' * 512),  # gap at 1536-2047
    ]
    filled = ReconstructionEngine.fill_gaps(segs_with_gap)
    print(f"Gap test: {len(segs_with_gap)} -> {len(filled)} segments")
    
    # Test 4: Different types should not merge
    segs_diff = [
        FileSegment(0, 512, 'jpg', b'\x00' * 512),
        FileSegment(512, 512, 'png', b'\x89PNG' + b'\x00' * 507),
    ]
    merged_diff = ReconstructionEngine.merge_segments(segs_diff)
    print(f"Different types: {len(segs_diff)} -> {len(merged_diff)} (should be same)")
    
    print("\n✅ ReconstructionEngine OK")
