"""V2.6 R3 场景 1 · 20 文件批量测试数据集

顾源源 5/23 钦定文件分布:
  · 合同 3 份 / 补充协议 2 份 / 方案 3 份 / 会议纪要 3 份
  · 年报 2 份 / 我方反馈 2 份 / 外部政策 2 份 / 对标 2 份
  · 预算表 1 份 / 客户宣传稿 1 份

虚拟客户: 日慈基金会 + 心盛计划 / 安心妈妈项目
"""
from __future__ import annotations

FILES_20 = [
    # 合同 3 份
    {
        "file_name": "日慈-益语-战略陪伴主合同_v1_20260101.docx",
        "expected_type": "contract",
        "expected_role": "client_official",
        "text_excerpt": (
            "甲方:日慈基金会 乙方:益语智库\n"
            "签订日期:2026 年 1 月 1 日\n"
            "项目名称:日慈基金会战略陪伴服务\n"
            "服务期限:2026 年 1 月至 12 月\n"
            "服务费总额:人民币 80 万元\n\n"
            "甲方责任:提供必要客户资料、业务背景、参与定期复盘会议\n"
            "乙方责任:派出 1 名战略顾问、每月 4 次复盘、每季度 1 次战略报告\n\n"
            "交付内容:战略陪伴月度纪要、季度战略报告、年度复盘、客户故事卡 4 次。"
        ),
    },
    {
        "file_name": "日慈-心盛计划合作协议_v1_20260215.docx",
        "expected_type": "contract",
        "expected_role": "client_official",
        "text_excerpt": (
            "甲方:日慈基金会 乙方:益语智库\n"
            "项目名称:心盛计划心理健康教育服务\n"
            "签订日期:2026 年 2 月 15 日\n"
            "项目预算:480 万元 (2026 年度)\n"
            "覆盖范围:20 所乡村学校\n"
            "甲方负责:学校选址、家长沟通、本地协调员配备\n"
            "乙方负责:课程开发、师资培训、效果评估、心理咨询师选派\n"
            "服务期:2026 年 3 月至 12 月。"
        ),
    },
    {
        "file_name": "CFFC-益语-乡村教育帮扶服务合同_20260301.docx",
        "expected_type": "contract",
        "expected_role": "client_official",
        "text_excerpt": (
            "甲方:CFFC(中华少年儿童慈善救助基金会某项目)\n"
            "乙方:益语智库\n"
            "签订日期:2026 年 3 月 1 日\n"
            "项目名称:乡村教育帮扶项目\n"
            "服务金额:320 万元\n"
            "覆盖学校:8 所乡村小学\n"
            "甲方:负责学校协调与资金拨付\n"
            "乙方:负责课程支持与教师培训\n"
            "服务期:2026 年 4 月至 11 月。"
        ),
    },
    # 补充协议 2 份
    {
        "file_name": "日慈-心盛计划补充协议_v2_20260518.docx",
        "expected_type": "supplementary_agreement",
        "expected_role": "client_official",
        "text_excerpt": (
            "本补充协议系对 2026 年 2 月 15 日 《日慈-心盛计划合作协议》 的修订.\n"
            "甲方:日慈基金会 乙方:益语智库\n"
            "签订日期:2026 年 5 月 18 日\n\n"
            "经双方协商, 自本补充协议生效之日起, 心盛计划项目预算调整为 300 万元,\n"
            "覆盖学校由原 20 所调整为 3 所试点学校.\n"
            "李明负责执行推进, 王华秘书长负责内部协调.\n\n"
            "其他条款仍按原合同执行."
        ),
    },
    {
        "file_name": "日慈-安心妈妈项目附件协议_v1_20260520.docx",
        "expected_type": "supplementary_agreement",
        "expected_role": "client_official",
        "text_excerpt": (
            "甲方:日慈基金会 乙方:益语智库\n"
            "签订日期:2026 年 5 月 20 日\n\n"
            "经双方友好协商, 在原战略陪伴合同基础上新增'安心妈妈家长项目'合作内容,\n"
            "试点学校 5 所, 预算 180 万元, 试点期 6 个月.\n"
            "甲方负责家长招募与场地, 乙方负责课程开发与师资.\n\n"
            "试点结束后双方共同评估是否扩大规模."
        ),
    },
    # 项目方案 3 份
    {
        "file_name": "日慈-心盛计划项目方案_v1_20260208.docx",
        "expected_type": "proposal",
        "expected_role": "client_official",
        "text_excerpt": (
            "项目名称:心盛计划\n"
            "覆盖学校:20 所(初版规划)\n"
            "预算:480 万\n"
            "项目目标:为乡村儿童提供长期心理健康教育支持。"
        ),
    },
    {
        "file_name": "日慈-心盛计划项目方案_v2_20260518.docx",
        "expected_type": "proposal",
        "expected_role": "client_official",
        "text_excerpt": (
            "项目名称:心盛计划(v2 调整版)\n"
            "覆盖学校:3 所试点\n"
            "预算:300 万\n"
            "目标:先验证服务质量, 再决定是否扩展。"
        ),
    },
    {
        "file_name": "日慈-安心妈妈试点方案_v1_20260519.docx",
        "expected_type": "proposal",
        "expected_role": "client_official",
        "text_excerpt": (
            "项目名称:安心妈妈家长项目\n"
            "试点学校:5 所\n"
            "预算:180 万\n"
            "周期:6 个月\n"
            "服务内容:家长心理建设工作坊、家校沟通指导。"
        ),
    },
    # 会议纪要 3 份
    {
        "file_name": "日慈-心盛计划战略复盘会议纪要_20260522.docx",
        "expected_type": "meeting_minute",
        "expected_role": "client_official",
        "text_excerpt": (
            "2026 年 5 月 22 日, 日慈基金会与益语智库召开心盛计划战略复盘.\n"
            "张真理事长提出战略调整: 心盛维持 12 所, 不再扩到 20 所. 第二曲线转向安心妈妈.\n"
            "强哥担忧 5 所一起开太冒险, 建议先 2 所验证.\n"
            "杨岩冰提出运营约束: 6 人团队同时维持心盛 12 所 + 安心妈妈 5 所有压力.\n"
            "张真承诺 5/30 前给最终预算方案, 强哥承诺 5/28 前给试点学校名单."
        ),
    },
    {
        "file_name": "CFFC-乡村教育帮扶季度复盘_20260520.docx",
        "expected_type": "meeting_minute",
        "expected_role": "client_official",
        "text_excerpt": (
            "2026 年 5 月 20 日, CFFC 与益语召开乡村教育帮扶季度复盘.\n"
            "覆盖 8 所学校, 服务 1500 名学生, 总预算 320 万, 已支付 180 万.\n"
            "王主任提出下季度新增 3 所新疆试点. 李丽担忧气候文化差异.\n"
            "周明 5/26 前给财务可行性分析."
        ),
    },
    {
        "file_name": "日慈-月度沟通纪要_20260408.docx",
        "expected_type": "meeting_minute",
        "expected_role": "client_official",
        "text_excerpt": (
            "2026 年 4 月 8 日月度沟通会.\n"
            "心盛计划 3 月已经入校 8 所学校, 学生反馈良好.\n"
            "下月计划再增 4 所. 各方运转正常."
        ),
    },
    # 年报/章程 2 份
    {
        "file_name": "日慈基金会-2025 年度报告.docx",
        "expected_type": "annual_report",
        "expected_role": "client_official",
        "text_excerpt": (
            "日慈基金会 2025 年度报告.\n"
            "理事长:张真. 秘书长:强哥.\n"
            "全年累计投入 1200 万元用于乡村儿童心理健康教育.\n"
            "服务覆盖 8 省 32 县 156 所学校."
        ),
    },
    {
        "file_name": "CFFC-基金会章程_20240101.docx",
        "expected_type": "annual_report",  # 章程类似官方文件
        "expected_role": "client_official",
        "text_excerpt": (
            "CFFC 基金会章程, 2024 年版.\n"
            "理事会构成: 9 人, 任期 3 年.\n"
            "主要业务范围: 乡村儿童救助 / 教育帮扶 / 应急援助."
        ),
    },
    # 我方反馈 2 份
    {
        "file_name": "益语-关于心盛计划扩张节奏的反馈_20260510.docx",
        "expected_type": "feedback_doc",
        "expected_role": "yiyu_produced",
        "text_excerpt": (
            "益语顾问反馈: 不建议心盛计划一开始扩到 20 所.\n"
            "理由: 服务质量难保, 师资储备不足. 建议先 3 所试点验证."
        ),
    },
    {
        "file_name": "益语-关于安心妈妈项目设计建议_20260519.docx",
        "expected_type": "feedback_doc",
        "expected_role": "yiyu_produced",
        "text_excerpt": (
            "益语建议: 安心妈妈先 2 所验证, 不直接 5 所铺开.\n"
            "理由: 家长工作是新方向, 经验少, 失败成本高."
        ),
    },
    # 外部政策 2 份
    {
        "file_name": "教育部-关于规范校外心理健康服务的通知_20260301.docx",
        "expected_type": "policy",
        "expected_role": "policy_basis",
        "text_excerpt": (
            "教育部关于规范校外心理健康服务进校园的通知.\n"
            "校外机构进校开展心理健康服务必须取得资质,\n"
            "活动内容须经当地教育部门备案."
        ),
    },
    {
        "file_name": "新疆教育厅-关于审批校外教育项目的暂行办法_20260401.docx",
        "expected_type": "policy",
        "expected_role": "policy_basis",
        "text_excerpt": (
            "新疆教育厅关于校外教育项目审批的暂行办法.\n"
            "外省机构开展教育项目需提交项目方案+资质证明,\n"
            "审批周期 30-60 天."
        ),
    },
    # 对标 2 份
    {
        "file_name": "对标-某基金会乡村心理项目案例_20251201.docx",
        "expected_type": "benchmark_case",
        "expected_role": "external_reference",
        "text_excerpt": (
            "对标案例: 某基金会 2025 年开展乡村儿童心理项目.\n"
            "覆盖 5 省 20 所学校, 投入 600 万.\n"
            "关键经验: 早期点位过快, 服务质量受挑战."
        ),
    },
    {
        "file_name": "对标-家长教育项目成功案例-某机构_20260201.docx",
        "expected_type": "benchmark_case",
        "expected_role": "external_reference",
        "text_excerpt": (
            "某机构家长教育成功案例:\n"
            "试点 3 所学校 9 个月, 家长参与率从 30% 提到 75%.\n"
            "核心方法: 入户 + 工作坊 + 微信群."
        ),
    },
    # 预算表 1 份
    {
        "file_name": "日慈-2026 年项目预算表_v2_20260519.xlsx",
        "expected_type": "budget_table",
        "expected_role": "client_official",
        "text_excerpt": (
            "2026 年日慈项目预算 (v2 调整版).\n"
            "心盛计划: 300 万 (原 480 万)\n"
            "安心妈妈试点: 180 万 (新增)\n"
            "运营储备: 30 万\n"
            "合计: 510 万."
        ),
    },
    # 客户宣传 1 份
    {
        "file_name": "日慈-心盛计划对外宣传稿_v1_20260301.docx",
        "expected_type": "publicity_doc",
        "expected_role": "client_official",
        "text_excerpt": (
            "日慈基金会 2026 年启动心盛计划,\n"
            "计划在 20 所乡村学校开展心理健康教育服务,\n"
            "总投入 480 万元."
        ),
    },
]

assert len(FILES_20) >= 20, f"need at least 20 files, got {len(FILES_20)}"
