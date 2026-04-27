from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from app.db import Database, from_json
from app.models import (
    DigitalAssetClientDetailRecord,
    DigitalAssetClientSummaryRecord,
    DigitalAssetDashboardRecord,
    DigitalAssetDepositSuggestionRecord,
    DigitalAssetDimensionRecord,
    DigitalAssetInsightRecord,
    DigitalAssetMapNodeRecord,
    DigitalAssetMetricRecord,
    DigitalAssetScoreBreakdownRecord,
    DigitalAssetSourceRefRecord,
    DigitalAssetUnitRecord,
)


@dataclass(frozen=True)
class AssetSource:
    source_type: str
    source_id: str
    title: str
    text: str
    updated_at: str | None = None


@dataclass(frozen=True)
class AssetDimension:
    key: str
    label: str
    description: str
    keywords: tuple[str, ...]
    value_insights: tuple[str, ...]
    suggestions: tuple[str, ...]
    gap: str


@dataclass(frozen=True)
class AssetUnit:
    key: str
    label: str
    level: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class AssetMapNode:
    key: str
    label: str
    description: str
    track_title: str
    keywords: tuple[str, ...]
    units: tuple[AssetUnit, ...]
    next_deposit: str
    unlocked_value: str


ASSET_DIMENSIONS: tuple[AssetDimension, ...] = (
    AssetDimension(
        key="strategy_identity",
        label="战略资产",
        description="使命、定位、阶段、战略判断和长期目标。",
        keywords=("战略", "使命", "愿景", "定位", "目标", "价值主张", "核心判断", "阶段", "路径", "突破口"),
        value_insights=("可以帮助 AI 理解组织为什么存在、当前往哪里走，以及哪些判断不能随意改写。",),
        suggestions=("持续沉淀战略复盘、阶段目标、关键判断和目标调整原因。",),
        gap="缺少能稳定说明组织方向、阶段和核心判断的资料。",
    ),
    AssetDimension(
        key="business_project",
        label="业务/项目资产",
        description="项目组合、业务模块、产品服务和交付对象。",
        keywords=("项目", "业务", "产品", "服务", "模块", "工作坊", "课程", "活动", "年会", "文献馆", "价值分析"),
        value_insights=("可以让 AI 看清组织正在交付什么，以及不同项目之间如何形成组合。",),
        suggestions=("为每个长期项目持续沉淀项目介绍、目标、对象、流程、产出和复盘。",),
        gap="缺少能说明业务/项目结构与项目价值的连续材料。",
    ),
    AssetDimension(
        key="audience_subject",
        label="服务对象资产",
        description="客户、受众、服务对象、合作方和关键人群画像。",
        keywords=("教师", "学校", "儿童", "青少年", "志愿者", "资方", "合作方", "县域", "客户", "用户", "对象", "受众"),
        value_insights=("长期沉淀后可以分析受众结构、需求变化和组织吸引力是否发生迁移。",),
        suggestions=("连续沉淀服务对象基础信息、参与动机、需求标签、反馈和留存变化。",),
        gap="缺少可持续观察服务对象是谁、为什么来、如何变化的资料。",
    ),
    AssetDimension(
        key="process_flow",
        label="过程资产",
        description="报名、审核、交付、反馈、结课、复盘等流程节点。",
        keywords=("报名", "申请", "前测", "后测", "问卷", "反馈", "审核", "入群", "签收", "结课", "复盘", "流程", "转化"),
        value_insights=("可以把零散项目动作变成可计算流程，未来分析转化、流失和关键瓶颈。",),
        suggestions=("按时间连续沉淀报名表、审核记录、参与记录、反馈表、结课记录和复盘纪要。",),
        gap="缺少能串起项目全过程的节点数据。",
    ),
    AssetDimension(
        key="outcome_evidence",
        label="成效资产",
        description="评估、变化、反馈、案例和结果证明。",
        keywords=("评估", "变化", "满意度", "韧性", "反馈", "效果", "成果", "案例", "影响", "前后测", "后测", "证明"),
        value_insights=("长期沉淀后可以判断项目是否真的有效，以及成效来自哪些关键机制。",),
        suggestions=("统一沉淀前后测、满意度、关键反馈、案例故事和阶段成效复盘。",),
        gap="缺少能证明结果变化和项目有效性的成效资料。",
    ),
    AssetDimension(
        key="relationship_ecosystem",
        label="关系生态资产",
        description="伙伴、资方、协作网络和关键关系变化。",
        keywords=("伙伴", "合作", "资方", "捐赠", "公益伙伴", "生态", "网络", "协作", "联盟", "政府"),
        value_insights=("可以让 AI 理解组织如何调动资源，以及哪些关系会影响项目推进。",),
        suggestions=("沉淀关键伙伴画像、合作历史、沟通纪要、资源承诺和关系风险。",),
        gap="缺少能说明关键合作关系和生态资源的资料。",
    ),
    AssetDimension(
        key="content_brand_fundraising",
        label="传播/筹款资产",
        description="品牌、传播、筹款、影响力表达和对外叙事。",
        keywords=("品牌", "传播", "筹款", "年报", "故事", "案例", "影响力", "叙事", "文案", "公众号", "募捐", "传播清晰度"),
        value_insights=("可以分析外部表达是否稳定，以及品牌吸引的人群和资源是否发生变化。",),
        suggestions=("沉淀传播内容、筹款材料、受众反馈、转化数据和典型案例。",),
        gap="缺少能连接品牌表达、传播反馈和筹款效果的资料。",
    ),
    AssetDimension(
        key="management_decision",
        label="管理决策资产",
        description="会议、纪要、OKR、执行手册、判断版本和管理复盘。",
        keywords=("会议", "纪要", "okr", "战略", "判断", "决策", "执行手册", "复盘", "管理", "计划", "机制"),
        value_insights=("可以让 AI 理解组织如何做决定、如何复盘，以及哪些管理机制在发挥作用。",),
        suggestions=("持续沉淀会议纪要、关键决策、判断依据、执行复盘和版本变化。",),
        gap="缺少能说明组织如何做决定和推进执行的管理资料。",
    ),
    AssetDimension(
        key="data_system",
        label="数据/系统资产",
        description="表单、看板、系统、平台、自动化和数据库。",
        keywords=("数据", "表单", "看板", "系统", "平台", "ai", "自动化", "数据库", "数字化", "仪表盘", "fti"),
        value_insights=("可以把资料沉淀升级为可查询、可计算、可持续复用的数据基础设施。",),
        suggestions=("沉淀字段说明、表单结构、看板指标、系统流程和数据口径。",),
        gap="缺少能让 AI 直接理解字段、指标、系统和数据口径的资料。",
    ),
)


def _unit(key: str, label: str, level: str, *keywords: str) -> AssetUnit:
    return AssetUnit(key=key, label=label, level=level, keywords=tuple(keywords))


