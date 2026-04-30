"""
AI File Repair Module
支持任意 OpenAI 兼容 API 的智能修復工具

目錄結構：
- Program Files: 程序安裝位置
- AppData: 用戶配置和日誌
- Temp: 暫存文件 (修復預覽、備份、API緩存)
- Output: 修復後的文件 (用戶指定)
"""

import requests
import yaml
import base64
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time
import tempfile


# ============================================
# 目錄結構定義
# ============================================

class DirectoryStructure:
    """
    目錄結構管理
    將安裝位置、配置、暫存、輸出完全分離
    """
    
    def __init__(self):
        # 程序安裝位置
        self.program_dir = Path(__file__).parent.parent
        self.program_files = self.program_dir / "dist"
        
        # 用戶配置位置 (AppData)
        self.appdata_dir = Path.home() / "AppData" / "Local" / "AI File Repair"
        self.config_dir = self.appdata_dir / "config"
        self.logs_dir = self.appdata_dir / "logs"
        
        # 暫存位置 (Temp)
        self.temp_dir = Path(tempfile.gettempdir()) / "AI File Repair"
        self.preview_dir = self.temp_dir / "preview"
        self.backup_dir = self.temp_dir / "backup"
        self.api_cache_dir = self.temp_dir / "api_cache"
        
        # 輸出位置 (默認)
        self.output_dir = Path.home() / "Documents" / "AI Repair Output"
        
        # 初始化目錄
        self._init_directories()
    
    def _init_directories(self):
        """初始化所有目錄"""
        dirs = [
            self.program_files,
            self.config_dir,
            self.logs_dir,
            self.temp_dir,
            self.preview_dir,
            self.backup_dir,
            self.api_cache_dir,
            self.output_dir
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def get_temp_file(self, prefix="temp_", suffix=".tmp"):
        """獲取臨時文件路徑"""
        return tempfile.NamedTemporaryFile(
            prefix=prefix,
            suffix=suffix,
            dir=self.temp_dir,
            delete=False
        ).name
    
    def cleanup_temp(self, max_age_days=7):
        """清理過期的暫存文件"""
        import glob
        
        patterns = [
            (self.preview_dir, "*.py_fixed_preview*"),
            (self.backup_dir, "*.bak"),
            (self.api_cache_dir, "*.json"),
        ]
        
        for dir_path, pattern in patterns:
            for f in glob.glob(str(dir_path / pattern)):
                try:
                    if (datetime.now() - datetime.fromtimestamp(os.path.getmtime(f))).days > max_age_days:
                        os.remove(f)
                        print(f"清理過期文件: {f}")
                except:
                    pass
    
    def cleanup_all_temp(self):
        """清理所有暫存文件"""
        dirs = [self.preview_dir, self.backup_dir, self.api_cache_dir]
        
        for d in dirs:
            for f in d.glob("*"):
                try:
                    f.unlink()
                except:
                    pass


# 初始化目錄結構
dirs = DirectoryStructure()


# ============================================
# 數據類定義
# ============================================

@dataclass
class RepairResult:
    """修復結果數據類"""
    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    repair_details: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    repair_type: str = ""
    original_file: str = ""
    repaired_file: str = ""
    repair_time: float = 0.0
    stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class FileTypeInfo:
    """文件類型信息"""
    name: str
    magic_bytes: List[bytes]
    extensions: List[str]
    repair_methods: List[str]
    ai_model: str = "gpt-4o-mini"


class FileClassifier:
    """文件類型分類器 - 使用 Magic Byte + 副檔名雙重驗證"""
    
    # 文件類型定義
    FILE_TYPES = {
        "code_python": FileTypeInfo(
            name="Python",
            magic_bytes=[b"#!/usr/bin/env python", b"#!/usr/bin/python", b"# -*- coding:"],
            extensions=[".py"],
            repair_methods=["syntax", "logic", "imports"],
            ai_model="gpt-4o-mini"
        ),
        "code_cpp": FileTypeInfo(
            name="C++",
            magic_bytes=[b"#include", b"using namespace", b"int main"],
            extensions=[".cpp", ".h", ".hpp", ".cc"],
            repair_methods=["syntax", "link", "compilation"],
            ai_model="gpt-4o-mini"
        ),
        "image_jpeg": FileTypeInfo(
            name="JPEG",
            magic_bytes=[b"\xFF\xD8\xFF"],
            extensions=[".jpg", ".jpeg"],
            repair_methods=["header", "entropy", "reconstruction"],
            ai_model="gpt-4o"
        ),
        "image_png": FileTypeInfo(
            name="PNG",
            magic_bytes=[b"\x89PNG\r\n\x1A\n"],
            extensions=[".png"],
            repair_methods=["header", "chunk", "compression"],
            ai_model="gpt-4o"
        ),
        "image_gif": FileTypeInfo(
            name="GIF",
            magic_bytes=[b"GIF87a", b"GIF89a"],
            extensions=[".gif"],
            repair_methods=["header", "animation", "palette"],
            ai_model="gpt-4o"
        ),
        "document_pdf": FileTypeInfo(
            name="PDF",
            magic_bytes=[b"%PDF-"],
            extensions=[".pdf"],
            repair_methods=["structure", "xref", "streams"],
            ai_model="gpt-4o"
        ),
        "document_word": FileTypeInfo(
            name="Word",
            magic_bytes=[b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"],
            extensions=[".doc", ".docx"],
            repair_methods=["structure", "ole", "xml"],
            ai_model="gpt-4o"
        ),
        "archive_zip": FileTypeInfo(
            name="ZIP",
            magic_bytes=[b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
            extensions=[".zip", ".jar", ".apk"],
            repair_methods=["header", "central_directory", "compression"],
            ai_model="gpt-4o-mini"
        ),
        "audio_wav": FileTypeInfo(
            name="WAV",
            magic_bytes=[b"RIFF", b"WAVE"],
            extensions=[".wav"],
            repair_methods=["header", "sample", "format"],
            ai_model="gpt-4o"
        ),
        "audio_mp3": FileTypeInfo(
            name="MP3",
            magic_bytes=[b"\xFF\xFB", b"\xFF\xF3", b"\xFF\xF2"],
            extensions=[".mp3"],
            repair_methods=["frame", "metadata", "stream"],
            ai_model="gpt-4o"
        ),
        "audio_flac": FileTypeInfo(
            name="FLAC",
            magic_bytes=[b"fLaC"],
            extensions=[".flac"],
            repair_methods=["header", "frame", "metadata"],
            ai_model="gpt-4o"
        ),
        "text_plain": FileTypeInfo(
            name="Text",
            magic_bytes=[],
            extensions=[".txt", ".md", ".log", ".csv", ".json", ".xml", ".yaml"],
            repair_methods=["encoding", "format", "content"],
            ai_model="gpt-4o-mini"
        ),
        "unknown": FileTypeInfo(
            name="Unknown",
            magic_bytes=[],
            extensions=[],
            repair_methods=["analysis"],
            ai_model="gpt-4o"
        )
    }
    
    def __init__(self):
        self.classifier_cache: Dict[str, FileTypeInfo] = {}
    
    def classify_file(self, file_path: str) -> Tuple[FileTypeInfo, Dict[str, Any]]:
        """分類文件類型"""
        path = Path(file_path)
        extension = path.suffix.lower()
        filename = path.name
        
        details = {
            "extension": extension,
            "filename": filename,
            "detected_type": None,
            "confidence": 0.0,
            "magic_bytes_match": False,
            "extension_match": False,
            "suggestions": []
        }
        
        try:
            with open(file_path, 'rb') as f:
                file_header = f.read(1024)
        except Exception as e:
            return self.FILE_TYPES["unknown"], {**details, "error": str(e)}
        
        for type_name, info in self.FILE_TYPES.items():
            if info.magic_bytes:
                for mb in info.magic_bytes:
                    if mb in file_header:
                        details["magic_bytes_match"] = True
                        details["detected_type"] = type_name
                        details["confidence"] = 0.95
                        break
            
            if extension in info.extensions:
                details["extension_match"] = True
                if details["detected_type"] == type_name:
                    details["confidence"] = 1.0
                elif details["confidence"] < 0.7:
                    details["confidence"] = 0.7
        
        if details["confidence"] < 0.7:
            details["suggestions"] = self._suggest_from_filename(filename)
        
        if details["detected_type"]:
            return self.FILE_TYPES[details["detected_type"]], details
        elif details["suggestions"]:
            return self.FILE_TYPES[details["suggestions"][0]], details
        else:
            return self.FILE_TYPES["unknown"], details
    
    def _suggest_from_filename(self, filename: str) -> List[str]:
        """從文件名推測類型"""
        suggestions = []
        lower_name = filename.lower()
        
        if lower_name.endswith(('.py', '.pyw')):
            suggestions.append("code_python")
        elif lower_name.endswith(('.cpp', '.h', '.hpp')):
            suggestions.append("code_cpp")
        elif lower_name.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            suggestions.append("image_jpeg")
        elif lower_name.endswith(('.pdf')):
            suggestions.append("document_pdf")
        elif lower_name.endswith(('.mp3', '.wav', '.flac')):
            suggestions.append("audio_mp3")
        elif lower_name.endswith(('.zip', '.rar')):
            suggestions.append("archive_zip")
        elif lower_name.endswith(('.txt', '.md')):
            suggestions.append("text_plain")
            
        return suggestions


class OpenAIRepairClient:
    """
    OpenAI API 兼容修復客戶端
    支持任意 OpenAI API 兼容端點
    """
    
    def __init__(self, config_path: str = "~/.hermes/config/ai-repair-config.yaml"):
        self.config = self._load_config(config_path)
        self.endpoint = self.config['openai_api']['endpoint']
        self.api_key = self.config['openai_api'].get('api_key', '')
        self.model = self.config['openai_api']['model']
        self.temperature = self.config['openai_api'].get('temperature', 0.3)
        self.max_tokens = self.config['openai_api'].get('max_tokens', 8000)
        self.timeout = self.config['openai_api'].get('timeout', 30)
        self.max_retries = self.config['openai_api'].get('max_retries', 3)
        
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
        
        self.classifier = FileClassifier()
        
        self.stats = {
            "total_files": 0,
            "successful_repairs": 0,
            "failed_repairs": 0,
            "repair_types": {},
            "total_time": 0.0
        }
    
    def _load_config(self, path: str) -> Dict:
        with open(Path(path).expanduser(), 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _create_payload(self, repair_type: str, file_info: FileTypeInfo, 
                        content: str, error_description: Optional[str] = None,
                        image_data: Optional[str] = None) -> Dict[str, Any]:
        
        system_prompt = self._get_system_prompt(repair_type, file_info)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        content_parts = []
        if error_description:
            content_parts.append({"type": "text", "text": f"錯誤描述：{error_description}"})
        if image_data:
            content_parts.append({"type": "image_url", "image_url": {"url": image_data}})
        
        max_content_length = 5000
        truncated_content = content[:max_content_length]
        content_parts.append({
            "type": "text",
            "text": f"請修復以下{file_info.name}文件：\n```{file_info.extensions[0].replace('.', '')}\n{truncated_content}\n```"
        })
        
        if len(content_parts) > 0:
            messages.append({"role": "user", "content": content_parts})
        
        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
    
    def _get_system_prompt(self, repair_type: str, file_info: FileTypeInfo) -> str:
        prompts = {
            "code": f"""你是專業的{file_info.name}程式碼修復工程師。

修復要求：
1. 分析代碼錯誤並提供修復方案
2. 保持原有功能和結構
3. 修復語法錯誤、邏輯錯誤、導入錯誤
4. 輸出完整的修復後代碼

修復類型：{repair_type}""",
            
            "image": f"""你是專業的{file_info.name}圖像修復工程師。

修復要求：
1. 分析圖像損壞程度和類型
2. 使用 AI 技術修復損壞區域
3. 保持原始色彩和風格
4. 輸出修復後的圖像數據

修復類型：{repair_type}""",
            
            "audio": f"""你是專業的{file_info.name}音頻修復工程師。

修復要求：
1. 分析音頻損壞位置和程度
2. 使用 SINC 插值修復缺失樣本
3. 保持原始音頻品質和頻率
4. 輸出修復後的音頻數據

修復類型：{repair_type}""",
            
            "document": f"""你是專業的{file_info.name}文檔修復工程師。

修復要求：
1. 分析文檔結構損壞
2. 修復文件頭、元數據、內容
3. 保持原有格式和結構
4. 輸出修復後的文檔

修復類型：{repair_type}"""
        }
        return prompts.get(repair_type, prompts["code"])
    
    def repair_code(self, file_path: str, error_description: Optional[str] = None,
                    language: Optional[str] = None) -> RepairResult:
        start_time = time.time()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return RepairResult(success=False, error_message=f"讀取文件失敗: {str(e)}")
        
        file_info, details = self.classifier.classify_file(file_path)
        
        if language is None:
            language = self._detect_language(file_info, content)
        
        context = f"語言: {language}\n文件類型: {file_info.name}\n"
        if error_description:
            context += f"錯誤描述: {error_description}\n"
        
        payload = self._create_payload("code", file_info, content, error_description, None)
        
        result = self._call_api(payload, "code")
        
        self.stats["total_files"] += 1
        if result.success:
            self.stats["successful_repairs"] += 1
        else:
            self.stats["failed_repairs"] += 1
        
        self.stats["repair_types"]["code"] = self.stats["repair_types"].get("code", 0) + 1
        self.stats["total_time"] += time.time() - start_time
        
        return result
    
    def repair_image(self, file_path: str, damage_type: Optional[str] = None) -> RepairResult:
        start_time = time.time()
        
        try:
            with open(file_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
        except Exception as e:
            return RepairResult(success=False, error_message=f"讀取文件失敗: {str(e)}")
        
        file_info, details = self.classifier.classify_file(file_path)
        
        image_url = f"data:image/jpeg;base64,{image_data}"
        
        payload = self._create_payload("image", file_info, "", damage_type, image_url)
        
        result = self._call_api(payload, "image")
        
        self.stats["total_files"] += 1
        if result.success:
            self.stats["successful_repairs"] += 1
        else:
            self.stats["failed_repairs"] += 1
        
        self.stats["repair_types"]["image"] = self.stats["repair_types"].get("image", 0) + 1
        self.stats["total_time"] += time.time() - start_time
        
        return result
    
    def repair_audio(self, file_path: str, damage_type: Optional[str] = None) -> RepairResult:
        start_time = time.time()
        
        try:
            with open(file_path, 'rb') as f:
                audio_data = base64.b64encode(f.read()).decode()
        except Exception as e:
            return RepairResult(success=False, error_message=f"讀取文件失敗: {str(e)}")
        
        file_info, details = self.classifier.classify_file(file_path)
        
        payload = self._create_payload("audio", file_info, "", damage_type, None)
        
        payload["messages"][1]["content"].append({
            "type": "input_audio",
            "input_audio": {"data": audio_data, "format": "wav"}
        })
        
        result = self._call_api(payload, "audio")
        
        self.stats["total_files"] += 1
        if result.success:
            self.stats["successful_repairs"] += 1
        else:
            self.stats["failed_repairs"] += 1
        
        self.stats["repair_types"]["audio"] = self.stats["repair_types"].get("audio", 0) + 1
        self.stats["total_time"] += time.time() - start_time
        
        return result
    
    def repair_document(self, file_path: str, damage_type: Optional[str] = None) -> RepairResult:
        start_time = time.time()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return RepairResult(success=False, error_message=f"讀取文件失敗: {str(e)}")
        
        file_info, details = self.classifier.classify_file(file_path)
        
        payload = self._create_payload("document", file_info, content, damage_type, None)
        
        result = self._call_api(payload, "document")
        
        self.stats["total_files"] += 1
        if result.success:
            self.stats["successful_repairs"] += 1
        else:
            self.stats["failed_repairs"] += 1
        
        self.stats["repair_types"]["document"] = self.stats["repair_types"].get("document", 0) + 1
        self.stats["total_time"] += time.time() - start_time
        
        return result
    
    def _call_api(self, payload: Dict[str, Any], response_type: str) -> RepairResult:
        url = f"{self.endpoint.rstrip('/')}/chat/completions"
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout,
                    verify=self.config['openai_api'].get('verify_ssl', True)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if "choices" in result and len(result["choices"]) > 0:
                        message = result["choices"][0]["message"]["content"]
                        
                        if response_type in ["code", "document"]:
                            extracted_content = self._extract_code(message)
                            return RepairResult(
                                success=True,
                                output_path=None,
                                repair_details={
                                    "content": message,
                                    "extracted_content": extracted_content,
                                    "model": self.model,
                                    "original_tokens": payload["max_tokens"]
                                },
                                confidence=0.95,
                                repair_type=response_type
                            )
                        elif response_type in ["image", "audio"]:
                            return RepairResult(
                                success=True,
                                output_path=None,
                                repair_details={
                                    "content": message,
                                    "model": self.model,
                                    "original_tokens": payload["max_tokens"]
                                },
                                confidence=0.95,
                                repair_type=response_type
                            )
                    
                    last_error = "API 響應格式不正確"
                    
                elif response.status_code == 401:
                    last_error = "API Key 無效或過期。請檢查 API Key 是否正確。"
                    break
                    
                elif response.status_code == 403:
                    last_error = "API Key 被拒絕。可能沒有權限或配額不足。"
                    break
                    
                elif response.status_code == 404:
                    last_error = f"API 端點不存在。請檢查 URL 是否正確。{url}"
                    break
                    
                elif response.status_code == 500:
                    last_error = "API 服務器內部錯誤。請稍後重試。"
                    
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    
            except requests.RequestException as e:
                last_error = f"網絡錯誤: {str(e)}"
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
        
        return RepairResult(success=False, error_message=last_error)
    
    def _extract_code(self, content: str) -> str:
        patterns = [
            r'```(?:python|cpp|c\+\+|java|javascript|typescript|go|rust|c|py)\n([\s\S]*?)\n```',
            r'```([\s\S]*?)\n```',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        
        return content.strip()
    
    def _detect_language(self, file_info: FileTypeInfo, content: str) -> str:
        extensions = file_info.extensions
        
        if '.py' in extensions:
            return "python"
        elif '.cpp' in extensions or '.hpp' in extensions:
            return "cpp"
        elif '.c' in extensions:
            return "c"
        elif '.java' in extensions:
            return "java"
        elif '.js' in extensions:
            return "javascript"
        elif '.ts' in extensions:
            return "typescript"
        elif '.go' in extensions:
            return "go"
        elif '.rs' in extensions:
            return "rust"
        elif '.rb' in extensions:
            return "ruby"
        elif '.php' in extensions:
            return "php"
        else:
            return "unknown"
    
    def get_stats(self) -> Dict[str, Any]:
        total = self.stats["total_files"]
        success = self.stats["successful_repairs"]
        fail = self.stats["failed_repairs"]
        
        return {
            "total_files": total,
            "successful_repairs": success,
            "failed_repairs": fail,
            "success_rate": success / total * 100 if total > 0 else 0,
            "repair_types": self.stats["repair_types"],
            "total_time_seconds": self.stats["total_time"],
            "avg_time_per_file": self.stats["total_time"] / total if total > 0 else 0
        }


class AIRepair:
    """主修復類 - 統一接口"""
    
    def __init__(self, config_path: str = "~/.hermes/config/ai-repair-config.yaml"):
        self.client = OpenAIRepairClient(config_path)
        self.config_path = config_path
    
    def repair(self, file_path: str, file_type: Optional[str] = None,
               repair_type: Optional[str] = None,
               error_description: Optional[str] = None,
               damage_type: Optional[str] = None) -> RepairResult:
        
        if file_type is None:
            file_info, details = self.client.classifier.classify_file(file_path)
            file_type = file_info.name.lower()
        
        if repair_type is None:
            repair_type = self._map_file_to_repair(file_type)
        
        if repair_type == "code":
            return self.client.repair_code(file_path, error_description, file_type)
        elif repair_type == "image":
            return self.client.repair_image(file_path, damage_type)
        elif repair_type == "audio":
            return self.client.repair_audio(file_path, damage_type)
        elif repair_type == "document":
            return self.client.repair_document(file_path, damage_type)
        else:
            return RepairResult(success=False, error_message=f"不支持的修復類型: {repair_type}")
    
    def _map_file_to_repair(self, file_type: str) -> str:
        mapping = {
            "python": "code", "py": "code",
            "cpp": "code", "c++": "code",
            "java": "code",
            "javascript": "code", "typescript": "code",
            "go": "code", "rust": "code",
            "ruby": "code", "php": "code",
            "image": "image", "jpeg": "image",
            "jpg": "image", "png": "image",
            "gif": "image", "webp": "image",
            "bmp": "image",
            "audio": "audio", "wav": "audio",
            "mp3": "audio", "flac": "audio",
            "ogg": "audio", "m4a": "audio",
            "document": "document", "pdf": "document",
            "docx": "document", "doc": "document",
            "txt": "document", "md": "document",
            "json": "document", "xml": "document",
            "yaml": "document", "csv": "document"
        }
        return mapping.get(file_type.lower(), "document")
    
    def batch_repair(self, file_paths: List[str], repair_type: Optional[str] = None,
                     error_descriptions: Optional[List[str]] = None) -> List[RepairResult]:
        results = []
        for i, file_path in enumerate(file_paths):
            error_desc = error_descriptions[i] if error_descriptions and i < len(error_descriptions) else None
            result = self.repair(file_path, repair_type=repair_type, error_description=error_desc)
            results.append(result)
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        return self.client.get_stats()


if __name__ == "__main__":
    repairer = AIRepair()
    
    print("修復代碼文件...")
    result = repairer.repair("example.py", file_type="python", 
                            error_description="語法錯誤：缺少冒號")
    print(f"修復結果: {result.success}")
    if result.success:
        print(f"修復內容: {result.repair_details.get('content')}")
    else:
        print(f"錯誤: {result.error_message}")
    
    print("\n修復統計:")
    stats = repairer.get_stats()
    print(f"  總文件: {stats['total_files']}")
    print(f"  成功: {stats['successful_repairs']}")
    print(f"  失敗: {stats['failed_repairs']}")
    print(f"  成功率: {stats['success_rate']:.1f}%")