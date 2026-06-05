#!/usr/bin/env python3
"""Phase 0 度量脚手架:量一份"已填写"docx 的填充质量。

口径(对齐系统 status: value.startswith('【待确认】') 才算 missing):
  完整填  = 有内容且不含【待确认】
  局部    = 有实质内容 + 末尾局部【待确认】
  纯待确认 = 以【待确认】开头(真空)
  cite    = [实体.属性] 形式的字典/事实引用数(越多越锚定真数据)

用法: measure_template_fill.py <已填写.docx>
"""
import re
import sys

from docx import Document


def measure(path: str) -> dict:
    doc = Document(path)
    full, partial, missing = [], [], []
    cite_total = 0
    for table in doc.tables:
        for row in table.rows:
            cells = row.cells
            if len(cells) < 2:
                continue
            label = (cells[0].text or "").strip().split("\n")[0][:30]
            val = (cells[1].text or "").strip()
            if not label or label == "年度":
                continue
            cite_total += len(re.findall(r"\[[^\]]*\.", val))
            if val.startswith("【待确认"):
                missing.append(label)
            elif "【待确认" in val:
                partial.append(label)
            elif val:
                full.append(label)
    return {
        "full": full, "partial": partial, "missing": missing,
        "cite": cite_total,
        "filled_total": len(full) + len(partial),
        "missing_total": len(missing),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: measure_template_fill.py <已填写.docx>")
        sys.exit(1)
    m = measure(sys.argv[1])
    print(f"完整填 {len(m['full'])} / 局部 {len(m['partial'])} / 纯待确认 {len(m['missing'])}")
    print(f"系统口径: 已填 {m['filled_total']} | 待确认 {m['missing_total']} | cite {m['cite']}")
    print(f"  纯待确认字段: {m['missing']}")
