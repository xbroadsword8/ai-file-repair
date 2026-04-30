"""
File Size Estimator - 根據 magic/end marker 估算檔案大小
"""
import struct


class FileSizeEstimator:
    """估算檔案大小"""

    @staticmethod
    def estimate_jpeg_size(data: bytes, start: int) -> int:
        """搜尋 \\xFF\\xD9 (EOI marker)。找到就回傳 offset+2。找不到回傳 0。"""
        pos = start
        while pos < len(data) - 1:
            if data[pos] == 0xFF and data[pos + 1] == 0xD9:
                return (pos - start) + 2
            pos += 1
        return 0

    @staticmethod
    def estimate_png_size(data: bytes, start: int) -> int:
        """搜尋 IEND chunk。找到就計算總大小。找不到回傳 0。"""
        if data[start:start + 8] != b'\x89PNG\r\n\x1a\n':
            return 0
        # Find IEND - simplified: just scan for IEND after signature
        iend_pos = data.find(b'IEND', start + 8)
        if iend_pos != -1:
            # IEND chunk starts 4 bytes before the type name
            # Chunk: 4 length + 4 type + 4 CRC = 12 bytes
            chunk_start = iend_pos - 4
            return (chunk_start - start) + 12
        return 0

    @staticmethod
    def estimate_pdf_size(data: bytes, start: int) -> int:
        """搜尋 %%EOF。找不到回傳 0。"""
        pos = data.find(b'%%EOF', start)
        if pos != -1:
            return (pos - start) + 5
        return 0

    @staticmethod
    def estimate_mp3_size(data: bytes, start: int) -> int:
        """解析 frame header，累加 frame 大小直到遇到 invalid frame。"""
        pos = start
        max_frames = 100000
        frames = 0

        while frames < max_frames:
            if pos + 4 > len(data):
                break
            header = struct.unpack('>I', data[pos:pos + 4])[0]
            if (header & 0xFFE00000) != 0xFFE00000:
                if frames == 0:
                    return 0
                break
            if (header & 0x00000600) == 0x00000600:
                break

            version_bit = (header >> 19) & 3
            layer_bit = (header >> 17) & 3
            bitrate = (header >> 12) & 0xF
            sample_rate = (header >> 10) & 0x3
            padding = (header >> 9) & 0x1

            if bitrate == 0 or bitrate == 15:
                break
            if sample_rate == 0:
                break

            if layer_bit == 0:
                layer_bit = 3

            if version_bit == 3:
                bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384]
            else:
                bitrates = [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 176, 192, 224, 256, 320, 384]

            if layer_bit == 1:
                sample_rates = [44100, 48000, 32000]
                frame_size = int((12 * bitrates[bitrate]) / sample_rates[sample_rate] * 1000)
            else:
                sample_rates = [44100, 48000, 32000] if version_bit == 3 else [22050, 24000, 16000]
                frame_size = int((144 * bitrates[bitrate]) / sample_rates[sample_rate])

            if padding:
                frame_size += 1
            if frame_size <= 0:
                break

            pos += frame_size
            frames += 1

        return max(pos - start, 0) if frames > 0 else 0

    @staticmethod
    def estimate_zip_size(data: bytes, start: int) -> int:
        """搜尋 Central Directory (PK\\x01\\x02)，估算大小。"""
        pos = start + 4  # Skip local header
        cd_pos = data.find(b'PK\x01\x02', pos)
        if cd_pos != -1:
            # Approximate: cd_pos + some extra for directory entries
            return cd_pos + 512  # rough estimate
        return 4096

    @staticmethod
    def estimate_gif_size(data: bytes, start: int) -> int:
        """搜尋終止字元 ;"""
        pos = data.find(b';', start)
        if pos != -1:
            return (pos - start) + 1
        return 0

    @staticmethod
    def estimate_mp4_size(data: bytes, start: int) -> int:
        """搜尋 moov box。"""
        moov_pos = data.find(b'moov', start)
        if moov_pos != -1:
            return moov_pos + 8
        return 512

    @staticmethod
    def estimate_tiff_size(data: bytes, start: int) -> int:
        """TIFF - 回傳合理的預設值"""
        return 4096

    @staticmethod
    def estimate_doc_xlsx_pptx_size(data: bytes, start: int) -> int:
        """Office 2007+ (ZIP-based)"""
        return 4096

    @staticmethod
    def estimate_wav_size(data: bytes, start: int) -> int:
        """RIFf chunk size"""
        if data[start:start + 4] == b'RIFF' and data[start + 8:start + 12] == b'WAVE':
            size = struct.unpack('<I', data[start + 4:start + 8])[0]
            if size > 0 and size < 500 * 1024 * 1024:
                return 12 + size
        return 4096

    @staticmethod
    def estimate_exe_size(data: bytes, start: int) -> int:
        """PE 檔案，回傳合理預設值"""
        return 65536

    @staticmethod
    def estimate_size(data: bytes, start: int, ext: str) -> int:
        """
        統一入口：根據 ext 選擇對應的估算方法。
        
        Returns:
            估算大小 (bytes)，無法估算回傳 0
        """
        methods = {
            'jpg': FileSizeEstimator.estimate_jpeg_size,
            'jpeg': FileSizeEstimator.estimate_jpeg_size,
            'png': FileSizeEstimator.estimate_png_size,
            'pdf': FileSizeEstimator.estimate_pdf_size,
            'mp3': FileSizeEstimator.estimate_mp3_size,
            'zip': FileSizeEstimator.estimate_zip_size,
            'gif': FileSizeEstimator.estimate_gif_size,
            'mp4': FileSizeEstimator.estimate_mp4_size,
            'mov': FileSizeEstimator.estimate_mp4_size,
            'tiff': FileSizeEstimator.estimate_tiff_size,
            'wav': FileSizeEstimator.estimate_wav_size,
            'docx': FileSizeEstimator.estimate_doc_xlsx_pptx_size,
            'xlsx': FileSizeEstimator.estimate_doc_xlsx_pptx_size,
            'pptx': FileSizeEstimator.estimate_doc_xlsx_pptx_size,
            'exe': FileSizeEstimator.estimate_exe_size,
        }
        fn = methods.get(ext)
        if fn:
            return fn(data, start)
        return 0


