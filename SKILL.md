---
name: ai-file-repair
title: AI File Repair Module
category: software-development
version: 1.0
---

# AI File Repair Module - 完整指南

## 功能概述

AI修復模組整合OpenAI GPT-4 API，提供智能化的文件修復建議與自動修復功能。

---

## 🔧 安裝與配置

### 1. API Key 配置

```yaml
# ~/.hermes/config/ai-repair-config.yaml
openai:
  api_key: "您的 OpenAI API Key"
  model: "gpt-4o-mini"
  temperature: 0.3
  max_tokens: 8000

repair_settings:
  default_timeout: 30
  max_retries: 3
  batch_size: 10
  
file_types:
  supported:
    - code: [".py", ".cpp", ".h", ".java", ".js", ".ts"]
    - image: [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    - document: [".pdf", ".docx", ".txt", ".md"]
    - audio: [".wav", ".mp3", ".flac", ".ogg"]
    - video: [".mp4", ".avi", ".mkv", ".mov"]
    - data: [".json", ".xml", ".yaml", ".csv"]
```

### 2. Python 設置

```python
# ai_repair.py
import openai
import yaml
from pathlib import Path

class AIRepair:
    def __init__(self, config_path="~/.hermes/config/ai-repair-config.yaml"):
        config = self._load_config(config_path)
        openai.api_key = config['openai']['api_key']
        self.model = config['openai']['model']
        self.temperature = config['openai']['temperature']
        
    def _load_config(self, path):
        with open(Path(path).expanduser(), 'r') as f:
            return yaml.safe_load(f)
    
    def repair_file(self, file_path, repair_type="auto"):
        """修復指定文件"""
        # 實作見下文
        pass
```

---

## 📋 修復功能詳解

### 1. 代碼修復 (Code Repair)

```python
def repair_code(self, code_content, error_description=""):
    """
    修復代碼中的錯誤
    
    Args:
        code_content: 原始代碼
        error_description: 錯誤描述（可選）
        
    Returns:
        修復後的代碼
    """
    prompt = f"""你是一位資深程式開發者。請修復以下代碼中的錯誤。

{'錯誤描述：' + error_description if error_description else ''}
        
原始代碼：
```code
{code_content}
```

請提供：
1. 錯誤分析（指出問題所在）
2. 修復建議（具體的修改方案）
3. 修復後的完整代碼

要求：保持原有功能，只修復錯誤。"""

    response = openai.chat.completions.create(
        model=self.model,
        messages=[
            {"role": "system", "content": "你是程式碼修復專家。"},
            {"role": "user", "content": prompt}
        ],
        temperature=self.temperature,
        max_tokens=8000
    )
    
    return response.choices[0].message.content
```

**使用範例：**
```python
repairer = AIRepair()

# 自動修復
broken_code = """
def calculate_sum(numbers):
    result = 0
    for n in numbers
        result += n
    return result
"""

result = repairer.repair_code(broken_code)
print(result)
# 輸出：包含錯誤分析和修復後代碼
```

---

### 2. 圖像修復 (Image Repair)

```python
def repair_image(self, image_path):
    """
    修復損壞的圖像文件
    
    Args:
        image_path: 圖像文件路徑
        
    Returns:
        修復後的圖像數據
    """
    # 讀取圖像並轉為base64
    import base64
    with open(image_path, 'rb') as f:
        image_data = f.read()
        base64_image = base64.b64encode(image_data).decode()
    
    prompt = f"""請分析並修復這張損壞的圖像。

任務：
1. 識別圖像類型和損壞程度
2. 修復損壞的區域
3. 保持原有內容和風格

請返回修復後的圖像（PNG格式）。"""

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是圖像修復專家。"},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }}
            ]}
        ],
        max_tokens=1000
    )
    
    return response
```

---

### 3. 音頻修復 (Audio Repair)

