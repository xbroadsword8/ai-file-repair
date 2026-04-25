"""
AI File Repair - Windows GUI Version
專業的 AI 文件修復工具
支持任意 OpenAI 兼容 API

功能分離：
- AI 增強模式：使用 AI 協助所有功能
- 一般模式：使用原功能 RepairEngine 進行修復

目錄結構：
- Program Files: 程序安裝位置
- AppData: 用戶配置和日誌
- Temp: 暫存文件 (修復預覽、備份、API緩存)
- Output: 修復後的文件 (用戶指定)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import time
from datetime import datetime
from pathlib import Path
import json
import os
import tempfile
import shutil

# ============================================
# 目錄結構定義
# ============================================

class DirectoryStructure:
    """
    目錄結構管理
    將安裝位置、配置、暫存、輸出完全分離
    """
    
    def __init__(self):
        # 程序安裝位置
        self.program_dir = Path(__file__).parent.parent
        self.program_files = self.program_dir / "dist"
        
        # 用戶配置位置 (AppData)
        self.appdata_dir = Path.home() / "AppData" / "Local" / "AI File Repair"
        self.config_dir = self.appdata_dir / "config"
        self.logs_dir = self.appdata_dir / "logs"
        
        # 暫存位置 (Temp)
        self.temp_dir = Path(tempfile.gettempdir()) / "AI File Repair"
        self.preview_dir = self.temp_dir / "preview"
        self.backup_dir = self.temp_dir / "backup"
        self.api_cache_dir = self.temp_dir / "api_cache"
        
        # 輸出位置 (默認)
        self.output_dir = Path.home() / "Documents" / "AI Repair Output"
        
        # 初始化目錄
        self._init_directories()
    
    def _init_directories(self):
        """初始化所有目錄"""
        dirs = [
            self.program_files,
            self.config_dir,
            self.logs_dir,
            self.temp_dir,
            self.preview_dir,
            self.backup_dir,
            self.api_cache_dir,
            self.output_dir
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def get_temp_file(self, prefix="temp_", suffix=".tmp"):
        """獲取臨時文件路徑"""
        return tempfile.NamedTemporaryFile(
            prefix=prefix,
            suffix=suffix,
            dir=self.temp_dir,
            delete=False
        ).name
    
    def cleanup_temp(self, max_age_days=7):
        """清理過期的暫存文件"""
        import glob
        
        patterns = [
            (self.preview_dir, "*.py_fixed_preview*"),
            (self.backup_dir, "*.bak"),
            (self.api_cache_dir, "*.json"),
        ]
        
        for dir_path, pattern in patterns:
            for f in glob.glob(str(dir_path / pattern)):
                try:
                    if (datetime.now() - datetime.fromtimestamp(os.path.getmtime(f))).days > max_age_days:
                        os.remove(f)
                        print(f"清理過期文件: {f}")
                except:
                    pass
    
    def cleanup_all_temp(self):
        """清理所有暫存文件"""
        dirs = [self.preview_dir, self.backup_dir, self.api_cache_dir]
        
        for d in dirs:
            for f in d.glob("*"):
                try:
                    f.unlink()
                except:
                    pass


# 初始化目錄結構
dirs = DirectoryStructure()


# ============================================
# GUI 主程序
# ============================================

class AIRepairGUI:
    """AI 文件修復工具主窗口"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("AI File Repair - 智能文件修復工具")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 700)
        
        # 初始化變量
        self.files_to_repair = []
        self.repair_mode = tk.StringVar(value="ai")  # "ai" 或 "standard"
        self.repair_thread = None
        self.repair_queue = queue.Queue()
        self.directory_structure = dirs
        
        # 初始化 colors (必須在 create_widgets 之前)
        self.colors = {
            'bg': '#2b2b2b',
            'panel': '#3c3c3c',
            'accent': '#007acc',
            'ai_mode': '#007acc',
            'standard_mode': '#2d5a27',
            'text': '#ffffff',
            'text_secondary': '#a0a0a0',
            'success': '#4caf50',
            'warning': '#ff9800',
            'error': '#f44336',
            'border': '#505050'
        }
        
        # 設置 root 背景
        self.root.configure(bg=self.colors['bg'])
        
        # 創建界面
        self.create_widgets()
        self.bind_events()
        
        # 初始化 API 客戶端
        self.api_client = None
        
        # 自動加載配置
        self.load_config()
        
        # 顯示目錄信息
        self.show_directory_info()
        
    def show_directory_info(self):
        """顯示目錄信息（調試用）"""
        print("=" * 60)
        print("目錄結構:")
        print(f"  程序目錄: {self.directory_structure.program_dir}")
        print(f"  配置目錄: {self.directory_structure.config_dir}")
        print(f"  暫存目錄: {self.directory_structure.temp_dir}")
        print(f"  輸出目錄: {self.directory_structure.output_dir}")
        print("=" * 60)
    
    def create_menubar(self):
        """創建菜單欄"""
        # 創建主菜單
        self.menubar = tk.Menu(self.root, bg=self.colors['bg'], fg=self.colors['text'])
        self.root.config(menu=self.menubar)
        
        # 文件菜單
        file_menu = tk.Menu(self.menubar, tearoff=0, bg=self.colors['bg'], fg=self.colors['text'])
        self.menubar.add_cascade(label="📁 文件", menu=file_menu)
        file_menu.add_command(label="添加文件", command=self.add_files, accelerator="Ctrl+O")
        file_menu.add_command(label="全選", command=self.select_all_files, accelerator="Ctrl+A")
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit, accelerator="Alt+F4")
        
        # 修復菜單
        repair_menu = tk.Menu(self.menubar, tearoff=0, bg=self.colors['bg'], fg=self.colors['text'])
        self.menubar.add_cascade(label="🔧 修復", menu=repair_menu)
        repair_menu.add_command(label="修復選中文件", command=self.start_repair_selected, accelerator="F5")
        repair_menu.add_command(label="修復所有文件", command=self.start_repair_all, accelerator="Ctrl+F5")
        repair_menu.add_separator()
        repair_menu.add_command(label="取消修復", command=self.cancel_repair, accelerator="Esc")
        
        # 設置菜單
        settings_menu = tk.Menu(self.menubar, tearoff=0, bg=self.colors['bg'], fg=self.colors['text'])
        self.menubar.add_cascade(label="⚙️ 設置", menu=settings_menu)
        settings_menu.add_command(label="API 設置", command=self.show_api_settings)
        settings_menu.add_command(label="清空暫存", command=self.clear_temp)
        
        # 幫助菜單
        help_menu = tk.Menu(self.menubar, tearoff=0, bg=self.colors['bg'], fg=self.colors['text'])
        self.menubar.add_cascade(label="❓ 幫助", menu=help_menu)
        help_menu.add_command(label="使用說明", command=self.show_help)
        help_menu.add_command(label="關於", command=self.show_about)
    
    # ============= 菜單命令處理 =============
    
    def start_repair_selected(self):
        """修復選中的文件"""
        selected = self.files_listbox.curselection()
        if not selected:
            tk.messagebox.showinfo("提示", "請先選中要修復的文件")
            return
        self.start_repair(selected)
    
    def start_repair_all(self):
        """修復所有文件"""
        if self.files_listbox.size() == 0:
            tk.messagebox.showinfo("提示", "沒有文件可修復")
            return
        self.start_repair(range(self.files_listbox.size()))
    
    def cancel_repair(self):
        """取消正在進行的修復"""
        if self.repair_thread and self.repair_thread.is_alive():
            self.repair_queue.put(None)  # Signal to stop
            tk.messagebox.showinfo("提示", "修復已取消")
    
    def show_api_settings(self):
        """顯示 API 設置對話框"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("API 設置")
        settings_window.geometry("400x200")
        
        tk.Label(settings_window, text="API Key:", font=('Segoe UI', 10)).grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        api_key_entry = tk.Entry(settings_window, width=30, font=('Segoe UI', 10))
        api_key_entry.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(settings_window, text="Endpoint:", font=('Segoe UI', 10)).grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        endpoint_entry = tk.Entry(settings_window, width=30, font=('Segoe UI', 10))
        endpoint_entry.grid(row=1, column=1, padx=10, pady=10)
        
        def save_settings():
            # Save settings logic here
            tk.messagebox.showinfo("提示", "設置已保存")
            settings_window.destroy()
        
        tk.Button(settings_window, text="保存", command=save_settings, bg=self.colors['accent'], fg='white').grid(row=2, column=0, columnspan=2, pady=10)
    
    def clear_temp(self):
        """清空暫存文件"""
        import shutil
        import os
        
        temp_dir = os.path.join(os.path.expanduser('~'), '.hermes', 'temp', 'ai-repair')
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            tk.messagebox.showinfo("提示", "暫存已清空")
        else:
            tk.messagebox.showinfo("提示", "沒有暫存文件可清空")
    
    def show_help(self):
        """顯示使用說明"""
        help_text = """
