"""
EULA Display Module
在安裝/啟動時顯示最終用戶許可協議
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import sys
import os

class EULADialog:
    def __init__(self, parent=None):
        self.parent = parent
        self.accepted = False
        self.eula_path = os.path.join(
            os.path.dirname(__file__), 
            '../windows/EULA-TW.md'
        )
    
    def show_eula(self):
        """顯示 EULA 對話框"""
        if self.parent:
            window = tk.Toplevel(self.parent)
        else:
            window = tk.Tk()
            window.withdraw()  # 隱藏主視窗
        
        window.title("AI File Repair - 使用許可協議")
        window.geometry("800x600")
        window.resizable(True, True)
        
        # 設置最小尺寸
        window.minsize(600, 400)
        
        # 主框架
        main_frame = tk.Frame(window, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 標題
        title_label = tk.Label(
            main_frame, 
            text="FINAL USER LICENSE AGREEMENT",  # EULA-TW.md
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # 警告標語
        warning_label = tk.Label(
            main_frame,
            text="⚠️ 請仔細閱讀以下協議 ⚠️",
            font=("Helvetica", 12, "bold"),
            fg="red"
        )
        warning_label.pack(pady=(0, 10))
        
        # EULA 內容區域
        content_frame = tk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 滾動文字框
        text_widget = scrolledtext.ScrolledText(
            content_frame,
            wrap=tk.WORD,
            width=80,
            height=20,
            font=("Courier", 10)
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # 讀取並顯示 EULA 內容
        try:
            with open(self.eula_path, 'r', encoding='utf-8') as f:
                eula_content = f.read()
                text_widget.insert('1.0', eula_content)
                text_widget.config(state=tk.DISABLED)  # 只讀模式
        except FileNotFoundError:
            text_widget.insert('1.0', "EULA 文件未找到！")
        
        # 按鈕框架
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        # 勾選框
        self.accept_var = tk.BooleanVar()
        accept_check = tk.Checkbutton(
            button_frame,
            text="我已閱讀並同意上述所有條款",
            variable=self.accept_var,
            font=("Helvetica", 11)
        )
        accept_check.pack(side=tk.LEFT, padx=10)
        
        # 按鈕
        def on_accept():
            if self.accept_var.get():
                self.accepted = True
                if self.parent:
                    window.destroy()
                else:
                    window.quit()
            else:
                messagebox.showwarning("請確認", "請勾選「我已閱讀並同意上述所有條款」")
        
        def on_reject():
            self.accepted = False
            if self.parent:
                window.destroy()
            else:
                window.quit()
        
        accept_button = tk.Button(
            button_frame,
            text="我接受",
            command=on_accept,
            bg="#4CAF50",
            fg="white",
            font=("Helvetica", 11, "bold"),
            padx=20,
            pady=5
        )
        accept_button.pack(side=tk.RIGHT, padx=5)
        
        reject_button = tk.Button(
            button_frame,
            text="我不接受",
            command=on_reject,
            bg="#f44336",
            fg="white",
            font=("Helvetica", 11),
            padx=20,
            pady=5
        )
        reject_button.pack(side=tk.RIGHT, padx=5)
        
        # 如果沒有父視窗，進入主循環
        if not self.parent:
            window.deiconify()
            window.mainloop()
        
        return self.accepted

# 測試
if __name__ == "__main__":
    app = EULADialog()
    result = app.show_eula()
    print(f"EULA Accepted: {result}")
    sys.exit(0 if result else 1)
