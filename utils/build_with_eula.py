#!/usr/bin/env python3
"""
Build AI File Repair with EULA Integration
集成 EULA 的自動化打包腳本
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def ensure_eula_in_build():
    """確保 EULA 文件已複製到構建目錄"""
    script_dir = Path(__file__).parent
    windows_dir = script_dir / "../windows"
    build_dir = script_dir / "build/AI File Repair"
    
    # 確保目錄存在
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # 複製 EULA 到構建目錄
    eula_source = windows_dir / "EULA-TW.md"
    eula_dest = build_dir / "EULA-TW.md"
    
    if eula_source.exists():
        shutil.copy(eula_source, eula_dest)
        print(f"✓ EULA 已複製到: {eula_dest}")
        return True
    else:
        print("✗ EULA 文件不存在！")
        return False

def build_exe():
    """使用 PyInstaller 構建 Windows .exe"""
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # 檢查 EULA
    if not ensure_eula_in_build():
        print("ERROR: EULA 文件缺失")
        return False
    
    # PyInstaller 命令
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", "AI File Repair",
        "--add-data", f"windows/EULA-TW.md;.",
        "--add-data", f"scripts/gui_main.py;.",
        "--add-data", f"scripts/ai_repair.py;.",
        "scripts/gui_main.py"
    ]
    
    print("開始構建 Windows .exe...")
    print(f"命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("✓ 構建成功！")
        print(f"輸出位置: {script_dir / 'dist/AI File Repair.exe'}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 構建失敗: {e}")
        return False

def main():
    """主函數"""
    print("=" * 50)
    print("AI File Repair - EULA 整合打包工具")
    print("=" * 50)
    
    success = build_exe()
    
    if success:
        print("\n" + "=" * 50)
        print("✓ 打包完成！")
        print("  EULA 已集成到 Windows .exe 中")
        print("  使用者在首次啟動時將看到 EULA")
        print("=" * 50)
        return 0
    else:
        print("\n" + "=" * 50)
        print("✗ 打包失敗")
        print("=" * 50)
        return 1

if __name__ == "__main__":
    sys.exit(main())
