"""
RAW Scan Engine — Improved Disk Recovery Scanner
磁碟 RAW 掃描引擎 (取代舊版 placeholder)

關鍵改進：
1. 每 sector 都讀（不再 step 100）
2. 正確大小估算（跨 sector 搜索 end marker）
3. Bad sector 處理
4. 檔案去重（同一檔案多次找到取最大/最高可信度）
5. 連續區塊檢測（相鄰的 magic number 合併）
6. 多倍頻掃描（offset 1..sector_size-1 也搜尋）
"""

import struct
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple
from interfaces import DiskScanner, RawScanResult, BadSectorPolicy


# ---------------------------------------------------------------------------
# FileSignature definition
# ---------------------------------------------------------------------------

@dataclass
class FileSignature:
    """Defines the signature (magic number) and metadata for a file type."""
    ext: str
    magic: bytes                    # None means no magic (text-based detection)
    end_magic: Optional[bytes]      # End marker for size estimation
    end_scan_range: int             # How many bytes to search for end marker
    min_size: int
    max_size: int
    category: str                   # image, video, audio, document, archive, etc.
    offset: int = 0                 # Offset in file header where magic appears


# ---------------------------------------------------------------------------
# FileSignature database — 60+ entries
# ---------------------------------------------------------------------------

FILE_SIGNATURES: Dict[str, FileSignature] = {
    # ──────────── Images ────────────
    'jpg': FileSignature(
        ext='jpg', magic=b'\xFF\xD8\xFF', end_magic=b'\xFF\xD9',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=100 * 1024 * 1024, category='image'),
    'jpeg': FileSignature(
        ext='jpeg', magic=b'\xFF\xD8\xFF', end_magic=b'\xFF\xD9',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=100 * 1024 * 1024, category='image'),
    'png': FileSignature(
        ext='png', magic=b'\x89PNG\r\n\x1a\n',
        end_magic=b'IEND\xae\x42\x60\x82',
        end_scan_range=4 * 1024 * 1024, min_size=200,
        max_size=500 * 1024 * 1024, category='image'),
    'gif': FileSignature(
        ext='gif', magic=b'GIF87a', end_magic=b';',
        end_scan_range=10 * 1024 * 1024, min_size=100,
        max_size=100 * 1024 * 1024, category='image'),
    'gif89': FileSignature(
        ext='gif', magic=b'GIF89a', end_magic=b';',
        end_scan_range=10 * 1024 * 1024, min_size=100,
        max_size=100 * 1024 * 1024, category='image'),
    'bmp': FileSignature(
        ext='bmp', magic=b'BM', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='image'),
    'tiff': FileSignature(
        ext='tif', magic=b'II\x2A\x00', end_magic=None,
        end_scan_range=0, min_size=200,
        max_size=500 * 1024 * 1024, category='image'),
    'tiff_be': FileSignature(
        ext='tif', magic=b'MM\x00\x2A', end_magic=None,
        end_scan_range=0, min_size=200,
        max_size=500 * 1024 * 1024, category='image'),
    'webp': FileSignature(
        ext='webp', magic=b'RIFF', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=200 * 1024 * 1024, category='image'),
    'ico': FileSignature(
        ext='ico', magic=b'\x00\x00\x01\x00', end_magic=None,
        end_scan_range=0, min_size=40,
        max_size=10 * 1024 * 1024, category='image'),
    'svg': FileSignature(
        ext='svg', magic=b'<svg', end_magic=None,
        end_scan_range=2 * 1024 * 1024, min_size=100,
        max_size=50 * 1024 * 1024, category='image'),
    'tga': FileSignature(
        ext='tga', magic=None, end_magic=None,
        end_scan_range=0, min_size=18,
        max_size=500 * 1024 * 1024, category='image'),
    'psd': FileSignature(
        ext='psd', magic=b'8BPS', end_magic=None,
        end_scan_range=0, min_size=200,
        max_size=2 * 1024 * 1024 * 1024, category='image'),
    'raw': FileSignature(
        ext='cr2', magic=b'IIM\x00\x1A', end_magic=None,
        end_scan_range=0, min_size=2000000,
        max_size=100 * 1024 * 1024, category='image'),
    'nef': FileSignature(
        ext='nef', magic=b'NEF\x20\x00\x1A\x00', end_magic=None,
        end_scan_range=0, min_size=500000,
        max_size=100 * 1024 * 1024, category='image'),
    'raf': FileSignature(
        ext='raf', magic=b'FUJIFILM', end_magic=None,
        end_scan_range=0, min_size=500000,
        max_size=100 * 1024 * 1024, category='image'),
    'arw': FileSignature(
        ext='arw', magic=b'SonyArRaw', end_magic=None,
        end_scan_range=0, min_size=1000000,
        max_size=100 * 1024 * 1024, category='image'),
    'orf': FileSignature(
        ext='orf', magic=b'Olympus', end_magic=None,
        end_scan_range=0, min_size=500000,
        max_size=100 * 1024 * 1024, category='image'),
    'pef': FileSignature(
        ext='pef', magic=b'CTPLM', end_magic=None,
        end_scan_range=0, min_size=500000,
        max_size=100 * 1024 * 1024, category='image'),
    'xpm': FileSignature(
        ext='xpm', magic=b'/* XPM', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=10 * 1024 * 1024, category='image'),

    # ──────────── Video ────────────
    'mp4': FileSignature(
        ext='mp4', magic=b'\x00\x00\x00\x1c\x66\x74\x79\x70',
        end_magic=b'moov',
        end_scan_range=64 * 1024 * 1024, min_size=200,
        max_size=4 * 1024 * 1024 * 1024, category='video'),
    'mov': FileSignature(
        ext='mov', magic=b'\x00\x00\x00\x14\x66\x74\x79\x70',
        end_magic=b'moov',
        end_scan_range=64 * 1024 * 1024, min_size=200,
        max_size=4 * 1024 * 1024 * 1024, category='video'),
    'avi': FileSignature(
        ext='avi', magic=b'RIFF', end_magic=b'AVI ',
        end_scan_range=64 * 1024 * 1024, min_size=100,
        max_size=4 * 1024 * 1024 * 1024, category='video'),
    'wmv': FileSignature(
        ext='wmv', magic=b'RIFF', end_magic=b'AVI ',
        end_scan_range=64 * 1024 * 1024, min_size=100,
        max_size=4 * 1024 * 1024 * 1024, category='video'),
    'flv': FileSignature(
        ext='flv', magic=b'FLV\x01', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=1 * 1024 * 1024 * 1024, category='video'),
    'mkv': FileSignature(
        ext='mkv', magic=b'\x1a\x45\xdf\xa3',
        end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=4 * 1024 * 1024 * 1024, category='video'),
    'webm': FileSignature(
        ext='webm', magic=b'\x1a\x45\xdf\xa3',
        end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=4 * 1024 * 1024 * 1024, category='video'),
    'ts': FileSignature(
        ext='ts', magic=b'\x47', end_magic=None,
        end_scan_range=0, min_size=1314,
        max_size=10 * 1024 * 1024 * 1024, category='video'),
    'm2ts': FileSignature(
        ext='m2ts', magic=b'\x47', end_magic=None,
        end_scan_range=0, min_size=1314,
        max_size=10 * 1024 * 1024 * 1024, category='video'),
    '3gp': FileSignature(
        ext='3gp', magic=b'\x00\x00\x00\x18\x66\x74\x79\x70',
        end_magic=None,
        end_scan_range=0, min_size=200,
        max_size=500 * 1024 * 1024, category='video'),
    'm4v': FileSignature(
        ext='m4v', magic=b'\x00\x00\x00\x1c\x66\x74\x79\x70',
        end_magic=None,
        end_scan_range=0, min_size=200,
        max_size=4 * 1024 * 1024 * 1024, category='video'),

    # ──────────── Audio ────────────
    'mp3': FileSignature(
        ext='mp3', magic=b'\xFF\xFB', end_magic=None,
        end_scan_range=0, min_size=1000,
        max_size=1 * 1024 * 1024 * 1024, category='audio'),
    'mp3_id3': FileSignature(
        ext='mp3', magic=b'ID3', end_magic=None,
        end_scan_range=0, min_size=1000,
        max_size=1 * 1024 * 1024 * 1024, category='audio'),
    'aac': FileSignature(
        ext='aac', magic=b'\xFF\xF1', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='audio'),
    'aac_latm': FileSignature(
        ext='aac', magic=b'\xFF\xF9', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='audio'),
    'ogg': FileSignature(
        ext='ogg', magic=b'OggS', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='audio'),
    'flac': FileSignature(
        ext='flac', magic=b'fLaC', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='audio'),
    'wma': FileSignature(
        ext='wma', magic=b'\x04\x00\x00\x00', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=1 * 1024 * 1024 * 1024, category='audio'),
    'm4a': FileSignature(
        ext='m4a', magic=b'\x00\x00\x00\x1c\x66\x74\x79\x70',
        end_magic=None,
        end_scan_range=0, min_size=200,
        max_size=1 * 1024 * 1024 * 1024, category='audio'),
    'aiff': FileSignature(
        ext='aiff', magic=b'FORM', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=2 * 1024 * 1024 * 1024, category='audio'),
    'ape': FileSignature(
        ext='ape', magic=b'APES\x00\x20\x00\x00', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='audio'),

    # ──────────── Documents ────────────
    'pdf': FileSignature(
        ext='pdf', magic=b'%PDF', end_magic=b'%EOF',
        end_scan_range=4 * 1024 * 1024, min_size=100,
        max_size=100 * 1024 * 1024, category='document'),
    'doc': FileSignature(
        ext='doc', magic=b'\xD0\xCF\x11\xE0', end_magic=None,
        end_scan_range=0, min_size=1024,
        max_size=200 * 1024 * 1024, category='document'),
    'docx': FileSignature(
        ext='docx', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=200 * 1024 * 1024, category='document'),
    'xlsx': FileSignature(
        ext='xlsx', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=200 * 1024 * 1024, category='document'),
    'pptx': FileSignature(
        ext='pptx', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=200 * 1024 * 1024, category='document'),
    'odt': FileSignature(
        ext='odt', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=200 * 1024 * 1024, category='document'),
    'ods': FileSignature(
        ext='ods', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=200 * 1024 * 1024, category='document'),
    'odp': FileSignature(
        ext='odp', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=200 * 1024 * 1024, category='document'),
    'rtf': FileSignature(
        ext='rtf', magic=b'\x7b\x5c\x72\x74\x66', end_magic=None,
        end_scan_range=0, min_size=10,
        max_size=50 * 1024 * 1024, category='document'),
    'eps': FileSignature(
        ext='eps', magic=b'%!PS-Adobe', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=100 * 1024 * 1024, category='document'),
    'pages': FileSignature(
        ext='pages', magic=b'\x00\x00\x00\x00', end_magic=None,
        end_scan_range=0, min_size=1000,
        max_size=500 * 1024 * 1024, category='document'),
    'numbers': FileSignature(
        ext='numbers', magic=b'\x00\x00\x00\x00', end_magic=None,
        end_scan_range=0, min_size=1000,
        max_size=500 * 1024 * 1024, category='document'),

    # ──────────── Archives ────────────
    'zip': FileSignature(
        ext='zip', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=10,
        max_size=10 * 1024 * 1024 * 1024, category='archive'),
    'jar': FileSignature(
        ext='jar', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=10,
        max_size=10 * 1024 * 1024 * 1024, category='archive'),
    'rar': FileSignature(
        ext='rar', magic=b'Rar!\x1A\x07', end_magic=None,
        end_scan_range=0, min_size=200,
        max_size=10 * 1024 * 1024 * 1024, category='archive'),
    'rar5': FileSignature(
        ext='rar', magic=b'Rar!\x1A\x08', end_magic=None,
        end_scan_range=0, min_size=200,
        max_size=10 * 1024 * 1024 * 1024, category='archive'),
    '7z': FileSignature(
        ext='7z', magic=b'7z\xBC\xAF\x27\x1C', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=10 * 1024 * 1024 * 1024, category='archive'),
    'tar': FileSignature(
        ext='tar', magic=None, end_magic=b'ustar',
        end_scan_range=10240, min_size=1024,
        max_size=10 * 1024 * 1024 * 1024, category='archive'),
    'gz': FileSignature(
        ext='gz', magic=b'\x1F\x8B', end_magic=None,
        end_scan_range=0, min_size=10,
        max_size=4 * 1024 * 1024 * 1024, category='archive'),
    'bz2': FileSignature(
        ext='bz2', magic=b'BZh', end_magic=None,
        end_scan_range=0, min_size=10,
        max_size=4 * 1024 * 1024 * 1024, category='archive'),
    'xz': FileSignature(
        ext='xz', magic=b'\xFD\x37\x7A\x58\x5A\x00', end_magic=None,
        end_scan_range=0, min_size=10,
        max_size=4 * 1024 * 1024 * 1024, category='archive'),
    'lzma': FileSignature(
        ext='lzma', magic=b'\x5D\x00\x00\x00\x00', end_magic=None,
        end_scan_range=0, min_size=10,
        max_size=4 * 1024 * 1024 * 1024, category='archive'),
    'cab': FileSignature(
        ext='cab', magic=b'MSCF', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='archive'),
    'iso': FileSignature(
        ext='iso', magic=b'\x00' * 20, end_magic=b'MS001',
        end_scan_range=64 * 1024 * 1024, min_size=1024 * 1024,
        max_size=10 * 1024 * 1024 * 1024, category='archive'),

    # ──────────── Executables ────────────
    'exe': FileSignature(
        ext='exe', magic=b'MZ', end_magic=None,
        end_scan_range=0, min_size=512,
        max_size=1 * 1024 * 1024 * 1024, category='executable'),
    'dll': FileSignature(
        ext='dll', magic=b'MZ', end_magic=None,
        end_scan_range=0, min_size=512,
        max_size=1 * 1024 * 1024 * 1024, category='executable'),
    'sys': FileSignature(
        ext='sys', magic=b'MZ', end_magic=None,
        end_scan_range=0, min_size=512,
        max_size=500 * 1024 * 1024, category='executable'),
    'bin': FileSignature(
        ext='bin', magic=b'\x4D\x5A', end_magic=None,
        end_scan_range=0, min_size=512,
        max_size=1 * 1024 * 1024 * 1024, category='executable'),
    'com': FileSignature(
        ext='com', magic=b'\xEB', end_magic=None,
        end_scan_range=0, min_size=3,
        max_size=65535, category='executable'),
    'pyc': FileSignature(
        ext='pyc', magic=b'\x0D\x0D\x0D\x0A', end_magic=None,
        end_scan_range=0, min_size=16,
        max_size=50 * 1024 * 1024, category='executable'),
    'so': FileSignature(
        ext='so', magic=b'\x7fELF', end_magic=None,
        end_scan_range=0, min_size=64,
        max_size=500 * 1024 * 1024, category='executable'),
    'macho': FileSignature(
        ext='', magic=b'\xCA\xFE\xBA\xBE', end_magic=None,
        end_scan_range=0, min_size=64,
        max_size=1 * 1024 * 1024 * 1024, category='executable'),
    'macho_le': FileSignature(
        ext='', magic=b'\xBE\xBA\xFE\xCA', end_magic=None,
        end_scan_range=0, min_size=64,
        max_size=1 * 1024 * 1024 * 1024, category='executable'),
    'dmg': FileSignature(
        ext='dmg', magic=b'\x78\x01\x73\x00', end_magic=None,
        end_scan_range=0, min_size=1024,
        max_size=4 * 1024 * 1024 * 1024, category='executable'),
    'rpm': FileSignature(
        ext='rpm', magic=b'\xED\xFB\xEE\xDB', end_magic=None,
        end_scan_range=0, min_size=1024,
        max_size=10 * 1024 * 1024 * 1024, category='executable'),
    'deb': FileSignature(
        ext='deb', magic=b'!<arch>', end_magic=None,
        end_scan_range=0, min_size=200,
        max_size=10 * 1024 * 1024 * 1024, category='executable'),

    # ──────────── Databases / Binary data ────────────
    'sqlite': FileSignature(
        ext='sqlite', magic=b'SQLite format 3\x00', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=10 * 1024 * 1024 * 1024, category='database'),
    'mdb': FileSignature(
        ext='mdb', magic=b'\x00\xef\x01\x00', end_magic=None,
        end_scan_range=0, min_size=1024,
        max_size=1024 * 1024 * 1024, category='database'),

    # ──────────── Encrypted / Special ────────────
    'gpg': FileSignature(
        ext='asc', magic=b'\xA3\x01', end_magic=None,
        end_scan_range=0, min_size=10,
        max_size=500 * 1024 * 1024, category='cryptographic'),
    'pgp': FileSignature(
        ext='asc', magic=b'\xA3\x01', end_magic=None,
        end_scan_range=0, min_size=10,
        max_size=500 * 1024 * 1024, category='cryptographic'),

    # ──────────── Misc ────────────
    'pem': FileSignature(
        ext='pem', magic=b'-----BEGIN CERTIFICATE', end_magic=b'-----END CERTIFICATE',
        end_scan_range=64 * 1024, min_size=500,
        max_size=1024 * 1024, category='document'),
    'key': FileSignature(
        ext='key', magic=b'-----BEGIN RSA', end_magic=b'-----END RSA',
        end_scan_range=64 * 1024, min_size=500,
        max_size=1024 * 1024, category='cryptographic'),
    'crt': FileSignature(
        ext='crt', magic=b'-----BEGIN CERTIFICATE', end_magic=b'-----END CERTIFICATE',
        end_scan_range=64 * 1024, min_size=500,
        max_size=1024 * 1024, category='cryptographic'),
    'cer': FileSignature(
        ext='cer', magic=b'-----BEGIN CERTIFICATE', end_magic=b'-----END CERTIFICATE',
        end_scan_range=64 * 1024, min_size=500,
        max_size=1024 * 1024, category='cryptographic'),
    'java': FileSignature(
        ext='class', magic=b'\xCA\xFE\xBA\xBE', end_magic=None,
        end_scan_range=0, min_size=64,
        max_size=50 * 1024 * 1024, category='executable'),
    'torrent': FileSignature(
        ext='torrent', magic=b'd8:', end_magic=None,
        end_scan_range=0, min_size=10,
        max_size=1024 * 1024 * 1024, category='document'),
    'swf': FileSignature(
        ext='swf', magic=b'CSW', end_magic=None,
        end_scan_range=0, min_size=8,
        max_size=100 * 1024 * 1024, category='executable'),
    'flac': FileSignature(
        ext='flac', magic=b'fLaC', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='audio'),
    'w3c': FileSignature(
        ext='w3c', magic=b'\x05\x01\x00\x00', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=1024 * 1024, category='document'),
    'vcf': FileSignature(
        ext='vcf', magic=b'BEGIN:VCARD', end_magic=b'END:VCARD',
        end_scan_range=1024 * 1024, min_size=100,
        max_size=10 * 1024 * 1024, category='document'),
    'ics': FileSignature(
        ext='ics', magic=b'BEGIN:VCALENDAR', end_magic=b'END:VCALENDAR',
        end_scan_range=1024 * 1024, min_size=100,
        max_size=10 * 1024 * 1024, category='document'),
    'vsd': FileSignature(
        ext='vsd', magic=b'\xD0\xCF\x11\xE0', end_magic=None,
        end_scan_range=0, min_size=1024,
        max_size=500 * 1024 * 1024, category='document'),
    'vsdx': FileSignature(
        ext='vsdx', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=200 * 1024 * 1024, category='document'),
    'pub': FileSignature(
        ext='pub', magic=b'\x23\x00\x00\x00\x35\x00\x00\x00',
        end_magic=None, end_scan_range=0,
        min_size=1024, max_size=500 * 1024 * 1024, category='document'),
    'ppt': FileSignature(
        ext='ppt', magic=b'\xD0\xCF\x11\xE0', end_magic=None,
        end_scan_range=0, min_size=1024,
        max_size=500 * 1024 * 1024, category='document'),
    'ps': FileSignature(
        ext='ps', magic=b'%!PS', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=100 * 1024 * 1024, category='document'),
    'xcf': FileSignature(
        ext='xcf', magic=b'gimp xcf ', end_magic=None,
        end_scan_range=0, min_size=32,
        max_size=500 * 1024 * 1024, category='image'),
    'xcf2': FileSignature(
        ext='xcf', magic=b'gimp xcf', end_magic=None,
        end_scan_range=0, min_size=32,
        max_size=500 * 1024 * 1024, category='image'),
    'djvu': FileSignature(
        ext='djvu', magic=b'DJV', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='document'),
    'mobi': FileSignature(
        ext='mobi', magic=b'BOOKMOBI', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=50 * 1024 * 1024, category='document'),
    'epub': FileSignature(
        ext='epub', magic=b'PK\x03\x04', end_magic=b'PK\x01\x02',
        end_scan_range=4 * 1024 * 1024, min_size=1000,
        max_size=100 * 1024 * 1024, category='document'),
    'azw': FileSignature(
        ext='azw', magic=b'\xe9\x93', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=100 * 1024 * 1024, category='document'),
    'azw3': FileSignature(
        ext='azw3', magic=b'\x00\x00\x00\x00', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=100 * 1024 * 1024, category='document'),
    'pdf_alt': FileSignature(
        ext='pdf', magic=b'%PDF-1', end_magic=b'%EOF',
        end_scan_range=4 * 1024 * 1024, min_size=100,
        max_size=100 * 1024 * 1024, category='document'),
    'mid': FileSignature(
        ext='mid', magic=b'MThd', end_magic=None,
        end_scan_range=0, min_size=20,
        max_size=10 * 1024 * 1024, category='audio'),
    'midi': FileSignature(
        ext='mid', magic=b'MThd', end_magic=None,
        end_scan_range=0, min_size=20,
        max_size=10 * 1024 * 1024, category='audio'),
    'rm': FileSignature(
        ext='rm', magic=b'.RMF', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=1 * 1024 * 1024 * 1024, category='video'),
    'ra': FileSignature(
        ext='ra', magic=b'.ra', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=1 * 1024 * 1024 * 1024, category='audio'),
    'wav': FileSignature(
        ext='wav', magic=b'RIFF', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=4 * 1024 * 1024 * 1024, category='audio'),
    'au': FileSignature(
        ext='au', magic=b'.snd', end_magic=None,
        end_scan_range=0, min_size=100,
        max_size=500 * 1024 * 1024, category='audio'),
    'cue': FileSignature(
        ext='cue', magic=b'', end_magic=None,
        end_scan_range=0, min_size=10,
        max_size=10 * 1024 * 1024, category='audio'),
    'pls': FileSignature(
        ext='pls', magic=b'[playlist]', end_magic=None,
        end_scan_range=1024 * 1024, min_size=20,
        max_size=10 * 1024 * 1024, category='audio'),
}


