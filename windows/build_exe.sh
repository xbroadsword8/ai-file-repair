#!/bin/bash
# 
# 在 Linux 上使用 Wine 打包 Windows .exe 文件
# 
# 此腳本會：
# 1. 安裝 Wine（如果還沒有）
# 2. 配置 64-bit Windows 環境
# 3. 安裝 Windows Python 和依賴
# 4. 使用 PyInstaller 打包 Windows .exe
# 

set -e

echo "========================================"
echo "  Wine - Windows .exe 打包腳本"
echo "========================================"
echo ""

# 檢查 Wine
if ! command -v wine &> /dev/null; then
    echo "⚠️  Wine 未安裝，正在安裝..."
    sudo apt update
    sudo apt install -y wine64 winetricks
fi

# 檢查 Python
if ! command -v python &> /dev/null; then
    echo "⚠️  Python 未安裝，正在安裝..."
    sudo apt install -y python3 python3-pip
fi

# 初始化 Wine 環境
echo "🔧 初始化 Wine 環境..."
export WINEARCH=win64
export WINEPREFIX="$HOME/.wine-ai-repair"

# 清理舊環境
rm -rf "$WINEPREFIX"

# 創建新環境
wine wineboot --init

echo "📦 安裝 Windows Python..."
# 下載並安裝 Windows Python
PYTHON_VERSION="3.11.9"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe"

if [ ! -f "$HOME/python-${PYTHON_VERSION}-amd64.exe" ]; then
    echo "下載 Python 安裝程序..."
    curl -L "$PYTHON_URL" -o "$HOME/python-${PYTHON_VERSION}-amd64.exe"
fi

# 安裝 Python
wine msiexec /i "$HOME/python-${PYTHON_VERSION}-amd64.exe" /passive /norestart

# 配置 Python 路徑
export PATH="$WINEPREFIX/drive_c/Python311:$WINEPREFIX/drive_c/Python311/Scripts:$PATH"

# 安裝 PyInstaller
echo "📦 安裝 PyInstaller..."
wine pip install pyinstaller

# 切換到項目目錄
cd "$(dirname "$0")/../scripts"

# 打包
echo "🔨 開始打包 Windows .exe..."
wine pyinstaller --onefile --windowed --name "AI File Repair" gui_main.py

# 檢查輸出
if [ -f "dist/AI File Repair.exe" ]; then
    echo ""
    echo "✅ 成功！Windows .exe 已生成"
    echo "📁 位置: dist/AI File Repair.exe"
    echo "📊 大小: $(ls -lh dist/AI File Repair.exe | awk '{print $5}')"
else
    echo ""
    echo "❌ 打包失敗"
fi