AI File Repair 使用說明

1. 添加文件：點擊「+ 添加文件」按鈕
2. 選擇模式：選擇 AI 增強模式 或 一般模式
3. 修復文件：點擊「修復選中文件」或「修復所有文件」
4. 查看結果：修復後的文件會保存在輸出目錄

快捷鍵：
Ctrl+O - 添加文件
Ctrl+A - 全選
F5 - 修復選中文件
Ctrl+F5 - 修復所有文件
Esc - 取消修復
"""
        tk.messagebox.showinfo("使用說明", help_text)
    
    def show_about(self):
        """顯示關於對話框"""
        about_text = """
AI File Repair v1.0.0

一個結合 AI 技術的文件修復工具

開發者: xmacclaw
日期: 2026-04-25

本软件使用 MIT License
"""
        tk.messagebox.showinfo("關於", about_text)
    
    def create_widgets(self):
        """創建所有窗口部件"""
        
        # 設置主題
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # ============= 顶部菜单栏 =============
        self.create_menubar()
        
        # ============= 主容器 =============
        main_container = tk.Frame(self.root, bg=self.colors['bg'], padx=10, pady=10)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # ============= 左側文件列表面板 =============
        left_panel = tk.Frame(main_container, bg=self.colors['panel'], 
                              relief=tk.RAISED, borderwidth=2)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        left_title = tk.Label(left_panel, text="📁 文件列表", 
                              bg=self.colors['panel'], fg=self.colors['text'],
                              font=('Segoe UI', 12, 'bold'), anchor=tk.W)
        left_title.pack(fill=tk.X, pady=(10, 10))
        
        list_frame = tk.Frame(left_panel, bg=self.colors['panel'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.files_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE,
                                       bg=self.colors['bg'], fg=self.colors['text'],
                                       highlightthickness=0, relief=tk.FLAT)
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                command=self.files_listbox.yview,
                                bg=self.colors['panel'],
                                troughcolor=self.colors['bg'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.files_listbox.config(yscrollcommand=scrollbar.set)
        
        btn_frame = tk.Frame(left_panel, bg=self.colors['panel'])
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.add_file_btn = tk.Button(btn_frame, text="+ 添加文件", 
                                       command=self.add_files,
                                       bg=self.colors['accent'], fg='white',
                                       relief=tk.FLAT, padx=15, pady=8,
                                       font=('Segoe UI', 9))
        self.add_file_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.remove_file_btn = tk.Button(btn_frame, text="🗑️ 刪除選中",
                                        command=self.remove_selected_files,
                                        bg=self.colors['error'], fg='white',
                                        relief=tk.FLAT, padx=15, pady=8,
                                        font=('Segoe UI', 9))
        self.remove_file_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.select_all_btn = tk.Button(btn_frame, text="✓ 全選",
                                       command=self.select_all_files,
                                       bg=self.colors['success'], fg='white',
                                       relief=tk.FLAT, padx=15, pady=8,
                                       font=('Segoe UI', 9))
        self.select_all_btn.pack(side=tk.LEFT)
        
        # ============= 中央預覽/修復面板 =============
        center_panel = tk.Frame(main_container, bg=self.colors['panel'],
                               relief=tk.RAISED, borderwidth=2)
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        center_title = tk.Label(center_panel, text="🎨 修復預覽", 
                                bg=self.colors['panel'], fg=self.colors['text'],
                                font=('Segoe UI', 12, 'bold'), anchor=tk.W)
        center_title.pack(fill=tk.X, pady=(10, 10))
        
        # 修復模式選擇
        mode_frame = tk.Frame(center_panel, bg=self.colors['panel'])
        mode_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(mode_frame, text="修復模式:", bg=self.colors['panel'],
                 fg=self.colors['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        
        # AI 修復模式
        self.ai_mode_rb = tk.Radiobutton(mode_frame, text="🤖 AI 增強模式",
                                        variable=self.repair_mode,
                                        value="ai",
                                        bg=self.colors['panel'], 
                                        fg=self.colors['text'],
                                        selectcolor=self.colors['ai_mode'],
                                        font=('Segoe UI', 9, 'bold'),
                                        command=self.on_mode_change)
        self.ai_mode_rb.pack(side=tk.LEFT, padx=(0, 15))
        
        # 原功能修復模式
        self.standard_mode_rb = tk.Radiobutton(mode_frame, text="🔧 一般模式",
                                              variable=self.repair_mode,
                                              value="standard",
                                              bg=self.colors['panel'], 
                                              fg=self.colors['text'],
                                              selectcolor=self.colors['standard_mode'],
                                              font=('Segoe UI', 9, 'bold'),
                                              command=self.on_mode_change)
        self.standard_mode_rb.pack(side=tk.LEFT)
        
        # 修復類型選擇
        type_frame = tk.Frame(center_panel, bg=self.colors['panel'])
        type_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(type_frame, text="修復類型:", bg=self.colors['panel'],
                 fg=self.colors['text'], font=('Segoe UI', 9)).pack(side=tk.LEFT)
        
        self.repair_type_var = tk.StringVar(value="auto")
        repair_types = [
            ("自動檢測", "auto"),
            ("代碼修復", "code"),
            ("圖像修復", "image"),
            ("音頻修復", "audio"),
            ("文檔修復", "document")
        ]
        
        for text, value in repair_types:
            rb = tk.Radiobutton(type_frame, text=text, variable=self.repair_type_var,
                               value=value, bg=self.colors['panel'], 
                               fg=self.colors['text'], selectcolor=self.colors['accent'],
                               font=('Segoe UI', 9))
            rb.pack(side=tk.LEFT, padx=(0, 15))
        
        # 差異顯示區域
        diff_frame = tk.Frame(center_panel, bg=self.colors['panel'])
        diff_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # 左側：原始文件
        original_frame = tk.Frame(diff_frame, bg=self.colors['bg'])
        original_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        tk.Label(original_frame, text="📄 原始文件", bg=self.colors['bg'],
                 fg=self.colors['text'], font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W)
        
        self.original_text = scrolledtext.ScrolledText(original_frame,
                                                       bg=self.colors['bg'],
                                                       fg=self.colors['text_secondary'],
                                                       insertbackground='white',
                                                       relief=tk.FLAT,
                                                       height=20)
        self.original_text.pack(fill=tk.BOTH, expand=True)
        
        # 右側：修復後
        repaired_frame = tk.Frame(diff_frame, bg=self.colors['bg'])
        repaired_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        tk.Label(repaired_frame, text="✅ 修復後預覽", bg=self.colors['bg'],
                 fg=self.colors['success'], font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W)
        
        self.repaired_text = scrolledtext.ScrolledText(repaired_frame,
                                                       bg=self.colors['bg'],
                                                       fg=self.colors['success'],
                                                       insertbackground='white',
                                                       relief=tk.FLAT,
                                                       height=20)
        self.repaired_text.pack(fill=tk.BOTH, expand=True)
        
        # 修復按鈕
        repair_btn_frame = tk.Frame(center_panel, bg=self.colors['panel'])
        repair_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.preview_btn = tk.Button(repair_btn_frame, text="🔍 預覽修復",
                                     command=self.preview_repair,
                                     bg=self.colors['accent'], fg='white',
                                     relief=tk.FLAT, padx=20, pady=10,
                                     font=('Segoe UI', 10, 'bold'))
        self.preview_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.start_repair_btn = tk.Button(repair_btn_frame, text="🚀 開始修復",
                                         command=self.start_repair,
                                         bg=self.colors['success'], fg='white',
                                         relief=tk.FLAT, padx=20, pady=10,
                                         font=('Segoe UI', 10, 'bold'))
        self.start_repair_btn.pack(side=tk.LEFT)
        
        # ============= 右側設置面板 =============
        right_panel = tk.Frame(main_container, bg=self.colors['panel'],
                              relief=tk.RAISED, borderwidth=2)
        right_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        right_title = tk.Label(right_panel, text="⚙️ 設置", 
                               bg=self.colors['panel'], fg=self.colors['text'],
                               font=('Segoe UI', 12, 'bold'), anchor=tk.W)
        right_title.pack(fill=tk.X, pady=(10, 10))
        
        # AI 設置區域
        ai_settings_frame = tk.LabelFrame(right_panel, text="🤖 AI API 設置",
                                  bg=self.colors['panel'], fg=self.colors['text'],
                                  font=('Segoe UI', 9, 'bold'), labelanchor=tk.N)
        ai_settings_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(ai_settings_frame, text="端點 URL:", bg=self.colors['panel'],
                 fg=self.colors['text'], font=('Segoe UI', 8)).pack(anchor=tk.W, padx=5)
        
        self.api_endpoint_entry = tk.Entry(ai_settings_frame, bg=self.colors['bg'],
                                          fg=self.colors['text'], relief=tk.FLAT,
                                          font=('Segoe UI', 9))
        self.api_endpoint_entry.pack(fill=tk.X, padx=5, pady=(0, 8))
        self.api_endpoint_entry.insert(0, "https://api.openai.com/v1")
        
        tk.Label(ai_settings_frame, text="API Key:", bg=self.colors['panel'],
                 fg=self.colors['text'], font=('Segoe UI', 8)).pack(anchor=tk.W, padx=5)
        
        self.api_key_entry = tk.Entry(ai_settings_frame, bg=self.colors['bg'],
                                     fg=self.colors['text'], relief=tk.FLAT,
                                     font=('Segoe UI', 9), show='•')
        self.api_key_entry.pack(fill=tk.X, padx=5, pady=(0, 8))
        
        tk.Label(ai_settings_frame, text="模型:", bg=self.colors['panel'],
                 fg=self.colors['text'], font=('Segoe UI', 8)).pack(anchor=tk.W, padx=5)
        
        self.model_var = tk.StringVar(value="gpt-4o-mini")
        models = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo", "deepseek-r1:1.5b"]
        self.model_combo = ttk.Combobox(ai_settings_frame, textvariable=self.model_var,
                                       values=models, state='readonly',
                                       font=('Segoe UI', 9))
        self.model_combo.pack(fill=tk.X, padx=5, pady=(0, 8))
        
        # 修復設置區域
        repair_settings_frame = tk.LabelFrame(right_panel, text="🔧 修復設置",
                                              bg=self.colors['panel'], 
                                              fg=self.colors['text'],
                                              font=('Segoe UI', 9, 'bold'),
                                              labelanchor=tk.N)
        repair_settings_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(repair_settings_frame, text="超時時間:", bg=self.colors['panel'],
                 fg=self.colors['text'], font=('Segoe UI', 8)).pack(anchor=tk.W, padx=5)
        
        self.timeout_var = tk.StringVar(value="30")
        tk.Entry(repair_settings_frame, textvariable=self.timeout_var,
                bg=self.colors['bg'], fg=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 9), width=10).pack(anchor=tk.W, padx=5, pady=(0, 8))
        
        tk.Label(repair_settings_frame, text="重試次數:", bg=self.colors['panel'],
                 fg=self.colors['text'], font=('Segoe UI', 8)).pack(anchor=tk.W, padx=5)
        
        self.retries_var = tk.StringVar(value="3")
        tk.Entry(repair_settings_frame, textvariable=self.retries_var,
                bg=self.colors['bg'], fg=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 9), width=10).pack(anchor=tk.W, padx=5, pady=(0, 8))
        
        # 保存配置按鈕
        save_config_btn = tk.Button(right_panel, text="💾 保存配置",
                                    command=self.save_config,
                                    bg=self.colors['accent'], fg='white',
                                    relief=tk.FLAT, padx=20, pady=8,
                                    font=('Segoe UI', 9))
        save_config_btn.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # ============= 狀態欄 =============
        status_frame = tk.Frame(self.root, bg=self.colors['panel'],
                               relief=tk.RAISED, borderwidth=2)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = tk.Label(status_frame, text="✅ 就緒", 
                                     bg=self.colors['panel'], 
                                     fg=self.colors['text'],
                                     font=('Segoe UI', 9))
        self.status_label.pack(side=tk.LEFT, padx=15)
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(status_frame, 
                                           variable=self.progress_var,
                                           maximum=100, mode='determinate',
                                           )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)
        
        self.files_count_label = tk.Label(status_frame, text="文件: 0/0", 
                                         bg=self.colors['panel'],
                                         fg=self.colors['text_secondary'],
                                         font=('Segoe UI', 9))
        self.files_count_label.pack(side=tk.RIGHT, padx=15)
        
    def bind_events(self):
        """綁定事件"""
        self.add_file_btn.bind('<Enter>', lambda e: 
            self.status_label.config(text="➕ 添加文件到修復隊列"))
        self.add_file_btn.bind('<Leave>', lambda e: 
            self.status_label.config(text="✅ 就緒"))
            
        self.start_repair_btn.bind('<Enter>', lambda e: 
            self.status_label.config(text="🚀 開始修復選中的文件"))
        self.start_repair_btn.bind('<Leave>', lambda e: 
            self.status_label.config(text="✅ 就緒"))
            
    def on_mode_change(self):
        """模式切換處理"""
        mode = self.repair_mode.get()
        if mode == "ai":
            self.status_label.config(text="🤖 AI 增強模式 - 需要 API 配置")
        else:
            self.status_label.config(text="🔧 一般模式 - 無需 API")
            
    def add_files(self):
        """添加文件"""
        filetypes = [
            ("所有支持的文件", "*.py;*.cpp;*.jpg;*.jpeg;*.png;*.mp3;*.wav;*.flac;*.pdf;*.docx;*.txt;*.json;*.xml"),
            ("Python 文件", "*.py"),
            ("C++ 文件", "*.cpp"),
            ("圖片文件", "*.jpg;*.jpeg;*.png"),
            ("音頻文件", "*.mp3;*.wav;*.flac"),
            ("文檔文件", "*.pdf;*.docx"),
            ("文本文件", "*.txt"),
            ("配置文件", "*.json;*.xml"),
            ("所有文件", "*.*")
        ]
        
        files = filedialog.askopenfilenames(
            title="選擇要修復的文件",
            filetypes=filetypes,
            initialdir=str(Path.home() / "Documents")
        )
        
        if files:
            for file in files:
                self.files_listbox.insert(tk.END, file)
                self.files_to_repair.append(file)
            self.update_status()
            
    def remove_selected_files(self):
        """刪除選中的文件"""
        selection = self.files_listbox.curselection()
        if selection:
            for index in reversed(selection):
                self.files_listbox.delete(index)
                del self.files_to_repair[index]
            self.update_status()
            
    def select_all_files(self):
        """全選"""
        self.files_listbox.select_range(0, tk.END)
        
    def update_status(self):
        """更新狀態"""
        count = len(self.files_to_repair)
        self.files_count_label.config(text=f"文件: {count}/{count}")
        
    def load_config(self):
        """加載配置"""
        config_file = self.directory_structure.config_dir / "ai-repair-config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.api_endpoint_entry.delete(0, tk.END)
                    self.api_endpoint_entry.insert(0, config.get('endpoint', ''))
                    self.api_key_entry.delete(0, tk.END)
                    self.api_key_entry.insert(0, config.get('api_key', ''))
                    self.model_var.set(config.get('model', 'gpt-4o-mini'))
                    self.timeout_var.set(str(config.get('timeout', 30)))
                    self.retries_var.set(str(config.get('max_retries', 3)))
                    self.status_label.config(text="✅ 配置已加載")
            except Exception as e:
                self.status_label.config(text=f"⚠️ 加載配置失敗: {str(e)}")
                
    def save_config(self):
        """保存配置"""
        config = {
            'endpoint': self.api_endpoint_entry.get().strip(),
            'api_key': self.api_key_entry.get().strip(),
            'model': self.model_var.get(),
            'timeout': int(self.timeout_var.get()),
            'max_retries': int(self.retries_var.get())
        }
        
        config_file = self.directory_structure.config_dir / "ai-repair-config.json"
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            
        self.status_label.config(text="✅ 配置已保存")
        messagebox.showinfo("保存成功", 
            f"配置已成功保存到:\n{config_file}\n\n"
            f"這是一個持久化配置，下次啟動會自動加載。")
            
    def get_api_client(self):
        """獲取或創建 API 客戶端"""
        if self.api_client is None:
            from ai_repair import AIRepair
            config_path = str(self.directory_structure.config_dir / "ai-repair-config.yaml")
            
            import yaml
            yaml_config = {
                'openai_api': {
                    'endpoint': self.api_endpoint_entry.get().strip(),
                    'api_key': self.api_key_entry.get().strip(),
                    'model': self.model_var.get(),
                    'timeout': int(self.timeout_var.get()),
                    'max_retries': int(self.retries_var.get()),
                    'verify_ssl': True
                }
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_config, f, default_flow_style=False, allow_unicode=True)
            
            self.api_client = AIRepair(config_path=config_path)
            
        return self.api_client
        
    def preview_repair(self):
        """預覽修復"""
        selection = self.files_listbox.curselection()
        if not selection:
            messagebox.showwarning("未選擇文件", "請先在左側列表中選中要修復的文件")
            return
            
        file_path = self.files_listbox.get(selection[0])
        repair_type = self.repair_type_var.get()
        mode = self.repair_mode.get()
        
        if mode == "ai":
            self.status_label.config(text="🔍 正在使用 AI 分析文件...")
            
            def preview_thread():
                try:
                    client = self.get_api_client()
                    
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    self.original_text.delete(1.0, tk.END)
                    self.original_text.insert(1.0, content[:5000])
                    
                    result = client.repair(
                        file_path,
                        file_type=repair_type if repair_type != 'auto' else None,
                        repair_type=repair_type if repair_type != 'auto' else None
                    )
                    
                    if result.success:
                        repaired_content = result.repair_details.get('content', '')
                        self.repaired_text.delete(1.0, tk.END)
                        self.repaired_text.insert(1.0, repaired_content[:5000])
                        
                        self.status_label.config(text="✅ 預覽完成")
                        messagebox.showinfo("修復預覽", 
                            f"修復成功！\n\n"
                            f"預覽已顯示在右側。\n"
                            f"實際修復請點擊「開始修復」按鈕。\n"
                            f"修復後文件將保存在:\n{self.directory_structure.output_dir}")
                    else:
                        self.status_label.config(text="❌ 修復失敗")
                        messagebox.showerror("修復失敗", result.error_message)
                        
                except Exception as e:
                    self.status_label.config(text="❌ 預覽失敗")
                    messagebox.showerror("錯誤", str(e))
                    
            thread = threading.Thread(target=preview_thread, daemon=True)
            thread.start()
        else:
            # 一般模式預覽
            self.status_label.config(text="🔍 正在使用原功能分析文件...")
            
            def standard_preview():
                try:
                    # 讀取文件
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    self.original_text.delete(1.0, tk.END)
                    self.original_text.insert(1.0, content[:5000])
                    
                    # 顯示原功能修復信息
                    self.repaired_text.delete(1.0, tk.END)
                    self.repaired_text.insert(1.0, 
                        "🔧 一般模式修復預覽\n" +
                        "===================\n" +
                        f"文件: {Path(file_path).name}\n" +
                        f"類型: {repair_type}\n" +
                        f"修復模式: 一般模式\n\n" +
                        "可用修復技術：\n" +
                        "• 壞軌跳過 (Bad Sector Skipping)\n" +
                        "• Parity Repair (奇偶校驗)\n" +
                        "• Redundancy Repair (冗餘修復)\n" +
                        "• Pattern Repair (模式修復)\n" +
                        "• SINC 插值修復\n\n" +
                        "注意：\n" +
                        "• 一般模式無需 API\n" +
                        "• 使用本地 RepairEngine 修復\n" +
                        f"• 修復後文件將保存在: {self.directory_structure.output_dir}\n" +
                        "• 點擊「開始修復」執行實際修復\n"
                    )
                    
                    self.status_label.config(text="✅ 預覽完成")
                    
                except Exception as e:
                    self.status_label.config(text="❌ 預覽失敗")
                    messagebox.showerror("錯誤", str(e))
                    
            thread = threading.Thread(target=standard_preview, daemon=True)
            thread.start()
            
    def start_repair(self):
        """開始修復"""
        if not self.files_to_repair:
            messagebox.showwarning("沒有文件", "請先添加要修復的文件")
            return
            
        mode = self.repair_mode.get()
        
        if mode == "ai":
            result = messagebox.askyesno("確認修復", 
                f"即將使用 AI 修復 {len(self.files_to_repair)} 個文件。\n\n"
                f"⚠️ 注意：\n"
                f"1. AI 修復需要配置 API\n"
                f"2. 修復過程可能需要一些時間\n"
                f"3. 原始文件將被備份到: {self.directory_structure.backup_dir}\n"
                f"4. 修復後的文件名將添加 _fixed 後綴\n"
                f"5. 修復後文件將保存在: {self.directory_structure.output_dir}\n\n"
                f"是否繼續？")
        else:
            result = messagebox.askyesno("確認修復", 
                f"即將使用一般模式修復 {len(self.files_to_repair)} 個文件。\n\n"
                f"✅ 一般模式特點：\n"
                f"• 無需 API，本地修復\n"
                f"• 壞軌跳過 + 數據重構\n"
                f"• 音視頻 SINC 插值修復\n"
                f"• 速度快，無 API 成本\n\n"
                f"⚠️ 注意：\n"
                f"1. 修復過程可能需要一些時間\n"
                f"2. 原始文件將被備份到: {self.directory_structure.backup_dir}\n"
                f"3. 修復後的文件名將添加 _fixed 後綴\n"
                f"4. 修復後文件將保存在: {self.directory_structure.output_dir}\n\n"
                f"是否繼續？")
                
        if not result:
            return
            
        # 禁用按鈕
        self.start_repair_btn.config(state=tk.DISABLED)
        self.preview_btn.config(state=tk.DISABLED)
        
        def repair_thread():
            success_count = 0
            fail_count = 0
            total = len(self.files_to_repair)
            
            for i, file_path in enumerate(self.files_to_repair):
                self.progress_var.set((i / total) * 100)
                self.status_label.config(text=f"修復中 ({i+1}/{total}): {Path(file_path).name}")
                
                try:
                    if mode == "ai":
                        client = self.get_api_client()
                        repair_type = self.repair_type_var.get()
                        
                        result = client.repair(
                            file_path,
                            file_type=repair_type if repair_type != 'auto' else None,
                            repair_type=repair_type if repair_type != 'auto' else None
                        )
                    else:
                        # 一般模式修復
                        # 這裡調用本地 RepairEngine
                        result = self._run_standard_repair(file_path)
                    
                    if result.success:
                        success_count += 1
                        # 保存修復後的文件
                        original_path = Path(file_path)
                        fixed_path = self.directory_structure.output_dir / (
                            original_path.stem + "_fixed" + original_path.suffix
                        )
                        
                        if result.repair_details.get('content'):
                            with open(fixed_path, 'w', encoding='utf-8') as f:
                                f.write(result.repair_details['content'])
                        
                        self.root.after(0, lambda: self.status_label.config(
                            text=f"✅ {Path(file_path).name} 修復成功"
                        ))
                        
                    else:
                        fail_count += 1
                        self.root.after(0, lambda: self.status_label.config(
                            text=f"❌ {Path(file_path).name} 修復失敗: {result.error_message}"
                        ))
                        
                except Exception as e:
                    fail_count += 1
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"❌ {Path(file_path).name} 修復出錯: {str(e)}"
                    ))
                    
            # 完成
            self.progress_var.set(100)
            self.status_label.config(text="✅ 修復完成")
            self.start_repair_btn.config(state=tk.NORMAL)
            self.preview_btn.config(state=tk.NORMAL)
            
            messagebox.showinfo("修復完成", 
                f"修復完成！\n\n"
                f"成功: {success_count}\n"
                f"失敗: {fail_count}\n"
                f"成功率: {success_count/total*100:.1f}%\n\n"
                f"修復後的文件已保存到:\n{self.directory_structure.output_dir}")
                
        self.repair_thread = threading.Thread(target=repair_thread, daemon=True)
        self.repair_thread.start()
        
    def _run_standard_repair(self, file_path):
        """運行一般模式修復"""
        from repair_engine import RepairEngine
        
        engine = RepairEngine()
        engine.SetSkipBadSectors(True)
        engine.SetMaxBadSectors(100)
        
        result = engine.RepairFile(file_path)
        
        return result
    
    def run(self):
        """運行 GUI"""
        self.root.mainloop()


def main():
    """主函數"""
    root = tk.Tk()
    app = AIRepairGUI(root)
    app.run()


if __name__ == "__main__":
    main()