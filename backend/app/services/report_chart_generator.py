"""报告信息图生成器（matplotlib 后端）。

提供报告里常用图表的统一接口：
- commit 类型饼图（pie）
- 进度横向条形图（progress_bar_h）
- 时间线（timeline）
- 风险矩阵气泡图（risk_bubble）
- 完成度对比柱状图（completion_grouped_bar）

所有函数返回 PNG bytes，便于直接插入 docx。
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Sequence

import matplotlib
matplotlib.use("Agg")  # 无头后端
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager, rcParams

# ============ 中文字体配置 ============
# Linux sandbox 用 Droid Sans Fallback / Noto Sans CJK；Mac 用 PingFang SC
_CN_FONT_CANDIDATES = [
    "PingFang SC",
    "Heiti SC",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "WenQuanYi Zen Hei",
    "Droid Sans Fallback",
    "DejaVu Sans",
]

def _pick_cn_font() -> str:
    available = {f.name for f in font_manager.fontManager.ttflist}
    for cand in _CN_FONT_CANDIDATES:
        if cand in available:
            return cand
    return "DejaVu Sans"

CN_FONT = _pick_cn_font()
# 字体回退链：CJK 字体优先（解决中文方框）+ 后备 ASCII 字体
# matplotlib 在 3.6+ 支持 font.family 为列表实现真正回退
rcParams["font.family"] = [CN_FONT, "DejaVu Sans"]
rcParams["font.sans-serif"] = [CN_FONT, "DejaVu Sans", "Liberation Sans"]
rcParams["axes.unicode_minus"] = False  # 负号显示


# ============ 配色（与报告主体一致）============
BRAND = "#2E75B6"
BRAND_LIGHT = "#5B9BD5"
BRAND_DARK = "#1F4E79"
GREEN = "#2EA047"
YELLOW = "#E69F00"
RED = "#C0392B"
GREY = "#888888"
GREY_LIGHT = "#DDDDDD"
BG_CARD = "#F5F8FB"


@dataclass(frozen=True)
class ChartStyle:
    """统一的图表样式 token。"""
    title_size: float = 14.0
    label_size: float = 11.0
    tick_size: float = 10.0
    annotation_size: float = 9.0
    brand_color: str = BRAND
    dpi: int = 150


STYLE = ChartStyle()


def _save_to_bytes(fig) -> bytes:
    """保存 figure 为 PNG bytes 并关闭 figure。"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=STYLE.dpi, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ============ 1. Commit 类型饼图 ============

def pie_commit_breakdown(
    *,
    title: str = "本期 commit 类型分布",
    labels: Sequence[str],
    counts: Sequence[int],
    colors: Sequence[str] | None = None,
) -> bytes:
    """生成 commit 类型饼图。"""
    fig, ax = plt.subplots(figsize=(6, 4))
    if colors is None:
        palette = [BRAND, BRAND_LIGHT, "#A5C8E6", GREY_LIGHT]
        colors = list(palette[:len(labels)])

    wedges, texts, autotexts = ax.pie(
        counts,
        labels=labels,
        colors=colors,
        autopct=lambda pct: f"{pct:.0f}%",
        startangle=90,
        textprops={"fontsize": STYLE.label_size},
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")

    # 图例放右侧
    total = sum(counts)
    legend_labels = [f"{l}（{c} 个）" for l, c in zip(labels, counts)]
    ax.legend(wedges, legend_labels,
              loc="center left", bbox_to_anchor=(1.0, 0.5),
              fontsize=STYLE.annotation_size, frameon=False)

    ax.set_title(f"{title}（共 {total} 个）",
                 fontsize=STYLE.title_size, fontweight="bold", color="#333333",
                 pad=12)
    return _save_to_bytes(fig)


# ============ 2. 进度横向条形图 ============

def progress_bar_h(
    *,
    title: str,
    items: Sequence[str],
    before: Sequence[float],
    after: Sequence[float],
    target: float | None = None,
) -> bytes:
    """生成 before/after 对比的横向进度条。

    Args:
        items: 模块名列表
        before: 期初完成度（0-100）
        after: 期末完成度（0-100）
        target: 可选的目标线（如 50）
    """
    y = list(range(len(items)))
    fig_h = max(3.5, 0.55 * len(items) + 1.2)
    fig, ax = plt.subplots(figsize=(9, fig_h))

    # 背景灰条（0-100）
    ax.barh(y, [100] * len(items), color=GREY_LIGHT, height=0.55, alpha=0.4,
            edgecolor="none")
    # 期初浅色
    ax.barh(y, before, color=BRAND_LIGHT, alpha=0.45, height=0.55,
            edgecolor="none", label="期初")
    # 期末深色
    ax.barh(y, after, color=BRAND, height=0.55, edgecolor="none", label="期末")

    # 数值标注
    for i, (b, a) in enumerate(zip(before, after)):
        delta = a - b
        delta_text = f" (+{delta:.0f}%)" if delta > 0.5 else ""
        ax.text(a + 1.5, i, f"{a:.0f}%{delta_text}",
                va="center", ha="left",
                fontsize=STYLE.annotation_size, color="#333333")

    ax.set_yticks(y)
    ax.set_yticklabels(items, fontsize=STYLE.label_size)
    ax.invert_yaxis()
    ax.set_xlim(0, 115)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"],
                       fontsize=STYLE.tick_size, color=GREY)
    ax.tick_params(axis="y", colors="#333333", length=0)
    ax.tick_params(axis="x", colors=GREY, length=0)
    ax.spines[:].set_visible(False)
    ax.grid(axis="x", linestyle="--", linewidth=0.5, color=GREY_LIGHT)

    if target is not None:
        ax.axvline(target, color=RED, linestyle="--", linewidth=1.2, alpha=0.6)
        ax.text(target + 0.5, -0.7, f"目标 {target:.0f}%",
                color=RED, fontsize=STYLE.annotation_size)

    ax.set_title(title, fontsize=STYLE.title_size, fontweight="bold",
                 color="#333333", pad=12, loc="left")
    ax.legend(loc="lower right", fontsize=STYLE.annotation_size, frameon=False)
    return _save_to_bytes(fig)