ASSET_MAP_NODES: tuple[AssetMapNode, ...] = (
    AssetMapNode(
        key="organization_identity",
        label="组织身份",
        description="组织是谁、服务什么对象、处在什么阶段。",
        track_title="组织资产型",
        keywords=("组织", "简介", "使命", "愿景", "定位", "阶段", "客户", "基金会", "公司", "机构"),
        units=(
            _unit("identity_intro", "组织介绍/使命定位", "required", "组织介绍", "简介", "使命", "愿景", "定位"),
            _unit("current_stage", "当前阶段", "required", "阶段", "当前", "推进中", "转型", "试点"),
            _unit("business_scope", "业务/服务范围", "required", "业务", "服务", "项目", "产品", "工作坊"),
            _unit("key_people", "关键角色/负责人", "advanced", "负责人", "团队", "部门", "角色", "关键人"),
            _unit("boundary_rule", "组织边界和原则", "advanced", "边界", "原则", "不做", "取舍", "约束"),
            _unit("identity_evolution", "组织身份变化线索", "opportunity", "变化", "转型", "升级", "第二曲线", "新定位"),
        ),
        next_deposit="补一份组织资产说明：使命定位、当前阶段、业务边界、关键角色。",
        unlocked_value="让 AI 先稳定知道组织是谁、现在处在什么阶段，避免把资料理解成零散项目。",
    ),
    AssetMapNode(
        key="strategic_judgment",
        label="战略判断",
        description="关键战略命题、判断依据、版本变化和验证结果。",
        track_title="战略判断型",
        keywords=("战略", "判断", "定位", "路径", "目标", "突破口", "假设", "验证", "决策"),
        units=(
            _unit("strategic_topic", "战略命题", "required", "战略", "命题", "目标", "定位", "突破口"),
            _unit("judgment_content", "关键判断", "required", "判断", "结论", "假设", "观点"),
            _unit("evidence_basis", "判断依据", "required", "依据", "证据", "原因", "事实"),
            _unit("judgment_time", "判断时间/版本", "advanced", "时间", "日期", "版本", "阶段", "季度", "年度"),
            _unit("validation_result", "后续验证结果", "advanced", "验证", "结果", "复盘", "是否成立", "证伪"),
            _unit("new_strategy_opportunity", "新战略机会", "opportunity", "新机会", "第二曲线", "新业务", "新产品", "新服务"),
        ),
        next_deposit="补战略判断表：时间、判断、依据、后续验证结果。",
        unlocked_value="解锁判断验证库，让 AI 追踪哪些战略判断被事实验证。",
    ),
    AssetMapNode(
        key="business_portfolio",
        label="业务/项目组合",
        description="业务线、项目台账、交付对象、产出和价值结果。",
        track_title="业务机会型",
        keywords=("项目", "业务", "产品", "服务", "模块", "课程", "活动", "年会", "文献馆", "价值分析"),
        units=(
            _unit("project_list", "项目/业务清单", "required", "项目", "业务", "产品", "服务", "清单", "台账"),
            _unit("project_goal", "项目目标", "required", "目标", "目的", "价值", "意图"),
            _unit("delivery_output", "交付内容/产出", "required", "交付", "产出", "活动", "课程", "工作坊"),
            _unit("target_object", "服务/交付对象", "advanced", "对象", "客户", "用户", "教师", "学校", "受众"),
            _unit("result_field", "结果字段", "advanced", "结果", "成效", "反馈", "指标", "评分", "转化"),
            _unit("business_map", "业务价值地图", "opportunity", "价值地图", "组合", "新业务", "新产品", "商业化", "机会"),
        ),
        next_deposit="补项目台账：项目、阶段、对象、目标、产出、结果字段。",
        unlocked_value="解锁业务组合分析，比较不同项目的交付模型和价值结果。",
    ),
    AssetMapNode(
        key="audience_profile",
        label="服务对象画像",
        description="对象是谁、从哪里来、为什么参与、如何变化。",
        track_title="服务对象型",
        keywords=("教师", "学校", "儿童", "青少年", "志愿者", "资方", "合作方", "客户", "用户", "对象", "受众", "画像"),
        units=(
            _unit("role_identity", "身份/角色字段", "required", "身份", "角色", "教师", "学校", "客户", "用户", "对象"),
            _unit("source_channel", "来源渠道", "required", "来源", "渠道", "推荐", "报名来源"),
            _unit("participation_motivation", "参与动机", "required", "动机", "意图", "需求", "为什么"),
            _unit("need_tags", "需求标签", "advanced", "需求", "标签", "画像", "痛点", "问题"),
            _unit("status_feedback", "参与状态与反馈", "advanced", "状态", "参与", "反馈", "满意度", "结课"),
            _unit("anonymous_link_id", "匿名关联 ID", "advanced", "编号", "编码", "id", "匿名", "关联"),
            _unit("audience_shift", "受众变化趋势", "opportunity", "变化", "迁移", "趋势", "留存", "分群", "队列"),
        ),
        next_deposit="补服务对象画像表：身份、来源、参与动机、需求标签、状态和反馈。",
        unlocked_value="解锁受众结构、需求变化和组织吸引力分析。",
    ),
    AssetMapNode(
        key="process_flow",
        label="项目流程节点",
        description="报名、审核、参与、反馈、结课等流程是否能串起来。",
        track_title="项目流程型",
        keywords=("报名", "申请", "审核", "入群", "签收", "参与", "反馈", "结课", "流程", "转化"),
        units=(
            _unit("flow_nodes", "流程节点", "required", "报名", "申请", "审核", "参与", "反馈", "结课", "流程"),
            _unit("node_time", "节点时间", "required", "时间", "日期", "批次", "年度", "阶段"),
            _unit("node_status", "节点状态", "required", "状态", "通过", "完成", "结课", "未完成"),
            _unit("flow_owner", "负责人/执行角色", "advanced", "负责人", "执行", "角色", "部门"),
            _unit("conversion_field", "转化/流失字段", "advanced", "转化", "流失", "转化率", "比例"),
            _unit("linked_result", "与结果联动", "opportunity", "联动", "归因", "影响因子"),
        ),
        next_deposit="补流程节点表：报名、审核、参与、反馈、结课状态和时间。",
        unlocked_value="解锁流程转化、流失节点和关键瓶颈分析。",
    ),
    AssetMapNode(
        key="outcome_evidence",
        label="成效证据",
        description="结果变化、前后测、反馈、案例和影响机制。",
        track_title="成效评估型",
        keywords=("评估", "变化", "满意度", "韧性", "反馈", "效果", "成果", "案例", "影响", "前后测", "证明"),
        units=(
            _unit("outcome_metric", "成效指标", "required", "指标", "成效", "效果", "成果", "评估"),
            _unit("feedback_record", "反馈记录", "required", "反馈", "满意度", "问卷", "评价"),
            _unit("case_evidence", "案例证据", "required", "案例", "故事", "证明", "证据"),
            _unit("pre_post", "前后测/变化", "advanced", "前测", "后测", "前后测", "变化", "提升"),
            _unit("mechanism_clue", "影响机制线索", "advanced", "机制", "原因", "影响因素", "为什么有效"),
            _unit("attribution_signal", "归因/趋势信号", "opportunity", "归因", "趋势", "长期", "同比", "环比", "影响因子"),
        ),
        next_deposit="补成效评估表：前后测、反馈、案例、结果字段和机制复盘。",
        unlocked_value="解锁项目有效性、成效机制和影响因子分析。",
    ),
    AssetMapNode(
        key="resource_ecosystem",
        label="资源/伙伴生态",
        description="伙伴、资方、协作网络、资源承诺和关系风险。",
        track_title="生态资源型",
        keywords=("伙伴", "合作", "资方", "捐赠", "公益伙伴", "生态", "网络", "协作", "联盟", "政府"),
        units=(
            _unit("partner_type", "伙伴类型", "required", "伙伴", "合作方", "资方", "政府", "联盟"),
            _unit("resource_commitment", "资源承诺", "required", "资源", "承诺", "捐赠", "资助", "支持"),
            _unit("collaboration_record", "协作记录", "required", "沟通", "会议", "纪要", "协作"),
            _unit("relationship_status", "关系状态", "advanced", "状态", "风险", "稳定", "推进"),
            _unit("contribution_result", "伙伴贡献结果", "advanced", "贡献", "结果", "成效", "价值"),
            _unit("ecosystem_opportunity", "生态机会", "opportunity", "联盟", "生态", "新协作", "机会", "资源网络"),
        ),
        next_deposit="补伙伴关系表：伙伴类型、资源承诺、协作状态、贡献结果。",
        unlocked_value="解锁资源网络、伙伴贡献和协作风险分析。",
    ),
    AssetMapNode(
        key="communication_conversion",
        label="传播/筹款转化",
        description="内容、渠道、触达、反馈、筹款和资源转化。",
        track_title="传播转化型",
        keywords=("品牌", "传播", "筹款", "年报", "故事", "案例", "影响力", "叙事", "公众号", "募捐"),
        units=(
            _unit("content_asset", "传播内容", "required", "内容", "文案", "故事", "案例", "公众号", "年报"),
            _unit("channel", "传播渠道", "required", "渠道", "公众号", "媒体", "社群"),
            _unit("audience_response", "受众反馈", "required", "反馈", "评论", "阅读", "触达"),
            _unit("fundraising_signal", "筹款/资源转化", "advanced", "筹款", "募捐", "捐赠", "转化", "金额"),
            _unit("brand_audience_link", "品牌与受众联动", "advanced", "受众", "人群", "吸引力", "品牌"),
            _unit("conversion_opportunity", "传播转化机会", "opportunity", "转化率", "新渠道", "增长", "机会"),
        ),
        next_deposit="补传播/筹款数据：内容、渠道、触达、反馈、转化。",
        unlocked_value="解锁品牌吸引力、传播反馈和资源转化分析。",
    ),
    AssetMapNode(
        key="management_decision",
        label="管理决策",
        description="会议、决策、负责人、执行复盘和判断验证。",
        track_title="管理协作型",
        keywords=("会议", "纪要", "okr", "判断", "决策", "执行手册", "复盘", "管理", "计划", "机制"),
        units=(
            _unit("meeting_record", "会议/纪要", "required", "会议", "纪要", "讨论"),
            _unit("decision_record", "决策记录", "required", "决策", "判断", "决定"),
            _unit("owner_action", "负责人/动作", "required", "负责人", "行动", "任务", "执行"),
            _unit("review_result", "执行复盘", "advanced", "复盘", "结果", "推进", "完成"),
            _unit("decision_validation", "决策验证", "advanced", "验证", "依据", "是否成立", "版本"),
            _unit("management_model", "管理机制机会", "opportunity", "机制", "模型", "自动化", "协作效率"),
        ),
        next_deposit="补决策台账：会议、决策、负责人、执行结果、验证结论。",
        unlocked_value="解锁管理判断、执行复盘和组织协作机制分析。",
    ),
    AssetMapNode(
        key="data_system",
        label="数据/系统底座",
        description="字段、表单、看板、系统流程和可查询数据口径。",
        track_title="数据系统型",
        keywords=("数据", "表单", "看板", "系统", "平台", "ai", "自动化", "数据库", "数字化", "仪表盘", "fti"),
        units=(
            _unit("field_dictionary", "字段口径", "required", "字段", "口径", "数据字典"),
            _unit("data_table", "表单/数据表", "required", "表单", "数据表", "excel", "xlsx", "csv", "sheet"),
            _unit("system_flow", "系统流程", "required", "系统", "平台", "流程", "自动化"),
            _unit("dashboard_metric", "看板指标", "advanced", "看板", "指标", "仪表盘", "统计"),
            _unit("queryable_asset", "可查询资产", "advanced", "数据库", "查询", "检索", "结构化"),
            _unit("automation_opportunity", "自动化/数字化机会", "opportunity", "自动化", "AI", "智能", "新系统", "数字化机会"),
        ),
        next_deposit="补字段口径、表单结构、看板指标和系统流程说明。",
        unlocked_value="解锁可查询、可比较、可持续复用的数据基础设施。",
    ),
    AssetMapNode(
        key="opportunity_pipeline",
        label="产品/业务机会",
        description="从资料中显现的新产品、新业务、新服务和数字化可能性。",
        track_title="业务机会型",
        keywords=("新产品", "新业务", "新服务", "机会", "第二曲线", "数字化", "自动化", "增长", "需求"),
        units=(
            _unit("unmet_need", "未满足需求", "required", "需求", "痛点", "未满足", "问题"),
            _unit("opportunity_hypothesis", "机会假设", "required", "机会", "假设", "可能性"),
            _unit("target_scenario", "目标场景", "required", "场景", "对象", "用户", "客户"),
            _unit("experiment_record", "试点/实验记录", "advanced", "试点", "实验", "验证", "测试"),
            _unit("result_feedback", "机会反馈结果", "advanced", "结果", "反馈", "转化", "采用"),
            _unit("new_business_signal", "新业务/产品信号", "opportunity", "新产品", "新业务", "新服务", "商业模式", "规模化"),
        ),
        next_deposit="补机会假设表：未满足需求、目标场景、试点动作、反馈结果。",
        unlocked_value="解锁从组织资产中发现新产品、新业务和数字化机会。",
    ),
)

STAGE_NAMES = ("资料整理期", "组织画像期", "结构计算期", "机制洞察期", "机会生成期")
NODE_STAGE_NAMES = ("整理", "画像", "计算", "洞察", "机会")
CORE_NODE_KEYS = {"organization_identity", "business_portfolio", "strategic_judgment"}
NODE_COMPLEXITY_PENALTY: dict[str, int] = {
    "organization_identity": 0,
    "strategic_judgment": 2,
    "business_portfolio": 4,
    "management_decision": 4,
    "resource_ecosystem": 5,
    "process_flow": 6,
    "audience_profile": 7,
    "data_system": 8,
    "communication_conversion": 9,
    "outcome_evidence": 10,
    "opportunity_pipeline": 12,
}


SOURCE_TYPE_LABELS: dict[str, str] = {
    "document": "资料",
    "document_card": "文档卡",
    "memory": "记忆",
    "event_line": "事件线",
    "meeting": "会议",
    "task": "任务",
    "evidence": "证据卡",
    "theme": "主题簇",
    "question": "开放问题",
    "judgment": "判断",
    "notebook": "组织画像",
}


ASSET_NODE_DOCUMENT_GUIDANCE: dict[str, dict[str, object]] = {
    "organization_identity": {
        "title": "{client}组织职责与协作边界说明",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别组织定位和基础业务范围。",
        "missing": "还缺一份说明部门职责、关键角色和协作边界的资料。目前 AI 能知道组织大致在做什么，但还不够稳定地判断谁负责什么、哪些事情由谁决策。",
        "content": ["部门/角色", "职责范围", "负责项目", "协作对象", "审批边界", "关键决策事项"],
        "value": "补齐后，AI 可以更稳定地理解{client}是谁、谁在负责哪些事情，以及不同资料应该归到哪个组织角色上。",
    },
    "strategic_judgment": {
        "title": "{client}战略判断验证表",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能提取部分战略判断和阶段方向。",
        "missing": "还缺一份把重要判断和后续事实放在一起复盘的资料。目前 AI 能看到判断本身，但还不能稳定判断哪些判断后来被验证、哪些需要修正。",
        "content": ["战略判断", "提出时间", "判断依据", "采取行动", "后续事实", "验证结论", "是否需要修正"],
        "value": "补齐后，AI 可以形成{client}的判断验证库，追踪哪些战略判断成立、哪些判断需要调整。",
    },
    "business_portfolio": {
        "title": "{client}重点项目年度结果表",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别重点项目和业务线索。",
        "missing": "还缺一份把重点项目放在一起比较的年度结果资料。目前 AI 能知道有哪些项目，但还不能稳定判断哪些项目产生了更强价值、哪些项目需要调整。",
        "content": ["重点项目/业务名称", "当前阶段", "服务对象", "关键动作", "参与情况", "反馈摘要", "是否达到预期", "下一步判断"],
        "value": "补齐后，AI 可以比较{client}不同项目的交付方式、参与反馈和年度结果，判断哪些项目最值得继续投入。",
    },
    "audience_profile": {
        "title": "{client}参与方反馈整理表",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别部分服务对象和参与方线索。",
        "missing": "还缺一份能持续观察同一类参与方变化的反馈资料。目前 AI 能看到谁参与过，但还不够稳定地判断他们为什么来、参与后有什么变化、后续还需要什么。",
        "content": ["参与方类型", "参与项目", "参与原因", "最关心的问题", "参与后的反馈", "是否继续参与", "后续需求"],
        "value": "补齐后，AI 可以分析{client}服务对象结构、需求变化和组织吸引力是否发生迁移。",
    },
    "process_flow": {
        "title": "{client}重点项目流程复盘表",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别部分项目流程和交付动作。",
        "missing": "还缺一份按项目连续记录筹备、邀约、参与、反馈和复盘的资料。目前 AI 能看到若干流程片段，但还不能稳定分析哪里最容易卡住、哪里最影响最终结果。",
        "content": ["项目名称", "筹备动作", "邀约对象", "实际参与", "交付内容", "现场反馈", "复盘结论", "下一步改进"],
        "value": "补齐后，AI 可以分析{client}重点项目的转化、流失和关键瓶颈，找出哪些动作最影响交付质量。",
    },
    "outcome_evidence": {
        "title": "{client}项目成效与反馈汇总表",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别部分反馈、案例或成效线索。",
        "missing": "还缺一份把项目目标、实际反馈和典型案例放在一起的成效资料。目前 AI 能看到一些好评或案例，但还不能稳定判断项目到底产生了什么变化。",
        "content": ["项目名称", "目标对象", "预期结果", "实际反馈", "典型案例", "成效证据", "影响因素", "复盘结论"],
        "value": "补齐后，AI 可以分析{client}项目是否有效、成效来自哪些关键动作，以及未来应强化哪些机制。",
    },
    "resource_ecosystem": {
        "title": "{client}伙伴贡献与协作记录表",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别部分伙伴、资方或协作网络。",
        "missing": "还缺一份持续记录伙伴贡献和协作状态的资料。目前 AI 能看到谁出现过，但还不够稳定地判断谁贡献了什么、合作是否变强、哪里存在协作风险。",
        "content": ["伙伴名称", "伙伴类型", "合作项目", "提供资源", "协作动作", "贡献结果", "关系状态", "下一步机会"],
        "value": "补齐后，AI 可以分析{client}的资源网络、伙伴贡献和潜在协作机会。",
    },
    "communication_conversion": {
        "title": "{client}传播内容反馈表",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别部分传播、品牌或筹款线索。",
        "missing": "还缺一份把传播内容、渠道反馈和资源变化放在一起的资料。目前 AI 能看到对外表达，但还不能稳定判断哪些内容真正带来了关注、反馈或资源。",
        "content": ["传播内容", "发布渠道", "目标人群", "阅读/触达情况", "反馈摘要", "后续咨询", "资源转化结果"],
        "value": "补齐后，AI 可以分析{client}品牌表达、受众反应和资源转化之间的关系。",
    },
    "management_decision": {
        "title": "{client}会议决策执行跟踪表",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别部分会议、决策和执行线索。",
        "missing": "还缺一份持续记录决策后执行情况的资料。目前 AI 能看到会议或判断，但还不能稳定追踪哪些决策真正推进了、哪些后来被调整。",
        "content": ["会议名称", "决策事项", "负责人", "计划动作", "实际进展", "执行结果", "阻碍原因", "后续调整"],
        "value": "补齐后，AI 可以分析{client}的决策质量、执行节奏和组织协作机制。",
    },
    "data_system": {
        "title": "{client}数据表与看板说明",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别部分表单、看板或系统线索。",
        "missing": "还缺一份说明每张表记录什么、每个统计指标怎么算、看板数据从哪里来的资料。目前 AI 能看到一些数据资料，但还不能稳定复用为可查询、可比较的组织资产。",
        "content": ["表单名称", "记录内容", "数据来源", "统计方式", "看板指标", "更新频率", "负责人", "使用场景"],
        "value": "补齐后，AI 可以把{client}的表单、看板和系统资料整理成可查询、可比较、可持续复用的数据底座。",
    },
    "opportunity_pipeline": {
        "title": "{client}机会实验与需求反馈表",
        "seen": "系统已看到{client}的{sources}等资料，AI 已能识别部分新需求、新业务或数字化机会线索。",
        "missing": "还缺一份记录未满足需求、试点动作和反馈结果的资料。目前 AI 能看到机会信号，但还不能稳定判断哪些机会值得继续投入。",
        "content": ["未满足需求", "目标场景", "试点动作", "参与对象", "反馈结果", "是否继续投入"],
        "value": "补齐后，AI 可以从{client}长期资料中识别新产品、新业务、新服务和数字化机会。",
    },
}


