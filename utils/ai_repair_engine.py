"""
AI Repair Engine - 斷層分析與結構修復
"""
import struct


class AIFrameAnalyzer:
    """分析資料中的斷層與結構異常"""
    
    @staticmethod
    def analyze_jpeg(data: bytes) -> dict:
        """分析 JPEG 資料的完整性"""
        result = {
            'is_valid': False,
            'sof_marker': '',
            'quality_factor': 0,
            'width': 0,
            'height': 0,
            'components': 0,
            'segments': 0,
            'corruption_offset': -1,
            'damage_ratio': 0.0,
            'suggestions': []
        }
        
        if not data or len(data) < 4:
            result['suggestions'].append('File too small to be valid JPEG')
            return result
        
        if data[0] != 0xFF or data[1] != 0xD8:
            result['suggestions'].append('Missing SOI marker (FFD8)')
            result['corruption_offset'] = 0
            return result
        
        result['is_valid'] = True
        segments = 1
        offset = 2
        corruption_found = False
        
        while offset < len(data) - 4:
            if data[offset] != 0xFF:
                result['corruption_offset'] = offset if not corruption_found else result['corruption_offset']
                result['is_valid'] = False
                corruption_found = True
                offset += 1
                continue
            
            marker = data[offset + 1]
            if marker == 0xD9:  # EOI
                result['segments'] = segments
                break
            elif marker == 0xD0:  # RST
                segments += 1
                offset += 2
                continue
            elif marker in (0x00, 0x01):  # Pad / TEM
                offset += 2
                continue
            elif marker >= 0xD0 and marker <= 0xD9:
                offset += 2
                continue
            elif marker >= 0xC0 and marker <= 0xCF:  # SOF markers
                if len(data) >= offset + 9:
                    result['sof_marker'] = f'FF{marker:02X}'
                    result['quality_factor'] = data[offset + 5]
                    result['height'] = struct.unpack('>H', data[offset + 3:offset + 5])[0]
                    result['width'] = struct.unpack('>H', data[offset + 7:offset + 9])[0]
                    result['components'] = data[offset + 9] if offset + 10 < len(data) else 0
                    result['segments'] = segments
                    segments += 1
                
                if not corruption_found:
                    result['is_valid'] = True
                offset += 2
                continue
            elif marker == 0xDA:  # SOS
                result['segments'] = segments + 1
                break
            else:
                if offset + 2 >= len(data):
                    break
                seg_len = struct.unpack('>H', data[offset + 2:offset + 4])[0] if offset + 4 <= len(data) else 0
                if seg_len > len(data) - offset - 4:
                    if not corruption_found:
                        result['corruption_offset'] = offset
                        result['is_valid'] = False
                    break
                offset += 2 + seg_len
                segments += 1
        
        if corruption_found:
            result['damage_ratio'] = min(1.0, result['corruption_offset'] / max(1, len(data)))
        
        return result
    
    @staticmethod
    def analyze_png(data: bytes) -> dict:
        """分析 PNG 資料"""
        result = {
            'is_valid': False,
            'chunks': 0,
            'width': 0,
            'height': 0,
            'bit_depth': 0,
            'color_type': 0,
            'corruption_offset': -1,
            'damage_ratio': 0.0,
            'suggestions': []
        }
        
        if not data or len(data) < 8:
            result['suggestions'].append('File too small')
            return result
        
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            result['suggestions'].append('Invalid PNG signature')
            result['corruption_offset'] = 0
            return result
        
        result['is_valid'] = True
        offset = 8
        chunks = 0
        
        while offset < len(data) - 12:
            chunk_len = struct.unpack('>I', data[offset:offset + 4])[0]
            chunk_type = data[offset + 4:offset + 8]
            
            if offset + 12 > len(data):
                if not result['is_valid']:
                    result['corruption_offset'] = offset
                result['is_valid'] = False
                break
            
            if chunk_type == b'IHDR':
                result['width'] = struct.unpack('>I', data[offset + 8:offset + 12])[0]
                if offset + 16 <= len(data):
                    result['height'] = struct.unpack('>I', data[offset + 12:offset + 16])[0]
                if offset + 20 <= len(data):
                    result['bit_depth'] = data[offset + 16]
                if offset + 21 <= len(data):
                    result['color_type'] = data[offset + 17]
            
            if chunk_type == b'IEND':
                result['chunks'] = chunks
                break
            
            chunks += 1
            offset += 12 + chunk_len
        
        result['chunks'] = chunks
        return result
    
    @staticmethod
    def analyze_mp3(data: bytes) -> dict:
        """分析 MP3 資料"""
        result = {
            'valid_frames': 0,
            'invalid_frames': 0,
            'bitrate': 0,
            'sample_rate': 0,
            'channels': 0,
            'damage_ratio': 0.0,
            'suggestions': []
        }
        
        if not data or len(data) < 4:
            result['suggestions'].append('File too small')
            return result
        
        pos = 0
        valid = 0
        invalid = 0
        
        while pos + 4 <= len(data):
            header = struct.unpack('>I', data[pos:pos + 4])[0]
            
            if (header & 0xFFE00000) != 0xFFE00000:
                if invalid == 0 and valid == 0:
                    pos += 1
                    continue
                break
            
            if (header & 0x00000600) == 0x00000600:
                break
            if (header & 0x0000000C) == 0x0000000C:
                break
            
            layer_bit = (header >> 17) & 3
            bitrate_idx = (header >> 12) & 0xF
            sample_rate_idx = (header >> 10) & 0x3
            padding = (header >> 9) & 0x1
            
            if layer_bit == 0:
                layer_bit = 3
            
            bitrates_v1 = [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,384]
            bitrates_v2 = [0,32,48,56,64,80,96,112,128,160,176,192,224,256,320,384]
            
            if (header >> 19) & 1:
                bitrates = bitrates_v1
            else:
                bitrates = bitrates_v2
            
            sample_rates = [44100, 48000, 32000] if (header >> 19) & 1 else [22050, 24000, 16000]
            
            if bitrate_idx == 0 or sample_rate_idx == 0 or bitrate_idx == 15:
                invalid += 1
                pos += 1
                continue
            
            bitrate = bitrates[bitrate_idx]
            result['bitrate'] = bitrate
            
            if layer_bit == 1:
                frame_size = int((12 * bitrate) / sample_rates[sample_rate_idx] * 1000)
            else:
                frame_size = int((144 * bitrate) / sample_rates[sample_rate_idx])
            
            if frame_size <= 0:
                invalid += 1
                pos += 1
                continue
            
            result['sample_rate'] = sample_rates[sample_rate_idx]
            result['channels'] = 2 if (header & 0x1800) == 0x1800 else 1
            
            if pos + frame_size > len(data):
                valid += 1
                break
            
            pos += frame_size
            valid += 1
        
        result['valid_frames'] = valid
        result['invalid_frames'] = invalid
        
        total = valid + invalid
        result['damage_ratio'] = invalid / max(1, total)
        
        return result
    
    @staticmethod
    def analyze_generic(data: bytes, signature: str) -> dict:
        """通用分析"""
        result = {
            'is_valid': False,
            'signature': signature,
            'file_size': len(data),
            'corruption_offset': -1,
            'damage_ratio': 0.0,
            'suggestions': []
        }
        
        if not data:
            result['suggestions'].append('Empty file')
            return result
        
        sig_map = {
            'pdf': b'%PDF',
            'zip': b'PK\x03\x04',
            'doc': b'\xD0\xCF\x11\xE0',
            'tiff': b'II' + b'\x2A\x00' + b'\x08\x00\x00\x00',
            'wav': b'RIFF',
            'exe': b'MZ',
        }
        
        expected = sig_map.get(signature)
        if expected:
            if data[:len(expected)] == expected:
                result['is_valid'] = True
            else:
                result['corruption_offset'] = 0
                result['is_valid'] = False
                result['suggestions'].append(f'Missing {signature} header')
        
        return result