# ============ 3. 时间线 ============

def timeline(
    *,
    title: str,
    events: Sequence[tuple[str, str, str]],  # (date, label, status)
) -> bytes:
    """生成事件线时间轴。

    status ∈ {"done", "in_progress", "planned"}
    """
    status_color = {
        "done": GREEN,
        "in_progress": YELLOW,
        "planned": GREY,
    }
    n = len(events)
    fig, ax = plt.subplots(figsize=(11, max(3.0, 0.7 * n + 1.2)))

    # 主线
    ax.axvline(0.05, ymin=0.02, ymax=0.98, color=BRAND, linewidth=2.5,
               alpha=0.85, solid_capstyle="round")

    for i, (date, label, status) in enumerate(events):
        y = n - 1 - i
        color = status_color.get(status, GREY)
        # 节点圆点
        ax.scatter(0.05, y, s=220, color=color, edgecolor="white",
                   linewidths=2.5, zorder=3)
        # 日期（左侧）
        ax.text(0.025, y, date,
                ha="right", va="center",
                fontsize=STYLE.label_size, fontweight="bold",
                color="#333333")
        # 内容（右侧）
        ax.text(0.085, y, label,
                ha="left", va="center",
                fontsize=STYLE.label_size,
                color="#333333")
        # 状态徽章
        status_text = {"done": "已完成", "in_progress": "进行中", "planned": "计划"}[status]
        ax.text(0.97, y, status_text,
                ha="right", va="center",
                fontsize=STYLE.annotation_size,
                color=color, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=color,
                          alpha=0.12, edgecolor="none"))

    ax.set_xlim(-0.05, 1.0)
    ax.set_ylim(-0.7, n - 0.3)
    ax.axis("off")
    ax.set_title(title, fontsize=STYLE.title_size, fontweight="bold",
                 color="#333333", pad=14, loc="left")
    return _save_to_bytes(fig)


# ============ 4. 完成度对比柱状图（双系列）============