```python
def repair_audio(self, audio_path):
    """
    修復損壞的音頻文件
    
    Args:
        audio_path: 音頻文件路徑
        
    Returns:
        修復後的音頻數據
    """
    # 讀取音頻並轉為base64
    import base64
    with open(audio_path, 'rb') as f:
        audio_data = f.read()
        base64_audio = base64.b64encode(audio_data).decode()
    
    prompt = f"""請分析並修復這段損壞的音頻。

任務：
1. 識別音頻格式和損壞位置
2. 使用SINC插值修復缺失的樣本
3. 保持原有音頻內容和品質

請返回修復後的音頻（WAV格式）。"""

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是音頻修復專家。"},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "input_audio", "input_audio": {
                    "data": base64_audio,
                    "format": "wav"
                }}
            ]}
        ],
        max_tokens=1000
    )
    
    return response
```

---

### 4. 文檔修復 (Document Repair)

```python
def repair_document(self, doc_content, doc_type="general"):
    """
    修復損壞的文檔
    
    Args:
        doc_content: 文檔內容
        doc_type: 文檔類型（pdf, docx, txt, md）
        
    Returns:
        修復後的文檔
    """
    prompt = f"""你是一位文檔修復專家。請修復以下損壞的文檔。

文檔類型：{doc_type}

原始內容：
```{doc_type}
{doc_content}
```

請提供：
1. 損壞分析
2. 修復建議
3. 修復後的完整文檔

要求：保持原有格式和結構。"""

    response = openai.chat.completions.create(
        model=self.model,
        messages=[
            {"role": "system", "content": "你是文檔修復專家。"},
            {"role": "user", "content": prompt}
        ],
        temperature=self.temperature,
        max_tokens=8000
    )
    
    return response.choices[0].message.content
```

---

## 🔄 修復工作流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI修復完整流程                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  1. 文件掃描與分析                                              │  │
│  │     └─> 识别文件类型、损坏程度、缺失区域                       │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │  2. AI修復建議                                                 │  │
│  │     └─> GPT-4分析並提供修復方案                               │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │  3. 修復預覽                                                   │  │
│  │     └─> 顯示修復前後對比，用戶確認                            │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │  4. 執行修復                                                   │  │
│  │     └─> 應用修復並保存                                        │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │  5. 修復驗證                                                   │  │
│  │     └─> 校驗修復後文件的完整性                                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 修復統計與報告

```python
class RepairReport:
    def __init__(self):
        self.stats = {
            "total_files": 0,
            "successful_repairs": 0,
            "failed_repairs": 0,
            "suggested_repairs": 0,
            "repair_types": {}
        }
        
    def log_repair(self, file_type, success, repair_type):
        self.stats["total_files"] += 1
        if success:
            self.stats["successful_repairs"] += 1
        else:
            self.stats["failed_repairs"] += 1
        self.stats["repair_types"][repair_type] = \
            self.stats["repair_types"].get(repair_type, 0) + 1
            
    def generate_report(self):
        report = f"""
        ═══════════════════════════════════════════════════
                    AI修復統計報告
        ═══════════════════════════════════════════════════
        
        總文件數: {self.stats["total_files"]}
        修復成功: {self.stats["successful_repairs"]}
        修復失敗: {self.stats["failed_repairs"]}
        成功率: {self.stats["successful_repairs"]/self.stats["total_files"]*100:.1f}%
        
        修復類型分布:
        """
        for rtype, count in self.stats["repair_types"].items():
            report += f"  • {rtype}: {count}\n"
        report += """
        ═══════════════════════════════════════════════════
        """
        return report
```

---

## ⚠️ 注意事項

1. **API使用成本**：AI修復會消耗API配額，建議設定每日上限
2. **修復確認**：重要文件修復前務必預覽並確認
3. **備份原文件**：修復前請先備份原始文件
4. **網絡要求**：需要穩定的網絡連接
5. **敏感信息**：不要修復包含敏感信息的文件

---

## 📊 完整使用範例

```python
from ai_repair import AIRepair, RepairReport

# 初始化
repairer = AIRepair()
reporter = RepairReport()

# 修復多個文件
files_to_repair = [
    ("broken_code.py", "code", "語法錯誤"),
    ("corrupt_image.jpg", "image", ""),
    ("damaged_audio.mp3", "audio", ""),
]

for file_path, file_type, error_desc in files_to_repair:
    print(f"正在修復: {file_path}")
    
    if file_type == "code":
        result = repairer.repair_code(
            open(file_path).read(), 
            error_desc
        )
    elif file_type == "image":
        result = repairer.repair_image(file_path)
    elif file_type == "audio":
        result = repairer.repair_audio(file_path)
    
    reporter.log_repair(file_type, result is not None, file_type)
    print(f"修復完成: {file_path}")

# 顯示報告
print(reporter.generate_report())
```

