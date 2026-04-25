#!/bin/bash
# GitHub Setup Script - 使用 .env 文件中的 Token

set -e

echo "========================================"
echo "  GitHub Setup Script"
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

# 檢查 GitHub CLI
if ! command -v gh &> /dev/null; then
    echo "📦 安裝 GitHub CLI..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt update && sudo apt install -y gh
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install gh
    fi
fi

# 登錄 GitHub CLI
echo "🔐 使用 .env 中的 Token 登錄 GitHub..."
echo "$GITHUB_TOKEN" | gh auth login --with-token

# 驗證
gh auth status

# 設置 Git
echo "📋 配置 Git..."
git config --global user.name "AI File Repair CI"
git config --global user.email "ci@github.com"

# 初始化 Git (如果還沒有)
if [ ! -d ".git" ]; then
    echo "📁 初始化 Git Repository..."
    git init
    git add .
    git commit -m "Initial commit: AI File Repair with GitHub Actions CI/CD"
fi

# 添加 remote (如果還沒有)
if ! git remote | grep -q origin; then
    git remote add origin https://github.com/$GITHUB_OWNER/$GITHUB_REPO.git
fi

# 推送代碼
echo "🚀 推送代碼到 GitHub..."
git push -u origin main --force

echo ""
echo "✅ GitHub Setup Complete!"
echo "========================================"
echo ""
echo "GitHub Actions 已觸發！"
echo "等待 5-10 分鐘，然後："
echo "1. 訪問 https://github.com/$GITHUB_OWNER/$GITHUB_REPO/actions"
echo "2. 下載生成的 'AI-File-Repair-Windows' artifact"
echo ""