def grouped_bar(
    *,
    title: str,
    categories: Sequence[str],
    series_a_name: str,
    series_a_values: Sequence[float],
    series_b_name: str,
    series_b_values: Sequence[float],
    y_label: str = "数量",
) -> bytes:
    """生成分组柱状图。"""
    import numpy as np
    x = np.arange(len(categories))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))

    bars_a = ax.bar(x - width / 2, series_a_values, width,
                    label=series_a_name, color=BRAND_LIGHT, edgecolor="white",
                    linewidth=1.5)
    bars_b = ax.bar(x + width / 2, series_b_values, width,
                    label=series_b_name, color=BRAND, edgecolor="white",
                    linewidth=1.5)

    # 数值标
    for bars in (bars_a, bars_b):
        for b in bars:
            height = b.get_height()
            if height > 0:
                ax.text(b.get_x() + b.get_width() / 2, height + 0.3,
                        f"{height:.0f}",
                        ha="center", va="bottom",
                        fontsize=STYLE.annotation_size, color="#333333")

    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=STYLE.label_size)
    ax.set_ylabel(y_label, fontsize=STYLE.label_size)
    ax.set_title(title, fontsize=STYLE.title_size, fontweight="bold",
                 color="#333333", pad=12, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color(GREY)
    ax.tick_params(colors=GREY, length=0)
    ax.tick_params(axis="x", labelcolor="#333333")
    ax.grid(axis="y", linestyle="--", linewidth=0.5, color=GREY_LIGHT)
    ax.set_axisbelow(True)
    ax.legend(fontsize=STYLE.annotation_size, frameon=False, loc="upper right")
    return _save_to_bytes(fig)


# ============ 5. 风险矩阵气泡图 ============

def risk_bubble(
    *,
    title: str,
    risks: Sequence[tuple[str, float, float, float]],  # (name, impact, prob, weight)
) -> bytes:
    """风险矩阵气泡图。
    impact / prob: 0-5 评分
    weight: 气泡大小（任意单位，最终归一化）
    """
    fig, ax = plt.subplots(figsize=(9, 6))

    # 背景区域分色
    ax.fill_between([0, 5], 0, 5, color=GREEN, alpha=0.04)  # 低风险背景
    ax.fill_between([0, 5], 2.5, 5, color=YELLOW, alpha=0.05)
    ax.fill_between([2.5, 5], 2.5, 5, color=RED, alpha=0.06)

    # 阈值参考线
    ax.axhline(2.5, color=GREY_LIGHT, linewidth=0.5, linestyle="--")
    ax.axvline(2.5, color=GREY_LIGHT, linewidth=0.5, linestyle="--")

    # 区域标签
    ax.text(0.8, 4.5, "高频低危", color=YELLOW, fontsize=10, fontweight="bold", alpha=0.7)
    ax.text(3.5, 4.5, "高频高危", color=RED, fontsize=10, fontweight="bold", alpha=0.7)
    ax.text(0.8, 0.5, "低频低危", color=GREEN, fontsize=10, fontweight="bold", alpha=0.7)
    ax.text(3.5, 0.5, "低频高危", color=YELLOW, fontsize=10, fontweight="bold", alpha=0.7)

    for name, impact, prob, weight in risks:
        # 颜色按象限
        if impact >= 2.5 and prob >= 2.5:
            color = RED
        elif impact >= 2.5 or prob >= 2.5:
            color = YELLOW
        else:
            color = GREEN
        # 气泡
        ax.scatter(impact, prob, s=weight * 80, color=color, alpha=0.55,
                   edgecolor=color, linewidth=2, zorder=3)
        # 标签
        ax.annotate(name, (impact, prob), xytext=(8, 0),
                    textcoords="offset points",
                    fontsize=STYLE.annotation_size, color="#333333",
                    va="center")

    ax.set_xlim(0, 5)
    ax.set_ylim(0, 5)
    ax.set_xticks([0, 1, 2, 3, 4, 5])
    ax.set_yticks([0, 1, 2, 3, 4, 5])
    ax.set_xlabel("影响程度（低 → 高）", fontsize=STYLE.label_size)
    ax.set_ylabel("发生概率（低 → 高）", fontsize=STYLE.label_size)
    ax.set_title(title, fontsize=STYLE.title_size, fontweight="bold",
                 color="#333333", pad=12, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color(GREY)
    ax.tick_params(colors=GREY, length=0)
    ax.grid(linestyle="--", linewidth=0.4, color=GREY_LIGHT, alpha=0.6)
    ax.set_axisbelow(True)
    return _save_to_bytes(fig)


# ============ 自检 ============

def main():
    import os
    out_dir = "/tmp/charts_test"
    os.makedirs(out_dir, exist_ok=True)

    samples = {
        "01_pie.png": pie_commit_breakdown(
            labels=["feat（特性）", "fix（修复）", "docs（文档）", "chore（杂项）"],
            counts=[22, 7, 6, 4],
        ),
        "02_progress.png": progress_bar_h(
            title="九大功能板块 Q1 完成度变化",
            items=["理解深度", "主动能力", "输入广度", "生产能力", "长期记忆",
                   "真计算能力", "协作能力", "外部接入", "反思自知"],
            before=[20, 15, 30, 15, 25, 5, 30, 25, 20],
            after=[70, 15, 30, 18, 27, 6, 32, 28, 22],
            target=50,
        ),
        "03_timeline.png": timeline(
            title="2026 Q1 关键里程碑",
            events=[
                ("Q1 前期", "客户计算中心 9 层架构审计", "done"),
                ("Q1 中期", "理解深度优化方案 + 执行计划", "done"),
                ("2026-04", "理解深度迭代 1 → 7 逐迭代落地", "done"),
                ("2026-05-07", "代码仓库整理 + 移动端解耦", "done"),
                ("2026-05-11", "V2.0 内测 DMG 发布", "done"),
                ("2026-05-12", "主动能力等剩余线程进入计划阶段", "in_progress"),
            ],
        ),
        "04_grouped.png": grouped_bar(
            title="commit 投入对比",
            categories=["feat", "fix", "docs", "chore"],
            series_a_name="Q4 2025",
            series_a_values=[10, 12, 3, 2],
            series_b_name="Q1 2026",
            series_b_values=[22, 7, 6, 4],
            y_label="commit 数",
        ),
        "05_risk.png": risk_bubble(
            title="V2.1 关键风险矩阵",
            risks=[
                ("AI Gateway 缺失", 4.5, 3.5, 4),
                ("sync outbox 无消费者", 3.8, 3.2, 3),
                ("主动能力空白", 4.0, 4.0, 4.5),
                ("生产能力只剩 Word", 3.5, 4.2, 3.5),
                ("真计算能力 5%", 4.8, 2.8, 4),
                ("Task #28 未完成", 2.5, 4.5, 2.5),
            ],
        ),
    }

    for name, png in samples.items():
        path = os.path.join(out_dir, name)
        with open(path, "wb") as f:
            f.write(png)
        print(f"  写入 {path} ({len(png) // 1024} KB)")

    print(f"\n✅ 5 张样图已生成在 {out_dir}")
    print(f"   中文字体使用：{CN_FONT}")


if __name__ == "__main__":
    main()
