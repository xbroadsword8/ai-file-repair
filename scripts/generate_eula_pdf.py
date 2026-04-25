"""
Generate PDF version of EULA
生成 EULA PDF 版本，用於法律存檔和專業展示
"""

from fpdf import FPDF
import markdown
import os
from pathlib import Path

class EULAPDFGenerator:
    def __init__(self):
        self.pdf = FPDF()
        self.pdf.add_font('SimSun', '', 'simsun.ttf', uni=True)
        self.pdf.set_font('SimSun', '', 12)
        
    def generate_pdf(self, md_path, pdf_path):
        """從 Markdown 生成 PDF"""
        # 讀取 Markdown
        with open(md_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()
        
        # 轉換為 HTML
        html = markdown.markdown(
            markdown_text,
            extensions=['extra', 'toc', 'nl2br']
        )
        
        # 添加頁面
        self.pdf.add_page()
        
        # 標題
        self.pdf.set_font('SimSun', 'B', 16)
        self.pdf.cell(0, 10, 'AI File Repair', ln=True, align='C')
        self.pdf.set_font('SimSun', '', 12)
        self.pdf.cell(0, 10, '最終用戶許可協議', ln=True, align='C')
        self.pdf.ln(20)
        
        # EULA 內容（簡單渲染）
        lines = markdown_text.split('\n')
        for line in lines:
            if line.startswith('#'):
                self.pdf.set_font('SimSun', 'B', 14)
            else:
                self.pdf.set_font('SimSun', '', 12)
            
            # 簡單處理
            text = line.lstrip('#').strip()
            if text:
                self.pdf.multi_cell(0, 8, text)
                self.pdf.ln(5)
        
        # 保存
        self.pdf.output(pdf_path)
        print(f"✓ PDF 已生成: {pdf_path}")

def main():
    script_dir = Path(__file__).parent
    eula_md = script_dir / "../windows/EULA-TW.md"
    eula_pdf = script_dir / "../windows/EULA-TW.pdf"
    
    generator = EULAPDFGenerator()
    generator.generate_pdf(str(eula_md), str(eula_pdf))

if __name__ == "__main__":
    main()