# Tests
if __name__ == '__main__':
    # JPG test
    jpeg_data = b'\xFF\xD8\xFF' + b'\x00' * 100 + b'\xFF\xD9'
    assert FileSizeEstimator.estimate_jpeg_size(jpeg_data, 0) == 105, f"Expected 105, got {FileSizeEstimator.estimate_jpeg_size(jpeg_data, 0)}"

    # PNG test: proper chunk structure (sig + IEND chunk)
    # PNG: sig(8) + IEND(12) = 20 bytes total
    png_data = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\x00' + b'IEND' + b'\xae\x42\x60\x82'
    assert FileSizeEstimator.estimate_png_size(png_data, 0) == 20, f"Expected 20, got {FileSizeEstimator.estimate_png_size(png_data, 0)}"

    # PDF test
    pdf_data = b'%PDF-1.4' + b'\x00' * 5 + b'%%EOF'
    assert FileSizeEstimator.estimate_pdf_size(pdf_data, 0) == 18, f"Expected 18, got {FileSizeEstimator.estimate_pdf_size(pdf_data, 0)}"

    # MP3 test (valid frame)
    mp3_data = b'\xFF\xFB\x90\x00' + b'\x00' * 412
    result = FileSizeEstimator.estimate_mp3_size(mp3_data, 0)
    assert result > 0, f"Expected >0, got {result}"

    # Generic estimate
    assert FileSizeEstimator.estimate_size(jpeg_data, 0, 'jpg') == 105
    assert FileSizeEstimator.estimate_size(png_data, 0, 'png') == 20

    print("SizeEstimator OK - all tests passed")
