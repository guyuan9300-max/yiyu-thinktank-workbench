"""
generate_raw_evidence_response 的契约测试（R5）：

验证：
1. depth_mode=True 时 system_instruction 含"1500-2500 字"和"具体的项目名"等深度引导
2. depth_mode=False（默认）时 system_instruction 含"600～1200 字"短回答引导
3. strategic_pack 非空时 prompt 含 STRATEGIC 标记 + 战略素材内容
4. strategic_pack 为空时 prompt 不出现 STRATEGIC 标记
5. raw_evidence_pack 始终在 prompt 中可见

用 object.__new__ 跳过 AiService.__init__ 避开 Database 依赖；
patch _health_for_task 让健康检查通过；patch _qwen_generate 捕获实际 LLM 调用参数。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.ai import AiService


@dataclass
class _StubHealth:
    """模拟 AiHealth：让 health.provider 非 mock 且 ready=True，触发真实路径。"""
    provider: str = "doubao_seed_2_pro"
    ready: bool = True


def _make_ai_service_stub() -> tuple[AiService, list[dict[str, object]]]:
    """构造一个 AiService 实例，绕过 __init__，patch 关键 method 用于捕获参数。

    返回 (service, captured_calls)：每次 _qwen_generate 调用会追加到 captured_calls。
    """
    service = object.__new__(AiService)  # type: ignore[call-arg]

    captured_calls: list[dict[str, object]] = []

    def fake_health_for_task(self_: AiService, task_kind: str) -> _StubHealth:
        return _StubHealth()

    def fake_qwen_generate(  # noqa: ANN001
        self_: AiService,
        prompt: str,
        system_instruction: str,
        response_schema: object,
        **kwargs: object,
    ) -> str:
        captured_calls.append({
            "prompt": prompt,
            "system_instruction": system_instruction,
            "response_schema": response_schema,
            "kwargs": dict(kwargs),
        })
        return "## 一、xxx\n\n正文。\n\n## 二、yyy\n\n正文。"

    def fake_structured_from_plain_answer(self_: AiService, text: str):  # noqa: ANN001
        from app.models import AiStructuredResponse
        return AiStructuredResponse(
            content=text,
            judgment="",
            analysis="",
            actions="",
            timeline="",
        )

    # bind methods to instance
    AiService._health_for_task = fake_health_for_task  # type: ignore[method-assign]
    AiService._qwen_generate = fake_qwen_generate  # type: ignore[method-assign]
    AiService._structured_from_plain_answer = fake_structured_from_plain_answer  # type: ignore[method-assign]

    return service, captured_calls


def test_depth_mode_off_default_short_length() -> None:
    """depth_mode 默认 False 时，system_instruction 含'600～1200 字'。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="客户战略有什么特点",
        system_instruction="你是顾问助手。",
        raw_evidence_pack="原始资料 ABC",
    )
    assert calls, "应该调用一次 _qwen_generate"
    instruction = calls[0]["system_instruction"]
    assert "600" in instruction and "1200" in instruction
    # depth_mode 关键字不应出现
    assert "1500-2500" not in instruction
    assert "具体的项目名" not in instruction


def test_depth_mode_on_long_length_and_detail_rule() -> None:
    """depth_mode=True 时，system_instruction 含'1500-2500 字' + '具体的项目名'强引导。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="客户战略有什么特点",
        system_instruction="你是顾问助手。",
        raw_evidence_pack="原始资料 ABC",
        depth_mode=True,
    )
    instruction = calls[0]["system_instruction"]
    assert "1500-2500" in instruction
    assert "具体的项目名" in instruction
    assert "时间节点" in instruction
    # 旧的 600-1200 不应再生效
    assert "600～1200" not in instruction


def test_strategic_pack_injected_into_prompt() -> None:
    """strategic_pack 非空时，prompt 含 STRATEGIC 标记块和战略素材内容。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="x",
        system_instruction="y",
        raw_evidence_pack="原始资料 ABC",
        strategic_pack="DNA：差异化定位 = 前置心理教育",
    )
    prompt = calls[0]["prompt"]
    assert "战略素材包" in prompt
    assert "差异化定位 = 前置心理教育" in prompt
    assert "原始文档资料包" in prompt
    assert "原始资料 ABC" in prompt


