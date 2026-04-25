# 🔑 GitHub Personal Access Token 生成指南

## 📋 完整步驟

### 步驟 1： 登錄 GitHub

```
1. 訪問 https://github.com
2. 點擊 "Sign in"
3. 使用你的帳戶登陸（可使用 Google 帳戶）
```

### 步驟 2：進入 Token 設置頁面

```
選項 A - 直接訪問：
  https://github.com/settings/tokens

選項 B - 通過菜單：
  1. 點擊右上角頭像
  2. 選擇 "Settings"
  3. 左側菜單 "Advanced"
  4. 點擊 "Personal access tokens"
  5. 點擊 "Tokens for desktop"
```

### 步驟 3：生成新 Token

```
點擊 [Generate new token] → [Generate new token (classic)]

┌─────────────────────────────────────────────────────────┐
│  Token settings                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Note:       AI File Repair CI/CD                      │
│              (描述這個 Token 的用途)                     │
│                                                         │
│  Expiration: 90 days                                   │
│              (建議選擇 90 天或 1 年)                    │
│                                                         │
│  Scopes (選中以下權限)：                                │
│  □ repo              (存取所有仓库)                     │
│  □ workflow          (自動化流程)                       │
│  □ write:packages    (發佈包)                          │
│                                                         │
│  [Generate token]                                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 步驟 4：複製 Token

```
生成成功後，會看到：

┌─────────────────────────────────────────────────────────┐
│  Token generated successfully                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX          │
│                                                         │
│  ⚠️  警告：Token 只會顯示一次                           │
│  ⚠️  請立即複製並妥善保管                              │
│                                                         │
│  [Copy] [Revoke]                                        │
│                                                         │
└─────────────────────────────────────────────────────────┘

按 "Copy" 複製 Token
```

### 步驟 5：保存 Token

```
將 Token 保存到安全的地方：

方法 1 - 密碼管理器：
  • 1Password
  • Bitwarden
  • LastPass

方法 2 - 安全文件：
  • encrypt the token
  • store in encrypted vault

方法 3 - 環境變量：
  Windows: setx GITHUB_TOKEN "your_token"
  Linux:   export GITHUB_TOKEN="your_token"

方法 4 - GitHub CLI (推薦)：
  gh auth login --with-token
```

---

## 🔧 配置 GitHub CLI

### Windows

```bash
# 1. 打開 PowerShell 或 CMD
# 2. 運行：
echo YOUR_TOKEN | gh auth login --with-token

# 或使用腳本：
windows/setup_github.bat
```

### Linux/macOS

```bash
# 1. 打開終端
# 2. 運行：
echo "YOUR_TOKEN" | gh auth login --with-token

# 或使用腳本：
chmod +x windows/setup_github.sh
./windows/setup_github.sh
```

---

## ✅ 驗證配置

```bash
# 檢查 GitHub CLI 是否配置成功
gh auth status

# 應該顯示：
# ✓ Logged in to github.com as YOUR_USERNAME
# ✓ GITHUB_TOKEN environment variable is set
```

---

## 🚀 配置完成後

### 1. 初始化 Git Repository

```bash
cd /path/to/ai-file-repair/scripts

# 初始化 Git（如果還沒有）
git init

# 添加所有文件
git add .

# 提交
git commit -m "Initial commit: AI File Repair with GitHub Actions"

# 添加 remote
git remote add origin https://github.com/YOUR_USERNAME/ai-file-repair.git

# 推送
git push -u origin main
```

### 2. 等待 GitHub Actions

```
推送後：
├─ 等待 5-10 分鐘
├─ GitHub Actions 自動觸發
├─ Windows runner 構建 .exe
└─ 生成完成！
```

### 3. 下載生成的文件

```
訪問：
https://github.com/YOUR_USERNAME/ai-file-repair/releases

或：
https://github.com/YOUR_USERNAME/ai-file-repair/actions
→ 點擊最近成功的 Workflow
→ 下載 "AI-File-Repair-Windows" artifact
```

---

## 🛡️ Token 安全提示

| 風險 | 防護措施 |
|------|----------|
| Token 泄露 | 不要提交到 Git 倉庫 |
| Token 過期 | 設置 90-365 天有效期 |
| 權限過大 | 只授予必需權限 |
| 被盜用 | 定期輪換 Token |

---

## ❓常見問題

### Q: Token 過期了怎麼辦？
A: 在 GitHub Settings → Tokens 中創建新 Token，然後更新配置

### Q: 可以用 OAuth 代替嗎？
A: 可以，但 Personal Access Token 更簡單，適合自動化

### Q: Token 被洩露了怎麼辦？
A: 立即在 GitHub Settings → Tokens 中「Revoke」該 Token

### Q: 需要什麼權限？
A: 最小權限：`repo`, `workflow`

---

## 📊 完整流程總結

```
┌────────────────────────────────────────────────────────────────┐
│                    Token 生成與配置流程                         │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 🌐 訪問 https://github.com/settings/tokens                 │
│     ↓                                                           │
│  2. ✨ 點擊 "Generate new token"                                │
│     ↓                                                           │
│  3. ⚙️  設置權限 (repo, workflow)                              │
│     ↓                                                           │
│  4. 📋 複製 Token (立即保存!)                                   │
│     ↓                                                           │
│  5. 🔧 配置 GitHub CLI                                          │
│     ↓                                                           │
│  6. 📦 初始化 Git + 推送代碼                                    │
│     ↓                                                           │
│  7. ⚙️  GitHub Actions 自動運行                                 │
│     ↓                                                           │
│  8. 📥  下載生成的 .exe                                         │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## 🎯 下一步

1. **跟隨上面的步驟生成 Token**
2. **運行 `windows/setup_github.bat` (Windows) 或 `setup_github.sh` (Linux)**
3. **推送代碼到 GitHub**
4. **等待 Actions 自動運行**
5. **下載並使用生成的 .exe 文件**

需要我：
- ✅ 創建更多自動化腳本？
- ✅ 提供其他配置方式？
- ✅ 其他協助？ 