VALUE_SIGNAL_BY_DIMENSION: dict[str, str] = {
    "strategy_identity": "战略判断资料已出现，可沉淀成组织长期方向与阶段变化的判断轨迹。",
    "business_project": "业务/项目资料已出现，可继续形成项目组合、交付模型和项目价值地图。",
    "audience_subject": "服务对象资料已出现，长期可分析受众结构、动机和需求变化。",
    "process_flow": "流程节点资料已出现，长期可计算报名、审核、参与、反馈、结课等关键转化。",
    "outcome_evidence": "成效与反馈资料已出现，可持续形成项目有效性和影响机制证据。",
    "relationship_ecosystem": "合作关系资料已出现，可沉淀资源网络、伙伴贡献和协作风险。",
    "content_brand_fundraising": "传播/筹款资料已出现，可分析品牌表达和资源转化之间的关系。",
    "management_decision": "管理决策资料已出现，可沉淀组织判断版本、执行复盘和管理机制。",
    "data_system": "数据/系统资料已出现，可进一步把表单、看板和平台变成可计算资产。",
}

STRUCTURED_KEYWORDS = (
    "表格", "表单", "字段", "excel", "xlsx", "csv", "sheet", "看板", "数据表", "数据库",
    "指标", "口径", "统计", "名单", "问卷", "评分", "分数", "满意度", "金额", "数量",
    "转化率", "比例", "编码", "编号",
)

FIELD_LEVEL_KEYWORDS = (
    "字段", "口径", "数据表", "表格", "表单", "excel", "xlsx", "csv", "sheet", "名单",
    "问卷", "评分", "分数", "金额", "数量", "转化率", "比例", "编码", "编号",
)

TIME_KEYWORDS = (
    "日期", "时间", "年度", "季度", "月度", "周度", "周期", "批次", "阶段", "前测",
    "后测", "复盘", "连续", "长期", "趋势", "变化", "同比", "环比",
)

OBJECT_KEYWORDS = (
    "客户", "用户", "对象", "受众", "教师", "学校", "儿童", "青少年", "志愿者", "资方",
    "合作方", "伙伴", "负责人", "部门", "人群", "画像",
)

RESULT_KEYWORDS = (
    "反馈", "结果", "状态", "成效", "效果", "成果", "满意度", "评估", "转化", "留存",
    "完成", "结课", "通过", "验证", "影响",
)

TREND_KEYWORDS = (
    "趋势", "变化", "连续", "长期", "周期", "批次", "复盘", "前后测", "年度", "季度",
    "月度", "沉淀", "验证", "演变",
)

PREDICTIVE_DATA_KEYWORDS = (
    "时间序列", "同比", "环比", "留存率", "转化率", "归因", "影响因子", "相关性",
    "预测模型", "趋势模型", "回归", "分群", "队列",
)

LINKAGE_KEYWORDS = ("联动", "归因", "影响因子", "转化率", "留存率", "验证库")
OPPORTUNITY_SIGNAL_KEYWORDS = ("新产品", "新业务", "新服务", "第二曲线", "商业模式", "数字化机会", "规模化")
PROCESS_SIGNAL_KEYWORDS = (
    "报名", "申请", "审核", "入群", "签收", "参与", "结课", "完成", "前测", "后测",
)
DECISION_SIGNAL_KEYWORDS = ("验证", "判断", "决策", "复盘", "版本", "依据")
CROSS_PERIOD_KEYWORDS = ("时间序列", "同比", "环比", "跨周期", "队列", "连续多年", "长期追踪", "年度变化")
NARRATIVE_ADVANCED_UNIT_KEYS = {
    "key_people",
    "boundary_rule",
    "judgment_time",
    "validation_result",
    "relationship_status",
    "review_result",
    "decision_validation",
}
OPPORTUNITY_GENERATION_UNIT_KEYS = {
    "identity_evolution",
    "new_strategy_opportunity",
    "business_map",
    "ecosystem_opportunity",
    "conversion_opportunity",
    "automation_opportunity",
    "new_business_signal",
}

TIME_RE = re.compile(r"(20\d{2}|19\d{2})(?:[-./年](0?[1-9]|1[0-2]))?|(?:第[一二三四五六七八九十\d]+期)|(?:Q[1-4])", re.I)


def build_digital_asset_dashboard(db: Database) -> DigitalAssetDashboardRecord:
    clients = []
    for row in db.fetchall("SELECT id FROM clients ORDER BY updated_at DESC"):
        detail = build_client_digital_assets(db, str(row["id"]))
        clients.append(_summarize_detail(detail))
    return DigitalAssetDashboardRecord(
        generatedAt=_now_iso(),
        clients=clients,
    )


def build_client_digital_assets(db: Database, client_id: str) -> DigitalAssetClientDetailRecord:
    client_row = db.fetchone("SELECT id, name, stage, intro, updated_at FROM clients WHERE id = ?", (client_id,))
    if not client_row:
        raise ValueError("Client not found")

    sources = _collect_sources(db, client_id)
    metrics = _build_metrics(db, client_id)
    notebook = _read_notebook_snapshot(db, client_id)
    understanding_score = _normalize_score(float(notebook.get("confidence", 0.0)) if notebook else 0.0)
    source_total = sum(metric.value for metric in metrics if metric.key in {"documents", "memoryFacts", "eventLines", "meetings", "tasks"})
    empty_state = source_total == 0
    dimensions = [_build_dimension_record(dimension, sources, metrics) for dimension in ASSET_DIMENSIONS]
    client_name = str(client_row["name"])
    asset_map_nodes = _build_asset_map_nodes(client_name, sources, empty_state)
    stage_summary = _build_stage_summary(asset_map_nodes, metrics, understanding_score, empty_state)
    next_best_deposits = _build_next_best_deposits(client_name, asset_map_nodes, empty_state)
    active_dimensions = [dimension for dimension in dimensions if dimension.scoreBreakdown.deposited > 0]
    asset_completion_score = _compute_asset_completion_score(dimensions, empty_state=empty_state)
    if empty_state:
        asset_completion_score = 0

    value_insights = _build_value_insights_from_nodes(asset_map_nodes) or _build_value_insights(dimensions)
    deposit_suggestions = next_best_deposits or _build_deposit_suggestions(dimensions, empty_state)
    critical_gaps = stage_summary["stageBlockers"] or _build_critical_gaps(dimensions, empty_state)
    next_deposits = [item.title for item in deposit_suggestions[:3]]
    high_value_signals = [item.summary for item in value_insights[:3]]
    strongest_dimensions = [node.label for node in sorted(asset_map_nodes, key=lambda item: (item.stageIndex, item.coverageScore, item.evidenceCount), reverse=True)[:3]]
    statement = _build_understanding_statement(
        client_name=client_name,
        score=int(stage_summary["stageProgress"]),
        dimensions=active_dimensions,
        empty_state=empty_state,
        notebook_intro=str(notebook.get("organizationIntro", "")) if notebook else "",
        asset_stage=str(stage_summary["assetStage"]),
        track_title=str(stage_summary["assetTrackTitle"]),
        blockers=critical_gaps,
    )

    return DigitalAssetClientDetailRecord(
        id=str(client_row["id"]),
        name=client_name,
        stage=str(client_row["stage"] or ""),
        intro=_sanitize_public_text(str(client_row["intro"] or ""), limit=180),
        assetCompletionScore=asset_completion_score,
        understandingScore=understanding_score,
        understandingStatement=statement,
        depositedValueLevel=_level_from_score(_average_breakdown(dimensions, "deposited"), "deposited"),
        nextValueSpace=_next_value_space(deposit_suggestions),
        depositXp=_compute_deposit_xp(metrics),
        assetStage=str(stage_summary["assetStage"]),
        assetTrackTitle=str(stage_summary["assetTrackTitle"]),
        growthMode=str(stage_summary["growthMode"]),  # type: ignore[arg-type]
        stageProgress=int(stage_summary["stageProgress"]),
        nextStage=str(stage_summary["nextStage"]),
        unlockedCapabilities=list(stage_summary["unlockedCapabilities"]),
        stageBlockers=list(stage_summary["stageBlockers"]),
        nextBestDeposits=next_best_deposits,
        assetMapNodes=asset_map_nodes,
        assetDimensionCount=len(asset_map_nodes),
        strongestDimensions=strongest_dimensions,
        highValueSignals=high_value_signals,
        criticalGaps=critical_gaps,
        nextDeposits=next_deposits,
        metrics=metrics,
        emptyState=empty_state,
        updatedAt=str(client_row["updated_at"] or "") or None,
        dimensions=dimensions,
        valueInsights=value_insights,
        depositSuggestions=deposit_suggestions,
        sourceMetrics=metrics,
    )


def _summarize_detail(detail: DigitalAssetClientDetailRecord) -> DigitalAssetClientSummaryRecord:
    return DigitalAssetClientSummaryRecord(
        id=detail.id,
        name=detail.name,
        stage=detail.stage,
        intro=detail.intro,
        assetCompletionScore=detail.assetCompletionScore,
        understandingScore=detail.understandingScore,
        understandingStatement=detail.understandingStatement,
        depositedValueLevel=detail.depositedValueLevel,
        nextValueSpace=detail.nextValueSpace,
        depositXp=detail.depositXp,
        assetStage=detail.assetStage,
        assetTrackTitle=detail.assetTrackTitle,
        growthMode=detail.growthMode,
        stageProgress=detail.stageProgress,
        nextStage=detail.nextStage,
        unlockedCapabilities=detail.unlockedCapabilities,
        stageBlockers=detail.stageBlockers,
        nextBestDeposits=detail.nextBestDeposits,
        assetMapNodes=detail.assetMapNodes[:4],
        assetDimensionCount=detail.assetDimensionCount,
        strongestDimensions=detail.strongestDimensions,
        highValueSignals=detail.highValueSignals,
        criticalGaps=detail.criticalGaps,
        nextDeposits=detail.nextDeposits,
        metrics=detail.metrics,
        emptyState=detail.emptyState,
        updatedAt=detail.updatedAt,
    )


def _build_asset_map_nodes(client_name: str, sources: list[AssetSource], empty_state: bool) -> list[DigitalAssetMapNodeRecord]:
    nodes = [_build_asset_map_node(client_name, definition, sources) for definition in ASSET_MAP_NODES]
    if empty_state:
        return [node for node in nodes if node.key in {"organization_identity", "business_portfolio", "process_flow"}]
    active = [
        node for node in nodes
        if node.evidenceCount > 0 or node.coveredUnits or node.key in CORE_NODE_KEYS
    ]
    return sorted(
        active,
        key=lambda node: (
            node.stageIndex,
            node.coverageScore,
            node.evidenceCount,
            -_track_priority(node.key),
        ),
        reverse=True,
    )


