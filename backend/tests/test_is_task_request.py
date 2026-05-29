"""R8.2：is_task_request 词表探测函数测试。

正例：任务型动词必须探测到
负例：分析型问题不能被误抓
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

# 从独立的 services/chat_intent 模块 import，避开 main.py 顶层副作用
from app.services.chat_intent import is_task_request


# ---- 正例：任务型动词必须探测到 ------------------------------------------

@pytest.mark.parametrize("prompt", [
    "根据C项目所有员工的合同，帮我做一张表",
    "帮我做表，包含姓名、岗位、入职时间",
    "做一份员工信息表",
    "做一张表对比 X 和 Y",
    "做个表汇总最近 3 个月的财务数据",
    "从合同里提取所有员工姓名",
    "抽取关键信息",
    "列出所有未签合同的员工",
    "列一下A组织的主要项目",
    "整理一份团队成员清单",
    "整理成 markdown 表格",
    "生成一份月度报告",
    "输出所有合作伙伴",
    "给我一份决策清单",
    "给一张项目时间表",
    "把会议纪要总结成行动清单",
    "把这段转成正式邮件",
    "改成更简洁的版本",
    "写一份给员工的通知",
    "写一封感谢信",
    "草拟合作协议",
    "起草一份方案",
    "帮我写一封邮件",
    "帮我整理一下",
    "帮我列下A组织核心人员",
])
def test_task_verbs_detected(prompt: str) -> None:
    assert is_task_request(prompt), f"任务型动词应被探测到：{prompt}"


# ---- 负例：分析型问题不能被误抓 ------------------------------------------

@pytest.mark.parametrize("prompt", [
    "A组织的战略有什么特点",
    "分析一下A组织的核心竞争力",
    "评估这个合作的风险",
    "判断这件事的影响",
    "讨论一下三飞轮的逻辑",
    "思考一下下一步该怎么做",
    "为什么用户留存率下降了",
    "客户的核心痛点是什么",
    "怎么看这次活动效果",
    "罗永浩给25岁自己的一封信",  # 看起来像写作，但用户没说"帮我写一份"
    "客户战略升级的关键节点",
    "解释一下这个判断",
])
def test_analysis_verbs_not_misdetected(prompt: str) -> None:
    assert not is_task_request(prompt), f"分析型问题不应被误抓：{prompt}"


# ---- 边界 case ---------------------------------------------------------

def test_empty_prompt_returns_false() -> None:
    assert is_task_request("") is False
    assert is_task_request("   ") is False


def test_whitespace_normalization() -> None:
    """空白字符不影响词表匹配（中文空格、tab、连续空格都正常）。"""
    assert is_task_request("帮 我 做 一 张 表") is True
    assert is_task_request("帮\t我\t做表") is True
    assert is_task_request("帮我  做  表") is True
