from __future__ import annotations

from datetime import datetime

from app.models import HierarchyReportRecord, OrganizationDnaModuleRecord, ReviewSimulationBundleRecord


DEPARTMENT_BLUEPRINTS = [
    {
        "name": "咨询策略部",
        "sample_size": 5,
        "monthly_dna": "本月主线是把重点客户方案验证做深，并把有效路径沉淀成可复用方法。",
        "headline": "咨询策略部的主线事项整体在推进，但方案验证与方法沉淀的节奏还没有完全同步。",
        "summary": "20 人模拟里，咨询策略部的前线动作最容易产生可见进展，但也最容易在“先交付、后沉淀”这里出现偏差。",
        "focus": ["重点客户方案验证", "关键客户推进节奏", "方法资产沉淀"],
        "support": ["高价值客户推进过度依赖少数核心同事", "已验证的方法还没有及时标准化"],
        "quotes": [
            "一线同事多次提到“方案已经能跑，但还没有整理成团队都能复用的版本”。",
            "有同事提到“客户推进能动，但每次都要重新解释一遍逻辑，沉淀速度跟不上”。",
        ],
        "actions": ["把已验证方案沉淀成标准模板", "区分哪些客户推进需要 CEO 级拍板，避免一线重复试错"],
    },
    {
        "name": "科技发展部",
        "sample_size": 5,
        "monthly_dna": "本月主线是把任务、复盘、权限和设置打成稳定可用的系统闭环。",
        "headline": "科技发展部的关键变量不是功能数量，而是稳定性、权限边界和链路一致性。",
        "summary": "20 人模拟里，科技发展部最值得关注的是核心流程是否足够稳定，而不是局部功能点是否继续堆叠。",
        "focus": ["核心链路稳定性", "权限边界一致性", "产品交互闭环"],
        "support": ["页面交互细节仍可能打断主流程", "历史数据兼容和新结构之间还有缝隙"],
        "quotes": [
            "有同事提到“不是没有功能，而是核心链路一旦不稳，所有功能都会失去价值”。",
            "也有人提到“权限和状态边界一旦混乱，前台体验会迅速失真”。",
        ],
        "actions": ["优先收敛登录、任务、周复盘这几条主链路", "把部门、权限和可见性规则固化成统一约束"],
    },
    {
        "name": "信息数据部",
        "sample_size": 5,
        "monthly_dna": "本月主线是把情报抓取、候选清洗、标签治理和数据库维护跑成稳定生产流。",
        "headline": "信息数据部的信息处理链路已经成形，但标签边界和来源质量仍在拉低判断效率。",
        "summary": "20 人模拟里，信息数据部的核心问题不是没有信息，而是怎样把信息处理成可追踪、可复用、可进入业务判断的资产。",
        "focus": ["情报抓取与清洗", "标签治理", "数据库可靠性"],
        "support": ["样本来源质量不稳定", "标签规则与业务优先级的映射还不够紧"],
        "quotes": [
            "有同事提到“真正耗时的不是抓，而是后面清洗、比对和统一口径”。",
            "也有人提到“如果标签边界不稳，最后给业务看的判断就会摇摆”。",
        ],
        "actions": ["先把高频来源的标签规则固化下来", "把数据质量波动单独提成经营风险项"],
    },
    {
        "name": "客户服务部",
        "sample_size": 5,
        "monthly_dna": "本月主线是把客户交付、过程协同和资料回流收成一条更顺的客户服务链路。",
        "headline": "客户服务部的风险主要集中在交接边界、客户反馈回流和服务节奏控制。",
        "summary": "20 人模拟里，客户服务部最容易出现的问题不是没人跟进，而是服务接口没有提前说清、反馈回流慢、复盘动作滞后。",
        "focus": ["客户交付节奏", "跨部门交接", "服务资料回流"],
        "support": ["交接时输入物标准还不够清楚", "客户反馈没有及时沉淀回内部系统"],
        "quotes": [
            "有同事提到“最容易反复的不是做事本身，而是等前一环输入补齐”。",
            "也有人提到“客户反馈经常来得晚，导致内部调整总慢半拍”。",
        ],
        "actions": ["把交接标准做成服务输入清单", "把客户反馈和复盘动作前置进排期，不再收尾再补"],
    },
]


