#!/bin/bash
# Complete GitHub Setup Script
# 自動初始化 Git、創建 Repository 並推送代碼

set -e

echo "========================================"
echo "  完整 GitHub Setup Script"
echo "========================================"
echo ""

# 讀取 .env 文件
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 找不到 .env 文件"
    exit 1
fi

# 解析 .env 文件
export $(grep -v '^#' "$ENV_FILE" | xargs)

# 初始化 Git（如果還沒有）
if [ ! -d ".git" ]; then
    echo "📁 初始化 Git Repository..."
    git init
    git config user.name "AI File Repair CI"
    git config user.email "ci@github.com"
    git add .
    git commit -m "Initial commit: AI File Repair with GitHub Actions CI/CD"
else
    echo "📁 Git Repository 已存在"
fi

# 檢查 remote
if ! git remote | grep -q origin; then
    # 創建 Repository
    echo "🔨 創建 GitHub Repository..."
    
    # 使用 gh api 創建（不需要交互）
    GITHUB_USERNAME=$(gh api user --jq '.login' 2>/dev/null)
    
    if [ -z "$GITHUB_USERNAME" ]; then
        echo "❌ 無法獲取 GitHub 用戶名"
        exit 1
    fi
    
    echo "GitHub 用戶名: $GITHUB_USERNAME"
    
    # 創建 Repository via API
    gh repo create ai-file-repair \
        --description "AI File Repair Tool - Auto-build Windows Executable via GitHub Actions" \
        --public \
        --source=. \
        --remote=origin
    
    echo "✅ Repository 創建成功!"
else
    echo "📁 Remote origin 已存在"
fi

# 推送代碼
echo "🚀 推送代碼到 GitHub..."
git push -u origin main --force

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "GitHub Actions 已觸發！"
echo ""
echo "請訪問以下網址查看進度："
echo "https://github.com/$GITHUB_USERNAME/ai-file-repair/actions"
echo ""
echo "等待 5-10 分鐘後，下載生成的 .exe："
echo "https://github.com/$GITHUB_USERNAME/ai-file-repair/releases"
echo ""