def test_empty_strategic_pack_keeps_prompt_clean() -> None:
    """strategic_pack 为空（默认）时，prompt 不出现 STRATEGIC 标记块。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="x",
        system_instruction="y",
        raw_evidence_pack="原始资料 ABC",
    )
    prompt = calls[0]["prompt"]
    assert "战略素材包" not in prompt
    assert "原始资料 ABC" in prompt


def test_strategic_pack_and_depth_mode_combined() -> None:
    """同时传 strategic_pack + depth_mode=True，两者都生效。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="x",
        system_instruction="y",
        raw_evidence_pack="原始资料",
        strategic_pack="DNA 内容",
        depth_mode=True,
    )
    assert calls
    prompt = calls[0]["prompt"]
    instruction = calls[0]["system_instruction"]
    assert "DNA 内容" in prompt
    assert "战略素材包" in prompt
    assert "1500-2500" in instruction
    assert "具体的项目名" in instruction


def test_writing_skill_md_injected_at_top_of_system_instruction() -> None:
    """R6：writing_skill_md 非空时插到 system_instruction 最顶部，优先级最高。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="x",
        system_instruction="原始系统指令",
        raw_evidence_pack="原始资料",
        writing_skill_md="## 罗永浩风格\n长短句猛烈交错；段子手节奏。",
    )
    instruction = calls[0]["system_instruction"]
    assert "写作风格约束" in instruction
    assert "罗永浩风格" in instruction
    assert "长短句猛烈交错" in instruction
    # 风格块要在原始系统指令前面（优先级最高）
    style_pos = instruction.index("罗永浩风格")
    sys_pos = instruction.index("原始系统指令")
    assert style_pos < sys_pos, "写作风格块必须在原始系统指令前面"


def test_empty_writing_skill_md_keeps_instruction_clean() -> None:
    """writing_skill_md 为空（默认）时，system_instruction 不出现风格约束块。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="x",
        system_instruction="y",
        raw_evidence_pack="原始资料",
    )
    instruction = calls[0]["system_instruction"]
    assert "写作风格约束" not in instruction


# R7：创意度三档 prompt 注入测试
def test_creativity_mode_creative_injects_free_creation_block() -> None:
    """creative 档：system_instruction 含「自由创作模式」/「等同于通用 LLM」"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="给25岁自己写信",
        system_instruction="y",
        raw_evidence_pack="客户资料",
        strategic_pack="DNA 内容",
        creativity_mode="creative",
    )
    instruction = calls[0]["system_instruction"]
    prompt = calls[0]["prompt"]
    assert "创意优先" in instruction
    assert "通用 LLM" in instruction or "豆包通用窗口" in instruction
    # creative 档不喂客户资料给 LLM
    assert "客户资料" not in prompt
    assert "DNA 内容" not in prompt
    assert "战略素材包" not in prompt


def test_creativity_mode_balanced_injects_balanced_block_and_keeps_resources() -> None:
    """balanced 档：system_instruction 含「事实是骨头/语言是血肉」+ 客户资料仍喂入"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="写一段品牌话术",
        system_instruction="y",
        raw_evidence_pack="客户资料 ABC",
        strategic_pack="DNA 差异化定位",
        creativity_mode="balanced",
    )
    instruction = calls[0]["system_instruction"]
    prompt = calls[0]["prompt"]
    assert "兼顾资料" in instruction
    assert "事实是骨头" in instruction or "语言是血肉" in instruction
    # 资料仍喂入
    assert "客户资料 ABC" in prompt
    assert "DNA 差异化定位" in prompt


def test_creativity_mode_strict_injects_strict_constraints() -> None:
    """strict 档：system_instruction 含「严格基于资料」+「溯源标记」+「零编造容忍」"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="客户战略分析",
        system_instruction="y",
        raw_evidence_pack="客户资料",
        creativity_mode="strict",
    )
    instruction = calls[0]["system_instruction"]
    assert "完全客观" in instruction or "严格模式" in instruction
    assert "溯源标记" in instruction or "[资料" in instruction
    assert "零编造" in instruction


def test_default_creativity_mode_is_strict_when_not_specified() -> None:
    """generate_raw_evidence_response 默认 creativity_mode='strict'"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="x",
        system_instruction="y",
        raw_evidence_pack="原始资料",
    )
    instruction = calls[0]["system_instruction"]
    assert "完全客观" in instruction or "严格模式" in instruction