def _module_titles(modules: list[OrganizationDnaModuleRecord]) -> str:
    titles = [module.title for module in modules if module.hasDocument]
    return "、".join(titles[:3]) if titles else "组织介绍、业务介绍、团队介绍"


def build_review_simulation_bundle(
    *,
    week_label: str,
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    sample_size: int = 20,
) -> ReviewSimulationBundleRecord:
    created_at = datetime.now().replace(microsecond=0).isoformat()
    dna_titles = _module_titles(organization_dna_modules)
    department_reports: list[HierarchyReportRecord] = []

    for blueprint in DEPARTMENT_BLUEPRINTS:
        report = HierarchyReportRecord(
            id=f"sim_dept_{blueprint['name']}_{week_label}",
            scopeType="team",
            scopeRefId=str(blueprint["name"]),
            weekLabel=week_label,
            logicMode="simulated_weighted_hypothesis_v1",
            headline=str(blueprint["headline"]),
            summary=f"模拟样本约 {blueprint['sample_size']} 人。部门月度 DNA 假设：{blueprint['monthly_dna']} 当前总结基于 {dna_titles} 与该部门周内一线汇总信号生成，用于 CEO 口径调教，不代表真实统计结果。",
            focusAreas=list(blueprint["focus"]),
            supportSignals=list(blueprint["support"]),
            suggestedActions=list(blueprint["actions"]),
            anonymousInsights=list(blueprint["quotes"]),
            sourcePolicy={
                "simulationMode": True,
                "sampleSize": blueprint["sample_size"],
                "visibility": "ceo_work_only",
                "monthlyDnaMode": "simulated_department_monthly_dna",
            },
            actions=[],
            createdAt=created_at,
            updatedAt=created_at,
        )
        department_reports.append(report)

    org_report = HierarchyReportRecord(
        id=f"sim_org_{week_label}",
        scopeType="org",
        scopeRefId="organization",
        weekLabel=week_label,
        logicMode="simulated_weighted_hypothesis_v1",
        headline="20 人组织模拟显示：主线整体仍在推进，但跨部门节奏、方法沉淀、系统稳定性和服务回流已经成为 CEO 层需要判断的组织变量。",
        summary=f"本轮机构视角为 CEO 调参模拟，不读取任何私人内容。它假设组织内约 {sample_size} 人，分布在 4 个部门，并参考 {dna_titles} 这几类 DNA 作为解释视角。当前最值得关注的不是单个任务是否完成，而是部门动作是否持续贴着组织主线、是否已经出现系统性偏差。",
        focusAreas=["跨部门节奏一致性", "方法资产沉淀速度", "系统稳定性", "客户服务回流"],
        supportSignals=[
            "若咨询策略部继续“先交付后沉淀”，组织复用效率会持续下降。",
            "若科技发展部的主链路稳定性继续波动，组织整体执行成本会持续升高。",
            "若客户服务部接口不收敛，部门间推进速度会被最慢环节拖住。",
        ],
        suggestedActions=[
            "把“部门月度 DNA vs 本周实际推进”做成 CEO 固定检查项。",
            "要求各部门周复盘都至少给出一条“如果不处理，会在下周放大的风险”。",
            "把跨部门共性卡点单独提成 CEO 层支持清单，而不是留在部门内部自转。",
        ],
        anonymousInsights=[
            "模拟里最明显的组织信号不是没人努力，而是不同部门对“什么算本周有效推进”的标准还不完全一致。",
            "如果不尽快统一“主线、沉淀、接口、业务结果”的判断语言，周复盘会继续停留在汇报而不是经营分析。",
        ],
        sourcePolicy={
            "simulationMode": True,
            "sampleSize": sample_size,
            "visibility": "ceo_work_only",
            "monthlyDnaMode": "simulated_department_monthly_dna",
        },
        actions=[],
        createdAt=created_at,
        updatedAt=created_at,
    )

    return ReviewSimulationBundleRecord(
        sampleSize=sample_size,
        label="CEO 调参与 20 人模拟视角",
        orgReport=org_report,
        departmentReports=department_reports,
    )
