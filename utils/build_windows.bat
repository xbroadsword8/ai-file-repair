@echo off
chcp 65001 >nul

echo ========================================
echo  AI File Repair - Windows打包腳本
echo ========================================
echo.

:: 檢查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] Python 未安裝
    pause
    exit /b 1
)
echo [信息] Python 已安裝
echo.

:: 檢查依賴
echo [信息] 安裝依賴...
pip install requests pyyaml pyinstaller >nul 2>&1
echo [完成] 依賴安裝完成
echo.

:: 打包
echo [信息] 開始打包...
pyinstaller --onefile ^
  --windowed ^
  --name "AI File Repair" ^
  --icon=icon.ico ^
  --add-data "assets;assets" ^
  gui_main.py

if errorlevel 1 (
    echo [錯誤] 打包失敗
    pause
    exit /b 1
)

echo.
echo ========================================
echo  ✅ 打包完成！
echo ========================================
echo  可執行文件位置: dist/AI File Repair.exe
echo.
echo  該程序可以在任何 Windows 電腦上直接運行
echo  無需安裝 Python 或任何依賴
echo.
pause