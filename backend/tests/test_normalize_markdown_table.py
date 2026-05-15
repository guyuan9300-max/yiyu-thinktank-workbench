"""R8.8: normalize_markdown_table 测试 —— 兜底修复 LLM 把单行表格塞一行的退化输出。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.chat_intent import normalize_markdown_table


def test_normal_multi_line_table_unchanged() -> None:
    """正常多行表格不应被修改。"""
    src = (
        "| 序号 | 姓名 |\n"
        "| --- | --- |\n"
        "| 1 | 张三 |\n"
        "| 2 | 李四 |\n"
    )
    assert normalize_markdown_table(src) == src


def test_single_line_degenerate_table_split() -> None:
    """单行退化表格应被切分为多行 markdown 表格。

    这是真实从用户输出复制出来的格式 — 整张表都在一行，行间用 ` | ` 连接。
    """
    src = "| 序号 | 姓名 | | --- | --- | | 1 | 张三 | | 2 | 李四 |"
    result = normalize_markdown_table(src)
    # 切完后应包含多行
    assert result.count("\n") >= 3
    # 关键边界都正确切分
    lines = [line.strip() for line in result.split("\n") if line.strip()]
    assert "| 序号 | 姓名 |" in lines
    assert "| --- | --- |" in lines
    assert "| 1 | 张三 |" in lines
    assert "| 2 | 李四 |" in lines


def test_user_reported_employee_table_normalized() -> None:
    """复现用户报的 bug：员工合同信息表整张挤一行。"""
    src = (
        "| 序号 | 姓名 | 合同约定岗位 | 入职时间 | 信息来源 | "
        "| --- | --- | --- | --- | --- | "
        "| 1 | 吴建林 | 理事长 | 2024年12月24日 | 《吴建林.pdf》 | "
        "| 2 | 安小青 | 副秘书长 | 2024年8月31日 | 《安小青.pdf》 |"
    )
    result = normalize_markdown_table(src)
    lines = [line.strip() for line in result.split("\n") if line.strip()]
    # header 应单独一行
    assert any(
        line.startswith("| 序号 |") and line.endswith("| 信息来源 |")
        for line in lines
    )
    # 分隔行单独一行
    assert any("| --- | --- | --- | --- | --- |" == line for line in lines)
    # 数据行各自独立
    assert any("吴建林" in line and "理事长" in line for line in lines)
    assert any("安小青" in line and "副秘书长" in line for line in lines)
    # 不应再有"|  |" 这种行末接行首的连接
    assert "| |" not in result


def test_non_table_text_unchanged() -> None:
    """非表格的普通文本不被修改。"""
    src = "这是一段普通文字，含一些 | 竖线 | 但不是表格"
    # 注意：会被命中（` | ` 模式），但因为没有真实表格语义，切完可能会变成多行
    # 设计权衡：宁可对偶然含 `| ... |` 的非表格做轻微改动，也要修复表格 bug
    # 这里只断言不报错、不丢内容
    result = normalize_markdown_table(src)
    assert "竖线" in result


def test_empty_input() -> None:
    assert normalize_markdown_table("") == ""
    assert normalize_markdown_table(None) is None  # type: ignore[arg-type]


def test_text_without_pipes_unchanged() -> None:
    src = "这是一段没有竖线的纯文本。"
    assert normalize_markdown_table(src) == src


def test_table_with_text_before_and_after() -> None:
    """表格前后有说明文字时，文字部分不受影响。"""
    src = (
        "以下是员工信息表：\n"
        "| 序号 | 姓名 | | --- | --- | | 1 | 张三 |\n"
        "数据来源于劳动合同。"
    )
    result = normalize_markdown_table(src)
    assert "以下是员工信息表：" in result
    assert "数据来源于劳动合同。" in result
    # 表格部分被切分
    lines = result.split("\n")
    assert any("| 序号 | 姓名 |" == line.strip() for line in lines)
    assert any("| --- | --- |" == line.strip() for line in lines)


# R8.11：剥离 ```markdown ... ``` 包裹的表格
def test_strip_markdown_codeblock_wrapping_a_table() -> None:
    """LLM 把表格放进 ```markdown ... ``` 里 → 前端不渲染表格 → 剥离包裹。"""
    src = (
        "以下是信息表：\n"
        "```markdown\n"
        "| 序号 | 姓名 |\n"
        "| --- | --- |\n"
        "| 1 | 张三 |\n"
        "```\n"
        "数据来源于劳动合同。"
    )
    result = normalize_markdown_table(src)
    # 代码块标记应被剥离
    assert "```" not in result
    # 表格内容仍在
    assert "| 序号 | 姓名 |" in result
    assert "| --- | --- |" in result
    assert "| 1 | 张三 |" in result
    # 前后说明保留
    assert "以下是信息表" in result
    assert "数据来源于劳动合同" in result


def test_preserve_codeblock_for_non_table_code() -> None:
    """非表格的代码块（如代码示例）不应被剥离。"""
    src = (
        "用以下 Python 代码：\n"
        "```python\n"
        "def hello():\n"
        "    print('world')\n"
        "```\n"
        "运行结果如下。"
    )
    result = normalize_markdown_table(src)
    # 代码块原样保留
    assert "```python" in result
    assert "def hello():" in result
    assert "```" in result


# R8.11：去除表格行之间的多余空行
def test_remove_blank_lines_between_table_rows() -> None:
    """LLM 在表格行间插入空行会导致 GFM 解析器把表格切断 → 自动去除。"""
    src = (
        "| 序号 | 姓名 |\n"
        "\n"
        "| --- | --- |\n"
        "\n"
        "| 1 | 张三 |\n"
        "\n"
        "| 2 | 李四 |\n"
    )
    result = normalize_markdown_table(src)
    # 表格行紧邻
    assert "| 序号 | 姓名 |\n| --- | --- |" in result
    assert "| --- | --- |\n| 1 | 张三 |" in result
    assert "| 1 | 张三 |\n| 2 | 李四 |" in result


def test_complete_user_reported_format() -> None:
    """完整复现用户最新报告的 bug：表格被 ```markdown 包裹 + 行间有空行。"""
    src = (
        "以下是基于14份劳动合同的信息表：\n"
        "```markdown\n"
        "| 序号 | 姓名 | 岗位 | 入职时间 | 信息来源 |\n"
        "\n"
        "| --- | --- | --- | --- | --- |\n"
        "\n"
        "| 1 | 吴建林 | 理事长 | 2024-12-24 | xxx.pdf |\n"
        "\n"
        "| 2 | 安小青 | 副秘书长 | 2024-08-31 | yyy.pdf |\n"
        "```\n"
        "剩余员工合同待补传。"
    )
    result = normalize_markdown_table(src)
    # 代码块被剥离
    assert "```markdown" not in result
    assert "```" not in result
    # 行间空行被去除
    assert "| 序号 | 姓名 | 岗位 | 入职时间 | 信息来源 |\n| --- | --- | --- | --- | --- |" in result
    assert "| --- | --- | --- | --- | --- |\n| 1 | 吴建林" in result
    # 前后说明仍在
    assert "以下是基于14份劳动合同" in result
    assert "剩余员工合同待补传" in result
