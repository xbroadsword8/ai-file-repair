#!/bin/bash
#
# GitHub Setup Script
# 自動化配置 GitHub CLI 和 Personal Access Token
#

set -e

echo "========================================"
echo "  GitHub Setup Script"
echo "========================================"
echo ""

# 檢查 GitHub CLI
if ! command -v gh &> /dev/null; then
    echo "📦 安裝 GitHub CLI..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt update && sudo apt install -y gh
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install gh
    fi
fi

# 配置 GitHub
echo "🔐 配置 GitHub..."
echo ""
echo "請按照以下步驟操作："
echo ""
echo "1️⃣  訪問：https://github.com/settings/tokens"
echo "2️⃣  點擊：Generate new token"
echo "3️⃣  設置權限：repo, workflow"
echo "4️⃣  複製生成的 Token"
echo ""
read -p "輸入你的 GitHub Token: " GITHUB_TOKEN

# 驗證 Token
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Token 不能为空"
    exit 1
fi

# 登錄 GitHub CLI
echo " authenticate with GitHub CLI..."
echo "$GITHUB_TOKEN" | gh auth login --with-token

# 檢查是否成功
if gh auth status &> /dev/null; then
    echo "✅ GitHub CLI 配置成功！"
    gh auth status
else
    echo "❌ GitHub CLI 配置失敗"
    exit 1
fi

# 設置環境變量
echo ""
echo "📁 將 Token 添加到環境變量..."
export GITHUB_TOKEN="$GITHUB_TOKEN"

# 設置 GitHub 用戶名
GITHUB_USERNAME=$(gh api user --jq '.login' 2>/dev/null || echo "your-username")
echo "GitHub Username: $GITHUB_USERNAME"

# 創建 GitHub Repository（如果需要）
read -p "是否創建新的 Repository？(y/n) " CREATE_REPO

if [ "$CREATE_REPO" == "y" ]; then
    read -p "Repository 名稱: " REPO_NAME
    read -p "Description: " REPO_DESC
    
    gh repo create "$REPO_NAME" \
        --description "$REPO_DESC" \
        --public \
        --confirm
    
    echo "✅ Repository '$REPO_NAME' 創建成功！"
fi

echo ""
echo "========================================"
echo "  GitHub Setup Complete!"
echo "========================================"
echo ""
echo "接下來："
echo "1. cd scripts"
echo "2. git init && git add . && git commit -m 'Initial commit'"
echo "3. git remote add origin https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
echo "4. git push -u origin main"
echo ""
echo "GitHub Actions 會自動觸發並生成 .exe 文件"