def _build_asset_map_node(client_name: str, definition: AssetMapNode, sources: list[AssetSource]) -> DigitalAssetMapNodeRecord:
    matched_sources = _match_asset_sources(definition.keywords, sources)
    covered_units: list[DigitalAssetUnitRecord] = []
    missing_units: list[DigitalAssetUnitRecord] = []
    for unit in definition.units:
        evidence_count = _unit_evidence_count(unit, sources)
        record = DigitalAssetUnitRecord(
            key=unit.key,
            label=unit.label,
            level=unit.level,  # type: ignore[arg-type]
            covered=evidence_count > 0,
            evidenceCount=evidence_count,
        )
        if evidence_count > 0:
            covered_units.append(record)
        else:
            missing_units.append(record)
    raw_coverage_score = _asset_unit_coverage_score(covered_units, definition.units)
    signal_cap = _asset_node_signal_cap(matched_sources)
    stage_index = min(_asset_node_stage_index(covered_units, definition.units), signal_cap)
    coverage_score = min(raw_coverage_score, _coverage_cap_for_signal(signal_cap))
    maturity_percent = _asset_node_maturity_percent(
        node_key=definition.key,
        stage_index=stage_index,
        signal_cap=signal_cap,
        covered_units=covered_units,
        all_units=definition.units,
        matched_sources=matched_sources,
    )
    representative_sources = [
        DigitalAssetSourceRefRecord(
            sourceType=source.source_type,
            sourceId=source.source_id,
            title=_sanitize_public_text(source.title, limit=48) or SOURCE_TYPE_LABELS.get(source.source_type, "资料"),
            excerpt=_sanitize_public_text(source.text, limit=96),
            updatedAt=source.updated_at,
        )
        for source in matched_sources[:3]
    ]
    source_highlights = _source_highlights(matched_sources)
    suggested_title = _suggested_document_title(client_name, definition.key)
    suggested_content = _suggested_document_content(definition.key)
    seen_summary = _seen_summary_for_node(client_name, definition, source_highlights)
    missing_summary = _missing_summary_for_node(client_name, definition)
    unlocked_analysis_value = _unlocked_analysis_value_for_node(client_name, definition)
    missing_labels = "、".join(unit.label for unit in missing_units[:3])
    next_deposit = suggested_title if missing_labels else _opportunity_deposit_for_node(client_name, definition.key)
    if missing_labels:
        next_deposit = suggested_title
    return DigitalAssetMapNodeRecord(
        key=definition.key,
        label=definition.label,
        description=definition.description,
        trackTitle=definition.track_title,
        currentStage=NODE_STAGE_NAMES[stage_index],
        stageIndex=stage_index,
        coverageScore=coverage_score,
        maturityPercent=maturity_percent,
        evidenceCount=max(len(matched_sources), sum(unit.evidenceCount for unit in covered_units)),
        coveredUnits=covered_units,
        missingUnits=missing_units,
        unlockedValue=_node_unlocked_value(definition, stage_index),
        nextDeposit=next_deposit,
        seenSummary=seen_summary,
        missingSummary=missing_summary,
        suggestedDocumentTitle=suggested_title,
        suggestedDocumentContent=suggested_content,
        unlockedAnalysisValue=unlocked_analysis_value,
        sourceHighlights=source_highlights,
        representativeSources=representative_sources,
    )


def _client_label(client_name: str) -> str:
    return _sanitize_public_text(client_name, limit=32) or "该组织"


def _guidance_for_node(node_key: str) -> dict[str, object]:
    return ASSET_NODE_DOCUMENT_GUIDANCE.get(node_key, {})


def _suggested_document_title(client_name: str, node_key: str) -> str:
    guidance = _guidance_for_node(node_key)
    template = str(guidance.get("title") or "{client}资料补充表")
    return f"《{template.format(client=_client_label(client_name))}》"


def _suggested_document_content(node_key: str) -> list[str]:
    guidance = _guidance_for_node(node_key)
    content = guidance.get("content")
    if isinstance(content, list):
        return [str(item) for item in content[:8]]
    return ["资料名称", "发生时间", "参与对象", "关键动作", "反馈摘要", "下一步判断"]


def _seen_summary_for_node(client_name: str, definition: AssetMapNode, source_highlights: list[str]) -> str:
    if not source_highlights:
        return f"系统还没有看到足够明确的{_client_label(client_name)}{definition.label}资料。"
    guidance = _guidance_for_node(definition.key)
    template = str(guidance.get("seen") or "系统已看到{client}的{sources}等资料，AI 已能识别这类资产的基础线索。")
    return template.format(
        client=_client_label(client_name),
        sources="、".join(source_highlights[:3]),
    )


def _missing_summary_for_node(client_name: str, definition: AssetMapNode) -> str:
    guidance = _guidance_for_node(definition.key)
    template = str(guidance.get("missing") or "还缺一份能持续记录这类资料变化的整理表。")
    summary = template.format(client=_client_label(client_name))
    content = _suggested_document_content(definition.key)
    if content:
        detail = "、".join(content[:6])
        summary = f"{summary} 需要补齐的关键内容包括：{detail}。"
    return summary


def _unlocked_analysis_value_for_node(client_name: str, definition: AssetMapNode) -> str:
    guidance = _guidance_for_node(definition.key)
    template = str(guidance.get("value") or definition.unlocked_value)
    return template.format(client=_client_label(client_name))


def _source_highlights(sources: list[AssetSource]) -> list[str]:
    highlights: list[str] = []
    seen: set[str] = set()
    ordered_sources = sorted(sources, key=lambda source: 1 if source.source_type == "notebook" else 0)
    for source in ordered_sources:
        title = _clean_source_title(source.title)
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        highlights.append(title)
        if len(highlights) >= 5:
            break
    return highlights


def _clean_source_title(title: str) -> str:
    text = _sanitize_public_text(title, limit=34)
    text = re.sub(r"\.(md|pdf|docx?|xlsx?|csv|txt|pptx?)$", "", text, flags=re.I)
    text = re.sub(r"(?:\[数字\][\s_\-]*)+", "", text)
    text = text.strip()
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"^\d+[、.．]\s*", "", text)
    text = re.sub(r"^(第[一二三四五六七八九十\d]+[章节篇][、.．]?\s*)", "", text)
    text = re.sub(r"[_\-]+", " ", text).strip(" /._-")
    return text


def _match_asset_sources(keywords: tuple[str, ...], sources: list[AssetSource]) -> list[AssetSource]:
    matched: list[AssetSource] = []
    for source in sources:
        text = f"{source.title} {source.text}".lower()
        if any(keyword.lower() in text for keyword in keywords):
            matched.append(source)
    return matched


def _unit_evidence_count(unit: AssetUnit, sources: list[AssetSource]) -> int:
    count = 0
    for source in sources:
        text = f"{source.title} {source.text}".lower()
        for keyword in unit.keywords:
            lower = keyword.lower()
            if lower not in text:
                continue
            if any(marker in text for marker in (f"没有{lower}", f"缺少{lower}", f"无{lower}", f"未沉淀{lower}")):
                continue
            if not _unit_source_qualifies(unit, source):
                continue
            count += 1
            break
    return count


def _asset_node_signal_cap(sources: list[AssetSource]) -> int:
    if not sources:
        return 0
    counts = _source_signal_counts(sources)
    if counts["opportunity"] >= 1:
        return 4
    if counts["linked"] >= 2:
        return 3
    if counts["structured"] >= 1:
        return 2
    return 1


