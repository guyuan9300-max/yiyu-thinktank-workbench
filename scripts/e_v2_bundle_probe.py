#!/usr/bin/env python3
"""策略 D 关键验证: knowledge_v2.retrieve_knowledge_bundle 对日慈 6 维度能否直接产出 citations。
若 coverage>0 + citations 有料, 则战略陪伴可一行 import 切换到 v2 检索栈, 跳过 document_chunks 桥接整件事。"""
import sys, os, pathlib, traceback
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services.knowledge_v2 import retrieve_knowledge_bundle as v2_retrieve
db = Database(DD / "app.db")
RICI = "client_284afd836e"
DIMS = [
    ("essence本质", "日慈基金会的核心使命价值观与战略本质定位"),
    ("cooperation合作", "日慈基金会与益语的合作关系陪伴内容"),
    ("business_intro业务", "日慈基金会主营业务与公益项目介绍"),
    ("people人物", "日慈基金会关键人物负责人与决策者"),
    ("timeline时间线", "日慈基金会战略陪伴的关键时间节点与里程碑"),
    ("next_steps下一步", "日慈基金会下一步行动计划与待推进事项"),
]
print(f"{'维度':<22} {'coverage':>9} {'citations':>10} {'failure':<22}")
print("-" * 70)
total_cits = 0
for name, q in DIMS:
    try:
        b = v2_retrieve(db, DD, RICI, q)
        cits = list(getattr(b, "citations", []) or [])
        total_cits += len(cits)
        cov = float(getattr(b, "coverage", 0.0) or 0.0)
        fr = getattr(b, "failure_reason", None) or "-"
        print(f"{name:<22} {cov:>9.3f} {len(cits):>10} {str(fr)[:22]:<22}")
    except Exception:
        print(f"{name:<22} ERR\n" + traceback.format_exc()[-500:])
print("-" * 70)
print(f"6 维度总 citations: {total_cits}")
print("")
print("=== 抽样 next_steps 的前 3 条 citations(看 excerpt 是不是真有料)===")
try:
    b = v2_retrieve(db, DD, RICI, "日慈基金会下一步行动计划与待推进事项")
    for c in (b.citations or [])[:3]:
        title = str(getattr(c, "title", "") or "")[:30]
        section = str(getattr(c, "section_label", "") or "")[:18]
        excerpt = str(getattr(c, "excerpt", "") or "").replace("\n", " ")[:130]
        score = float(getattr(c, "score", 0.0) or 0.0)
        print(f"  · [{score:.2f}] {title} / {section}")
        print(f"      {excerpt}")
except Exception:
    print(traceback.format_exc()[-500:])
print("\ndone")