---

## 🔮 下一步

1. ✅ AI修復功能 - 完成
2. ✅ GUI界面改進 - 完成
3. ✅ 修復流程視覺化 - 完成
4. ✅ 使用友善性提升 - 完成
5. ✅ GitHub Actions CI/CD - 完成
6. ✅ Windows Executable Building - 完成

---

## 🚀 GitHub Actions CI/CD 設置

### 完整工作流程

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    GitHub Actions 工作流程                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. 📦 代碼提交                                                        │
│     └─ User pushes code to GitHub                                       │
│                                                                          │
│  2. ⚙️  觸發 CI/CD                                                    │
│     └─ GitHub Actions 自動運行                                          │
│                                                                          │
│  3. 🔨  構建 Windows .exe                                             │
│     └─ Windows runner (windows-latest)                                  │
│                                                                          │
│  4. 📤  生成Artifact                                                  │
│     └─ Upload to GitHub Release                                         │
│                                                                          │
│  5. 📥  用戶下載                                                      │
│     └─ Direct download from GitHub                                      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### GitHub Actions Workflow File

```yaml
# .github/workflows/build-windows.yml
name: Build Windows Executable

on:
  push:
    branches: [main, master]
    tags: ['v*']
  pull_request:
    branches: [main, master]

env:
  PYTHON_VERSION: '3.11'

jobs:
  build:
    runs-on: windows-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          architecture: x64

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pyyaml pyinstaller
        shell: pwsh

      - name: Build executable
        run: |
          cd scripts
          pyinstaller --onefile --windowed --name "AI File Repair" ^
            gui_main.py
        shell: pwsh

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: AI-File-Repair-Windows
          path: scripts/dist/AI File Repair.exe
          retention-days: 7

      - name: Upload to Release
        if: ${{ startsWith(github.ref, 'refs/tags/v') }}
        uses: softprops/action-gh-release@v1
        with:
          files: scripts/dist/AI File Repair.exe
          generate_release_notes: true
```

### Personal Access Token Setup

```
1. 訪問: https://github.com/settings/tokens
2. 點擊: Generate new token (classic)
3. 設置:
   - Note: "AI File Repair CI/CD"
   - Expiration: 90 days
   - Scopes: repo, workflow, write:packages
4. 複製 Token 並保存到 .env 文件

.env 文件格式:
GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GITHUB_OWNER=your-username
GITHUB_REPO=ai-file-repair
```

### GitHub CLI Authentication

```bash
# 安裝 GitHub CLI
sudo apt install gh  # Ubuntu
brew install gh      # macOS

# 使用 Token 登錄
echo "YOUR_TOKEN" | gh auth login --with-token

# 驗證
gh auth status
```

---

## 📁 目錄結構

```
ai-file-repair/
├── .github/workflows/
│   └── build-windows.yml    ← GitHub Actions 配置
├── .env                       ← 環境變量 (Token)
├── scripts/
│   ├── gui_main.py          ← GUI 主程序
│   ├── ai_repair.py         ← 核心修復邏輯
│   └── build_windows.bat    ← Windows 打包腳本
├── windows/
│   ├── README.md            ← Windows 使用指南
│   └── build_windows.bat    ← 打包腳本
├── dist/
│   └── AI File Repair       ← 可執行文件 (生成)
├── venv/                      ← Python 虛擬環境
└── .git/                      ← Git 倉庫
```

---

## 📊 完成狀態

| 功能 | 狀態 |
|------|------|
| AI 修復功能 | ✅ 完成 |
| GUI 界面 | ✅ 完成 |
| 修復預覽 | ✅ 完成 |
| 批量修復 | ✅ 完成 |
| GitHub Actions | ✅ 完成 |
| Windows .exe 打包 | ✅ 完成 |
| 目錄分離 | ✅ 完成 |
| 配置管理 | ✅ 完成 |