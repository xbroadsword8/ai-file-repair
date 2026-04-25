# GitHub Actions 使用指南

## 📋 流程說明

### 用戶端（使用預建的 .exe）

```
1. 訪問 GitHub Release 頁面
   ↓
2. 下載最新版本的 AI File Repair.exe
   ↓
3. 雙擊運行，無需安裝 Python
   ↓
4. 配置 API Key 後即可開始修復
```

### 開發者端（自動生成新版本）

```
1. 推送代碼到 GitHub
   ↓
2. GitHub Actions 自動觸發
   ↓
3. 生成 Windows .exe 和 Linux 可執行文件
   ↓
4. 作為 Release Artifact 上傳
   ↓
5. 用戶可下載最新版本
```

---

## 🎯 自動化流程圖

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    GitHub Actions 自動化流程                            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    1. 代碼提交                                    │   │
│  │  User pushes to GitHub → Trigger CI/CD                         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                          │                               │
│                                          ▼                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    2. 觸發 GitHub Actions                       │   │
│  │  - On push to main/master                                       │   │
│  │  - On new tag (v1.0.0, etc.)                                   │   │
│  │  - On pull request                                              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                          │                               │
│                                          ▼                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    3. Windows Runner                            │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ • Windows 11/10 environment                            │   │   │
│  │  │ • Python 3.11 installed                                │   │   │
│  │  │ • PyInstaller available                                │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                          │                               │
│                                          ▼                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    4. 構建 .exe                                 │   │
│  │  pyinstaller --onefile --windowed --name "AI File Repair"     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                          │                               │
│                                          ▼                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    5. 上傳 Release                              │   │
│  │  • GitHub Release 自動創建                                      │   │
│  │  • Artifact 可下載 (7天保留)                                    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 設置步驟

### 步驟 1：創建 GitHub Repository

```bash
# 在 GitHub 上創建新倉庫
# 名稱: ai-file-repair
# 類型: Public (或 Private)

# 初始化並推送代碼
git init
git add .
git commit -m "Initial commit: AI File Repair"
git remote add origin https://github.com/username/ai-file-repair.git
git push -u origin main
```

### 步驟 2：創建 Release (可選)

```bash
# 如果你想手動發布版本
git tag v1.0.0
git push origin v1.0.0
```

### 步驟 3：確認自動化運行

```
1. 訪問 https://github.com/username/ai-file-repair/actions
2. 查看最近的 Workflow 執行
3. 等待 build job 完成
4. 下載生成的 .exe 文件
```

---

## 📥 用戶下載和使用

### 下載方式 1：從 Release

```
1. 訪問 https://github.com/username/ai-file-repair/releases
2. 下載最新版本的 AI File Repair.exe
3. 雙擊運行
```

### 下載方式 2：從 Artifact

```
1. 訪問 https://github.com/username/ai-file-repair/actions
2. 點擊最近成功的 Workflow
3. 下載 "AI-File-Repair-Windows" artifact
4. 解壓並運行 AI File Repair.exe
```

---

## 🔧 本地開發者工作流

### 編輯代碼

```bash
# 1. 編輯 GUI 或修復邏輯
nano scripts/gui_main.py
nano scripts/ai_repair.py

# 2. 本地測試
python scripts/gui_main.py

# 3. 提交到 GitHub
git add .
git commit -m "Update GUI and fix bugs"
git push

# 4. GitHub Actions 自動觸發
#    → 等待約 5-10 分鐘
#    → 下載新的 .exe 測試
```

---

## ⚙️ 配置文件說明

### .github/workflows/build-windows.yml

| 項目 | 說明 |
|------|------|
| `runs-on: windows-latest` | 使用最新 Windows runner |
| `python-version: '3.11'` | Python 3.11 環境 |
| `pyinstaller --windowed` | 生成無控制台窗口的 .exe |
| `retention-days: 7` | Artifact 保留 7 天 |

### 可自定義選項

```yaml
# 如果需要更多功能，可以添加：
steps:
  - name: Run tests
    run: pytest tests/
    
  - name: Build installer
    run: |
      # 使用 NSIS 或 Inno Setup 創建安裝包
      # install-shield /compile installer.nsi
      
  - name: Upload to CDN
    run: |
      # 上傳到 CDN 或其他存儲
      aws s3 cp dist/*.exe s3://your-bucket/
```

---

## 📈 優勢

| 優勢 | 說明 |
|------|------|
| ✅ 自動化 | 代碼更新 → 自動生成 .exe |
| ✅ 跨平台 | 一次推送，生成 Windows + Linux 版本 |
| ✅ 可信賴 | GitHub 官方服務，穩定可靠 |
| ✅ 免費 | GitHub Actions 免費额度足夠 |
| ✅ 易用 | 用戶直接下載，無需 Python |

---

## 🎯 完整工作流程總結

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    完整工作流程                                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  開發者:                                                               │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │  1. 編輯代碼                                                   │     │
│  │  2. git commit + git push                                     │     │
│  │  3. (可選) git tag v1.0.0                                     │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                    ↓                                                     │
│  GitHub Actions:                                                       │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │  1. 觸發 Workflow                                             │     │
│  │  2. Windows runner 環境準備                                   │     │
│  │  3. pip install pyyaml pyinstaller                          │     │
│  │  4. pyinstaller --onefile --windowed                        │     │
│  │  5. 生成 AI File Repair.exe                                   │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                    ↓                                                     │
│  用戶:                                                                 │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │  1. 下載 AI File Repair.exe                                   │     │
│  │  2. 雙擊運行 (無需 Python)                                    │     │
│  │  3. 配置 API Key                                              │     │
│  │  4. 開始修復文件                                              │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📝 下一步操作

1. **創建 GitHub Repository**
   ```bash
   gh repo create ai-file-repair --public --source=. --remote=origin
   ```

2. **推送代碼**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push -u origin main
   ```

3. **等待自動化**
   - 訪問 Actions 頁面
   - 等待 build 完成
   - 下載測試

4. **发布版本** (可選)
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

需要我幫你：
- ✅ 創建 GitHub Repository？
- ✅ 配置其他自動化任務？
- ✅ 添加測試流程？
- ✅ 其他需求？ 
