from app.models import OrganizationDnaModuleRecord
from app.services.review_simulation import build_review_simulation_bundle


def build_org_module(module_key: str, title: str, summary: str) -> OrganizationDnaModuleRecord:
    return OrganizationDnaModuleRecord(
        moduleKey=module_key,  # type: ignore[arg-type]
        title=title,
        markdownContent="",
        normalizedText=summary,
        summary=summary,
        fileName=None,
        contentHash=None,
        updatedAt="2026-03-01T00:00:00",
        updatedBy="tester",
        hasDocument=True,
    )


def test_build_review_simulation_bundle_returns_org_and_department_reports():
    modules = [
        build_org_module("organization_intro", "组织介绍", "组织当前关注跨部门协同。"),
        build_org_module("business_intro", "业务介绍", "业务当前关注把验证路径做深。"),
        build_org_module("team_intro", "团队介绍", "团队当前需要收敛接口节奏。"),
    ]

    bundle = build_review_simulation_bundle(
        week_label="2026-W11",
        organization_dna_modules=modules,
        sample_size=20,
    )

    assert bundle.label == "CEO 调参与 20 人模拟视角"
    assert bundle.sampleSize == 20
    assert bundle.orgReport is not None
    assert len(bundle.departmentReports) == 4
    assert bundle.orgReport.sourcePolicy["sampleSize"] == 20
    assert any(report.scopeRefId == "咨询策略部" for report in bundle.departmentReports)


def test_build_review_simulation_bundle_is_work_only_and_simulated():
    bundle = build_review_simulation_bundle(
        week_label="2026-W11",
        organization_dna_modules=[],
        sample_size=20,
    )

    assert bundle.orgReport is not None
    assert bundle.orgReport.sourcePolicy["simulationMode"] is True
    assert bundle.orgReport.sourcePolicy["visibility"] == "ceo_work_only"
    assert all(report.sourcePolicy["simulationMode"] is True for report in bundle.departmentReports)
    assert all(report.sourcePolicy["visibility"] == "ceo_work_only" for report in bundle.departmentReports)