def _source_signal_counts(sources: list[AssetSource]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for source in sources:
        flags = _source_signal_flags(source)
        if flags["structured"]:
            counts["structured"] += 1
        if flags["linked"]:
            counts["linked"] += 1
        if flags["opportunity"]:
            counts["opportunity"] += 1
    return counts


def _source_signal_flags(source: AssetSource) -> dict[str, bool]:
    text = f"{source.title} {source.text}".lower()
    time_buckets = _extract_time_buckets(text)
    has_field = _contains_any(text, FIELD_LEVEL_KEYWORDS)
    has_time = _contains_any(text, TIME_KEYWORDS) or bool(time_buckets)
    has_object = _contains_any(text, OBJECT_KEYWORDS)
    process_hits = sum(1 for keyword in PROCESS_SIGNAL_KEYWORDS if keyword.lower() in text)
    has_process = process_hits >= 2 or "流程节点" in text
    has_result = _contains_any(text, RESULT_KEYWORDS)
    has_decision = _contains_any(text, DECISION_SIGNAL_KEYWORDS)
    has_linkage = _contains_any(text, LINKAGE_KEYWORDS)
    has_cross_period = len(time_buckets) >= 2 or _contains_any(text, CROSS_PERIOD_KEYWORDS)
    has_opportunity_language = _contains_any(text, OPPORTUNITY_SIGNAL_KEYWORDS)
    has_predictive_language = _contains_any(text, PREDICTIVE_DATA_KEYWORDS)
    structured = has_field and has_time and (has_result or has_decision)
    linked = structured and has_object and has_process and has_result and has_linkage
    opportunity = linked and has_cross_period and has_opportunity_language and has_predictive_language
    return {
        "field": has_field,
        "time": has_time,
        "object": has_object,
        "process": has_process,
        "result": has_result,
        "decision": has_decision,
        "structured": structured,
        "linked": linked,
        "opportunity": opportunity,
    }


def _unit_source_qualifies(unit: AssetUnit, source: AssetSource) -> bool:
    if unit.level == "required":
        return True
    flags = _source_signal_flags(source)
    if unit.level == "advanced":
        if unit.key in NARRATIVE_ADVANCED_UNIT_KEYS:
            return flags["structured"] or flags["time"] or flags["decision"] or flags["result"]
        return flags["structured"]
    if unit.key in OPPORTUNITY_GENERATION_UNIT_KEYS:
        return flags["opportunity"]
    return flags["linked"] or flags["opportunity"]


def _coverage_cap_for_signal(signal_cap: int) -> int:
    return (22, 46, 72, 88, 100)[max(0, min(4, signal_cap))]


def _asset_node_maturity_percent(
    node_key: str,
    stage_index: int,
    signal_cap: int,
    covered_units: list[DigitalAssetUnitRecord],
    all_units: tuple[AssetUnit, ...],
    matched_sources: list[AssetSource],
) -> int:
    if not matched_sources and not covered_units:
        return 0
    ratios = _coverage_ratios(covered_units, all_units)
    signal_counts = _source_signal_counts(matched_sources)
    source_quality = min(
        1.0,
        (
            signal_counts.get("structured", 0)
            + signal_counts.get("linked", 0) * 2
            + signal_counts.get("opportunity", 0) * 3
        ) / max(3, len(matched_sources) * 0.35),
    ) if matched_sources else 0.0
    if stage_index <= 1:
        source_quality = min(1.0, len(matched_sources) / 4) if matched_sources else 0.0
    unit_quality = (
        ratios.get("required", 0.0) * 0.42
        + ratios.get("advanced", 0.0) * 0.38
        + ratios.get("opportunity", 0.0) * 0.20
    )
    stage_floor = (8, 24, 44, 64, 82)[max(0, min(4, stage_index))]
    stage_span = (14, 18, 26, 18, 14)[max(0, min(4, stage_index))]
    score = stage_floor + stage_span * (unit_quality * 0.72 + source_quality * 0.28)
    if signal_cap <= 2:
        score -= NODE_COMPLEXITY_PENALTY.get(node_key, 6)
    if signal_cap == 3:
        score -= max(0, NODE_COMPLEXITY_PENALTY.get(node_key, 6) // 3)
    cap_by_signal = (22, 46, 76, 90, 98)[max(0, min(4, signal_cap))]
    return max(5, min(cap_by_signal, int(round(score))))


def _asset_unit_coverage_score(covered_units: list[DigitalAssetUnitRecord], all_units: tuple[AssetUnit, ...]) -> int:
    if not all_units:
        return 0
    weight_by_level = {"required": 40, "advanced": 35, "opportunity": 25}
    total = sum(weight_by_level.get(unit.level, 0) for unit in all_units)
    covered = sum(weight_by_level.get(unit.level, 0) for unit in covered_units)
    return int(round((covered / total) * 100)) if total else 0


def _asset_node_stage_index(covered_units: list[DigitalAssetUnitRecord], all_units: tuple[AssetUnit, ...]) -> int:
    if not covered_units:
        return 0
    ratios = _coverage_ratios(covered_units, all_units)
    if ratios["required"] < 0.34:
        return 0
    stage_index = 1
    if ratios["required"] >= 0.67 and ratios["advanced"] >= 0.34:
        stage_index = 2
    if ratios["advanced"] >= 0.67 and ratios["opportunity"] >= 0.20:
        stage_index = 3
    opportunity_generation_units = {
        "new_strategy_opportunity",
        "business_map",
        "ecosystem_opportunity",
        "conversion_opportunity",
        "automation_opportunity",
        "new_business_signal",
    }
    if ratios["opportunity"] >= 0.67 and any(unit.key in opportunity_generation_units for unit in covered_units):
        stage_index = 4
    return stage_index


def _coverage_ratios(covered_units: list[DigitalAssetUnitRecord], all_units: tuple[AssetUnit, ...]) -> dict[str, float]:
    ratios: dict[str, float] = {}
    covered_by_level = Counter(unit.level for unit in covered_units)
    total_by_level = Counter(unit.level for unit in all_units)
    for level in ("required", "advanced", "opportunity"):
        total = total_by_level.get(level, 0)
        ratios[level] = (covered_by_level.get(level, 0) / total) if total else 0.0
    return ratios


def _build_stage_summary(
    nodes: list[DigitalAssetMapNodeRecord],
    metrics: list[DigitalAssetMetricRecord],
    understanding_score: int,
    empty_state: bool,
) -> dict[str, object]:
    deposit_xp = _compute_deposit_xp(metrics)
    if empty_state or not nodes:
        return {
            "assetStage": "资料整理期",
            "assetTrackTitle": "组织资产型",
            "growthMode": "均衡成长",
            "stageProgress": 0,
            "nextStage": "组织画像期",
            "unlockedCapabilities": ["资料归档和基础检索"],
            "stageBlockers": ["还没有足够资料形成组织数字资产，请先补充组织介绍、项目介绍、流程资料和反馈材料。"],
        }
    node_by_key = {node.key: node for node in nodes}
    org_ready = node_by_key.get("organization_identity", DigitalAssetMapNodeRecord(key="", label="")).stageIndex >= 1 or understanding_score >= 35
    business_ready = any(node_by_key.get(key, DigitalAssetMapNodeRecord(key="", label="")).stageIndex >= 1 for key in ("business_portfolio", "strategic_judgment"))
    has_structured = any(node.stageIndex >= 2 for node in nodes)
    # Recompute strict source-level caps from node stages: a stage 3/4 node means the
    # same source carried structured linkage, not merely keywords spread across files.
    linked_node_count = sum(1 for node in nodes if node.stageIndex >= 3)
    has_linked = linked_node_count >= 2 or (
        linked_node_count >= 1
        and any(node.key in {"audience_profile", "process_flow", "business_portfolio"} and node.stageIndex >= 2 for node in nodes)
    )
    has_opportunity = (
        any(node.key == "opportunity_pipeline" and node.stageIndex >= 4 for node in nodes)
        and linked_node_count >= 2
    )
    max_node_stage = max(node.stageIndex for node in nodes)
    cap = 4
    blockers: list[str] = []
    if not (org_ready and business_ready):
        cap = min(cap, 0)
        blockers.append("缺少组织身份、业务/项目或战略判断的基础资产，AI 还难以稳定理解这个组织。")
    if not has_structured:
        cap = min(cap, 1)
        blockers.append("缺少字段、表单、台账、指标等结构化资产，资料还主要停留在阅读和梳理层。")
    if not has_linked:
        cap = min(cap, 2)
        blockers.append("对象、流程、结果或判断尚未形成联动，暂时不能稳定解释机制和瓶颈。")
    if not has_opportunity:
        cap = min(cap, 3)
        blockers.append("缺少长期趋势、归因、转化或新机会信号，还不能进入机会生成阶段。")
    stage_index = min(max_node_stage, cap)
    if stage_index < 0:
        stage_index = 0
    track_node = _select_track_node(nodes)
    progress = _stage_progress(stage_index, nodes, deposit_xp)
    return {
        "assetStage": STAGE_NAMES[stage_index],
        "assetTrackTitle": track_node.trackTitle or "组织资产型",
        "growthMode": _growth_mode(nodes, deposit_xp, stage_index),
        "stageProgress": progress,
        "nextStage": STAGE_NAMES[stage_index + 1] if stage_index + 1 < len(STAGE_NAMES) else "已进入最高阶段",
        "unlockedCapabilities": _unlocked_capabilities(stage_index, track_node),
        "stageBlockers": blockers[:4],
    }


def _select_track_node(nodes: list[DigitalAssetMapNodeRecord]) -> DigitalAssetMapNodeRecord:
    if not nodes:
        return DigitalAssetMapNodeRecord(key="organization_identity", label="组织身份", trackTitle="组织资产型")
    return sorted(
        nodes,
        key=lambda node: (
            node.stageIndex,
            node.coverageScore,
            -_track_priority(node.key),
            node.evidenceCount,
        ),
        reverse=True,
    )[0]


def _track_priority(key: str) -> int:
    order = {
        "strategic_judgment": 0,
        "audience_profile": 1,
        "process_flow": 2,
        "outcome_evidence": 3,
        "data_system": 4,
        "business_portfolio": 5,
        "resource_ecosystem": 6,
        "communication_conversion": 7,
        "management_decision": 8,
        "opportunity_pipeline": 9,
        "organization_identity": 10,
    }
    return order.get(key, 99)


def _stage_progress(stage_index: int, nodes: list[DigitalAssetMapNodeRecord], deposit_xp: int) -> int:
    if not nodes:
        return 0
    if stage_index <= 0:
        return min(95, max(5, deposit_xp // 20))
    if stage_index == 1:
        values = [_level_coverage(node, "advanced") for node in nodes if node.stageIndex >= 1]
    elif stage_index == 2:
        values = [_level_coverage(node, "opportunity") for node in nodes if node.stageIndex >= 2]
    elif stage_index == 3:
        values = [node.coverageScore for node in nodes if node.stageIndex >= 3]
    else:
        values = [node.coverageScore for node in nodes]
    if not values:
        return 0
    return int(round(sum(values) / len(values)))


def _level_coverage(node: DigitalAssetMapNodeRecord, level: str) -> int:
    total = len([unit for unit in [*node.coveredUnits, *node.missingUnits] if unit.level == level])
    if total <= 0:
        return 0
    covered = len([unit for unit in node.coveredUnits if unit.level == level])
    return int(round(covered / total * 100))


def _growth_mode(nodes: list[DigitalAssetMapNodeRecord], deposit_xp: int, stage_index: int) -> str:
    active = [node for node in nodes if node.evidenceCount > 0 or node.coveredUnits]
    if deposit_xp >= 500 and stage_index <= 1:
        return "结构偏科"
    if len(active) <= 1:
        return "单项突破"
    stages = [node.stageIndex for node in active]
    if max(stages) - (sum(stages) / len(stages)) >= 1.2:
        return "单项突破"
    if any(node.coverageScore >= 70 for node in active) and sum(1 for node in active if node.coverageScore >= 45) <= 2:
        return "单项突破"
    return "均衡成长"


def _unlocked_capabilities(stage_index: int, track_node: DigitalAssetMapNodeRecord) -> list[str]:
    capabilities = ["资料归档、检索和基础梳理"]
    if stage_index >= 1:
        capabilities.append("组织背景、业务范围和关键关系理解")
    if stage_index >= 2:
        capabilities.append(f"{track_node.label}的结构化对比和分析")
    if stage_index >= 3:
        capabilities.append("对象、流程、结果、资源和判断之间的机制洞察")
    if stage_index >= 4:
        capabilities.append("新产品、新业务、新服务和数字化机会识别")
    return capabilities


def _compute_deposit_xp(metrics: list[DigitalAssetMetricRecord]) -> int:
    return (
        _metric_value(metrics, "documents") * 10
        + _metric_value(metrics, "memoryFacts") * 6
        + _metric_value(metrics, "evidenceCards") * 12
        + _metric_value(metrics, "themeClusters") * 20
        + _metric_value(metrics, "openQuestions") * 15
        + _metric_value(metrics, "judgments") * 24
        + _metric_value(metrics, "eventLines") * 30
        + _metric_value(metrics, "meetings") * 18
    )


def _build_next_best_deposits(
    client_name: str,
    nodes: list[DigitalAssetMapNodeRecord],
    empty_state: bool,
) -> list[DigitalAssetDepositSuggestionRecord]:
    if empty_state:
        title = f"《{_client_label(client_name)}组织介绍与项目资料包》"
        return [
            DigitalAssetDepositSuggestionRecord(
                priority="high",
                dimensionKey="organization_identity",
                title=title,
                reason=f"当前还没有足够资料进入组织画像期，需要先让 AI 稳定理解{_client_label(client_name)}是谁、做什么、服务谁。",
                examples=["组织介绍", "重点项目介绍", "项目流程", "反馈材料", "阶段复盘"],
                expectedGain=30,
                analysisValueUnlocked="解锁资料整理和组织画像的第一版资产地图。",
                suggestedDocumentContent=["组织使命/定位", "重点项目", "服务对象", "主要流程", "已有反馈", "下一阶段目标"],
            )
        ]
    suggestions: list[DigitalAssetDepositSuggestionRecord] = []
    for node in sorted(nodes, key=lambda item: (_suggestion_stage_bucket(item), -item.evidenceCount, _track_priority(item.key), -len(item.missingUnits), -item.coverageScore)):
        if not node.missingUnits and node.stageIndex >= 4:
            continue
        missing = node.missingUnits[:4] or _stage_gap_units(node)
        title = node.suggestedDocumentTitle or _stage_gap_deposit_title(node)
        priority = "high" if node.stageIndex <= 1 else ("medium" if node.stageIndex == 2 else "low")
        document_content = node.suggestedDocumentContent or [unit.label for unit in missing[:5]]
        suggestions.append(
            DigitalAssetDepositSuggestionRecord(
                priority=priority,  # type: ignore[arg-type]
                dimensionKey=node.key,
                title=title,
                reason=node.missingSummary or f"{node.label}还缺少可持续复盘的资料，限制了从{node.currentStage}进入下一层能力。",
                examples=document_content,
                expectedGain=max(4, min(18, len(missing) * 4 + (2 - node.stageIndex) * 2)),
                analysisValueUnlocked=node.unlockedAnalysisValue or node.unlockedValue,
                suggestedDocumentContent=document_content,
                sourceHighlights=node.sourceHighlights,
            )
        )
        if len(suggestions) >= 4:
            break
    return suggestions


def _suggestion_stage_bucket(node: DigitalAssetMapNodeRecord) -> int:
    if node.stageIndex == 2:
        return 0
    if node.stageIndex <= 1:
        return 1
    return 2


def _stage_gap_units(node: DigitalAssetMapNodeRecord) -> list[DigitalAssetUnitRecord]:
    if node.stageIndex <= 1:
        labels = ("字段口径", "时间/批次", "结果字段")
    elif node.stageIndex == 2:
        labels = ("对象-流程-结果联动", "机制/归因线索", "判断验证结果")
    else:
        labels = ("跨周期趋势", "转化/归因数据", "新业务/数字化机会信号")
    return [
        DigitalAssetUnitRecord(
            key=f"{node.key}_gap_{index}",
            label=label,
            level="advanced" if node.stageIndex <= 2 else "opportunity",
            covered=False,
            evidenceCount=0,
        )
        for index, label in enumerate(labels)
    ]


def _stage_gap_deposit_title(node: DigitalAssetMapNodeRecord) -> str:
    titles = {
        "strategic_judgment": "补判断验证库：判断、依据、时间、后续事实和验证结论",
        "business_portfolio": "补重点项目年度结果表：重点项目、服务对象、交付过程、反馈和年度结果放在一起比较",
        "audience_profile": "补参与方反馈整理表：参与方类型、来源、参与原因、反馈和后续需求",
        "process_flow": "补重点项目流程复盘表：筹备、邀约、参与、反馈和复盘连续记录",
        "outcome_evidence": "补项目成效与反馈汇总表：项目目标、实际反馈、典型案例和复盘结论",
        "data_system": "补数据表与看板说明：每张表记录什么、统计指标怎么算、看板数据从哪里来",
        "management_decision": "补决策复盘表：会议决策、负责人、执行结果和后续验证",
        "resource_ecosystem": "补伙伴贡献表：伙伴类型、资源承诺、协作动作和结果贡献",
        "communication_conversion": "补传播转化表：内容、渠道、触达、反馈和资源转化结果",
        "opportunity_pipeline": "补机会实验表：未满足需求、目标场景、试点动作、反馈和采用结果",
    }
    return titles.get(node.key, node.nextDeposit)


def _build_value_insights_from_nodes(nodes: list[DigitalAssetMapNodeRecord]) -> list[DigitalAssetInsightRecord]:
    insights: list[DigitalAssetInsightRecord] = []
    for node in sorted(nodes, key=lambda item: (item.stageIndex, item.coverageScore, item.evidenceCount), reverse=True):
        if node.stageIndex <= 0:
            continue
        title = f"{node.label}进入{node.currentStage}阶段"
        summary = node.unlockedValue or f"{node.label}已经形成可复用数字资产。"
        insights.append(
            DigitalAssetInsightRecord(
                dimensionKey=node.key,
                title=title,
                summary=summary,
                evidenceCount=node.evidenceCount,
            )
        )
    return insights


def _node_unlocked_value(definition: AssetMapNode, stage_index: int) -> str:
    if stage_index >= 4:
        return f"{definition.unlocked_value} 已开始具备机会生成价值。"
    if stage_index >= 3:
        return f"{definition.unlocked_value} 已具备机制洞察基础。"
    if stage_index >= 2:
        return f"{definition.unlocked_value} 已进入结构化计算阶段。"
    if stage_index >= 1:
        return f"{definition.label}已能作为 AI 理解组织的稳定背景。"
    return definition.unlocked_value


def _opportunity_deposit_for_node(client_name: str, node_key: str) -> str:
    suggestions = {
        "strategic_judgment": f"继续沉淀{_client_label(client_name)}战略判断和后续事实，形成判断验证库。",
        "business_portfolio": f"继续沉淀{_client_label(client_name)}项目结果、参与反馈和复盘结论，形成业务价值地图。",
        "audience_profile": f"继续按批次沉淀{_client_label(client_name)}参与方变化，分析服务对象迁移和需求变化。",
        "process_flow": f"继续沉淀{_client_label(client_name)}项目流程、反馈和复盘，分析转化和流失。",
        "outcome_evidence": f"继续沉淀{_client_label(client_name)}成效证据、趋势和影响因素，解释项目为什么有效。",
        "data_system": f"继续把{_client_label(client_name)}表单、看板和系统流程固化成可复用数据资产。",
    }
    return suggestions.get(node_key, "继续把资料、字段、结果和复盘绑定起来，提升长期复利价值。")


def _build_dimension_record(
    dimension: AssetDimension,
    sources: list[AssetSource],
    metrics: list[DigitalAssetMetricRecord],
) -> DigitalAssetDimensionRecord:
    matched = _match_sources(dimension, sources)
    type_counts = Counter(source.source_type for source in matched)
    evidence_count = len(matched)
    score_breakdown = _compute_score_breakdown(dimension, matched, type_counts)
    maturity = score_breakdown.deposited + score_breakdown.understood + score_breakdown.computable + score_breakdown.compounding
    next_best_deposit, expected_gain, analysis_value = _next_best_deposit_for_dimension(dimension, score_breakdown)
    representative_sources = [
        DigitalAssetSourceRefRecord(
            sourceType=source.source_type,
            sourceId=source.source_id,
            title=_sanitize_public_text(source.title, limit=48) or SOURCE_TYPE_LABELS.get(source.source_type, "资料"),
            excerpt=_sanitize_public_text(source.text, limit=96),
            updatedAt=source.updated_at,
        )
        for source in matched[:4]
    ]
    source_types = [SOURCE_TYPE_LABELS.get(source_type, source_type) for source_type, _ in type_counts.most_common()]
    formed_value = _formed_value_for_dimension(dimension, evidence_count, score_breakdown)
    value_insights = [formed_value, *dimension.value_insights] if formed_value else list(dimension.value_insights)
    gaps = []
    if evidence_count == 0:
        gaps.append(dimension.gap)
    elif score_breakdown.computable < 10:
        gaps.append(f"{dimension.label}已经有沉淀价值，但还缺少结构化、可对比的数据。")
    elif score_breakdown.compounding < 12:
        gaps.append(f"{dimension.label}已经能被理解和计算，但还缺少足够支撑趋势判断的连续数据。")
    suggestions = list(dimension.suggestions)
    if dimension.key in {"process_flow", "outcome_evidence", "audience_subject"} and _metric_value(metrics, "documents") > 0:
        suggestions.append("优先把同一类资料按时间持续沉淀，未来才能看出变化趋势。")
    if next_best_deposit and next_best_deposit not in suggestions:
        suggestions.insert(0, next_best_deposit)
    return DigitalAssetDimensionRecord(
        key=dimension.key,
        label=dimension.label,
        description=dimension.description,
        maturity=maturity,
        scoreBreakdown=score_breakdown,
        evidenceCount=evidence_count,
        sourceTypes=source_types,
        representativeSources=representative_sources,
        valueInsights=value_insights,
        gaps=gaps,
        depositSuggestions=suggestions,
        formedValue=formed_value,
        nextBestDeposit=next_best_deposit,
        expectedGain=expected_gain,
        analysisValueUnlocked=analysis_value,
        statusLabels=_status_labels(score_breakdown),
    )


def _match_sources(dimension: AssetDimension, sources: list[AssetSource]) -> list[AssetSource]:
    matched: list[AssetSource] = []
    for source in sources:
        text = source.text.lower()
        title = source.title.lower()
        if any(keyword.lower() in text or keyword.lower() in title for keyword in dimension.keywords):
            matched.append(source)
    return matched


def _compute_score_breakdown(
    dimension: AssetDimension,
    matched: list[AssetSource],
    type_counts: Counter[str],
) -> DigitalAssetScoreBreakdownRecord:
    evidence_count = len(matched)
    if evidence_count <= 0:
        return DigitalAssetScoreBreakdownRecord()
    text = _join_text(*(source.text for source in matched), *(source.title for source in matched)).lower()
    deposited = _score_deposited(evidence_count, type_counts)
    understood = _score_understood(evidence_count, type_counts)
    computable = _score_computable(dimension, text, evidence_count, type_counts)
    compounding = _score_compounding(text, evidence_count, computable)
    return DigitalAssetScoreBreakdownRecord(
        deposited=deposited,
        understood=understood,
        computable=computable,
        compounding=compounding,
    )


def _score_deposited(evidence_count: int, type_counts: Counter[str]) -> int:
    score = 10 if evidence_count else 0
    score += min(12, max(0, evidence_count - 1) * 2)
    score += min(8, len(type_counts) * 2)
    if type_counts.get("document") or type_counts.get("document_card"):
        score += 4
    if type_counts.get("memory"):
        score += 3
    if type_counts.get("evidence") or type_counts.get("theme") or type_counts.get("judgment"):
        score += 5
    return min(40, score)


def _score_understood(evidence_count: int, type_counts: Counter[str]) -> int:
    score = 4 if evidence_count else 0
    if type_counts.get("notebook"):
        score += 5
    if type_counts.get("theme"):
        score += 5
    if type_counts.get("evidence"):
        score += 5
    if type_counts.get("judgment"):
        score += 6
    if type_counts.get("memory") or type_counts.get("document_card"):
        score += 3
    if evidence_count >= 6 and len(type_counts) >= 2:
        score += 2
    return min(25, score)


def _score_computable(
    dimension: AssetDimension,
    text: str,
    evidence_count: int,
    type_counts: Counter[str],
) -> int:
    if evidence_count <= 0:
        return 0
    has_field_level = _contains_any(text, FIELD_LEVEL_KEYWORDS)
    has_structured = _contains_any(text, STRUCTURED_KEYWORDS)
    has_time = _contains_any(text, TIME_KEYWORDS) or bool(TIME_RE.search(text))
    has_object = _contains_any(text, OBJECT_KEYWORDS)
    has_result = _contains_any(text, RESULT_KEYWORDS)
    score = 0
    if has_field_level:
        score += 7
    elif has_structured:
        score += 3
    if has_time:
        score += 3
    if has_object:
        score += 3
    if has_result:
        score += 4
    if has_field_level and has_time and has_object and has_result:
        score += 2
    if evidence_count >= 10 and has_field_level and (type_counts.get("document") or type_counts.get("document_card")):
        score += 2
    if dimension.key in {"data_system", "process_flow", "outcome_evidence", "audience_subject"} and has_field_level:
        score += 1
    if any(marker in text for marker in ("没有连续字段", "缺少字段", "缺少口径", "没有结构化", "缺少结构化")):
        score -= 7
    if not has_field_level:
        score = min(score, 9)
    if not has_time:
        score = min(score, 14)
    if dimension.key in {"process_flow", "outcome_evidence", "content_brand_fundraising"} and not has_result:
        score = min(score, 12)
    return max(0, min(20, score))


def _score_compounding(text: str, evidence_count: int, computable_score: int) -> int:
    if evidence_count <= 0:
        return 0
    months = _extract_time_buckets(text)
    has_longitudinal_signal = _contains_any(text, TREND_KEYWORDS) or len(months) >= 2
    score = 0
    if len(months) >= 2:
        score += 3
    if len(months) >= 3:
        score += 2
    if len(months) >= 6:
        score += 3
    if _contains_any(text, TREND_KEYWORDS):
        score += 3
    if _contains_any(text, RESULT_KEYWORDS) and (_contains_any(text, TIME_KEYWORDS) or len(months) >= 2):
        score += 2
    if evidence_count >= 10 and len(months) >= 2:
        score += 1
    if computable_score >= 12 and has_longitudinal_signal:
        score += 2
    if any(marker in text for marker in ("没有连续", "缺少连续", "不连续", "缺少长期", "没有长期")):
        score -= 6
    if not _contains_any(text, PREDICTIVE_DATA_KEYWORDS):
        cap = 10 if computable_score >= 16 and has_longitudinal_signal else 8
    else:
        cap = 15
    if computable_score < 10:
        cap = 5
    elif computable_score < 16:
        cap = 10
    if not has_longitudinal_signal:
        cap = min(cap, 6)
    return max(0, min(15, cap, score))


def _build_value_insights(dimensions: list[DigitalAssetDimensionRecord]) -> list[DigitalAssetInsightRecord]:
    insights: list[DigitalAssetInsightRecord] = []
    for dimension in sorted(dimensions, key=lambda item: item.maturity, reverse=True):
        if dimension.evidenceCount <= 0:
            continue
        signal = dimension.formedValue or VALUE_SIGNAL_BY_DIMENSION.get(dimension.key)
        if not signal:
            continue
        insights.append(
            DigitalAssetInsightRecord(
                dimensionKey=dimension.key,
                title=f"{dimension.label}已形成价值",
                summary=signal,
                evidenceCount=dimension.evidenceCount,
            )
        )
    return insights


def _build_deposit_suggestions(
    dimensions: list[DigitalAssetDimensionRecord],
    empty_state: bool,
) -> list[DigitalAssetDepositSuggestionRecord]:
    if empty_state:
        return [
            DigitalAssetDepositSuggestionRecord(
                priority="high",
                dimensionKey="business_project",
                title="先上传项目介绍、流程资料、反馈表和评估材料",
                reason="当前资料还不足以形成组织数字资产地图，先建立 AI 理解组织的基础上下文。",
                examples=["项目介绍", "项目流程", "报名/反馈表", "阶段复盘", "成效评估"],
                expectedGain=18,
                analysisValueUnlocked="解锁基础组织理解和第一版资产地图。",
            )
        ]
    suggestions: list[DigitalAssetDepositSuggestionRecord] = []
    priority_dimensions = {
        "process_flow": "high",
        "outcome_evidence": "high",
        "audience_subject": "high",
        "data_system": "medium",
        "management_decision": "medium",
    }
    sorted_dimensions = sorted(
        dimensions,
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}[_dimension_priority(item)],
            -(item.expectedGain or 0),
            item.maturity,
        ),
    )
    for dimension in sorted_dimensions:
        suggestion = dimension.nextBestDeposit or (dimension.depositSuggestions[0] if dimension.depositSuggestions else "继续补齐这类资料的连续沉淀。")
        gap = dimension.gaps[0] if dimension.gaps else f"{dimension.label}还可以继续提升可计算性。"
        priority = _dimension_priority(dimension)
        if dimension.key in priority_dimensions and priority == "medium" and dimension.expectedGain >= 8:
            priority = "high"
        suggestions.append(
            DigitalAssetDepositSuggestionRecord(
                priority=priority,  # type: ignore[arg-type]
                dimensionKey=dimension.key,
                title=suggestion,
                reason=gap,
                examples=_suggestion_examples(dimension.key),
                expectedGain=dimension.expectedGain,
                analysisValueUnlocked=dimension.analysisValueUnlocked,
            )
        )
        if len(suggestions) >= 6:
            break
    return sorted(suggestions, key=lambda item: {"high": 0, "medium": 1, "low": 2}[item.priority])


def _formed_value_for_dimension(
    dimension: AssetDimension,
    evidence_count: int,
    score_breakdown: DigitalAssetScoreBreakdownRecord,
) -> str:
    if evidence_count <= 0:
        return ""
    if score_breakdown.computable >= 12:
        return f"{dimension.label}已经不只是资料线索，开始具备结构化分析价值。{VALUE_SIGNAL_BY_DIMENSION.get(dimension.key, '')}"
    if score_breakdown.understood >= 15:
        return f"{dimension.label}已经被 AI 稳定识别和概括，可作为后续研判的组织背景。"
    return f"{dimension.label}已经出现有效线索，说明这类资料的沉淀正在变成组织资产。"


def _next_best_deposit_for_dimension(
    dimension: AssetDimension,
    score_breakdown: DigitalAssetScoreBreakdownRecord,
) -> tuple[str, int, str]:
    if score_breakdown.deposited <= 0:
        return dimension.suggestions[0], 14, "解锁这个维度的基础识别和资产地图占位。"
    if score_breakdown.computable < 10:
        return (
            _computable_suggestion(dimension.key),
            min(16, 20 - score_breakdown.computable + 4),
            _computable_value(dimension.key),
        )
    if score_breakdown.compounding < 10:
        return (
            _compounding_suggestion(dimension.key),
            min(12, 15 - score_breakdown.compounding + 2),
            _compounding_value(dimension.key),
        )
    if score_breakdown.understood < 18:
        return (
            "补充一份人工确认的阶段复盘或关键判断说明。",
            min(10, 25 - score_breakdown.understood + 2),
            "让 AI 从资料命中升级为稳定组织理解。",
        )
    return (
        _advanced_suggestion(dimension.key),
        4,
        "继续提升这个维度的连续验证能力。",
    )


def _computable_suggestion(dimension_key: str) -> str:
    suggestions = {
        "strategy_identity": "补充战略判断表：时间、判断、依据、结果验证。",
        "business_project": "补充项目台账：项目、对象、阶段、产出、结果字段。",
        "audience_subject": "补充服务对象画像表：身份、来源、参与动机、需求标签。",
        "process_flow": "补充流程节点表：报名、审核、参与、反馈、结课状态。",
        "outcome_evidence": "补充成效评估表：前后测、反馈、案例和结果字段。",
        "relationship_ecosystem": "补充伙伴关系表：伙伴类型、资源承诺、协作状态。",
        "content_brand_fundraising": "补充传播/筹款数据：内容、渠道、触达、反馈、转化。",
        "management_decision": "补充决策台账：会议、决策、负责人、验证结果。",
        "data_system": "补充字段口径和看板指标说明，形成数据字典。",
    }
    return suggestions.get(dimension_key, "补充结构化字段和可对比数据。")


def _compounding_suggestion(dimension_key: str) -> str:
    suggestions = {
        "strategy_identity": "按季度沉淀战略判断变化和验证结果。",
        "business_project": "按项目周期持续沉淀项目复盘和交付结果。",
        "audience_subject": "按批次持续沉淀服务对象变化和参与动机。",
        "process_flow": "按每期项目持续沉淀同一套流程节点数据。",
        "outcome_evidence": "按前后测和结课周期持续沉淀成效变化。",
        "relationship_ecosystem": "按合作周期持续沉淀伙伴贡献和风险变化。",
        "content_brand_fundraising": "按传播/筹款周期持续沉淀触达、反馈和转化。",
        "management_decision": "按月沉淀决策复盘，记录判断是否被验证。",
        "data_system": "按月固化看板快照和指标变化说明。",
    }
    return suggestions.get(dimension_key, "持续按时间周期沉淀同一类资料。")


def _advanced_suggestion(dimension_key: str) -> str:
    suggestions = {
        "strategy_identity": "把关键战略判断与后续结果绑定，形成判断验证库。",
        "business_project": "把项目组合和结果数据联动，形成业务价值地图。",
        "audience_subject": "把画像字段和反馈结果联动，分析受众变化。",
        "process_flow": "把流程节点和结果字段联动，分析转化与流失。",
        "outcome_evidence": "把成效数据和项目机制联动，分析影响因子。",
        "relationship_ecosystem": "把伙伴资源和项目结果联动，分析生态贡献。",
        "content_brand_fundraising": "把传播内容和转化结果联动，分析品牌吸引力。",
        "management_decision": "把决策依据和结果验证联动，形成管理判断资产。",
        "data_system": "把字段口径、看板指标和业务判断联动，形成可复用数据资产。",
    }
    return suggestions.get(dimension_key, "把资料、判断和结果验证绑定起来。")


def _computable_value(dimension_key: str) -> str:
    values = {
        "audience_subject": "未来可分析受众结构、需求变化和组织吸引力。",
        "process_flow": "未来可分析报名、审核、参与、反馈、结课的转化链路。",
        "outcome_evidence": "未来可分析项目是否有效，以及成效来自哪些机制。",
        "data_system": "未来可让 AI 基于字段和指标直接查询、比较、解释。",
    }
    return values.get(dimension_key, "未来可从资料阅读升级为结构化分析。")


def _compounding_value(dimension_key: str) -> str:
    values = {
        "strategy_identity": "未来可追踪组织战略判断如何变化，以及哪些判断被验证。",
        "business_project": "未来可比较不同项目周期的投入、交付和价值变化。",
        "audience_subject": "未来可判断受众群体和参与动机是否发生迁移。",
        "process_flow": "未来可发现关键流程瓶颈和转化变化。",
        "outcome_evidence": "未来可看见成效趋势，而不是只看单次反馈。",
        "relationship_ecosystem": "未来可判断伙伴资源和协作风险如何变化。",
        "content_brand_fundraising": "未来可判断品牌吸引力和资源转化是否变化。",
        "management_decision": "未来可验证管理决策是否真的推动结果。",
        "data_system": "未来可沉淀组织自己的长期指标体系。",
    }
    return values.get(dimension_key, "未来可形成趋势判断和长期复利分析。")


def _status_labels(score_breakdown: DigitalAssetScoreBreakdownRecord) -> list[str]:
    continuity_label = "可预测" if score_breakdown.compounding >= 12 else ("可追踪" if score_breakdown.compounding >= 8 else "待连续")
    return [
        "已识别" if score_breakdown.deposited > 0 else "未识别",
        "可理解" if score_breakdown.understood >= 15 else "理解中",
        "可计算" if score_breakdown.computable >= 12 else "待结构化",
        continuity_label,
    ]


def _dimension_priority(dimension: DigitalAssetDimensionRecord) -> str:
    if dimension.scoreBreakdown.computable < 10:
        return "high"
    if dimension.scoreBreakdown.compounding < 10 or dimension.scoreBreakdown.understood < 18:
        return "medium"
    return "low"


def _suggestion_examples(dimension_key: str) -> list[str]:
    examples: dict[str, list[str]] = {
        "strategy_identity": ["战略复盘", "阶段目标", "关键判断"],
        "business_project": ["项目介绍", "交付清单", "项目复盘"],
        "audience_subject": ["报名信息", "参与动机", "服务对象反馈"],
        "process_flow": ["报名表", "审核记录", "结课记录"],
        "outcome_evidence": ["前后测", "满意度", "成效案例"],
        "relationship_ecosystem": ["伙伴沟通纪要", "资源承诺", "合作复盘"],
        "content_brand_fundraising": ["传播文案", "筹款材料", "转化反馈"],
        "management_decision": ["会议纪要", "OKR", "执行手册"],
        "data_system": ["字段说明", "表单结构", "看板指标"],
    }
    return examples.get(dimension_key, [])


def _build_critical_gaps(dimensions: list[DigitalAssetDimensionRecord], empty_state: bool) -> list[str]:
    if empty_state:
        return ["还没有足够资料形成数字资产，请先补充项目介绍、流程资料、反馈表和评估材料。"]
    gaps: list[str] = []
    for dimension in sorted(dimensions, key=lambda item: item.maturity):
        if dimension.maturity >= 45:
            continue
        if dimension.gaps:
            gaps.append(dimension.gaps[0])
        if len(gaps) >= 3:
            break
    return gaps or ["当前已形成基础资产地图，下一步应提高资料的连续性和结构化程度。"]


def _compute_asset_completion_score(dimensions: list[DigitalAssetDimensionRecord], empty_state: bool) -> int:
    if empty_state or not dimensions:
        return 0
    total = sum(dimension.maturity for dimension in dimensions)
    return int(round(total / len(dimensions)))


def _average_breakdown(dimensions: list[DigitalAssetDimensionRecord], key: str) -> int:
    if not dimensions:
        return 0
    values = [int(getattr(dimension.scoreBreakdown, key, 0)) for dimension in dimensions]
    return int(round(sum(values) / len(values)))


def _level_from_score(score: int, mode: str = "") -> str:
    if mode == "deposited":
        if score >= 30:
            return "高"
        if score >= 16:
            return "中"
        return "低"
    if score >= 70:
        return "高"
    if score >= 45:
        return "中"
    return "低"


def _next_value_space(suggestions: list[DigitalAssetDepositSuggestionRecord]) -> str:
    if not suggestions:
        return "小"
    high = sum(1 for item in suggestions if item.priority == "high")
    expected_gain = sum(item.expectedGain for item in suggestions[:3])
    if high >= 2 or expected_gain >= 24:
        return "大"
    if high >= 1 or expected_gain >= 12:
        return "中"
    return "小"


def _build_understanding_statement(
    *,
    client_name: str,
    score: int,
    dimensions: list[DigitalAssetDimensionRecord],
    empty_state: bool,
    notebook_intro: str,
    asset_stage: str = "",
    track_title: str = "",
    blockers: list[str] | None = None,
) -> str:
    if empty_state:
        return f"AI 还没有足够资料理解{client_name}，需要先建立项目、流程、对象和成效的基础材料。"
    if asset_stage:
        blocker_text = blockers[0] if blockers else "下一步应补齐能进入更高阶段的关键资产单元。"
        intro = _sanitize_public_text(notebook_intro, limit=80)
        intro_suffix = intro if intro else ""
        return f"{client_name}当前处于{asset_stage} · {track_title or '组织资产型'}，AI 已能围绕现有数字资产开展对应层级的工作。限制升级的关键短板是：{blocker_text}{intro_suffix}"
    top_labels = "、".join(dimension.label for dimension in sorted(dimensions, key=lambda item: item.maturity, reverse=True)[:3])
    weak_computable = [dimension.label for dimension in dimensions if dimension.scoreBreakdown.computable < 10][:2]
    weak_compounding = [dimension.label for dimension in dimensions if dimension.scoreBreakdown.compounding < 8][:2]
    if score >= 70:
        prefix = "数字资产已经形成较高完成度"
    elif score >= 45:
        prefix = "数字资产已经形成基础完成度"
    else:
        prefix = "数字资产仍处在初步沉淀阶段"
    intro = _sanitize_public_text(notebook_intro, limit=80)
    gap_sentence = ""
    if weak_computable:
        gap_sentence = f"下一步重点是把{ '、'.join(weak_computable) }补成结构化、可对比的数据。"
    elif weak_compounding:
        gap_sentence = f"下一步重点是让{ '、'.join(weak_compounding) }形成跨周期连续沉淀。"
    if intro:
        return f"{prefix}，当前最清晰的资产集中在{top_labels or '资料沉淀'}。{gap_sentence}{intro}"
    return f"{prefix}，当前最清晰的资产集中在{top_labels or '资料沉淀'}。{gap_sentence}"


def _build_metrics(db: Database, client_id: str) -> list[DigitalAssetMetricRecord]:
    document_count = _safe_count(db, "SELECT COUNT(1) AS count FROM documents WHERE client_id = ?", (client_id,))
    ready_document_count = _safe_count(
        db,
        "SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND parse_status IN ('ready','partial_ready')",
        (client_id,),
    )
    memory_fact_count = _safe_count(
        db,
        "SELECT COUNT(1) AS count FROM memory_facts WHERE scope_type = 'client' AND scope_id = ?",
        (client_id,),
    )
    event_line_count = _safe_count(db, "SELECT COUNT(1) AS count FROM event_lines WHERE primary_client_id = ?", (client_id,))
    meeting_count = _safe_count(db, "SELECT COUNT(1) AS count FROM meetings WHERE client_id = ?", (client_id,))
    task_count = _safe_count(
        db,
        """
        SELECT COUNT(1) AS count
        FROM tasks t
        LEFT JOIN event_lines e ON t.event_line_id = e.id
        WHERE e.primary_client_id = ? OR (t.source_type = 'client' AND t.source_id = ?)
        """,
        (client_id, client_id),
    )
    dna_count = _safe_count(
        db,
        "SELECT COUNT(1) AS count FROM client_dna_documents WHERE client_id = ? AND summary != '' AND summary IS NOT NULL",
        (client_id,),
    )
    evidence_count = _safe_count(db, "SELECT COUNT(1) AS count FROM evidence_cards WHERE client_id = ?", (client_id,))
    theme_count = _safe_count(db, "SELECT COUNT(1) AS count FROM theme_clusters WHERE client_id = ?", (client_id,))
    question_count = _safe_count(db, "SELECT COUNT(1) AS count FROM open_questions WHERE client_id = ?", (client_id,))
    judgment_count = _safe_count(db, "SELECT COUNT(1) AS count FROM judgment_versions WHERE client_id = ?", (client_id,))
    analysis_run_count = _safe_count(db, "SELECT COUNT(1) AS count FROM client_analysis_runs WHERE client_id = ?", (client_id,))
    return [
        DigitalAssetMetricRecord(key="documents", label="资料", value=document_count, hint=f"{ready_document_count} 份已解析"),
        DigitalAssetMetricRecord(key="memoryFacts", label="记忆", value=memory_fact_count),
        DigitalAssetMetricRecord(key="eventLines", label="事件线", value=event_line_count),
        DigitalAssetMetricRecord(key="meetings", label="会议", value=meeting_count),
        DigitalAssetMetricRecord(key="tasks", label="任务", value=task_count),
        DigitalAssetMetricRecord(key="dnaDocuments", label="DNA", value=dna_count),
        DigitalAssetMetricRecord(key="evidenceCards", label="证据卡", value=evidence_count),
        DigitalAssetMetricRecord(key="themeClusters", label="主题簇", value=theme_count),
        DigitalAssetMetricRecord(key="openQuestions", label="开放问题", value=question_count),
        DigitalAssetMetricRecord(key="judgments", label="判断", value=judgment_count),
        DigitalAssetMetricRecord(key="analysisRuns", label="分析", value=analysis_run_count),
    ]


def _collect_sources(db: Database, client_id: str) -> list[AssetSource]:
    sources: list[AssetSource] = []
    notebook = _read_notebook_snapshot(db, client_id)
    if notebook:
        notebook_text = " ".join(
            [
                str(notebook.get("organizationIntro", "")),
                str(notebook.get("collaborationRelationship", "")),
                str(notebook.get("currentStage", "")),
                " ".join(notebook.get("businessModules", [])),
                " ".join(notebook.get("keyProducts", [])),
                " ".join(notebook.get("currentChallenges", [])),
                " ".join(notebook.get("collaborationGoals", [])),
                " ".join(notebook.get("recentFacts", [])),
                " ".join(notebook.get("informationGaps", [])),
            ]
        )
        if notebook_text.strip():
            sources.append(
                AssetSource(
                    source_type="notebook",
                    source_id=str(notebook.get("id", "")),
                    title="组织画像",
                    text=notebook_text,
                    updated_at=str(notebook.get("updatedAt", "")) or None,
                )
            )

    for row in _safe_fetchall(
        db,
        """
        SELECT
          d.id, d.title, d.excerpt, d.kind, d.created_at,
          vd.file_name, vd.visible_category, vd.secondary_category, vd.preview_text,
          vd.doc_index_text, vd.markdown_content, vd.parse_status, vd.updated_at
        FROM documents d
        LEFT JOIN v2_documents vd ON vd.document_id = d.id
        WHERE d.client_id = ?
        ORDER BY COALESCE(vd.updated_at, d.created_at) DESC
        LIMIT 240
        """,
        (client_id,),
    ):
        title = _first_text(row["file_name"], row["title"], fallback="资料")
        text = _join_text(
            row["title"],
            row["file_name"],
            row["visible_category"],
            row["secondary_category"],
            row["kind"],
            row["excerpt"],
            row["preview_text"],
            _limit_text(row["doc_index_text"], 1500),
            _limit_text(row["markdown_content"], 1500),
        )
        sources.append(AssetSource("document", str(row["id"]), title, text, str(row["updated_at"] or row["created_at"] or "") or None))

    for row in _safe_fetchall(
        db,
        """
        SELECT dc.id, dc.title, dc.one_line_summary, dc.summary_200, dc.keywords_json,
               dc.tags_json, dc.entities_json, dc.updated_at
        FROM document_cards dc
        JOIN knowledge_documents kd ON kd.id = dc.knowledge_document_id
        WHERE kd.client_id = ?
        ORDER BY dc.updated_at DESC
        LIMIT 180
        """,
        (client_id,),
    ):
        text = _join_text(
            row["title"],
            row["one_line_summary"],
            row["summary_200"],
            " ".join(_parse_json_list(row["keywords_json"])),
            " ".join(_parse_json_list(row["tags_json"])),
            " ".join(_parse_json_list(row["entities_json"])),
        )
        sources.append(AssetSource("document_card", str(row["id"]), str(row["title"] or "文档卡"), text, str(row["updated_at"] or "") or None))

    for row in _safe_fetchall(
        db,
        """
        SELECT id, fact_key, fact_value, source_type, confidence, updated_at
        FROM memory_facts
        WHERE scope_type = 'client' AND scope_id = ?
        ORDER BY updated_at DESC
        LIMIT 180
        """,
        (client_id,),
    ):
        title = _first_text(row["fact_key"], row["source_type"], fallback="组织记忆")
        sources.append(AssetSource("memory", str(row["id"]), title, _join_text(row["fact_key"], row["fact_value"], row["source_type"]), str(row["updated_at"] or "") or None))

    for row in _safe_fetchall(
        db,
        """
        SELECT id, name, kind, business_category, stage, summary, intent, current_blocker,
               recent_decision, next_step, updated_at
        FROM event_lines
        WHERE primary_client_id = ?
        ORDER BY updated_at DESC
        LIMIT 120
        """,
        (client_id,),
    ):
        text = _join_text(row["name"], row["kind"], row["business_category"], row["stage"], row["summary"], row["intent"], row["current_blocker"], row["recent_decision"], row["next_step"])
        sources.append(AssetSource("event_line", str(row["id"]), str(row["name"] or "事件线"), text, str(row["updated_at"] or "") or None))

    for row in _safe_fetchall(
        db,
        """
        SELECT id, title, stage, notes, transcript_text, updated_at
        FROM meetings
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 80
        """,
        (client_id,),
    ):
        text = _join_text(row["title"], row["stage"], row["notes"], _limit_text(row["transcript_text"], 1000))
        sources.append(AssetSource("meeting", str(row["id"]), str(row["title"] or "会议"), text, str(row["updated_at"] or "") or None))

    for row in _safe_fetchall(
        db,
        """
        SELECT t.id, t.title, t.description, t.business_category, t.current_blocker,
               t.next_action, t.recent_decision, t.tags_json, t.updated_at
        FROM tasks t
        LEFT JOIN event_lines e ON t.event_line_id = e.id
        WHERE e.primary_client_id = ? OR (t.source_type = 'client' AND t.source_id = ?)
        ORDER BY t.updated_at DESC
        LIMIT 120
        """,
        (client_id, client_id),
    ):
        text = _join_text(row["title"], row["description"], row["business_category"], row["current_blocker"], row["next_action"], row["recent_decision"], " ".join(_parse_json_list(row["tags_json"])))
        sources.append(AssetSource("task", str(row["id"]), str(row["title"] or "任务"), text, str(row["updated_at"] or "") or None))

    for row in _safe_fetchall(
        db,
        """
        SELECT id, source_type, source_ref, quote, normalized_claim, evidence_type,
               tags_json, topic_keys_json, updated_at
        FROM evidence_cards
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 180
        """,
        (client_id,),
    ):
        title = _first_text(row["normalized_claim"], row["source_ref"], fallback="证据卡")
        text = _join_text(row["normalized_claim"], row["quote"], row["source_type"], row["evidence_type"], " ".join(_parse_json_list(row["tags_json"])), " ".join(_parse_json_list(row["topic_keys_json"])))
        sources.append(AssetSource("evidence", str(row["id"]), title, text, str(row["updated_at"] or "") or None))

    for row in _safe_fetchall(
        db,
        """
        SELECT id, theme_key, title, gap_summary, latest_change_summary, updated_at
        FROM theme_clusters
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 80
        """,
        (client_id,),
    ):
        text = _join_text(row["theme_key"], row["title"], row["gap_summary"], row["latest_change_summary"])
        sources.append(AssetSource("theme", str(row["id"]), str(row["title"] or "主题簇"), text, str(row["updated_at"] or "") or None))

    for row in _safe_fetchall(
        db,
        """
        SELECT id, theme_key, question, reason, blocker_level, updated_at
        FROM open_questions
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 80
        """,
        (client_id,),
    ):
        text = _join_text(row["theme_key"], row["question"], row["reason"], row["blocker_level"])
        sources.append(AssetSource("question", str(row["id"]), str(row["question"] or "开放问题"), text, str(row["updated_at"] or "") or None))

    for row in _safe_fetchall(
        db,
        """
        SELECT id, target_type, topic, status, summary, confidence, updated_at
        FROM judgment_versions
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 100
        """,
        (client_id,),
    ):
        text = _join_text(row["target_type"], row["topic"], row["status"], row["summary"], row["confidence"])
        sources.append(AssetSource("judgment", str(row["id"]), str(row["topic"] or "判断"), text, str(row["updated_at"] or "") or None))

    return sources


def _read_notebook_snapshot(db: Database, client_id: str) -> dict[str, object] | None:
    row = db.fetchone(
        "SELECT * FROM organization_notebook_snapshots WHERE client_id = ?",
        (client_id,),
    )
    if row:
        return {
            "id": str(row["id"]),
            "clientId": str(row["client_id"]),
            "organizationIntro": str(row["organization_intro"] or ""),
            "collaborationRelationship": str(row["collaboration_relationship"] or ""),
            "currentStage": str(row["current_stage"] or ""),
            "businessModules": _parse_json_list(row["business_modules_json"]),
            "keyPeople": _parse_json_list(row["key_people_json"]),
            "keyProducts": _parse_json_list(row["key_products_json"]),
            "currentChallenges": _parse_json_list(row["current_challenges_json"]),
            "collaborationGoals": _parse_json_list(row["collaboration_goals_json"]),
            "recentFacts": _parse_json_list(row["recent_facts_json"]),
            "informationGaps": _parse_json_list(row["information_gaps_json"]),
            "confidence": float(row["confidence"] or 0.0),
            "updatedAt": str(row["updated_at"] or ""),
        }
    client_row = db.fetchone("SELECT id, intro, stage, updated_at FROM clients WHERE id = ?", (client_id,))
    if not client_row:
        return None
    intro = str(client_row["intro"] or "").strip()
    stage = str(client_row["stage"] or "").strip()
    if not intro and not stage:
        return None
    return {
        "id": f"notebook_shadow_{client_id}",
        "clientId": client_id,
        "organizationIntro": intro,
        "collaborationRelationship": intro,
        "currentStage": stage,
        "businessModules": [],
        "keyPeople": [],
        "keyProducts": [],
        "currentChallenges": [],
        "collaborationGoals": [],
        "recentFacts": [],
        "informationGaps": [],
        "confidence": 0.0,
        "updatedAt": str(client_row["updated_at"] or ""),
    }


def _safe_fetchall(db: Database, query: str, params: tuple = ()) -> list:
    try:
        return db.fetchall(query, params)
    except Exception:
        return []


def _safe_count(db: Database, query: str, params: tuple = ()) -> int:
    try:
        row = db.fetchone(query, params)
        if not row:
            return 0
        return int(row["count"] or 0)
    except Exception:
        return 0


def _metric_value(metrics: list[DigitalAssetMetricRecord], key: str) -> int:
    for metric in metrics:
        if metric.key == key:
            return metric.value
    return 0


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def _extract_time_buckets(text: str) -> set[str]:
    buckets: set[str] = set()
    for match in TIME_RE.finditer(text):
        year = match.group(1)
        month = match.group(2)
        if year and month:
            buckets.add(f"{year}-{int(month):02d}")
        elif year:
            buckets.add(str(year))
        else:
            buckets.add(match.group(0))
    return buckets


def _normalize_score(value: float) -> int:
    normalized = value * 100 if 0 <= value <= 1 else value
    return int(round(max(0, min(100, normalized))))


def _parse_json_list(value: str | None) -> list[str]:
    try:
        data = from_json(value, [])
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if str(item).strip()]


def _first_text(*values: object, fallback: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return fallback


def _join_text(*values: object) -> str:
    return " ".join(str(value or "").strip() for value in values if str(value or "").strip())


def _limit_text(value: object, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _sanitize_public_text(value: str | None, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱]", text)
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号]", text)
    text = re.sub(r"(?<!\d)\d{6,}(?!\d)", "[数字]", text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