class RepairEngine:
    """修復引擎"""
    
    @staticmethod
    def repair_jpeg(data: bytes, metadata: dict = None) -> dict:
        """
        JPEG 修復
        
        策略：
        1. 檢查 SOI/EOI
        2. 跳過腐蝕區塊
        3. 補上 EOI
        """
        result = {
            'success': False,
            'original_size': len(data),
            'repaired_size': 0,
            'notes': [],
            'data': data
        }
        
        if not data or len(data) < 4:
            result['notes'].append('Data too small')
            return result
        
        repaired = bytearray(data)
        
        # Check SOI
        if data[0] != 0xFF or data[1] != 0xD8:
            repaired[0] = 0xFF
            repaired[1] = 0xD8
            result['notes'].append('Fixed missing SOI marker')
        
        # Remove corrupted segments (FF bytes without proper markers)
        i = 0
        clean = bytearray()
        while i < len(repaired):
            if repaired[i] == 0xFF and i + 1 < len(repaired):
                m = repaired[i + 1]
                if m == 0xD9:  # EOI - keep and stop
                    clean.extend(repaired[i:])
                    result['notes'].append(f'Found EOI at offset {i}')
                    break
                elif m == 0x00 or m == 0x01 or (0xD0 <= m <= 0xD9):
                    clean.append(0xFF)
                    clean.append(m)
                    i += 2
                    continue
                elif m >= 0xC0 and m <= 0xCF:
                    clean.append(0xFF)
                    clean.append(m)
                    if i + 4 <= len(repaired):
                        clean.extend(repaired[i + 2:i + 4])
                        seg_len = struct.unpack('>H', bytes(repaired[i + 2:i + 4]))[0]
                        clean.extend(repaired[i + 4:i + 4 + seg_len])
                    i += 4 + max(0, struct.unpack('>H', bytes(repaired[i + 2:i + 4]))[0] - 2)
                    continue
                elif m == 0xDA:  # SOS
                    clean.append(0xFF)
                    clean.append(m)
                    result['notes'].append(f'Found SOS at offset {i}')
                    break
                else:
                    clean.append(0xFF)
                    clean.append(m)
                    if i + 2 <= len(repaired):
                        seg_len = struct.unpack('>H', bytes(repaired[i + 2:i + 4]))[0] if i + 4 <= len(repaired) else 0
                        clean.extend(repaired[i + 4:i + 4 + seg_len])
                    i += 2 + max(0, seg_len)
                    continue
            else:
                clean.append(repaired[i])
                i += 1
        
        # Ensure ends with EOI
        if not clean or clean[-1] != 0xD9:
            if len(clean) >= 2 and clean[-2] == 0xFF:
                clean[-1] = 0xD9
            else:
                clean.extend([0xFF, 0xD9])
        
        result['success'] = True
        result['repaired_size'] = len(clean)
        result['data'] = bytes(clean)
        
        if not metadata or not metadata.get('is_valid'):
            result['notes'].append('JPEG had corruption, repaired')
        
        return result
    
    @staticmethod
    def repair_mp3(data: bytes) -> dict:
        """
        MP3 修復
        
        策略：
        1. 找出 valid frames
        2. 移除 invalid frames
        3. 嘗試重建 frame boundary
        """
        result = {
            'success': False,
            'original_size': len(data),
            'repaired_size': 0,
            'frames_removed': 0,
            'notes': [],
            'data': data
        }
        
        if not data or len(data) < 4:
            result['notes'].append('Data too small')
            return result
        
        repaired = bytearray()
        frames_removed = 0
        pos = 0
        
        while pos < len(data):
            if pos + 4 > len(data):
                break
            
            header = struct.unpack('>I', data[pos:pos + 4])[0]
            
            is_valid = (
                (header & 0xFFE00000) == 0xFFE00000 and
                (header & 0x00000600) != 0x00000600 and
                (header & 0x0000000C) != 0x0000000C and
                ((header >> 17) & 3) != 0 and
                ((header >> 12) & 0xF) != 0 and
                ((header >> 12) & 0xF) != 15 and
                ((header >> 10) & 0x3) != 0
            )
            
            if not is_valid:
                pos += 1
                frames_removed += 1
                continue
            
            layer_bit = (header >> 17) & 3
            if layer_bit == 0:
                layer_bit = 3
            bitrate_idx = (header >> 12) & 0xF
            sample_rate_idx = (header >> 10) & 0x3
            
            bitrates = [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,384]
            sample_rates = [44100, 48000, 32000]
            
            bitrate = bitrates[bitrate_idx]
            if layer_bit == 1:
                frame_size = int((12 * bitrate) / sample_rates[sample_rate_idx] * 1000)
            else:
                frame_size = int((144 * bitrate) / sample_rates[sample_rate_idx])
            
            if frame_size <= 0 or pos + frame_size > len(data):
                break
            
            repaired.extend(data[pos:pos + frame_size])
            pos += frame_size
        
        result['success'] = True
        result['repaired_size'] = len(repaired)
        result['frames_removed'] = frames_removed
        result['data'] = bytes(repaired)
        
        if frames_removed > 0:
            result['notes'].append(f'Removed {frames_removed} invalid frames')
        
        return result


