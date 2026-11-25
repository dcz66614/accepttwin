#!/usr/bin/env python3
"""把冻结的 md 规格文件转为 docx（只读转换，不修改源文件）。

用法：python3 build_docx.py <input.md> <output.docx>
只做一次性生成；验证 docx 时用只读文本提取核对内容，绝不靠重跑本脚本来“验证”。
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def build(md_path: Path, docx_path: Path) -> None:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(6)

    lines = md_path.read_text(encoding="utf-8").split("\n")
    i = 0
    in_code = False
    table_buf: list[list[str]] = []

    def flush_table() -> None:
        nonlocal table_buf
        if not table_buf:
            return
        rows = table_buf
        table_buf = []
        if len(rows) < 2:
            for r in rows:
                doc.add_paragraph(" | ".join(r))
            return
        t = doc.add_table(rows=0, cols=len(rows[0]))
        t.style = "Table Grid"
        for ri, row in enumerate(rows):
            cells = t.add_row().cells
            for ci, val in enumerate(row):
                if ci < len(cells):
                    cells[ci].text = val
                    if ri == 0:
                        for p in cells[ci].paragraphs:
                            for run in p.runs:
                                run.bold = True
        doc.add_paragraph("")

    while i < len(lines):
        ln = lines[i]
        i += 1
        s = ln.strip()
        if s.startswith("```"):
            flush_table()
            in_code = not in_code
            continue
        if in_code:
            p = doc.add_paragraph(ln)
            for run in p.runs:
                run.font.name = "Consolas"
                run.font.size = Pt(9)
            continue
        if not s:
            flush_table()
            continue
        if s == "---":
            continue
        if s.startswith("| ") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # markdown 表格分隔行
            table_buf.append(cells)
            continue
        flush_table()
        m = re.match(r"^(#{1,4}) (.*)$", s)
        if m:
            doc.add_heading(m.group(2), level=len(m.group(1)))
            continue
        if s.startswith(("• ", "- ")):
            doc.add_paragraph(s[2:], style="List Bullet")
            continue
        p = doc.add_paragraph(s)
        if s.startswith("注：") or s.startswith("README 一句话"):
            for run in p.runs:
                run.italic = True

    flush_table()
    doc.save(str(docx_path))
    print(f"{docx_path} written")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: build_docx.py <input.md> <output.docx>", file=sys.stderr)
        sys.exit(2)
    build(Path(sys.argv[1]), Path(sys.argv[2]))
