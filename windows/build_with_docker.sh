#!/bin/bash
#
# 使用 Docker 打包 Windows .exe
# 這個腳本使用 wine-stable Docker 鏡像在 Linux 上構建 Windows 可執行文件
#

set -e

echo "========================================"
echo "  Docker - Windows .exe 打包腳本"
echo "========================================"
echo ""

# 檢查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安裝"
    echo "請安裝 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 檢查項目文件
if [ ! -f "gui_main.py" ]; then
    echo "❌ 找不到 gui_main.py"
    echo "請確保你在正確的目錄中運行此腳本"
    exit 1
fi

# 創建臨時目錄
TEMP_DIR=$(mktemp -d)
echo "📁 臨時目錄: $TEMP_DIR"

# 複製需要的文件
cp gui_main.py "$TEMP_DIR/"
cp ai_repair.py "$TEMP_DIR/"

# 創建 Dockerfile
cat > "$TEMP_DIR/Dockerfile" << 'DOCKERFILE'
FROM wine/stable:latest

# 安裝 Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 設置工作目錄
WORKDIR /app

# 複製文件
COPY . .

# 安裝 Python 依賴
RUN pip3 install pyyaml pyinstaller

# 打包
RUN pyinstaller --onefile --windowed --name "AI File Repair" gui_main.py
DOCKERFILE

# 構建 Docker 鏡像
echo "🐳 構建 Docker 鏡像..."
docker build -t ai-repair-builder "$TEMP_DIR"

# 創建容器並提取文件
echo "📦 提取 .exe 文件..."
docker create --name ai-repair-container ai-repair-builder /bin/true

# 從容器中複製文件
docker cp ai-repair-container:/app/dist/AI\ File\ Repair.exe ./dist/AI\ File\ Repair.exe

# 清理
docker rm ai-repair-container
docker rmi ai-repair-builder
rm -rf "$TEMP_DIR"

echo ""
echo "✅ 成功！Windows .exe 已生成"
echo "📁 位置: dist/AI File Repair.exe"