# R8：任务型 + 全局禁止元描述测试
def test_global_anti_meta_description_rule_present_in_all_modes() -> None:
    """R8.1：所有档位的 system_instruction 都必须含「不要描述如何完成」等反元文档引导。"""
    for mode in ("creative", "balanced", "strict"):
        service, calls = _make_ai_service_stub()
        service.generate_raw_evidence_response(
            prompt="x",
            system_instruction="y",
            raw_evidence_pack="资料",
            creativity_mode=mode,
        )
        instruction = calls[0]["system_instruction"]
        # 关键约束词
        assert "直接给出" in instruction or "直接给" in instruction
        assert "方法论" in instruction or "应该建立" in instruction or "字段提取规则" in instruction


def test_task_mode_off_default_no_task_block() -> None:
    """task_mode 默认 False 时，system_instruction 不含任务执行模式块。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="x",
        system_instruction="y",
        raw_evidence_pack="资料",
    )
    instruction = calls[0]["system_instruction"]
    assert "任务执行模式" not in instruction


def test_task_mode_on_injects_structured_output_block() -> None:
    """R8.4：task_mode=True 时 system_instruction 含「任务执行模式」+「markdown 表格」+「待补全」等关键字。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="帮我做一张员工合同信息表",
        system_instruction="y",
        raw_evidence_pack="合同资料",
        task_mode=True,
    )
    instruction = calls[0]["system_instruction"]
    assert "任务执行模式" in instruction
    assert "具体产物" in instruction or "直接产出" in instruction
    assert "markdown" in instruction.lower() or "标准 markdown" in instruction
    assert "待补全" in instruction
    # 同时确认仍然禁止元文档
    assert "数据源说明" in instruction or "字段提取规则" in instruction or "方法论" in instruction


def test_task_mode_prompt_uses_real_multiline_markdown_example() -> None:
    """R8.7：task_mode prompt 必须用真实多行 markdown 表格示范，
    不能用 `\\n` 字面字符串（之前的 bug：LLM 把 \\n 当字面意思导致整张表挤一行）。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="帮我做一张员工表",
        system_instruction="y",
        raw_evidence_pack="资料",
        task_mode=True,
    )
    instruction = calls[0]["system_instruction"]
    # 含真实换行的多行表格示范
    assert "| 序号 | 姓名 |" in instruction
    assert "| --- | --- |" in instruction
    assert "| 1 | 张三 |" in instruction
    # 含明确的"禁止单行"约束（R8.13 prompt 缩短后改为"禁止全塞一行"）
    assert (
        "禁止把所有行塞到同一行" in instruction
        or "禁止把所有行塞到一行" in instruction
        or "禁止全塞一行" in instruction
    )
    # **不应**包含字面的 \\n 字符串（这是之前的 bug）
    assert "|\\n|" not in instruction
    assert "| 列1 | 列2 |\\n| ---" not in instruction


def test_task_mode_uses_strategic_pack_as_file_catalog() -> None:
    """R8.15：task_mode 时 strategic_pack（应是精简的文件目录）会被喂入 prompt。

    R8.13 之前完全跳 strategic_pack 是过度激进——导致 LLM 看不到客户全部合同文件名。
    R8.15 改为：调用方传精简的「客户文件目录」（build_client_file_catalog 输出）作为 strategic_pack。
    """
    service, calls = _make_ai_service_stub()
    file_catalog = "【客户已上传的全部资料目录】\n- 张三-顾问-2024.1.1-2027.1.1.pdf\n- 李四-编辑-2024.5.1-2027.5.1.pdf"
    service.generate_raw_evidence_response(
        prompt="帮我做一张员工表",
        system_instruction="y",
        raw_evidence_pack="合同原文 ABC",
        strategic_pack=file_catalog,
        task_mode=True,
    )
    prompt = calls[0]["prompt"]
    # 文件目录进 prompt
    assert "客户已上传的全部资料目录" in prompt
    assert "张三-顾问-2024.1.1-2027.1.1.pdf" in prompt
    assert "李四-编辑-2024.5.1-2027.5.1.pdf" in prompt
    # 原始资料也在 + 检索命中部分有明确标记
    assert "合同原文 ABC" in prompt
    assert "检索命中的文档原文片段" in prompt


def test_task_mode_empty_strategic_pack_still_works() -> None:
    """task_mode + 空 strategic_pack（调用方没传文件目录）—— 仍然能跑，只是没有目录引导。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="帮我做一张员工表",
        system_instruction="y",
        raw_evidence_pack="合同原文 ABC",
        strategic_pack="",
        task_mode=True,
    )
    prompt = calls[0]["prompt"]
    assert "合同原文 ABC" in prompt
    # 没有 catalog 时也不会有 "检索命中的文档原文片段" 标记
    assert "检索命中的文档原文片段" not in prompt
    assert "客户已上传的全部资料目录" not in prompt


