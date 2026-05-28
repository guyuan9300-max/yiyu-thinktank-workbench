#!/usr/bin/env python3
"""实测富化后日慈战略陪伴 6 维度的 retrieve_knowledge_bundle coverage + citations 内容。
验证"非CFFC bundle coverage=0"是否被富化修复。Qdrant 死/锁时自动 fallback FTS+lexical(生产真实路径)。"""
import sys, os, pathlib, traceback
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services.knowledge_base import retrieve_knowledge_bundle
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
for name, q in DIMS:
    try:
        b = retrieve_knowledge_bundle(db, DD, RICI, q)
        cits = list(getattr(b, "citations", []) or [])
        cov = float(getattr(b, "coverage", 0.0) or 0.0)
        fr = getattr(b, "failure_reason", None)
        print(f"\n【{name}】coverage={cov:.3f} citations={len(cits)} failure={fr}")
        for c in cits[:2]:
            t = str(getattr(c, "title", "") or "")[:26]
            ex = str(getattr(c, "excerpt", "") or "").replace("\n", " ")[:90]
            print(f"    · {t} | {ex}")
    except Exception:
        print(f"\n【{name}】ERR\n" + traceback.format_exc()[-600:])
print("\ndone")