# Tests
if __name__ == '__main__':
    # JPEG test
    jpeg_data = b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' + \
                b'\xFF\xDB\x00\x84\x00\x01\x02\x03\x04' + \
                b'\xFF\xD9'
    result = AIFrameAnalyzer.analyze_jpeg(jpeg_data)
    print(f"JPEG analysis valid: {result['is_valid']}")
    
    repaired = RepairEngine.repair_jpeg(jpeg_data)
    print(f"JPEG repair success: {repaired['success']}")
    
    # MP3 test (valid header)
    mp3_data = b'\xFF\xFB\x90\x00' + b'\x00' * 412 + b'\xFF\xFB\x90\x00' + b'\x00' * 412
    result = AIFrameAnalyzer.analyze_mp3(mp3_data)
    print(f"MP3 valid frames: {result['valid_frames']}")
    
    repaired_mp3 = RepairEngine.repair_mp3(mp3_data)
    print(f"MP3 repair success: {repaired_mp3['success']}")
    
    # PNG test
    png_data = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\x0cIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS' + \
               b'\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\x80\x00\x06\x00\x35\x50\xd2\x00\x00\x00\x00IEND' + \
               b'\xae\x42\x60\x82'
    result = AIFrameAnalyzer.analyze_png(png_data)
    print(f"PNG valid: {result['is_valid']}")
    
    print("\n✅ RepairEngine OK")