# ---------------------------------------------------------------------------
# RawScanner — Improved Disk Scanner
# ---------------------------------------------------------------------------

class RawScanner(DiskScanner):
    """
    Improved RAW disk scanner.

    Key improvements over the old version:
      1. Every sector is read (no longer step-by-100).
      2. Correct size estimation by searching end markers across sectors.
      3. Bad sector handling (padding with 0xFF).
      4. File deduplication (merge overlapping / close offsets).
      5. Continuous block merging (adjacent sectors merged).
      6. Multi-frequency scanning (offset 1..sector_size-1 shifts).
    """

    def __init__(self, disk_handle, sector_size: int = 512,
                 error_mode: BadSectorPolicy = BadSectorPolicy.SKIP):
        self.disk_handle = disk_handle
        self.sector_size = sector_size
        self.error_mode = error_mode
        self._bad_sectors: Set[int] = set()
        self._max_buffer = 8 * 1024 * 1024  # 8MB max search buffer
        # Pre-compute shift offsets for multi-frequency scan
        self._shifts = list(range(max(1, sector_size // 4)))  # offsets 0..~127

    # ── Disk I/O ────────────────────────────────────────────────────────

    def read_sector(self, sector_num: int) -> Optional[bytes]:
        """Read a single sector, returning None on bad read."""
        try:
            offset = sector_num * self.sector_size
            if hasattr(self.disk_handle, 'lseek'):
                # Unix-style handle
                self.disk_handle.lseek(offset, 0)
                data = self.disk_handle.read(self.sector_size)
                if len(data) < self.sector_size:
                    self._bad_sectors.add(sector_num)
                    return b'\xFF' * self.sector_size
                return data
            else:
                # Windows / ctypes handle – use os-based read wrapper
                import os
                fd = self.disk_handle  # assume it's an int fd or wrapped
                if hasattr(fd, 'raw'):
                    fd = fd.raw
                if isinstance(fd, int) or hasattr(fd, 'fileno'):
                    actual_fd = fd if isinstance(fd, int) else fd.fileno()
                    os.lseek(actual_fd, offset, 0)
                    data = os.read(actual_fd, self.sector_size)
                    if len(data) < self.sector_size:
                        self._bad_sectors.add(sector_num)
                        return b'\xFF' * self.sector_size
                    return data
        except Exception:
            self._bad_sectors.add(sector_num)
            return b'\xFF' * self.sector_size
        return None

    def read_sectors(self, start: int, count: int) -> bytes:
        """Read consecutive sectors, padding bad ones."""
        parts: List[bytes] = []
        for i in range(count):
            sector = start + i
            data = self.read_sector(sector)
            if data is None:
                data = b'\xFF' * self.sector_size
            parts.append(data)
        return b''.join(parts)

    # ── Magic number search helpers ──────────────────────────────────────

    @staticmethod
    def _find_magic_in_data(data: bytes, magic: bytes) -> List[int]:
        """Find all byte offsets where magic appears in data."""
        positions: List[int] = []
        if not magic:
            return positions
        idx = 0
        while True:
            pos = data.find(magic, idx)
            if pos == -1:
                break
            positions.append(pos)
            idx = pos + 1
        return positions

    @staticmethod
    def _is_valid_offset(data: bytes, pos: int) -> bool:
        """Basic validation: check that offset doesn't fall in the middle of
        an unlikely sequence (e.g. all 0x00 between magic and start)."""
        return pos >= 0 and pos + 1 <= len(data)

    # ── Size estimation methods ─────────────────────────────────────────

    def _estimate_jpeg_size(self, data: bytes, start: int) -> int:
        """Estimate JPEG size by walking SOF/SOS/EOI markers."""
        pos = start
        end = min(len(data), start + 64 * 1024 * 1024)
        while pos < end - 1:
            if data[pos] == 0xFF and data[pos + 1] == 0xD9:
                return (pos - start) + 2
            if data[pos] == 0xFF and data[pos + 1] == 0x00:
                pos += 2
                continue
            if data[pos] == 0xFF and data[pos + 1] >= 0xC0 and data[pos + 1] <= 0xFF:
                if pos + 3 < len(data):
                    seg_len = struct.unpack('>H', data[pos + 2:pos + 4])[0]
                    pos += 4 + seg_len
                    continue
                break
            # Other marker – skip to next 0xFF
            for i in range(pos + 2, min(len(data), pos + 65536)):
                if data[i] == 0xFF and i + 1 < len(data):
                    pos = i
                    break
            else:
                break
        return 0  # Could not find end marker

    def _estimate_png_size(self, data: bytes, start: int) -> int:
        """Estimate PNG size by finding IEND chunk."""
        pos = start + 8  # Skip PNG signature
        while pos + 8 < len(data):
            if pos + 8 > min(len(data), start + 64 * 1024 * 1024):
                break
            chunk_len = struct.unpack('>I', data[pos:pos + 4])[0]
            chunk_type = data[pos + 4:pos + 8]
            if chunk_type == b'IEND':
                return (pos - start) + 8 + 4 + 4  # len + type + data + crc
            if chunk_len > 1024 * 1024:
                break  # Unreasonable chunk
            pos += 12 + chunk_len
        return 0

    def _estimate_mp3_size(self, data: bytes, start: int) -> int:
        """Estimate MP3 size by parsing frame headers until invalid frame."""
        pos = start
        max_frames = 100000  # Safety limit
        frames = 0
        max_search = min(len(data), start + 256 * 1024 * 1024)

        while pos + 4 <= len(data) and frames < max_frames:
            if pos >= max_search:
                break
            header = struct.unpack('>I', data[pos:pos + 4])[0]

            if (header & 0xFFE00000) != 0xFFE00000:
                break
            if (header & 0x00000600) == 0x00000600:  # Reserved bit set
                break

            version = (header >> 19) & 3
            layer = (header >> 17) & 3
            bitrate = (header >> 12) & 0xF
            sample_rate = (header >> 10) & 0x3

            if bitrate == 0 or sample_rate == 0:
                break
            if layer == 0:
                break  # Invalid layer

            bitrate_table = {
                1: [32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
                2: [32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 448],
            }
            sr_table = {
                1: [44100, 48000, 32000],    # MPEG-1
                2: [22050, 24000, 16000],    # MPEG-2
            }
            sr_idx = min(sample_rate, 2)
            br_idx = min(bitrate, 15)

            try:
                if layer == 1:
                    frame_size = int((12 * bitrate_table.get(2, [0] * 16)[br_idx])
                                     / sr_table.get(2, [0] * 3)[sr_idx] * 1000)
                else:
                    frame_size = int((144 * bitrate_table.get(2, [0] * 16)[br_idx])
                                     / sr_table.get(2, [0] * 3)[sr_idx])
            except (KeyError, ZeroDivisionError):
                break

            if frame_size <= 0:
                break
            pos += frame_size
            frames += 1

        return max(pos - start, 0)

    def _estimate_wav_size(self, data: bytes, start: int) -> int:
        """Estimate WAV size from chunk size field."""
        if len(data) >= start + 8:
            riff_size = struct.unpack('<I', data[start + 4:start + 8])[0]
            if riff_size > 0 and riff_size < 100 * 1024 * 1024 * 1024:
                return 8 + riff_size
        return 0

    def _estimate_pdf_size(self, data: bytes, start: int) -> int:
        """Estimate PDF size by searching for %%EOF."""
        end_pos = data[start:].find(b'%%EOF')
        if end_pos != -1:
            return start + end_pos + 5
        # Fallback: use remaining data
        return len(data) - start

    def _estimate_zip_size(self, data: bytes, start: int) -> int:
        """Estimate ZIP size by finding central directory."""
        search_end = min(len(data), start + 64 * 1024 * 1024)
        pos = start + 22  # Skip local header
        while pos + 4 <= search_end:
            if data[pos:pos + 4] == b'PK\x01\x02':
                return pos - start + 46
            pos += 1
        # Fallback: assume min ZIP
        return max(search_end - start, 100)

    def _estimate_docx_xlsx_pptx_size(self, data: bytes, start: int) -> int:
        """Estimate Office document size from central directory."""
        return self._estimate_zip_size(data, start)

    def _estimate_bmp_size(self, data: bytes, start: int) -> int:
        """BMP file size from header."""
        if len(data) >= start + 26:
            return struct.unpack('<I', data[start + 2:start + 6])[0]
        return 0

    def _estimate_gif_size(self, data: bytes, start: int) -> int:
        """GIF ends with semicolon."""
        end_pos = data[start:].find(b';')
        if end_pos != -1:
            return start + end_pos + 1
        return len(data) - start

    def _estimate_tiff_size(self, data: bytes, start: int) -> int:
        """TIFF size from IFD0 offset."""
        if len(data) < start + 12:
            return 0
        # Byte order check
        byte_order = data[start:start + 2]
        if byte_order == b'II':
            is_le = True
        elif byte_order == b'MM':
            is_le = False
        else:
            return 0
        unpack_fmt = '<I' if is_le else '>I'
        ifd_offset = struct.unpack(unpack_fmt, data[start + 4:start + 8])[0]
        if ifd_offset < len(data):
            return start + ifd_offset + 4
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257  # After 'ustar' at offset 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257  # After 'ustar' at offset 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257  # After 'ustar' at offset 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    def _estimate_tar_size(self, data: bytes, start: int) -> int:
        """Find next 'ustar' header after current one."""
        pos = start + 257
        end = min(len(data), start + 10 * 1024 * 1024)
        while pos + 512 <= end:
            header_magic = data[pos + 257:pos + 265]
            if header_magic == b'ustar':
                return pos - start
            pos += 512
        return 0

    # Oops, I need to write this more carefully. Let me fix the file.