def test_task_mode_forces_enable_thinking_off() -> None:
    """R8.13：task_mode 时 enable_thinking 被强制覆盖为 False（加速生成，减少首字延迟）。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="帮我做一张员工表",
        system_instruction="y",
        raw_evidence_pack="资料",
        enable_thinking=True,  # 外部传 True
        task_mode=True,
    )
    # 检查最终传给 _qwen_generate 的 enable_thinking 是 False
    kwargs = calls[0]["kwargs"]
    assert kwargs.get("enable_thinking") is False, (
        f"task_mode=True 时 enable_thinking 应被强制 False，实际 {kwargs.get('enable_thinking')}"
    )


def test_non_task_mode_keeps_enable_thinking() -> None:
    """task_mode=False 时 enable_thinking 仍由外部参数控制（不影响普通分析型回答）。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="A组织战略有什么特点",
        system_instruction="y",
        raw_evidence_pack="资料",
        enable_thinking=True,
        task_mode=False,
    )
    kwargs = calls[0]["kwargs"]
    assert kwargs.get("enable_thinking") is True


def test_task_mode_prompt_does_not_self_sabotage_with_codeblock_example() -> None:
    """R8.10：task_mode prompt 的表格示范**不能**用 ```markdown ... ``` 包裹示范。
    这是之前的自爆 bug：LLM 学示范学到「输出表格用 ``` 包裹」→ 前端不渲染。
    """
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="帮我做一张员工表",
        system_instruction="y",
        raw_evidence_pack="资料",
        task_mode=True,
    )
    instruction = calls[0]["system_instruction"]
    # **不应**出现 ```markdown 包裹表格示范（直接 grep 即可，因为表格示范紧跟在 ```markdown 后）
    # 检查：不应有"```markdown\n| 序号"这种 pattern
    assert "```markdown\n| 序号" not in instruction
    assert "```markdown\n|" not in instruction
    # 同时显式约束词必须存在
    assert "禁止用 ```" in instruction or "禁止用 ``` 代码块" in instruction or "不要用 ``` 代码块" in instruction
    # 也要禁止表格行间空行（R8.13 prompt 缩短后改为"行之间不允许空行"）
    assert (
        "行之间禁止空行" in instruction
        or "行之间不能有空行" in instruction
        or "行之间不允许空行" in instruction
        or "禁止空行" in instruction
        or "不允许空行" in instruction
    )


def test_task_mode_prompt_instructs_to_enumerate_resource_index() -> None:
    """R9：task_mode prompt 必须引导 LLM「列出索引里所有相关条目」（不再 hardcode "目录"或"文件"，泛化为 5 域索引）。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="帮我做一张员工表",
        system_instruction="y",
        raw_evidence_pack="资料",
        task_mode=True,
    )
    instruction = calls[0]["system_instruction"]
    # R9 通用化：含「列出索引里所有相关条目」约束
    assert (
        "列出索引里所有相关条目" in instruction
        or "索引里所有相关条目" in instruction
    )
    # 资源索引 5 个域提及
    assert "客户资源索引" in instruction
    assert "projectModules" in instruction or "项目模块" in instruction
    assert "latestJudgments" in instruction or "已采纳判断" in instruction
    # 文件名解析引导
    assert "文件名" in instruction
    # 不需要等检索命中
    assert "不需要等检索命中" in instruction or "不需要等检索" in instruction


def test_task_mode_can_combine_with_creativity_mode() -> None:
    """task_mode 和 creativity_mode 是正交维度，可叠加生效。"""
    service, calls = _make_ai_service_stub()
    service.generate_raw_evidence_response(
        prompt="帮我整理一份客户判断列表",
        system_instruction="y",
        raw_evidence_pack="资料",
        creativity_mode="strict",
        task_mode=True,
    )
    instruction = calls[0]["system_instruction"]
    # 两个块都要在
    assert "任务执行模式" in instruction
    assert "完全客观" in instruction or "严格模式" in instruction
    # 任务块应该在创意度块之前（优先级更高）
    task_pos = instruction.index("任务执行模式")
    creativity_pos = instruction.index("完全客观") if "完全客观" in instruction else instruction.index("严格模式")
    assert task_pos < creativity_pos, "任务执行模式应在创意度块之前（优先级更高）"
