"""发版与反馈控制台 · API 路由 (RELEASE_CONSOLE_HANDOFF 契约).

设计要点:
- 动态定向 + 静态交付: org_code(=organizations.slug) 解析「该装哪版」, 二进制走 TOS 静态包。
- 不堆进 873KB 的 main.py: 本文件 register_release_routes(app, state) 在 create_app() return 前调用。
- 鉴权复用 main 的 _require_auth / _require_admin; 客户端提交反馈 _require_auth; 更新解析端点免鉴权(同产品不同版本, 非机密)。
"""
from __future__ import annotations

import json
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

# ── 枚举 ──────────────────────────────────────────────
ReleaseStatus = Literal["draft", "testing", "published", "rolled_back"]
AssignmentTargetType = Literal["all", "org", "group"]
AssignmentStatus = Literal["active", "paused", "rolled_back"]
FeedbackKind = Literal["bug", "lag", "inaccurate", "feature", "experience"]
FeedbackSeverity = Literal["blocker", "impaired", "minor"]
FeedbackStatus = Literal[
    "open", "confirmed", "triaged", "in_progress", "resolved", "next_release", "wontfix", "closed"
]


# ── Pydantic 模型 (camelCase) ─────────────────────────
class ReleaseCreatePayload(BaseModel):
    version: str = Field(min_length=1)
    platforms: list[str] = Field(default_factory=list)
    mandatory: bool = False
    userNotes: dict[str, list[str]] = Field(default_factory=dict)
    internalNotes: str = ""
    screenshots: list[str] = Field(default_factory=list)


class ReleasePatchPayload(BaseModel):
    status: ReleaseStatus | None = None
    platforms: list[str] | None = None
    mandatory: bool | None = None
    userNotes: dict[str, list[str]] | None = None
    internalNotes: str | None = None
    screenshots: list[str] | None = None


class ReleaseRecord(BaseModel):
    id: str
    version: str
    status: ReleaseStatus = "draft"
    platforms: list[str] = Field(default_factory=list)
    mandatory: bool = False
    userNotes: dict[str, list[str]] = Field(default_factory=dict)
    internalNotes: str = ""
    screenshots: list[str] = Field(default_factory=list)
    createdBy: str | None = None
    createdAt: str
    updatedAt: str
    publishedAt: str | None = None


class AssignmentCreatePayload(BaseModel):
    targetType: AssignmentTargetType = "all"
    orgCode: str | None = None
    rolloutPct: int = 100
    mandatory: bool = False


class AssignmentPatchPayload(BaseModel):
    status: AssignmentStatus | None = None
    targetType: AssignmentTargetType | None = None
    orgCode: str | None = None
    rolloutPct: int | None = None
    mandatory: bool | None = None


class AssignmentRecord(BaseModel):
    id: str
    releaseId: str
    targetType: AssignmentTargetType = "all"
    orgCode: str | None = None
    rolloutPct: int = 100
    mandatory: bool = False
    status: AssignmentStatus = "active"
    createdBy: str | None = None
    createdAt: str
    updatedAt: str


class PackageUpsertPayload(BaseModel):
    platform: str = Field(min_length=1)
    fileName: str = ""
    sizeBytes: int = 0
    sha512: str = ""
    downloadUrl: str = ""
    blockmapUrl: str | None = None
    downloadable: bool = True


class PackageRecord(BaseModel):
    id: str
    releaseId: str
    platform: str
    fileName: str = ""
    sizeBytes: int = 0
    sha512: str = ""
    downloadUrl: str = ""
    blockmapUrl: str | None = None
    downloadable: bool = True
    publishedAt: str | None = None


class FeedbackCreatePayload(BaseModel):
    kind: FeedbackKind
    severity: FeedbackSeverity = "minor"
    title: str = Field(min_length=1)
    description: str = ""
    orgCode: str | None = None
    version: str | None = None
    page: str | None = None
    os: str | None = None
    screenshotUrl: str | None = None
    logExcerpt: str | None = None


class FeedbackPatchPayload(BaseModel):
    status: FeedbackStatus | None = None
    severity: FeedbackSeverity | None = None
    dupOf: str | None = None
    linkedTaskId: str | None = None
    linkedReleaseId: str | None = None


class FeedbackRecord(BaseModel):
    id: str
    kind: FeedbackKind
    severity: FeedbackSeverity = "minor"
    title: str = ""
    description: str = ""
    submitterUserId: str | None = None
    submitterName: str = ""
    orgCode: str | None = None
    version: str | None = None
    page: str | None = None
    os: str | None = None
    screenshotUrl: str | None = None
    logExcerpt: str | None = None
    status: FeedbackStatus = "open"
    dupOf: str | None = None
    linkedTaskId: str | None = None
    linkedReleaseId: str | None = None
    createdAt: str
    updatedAt: str


# ── row → model ───────────────────────────────────────
def _release_record(row) -> ReleaseRecord:
    return ReleaseRecord(
        id=str(row["id"]),
        version=str(row["version"]),
        status=str(row["status"]),
        platforms=json.loads(row["platforms_json"] or "[]"),
        mandatory=bool(row["mandatory"]),
        userNotes=json.loads(row["user_notes_json"] or "{}"),
        internalNotes=str(row["internal_notes"] or ""),
        screenshots=json.loads(row["screenshots_json"] or "[]"),
        createdBy=str(row["created_by"]) if row["created_by"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
        publishedAt=str(row["published_at"]) if row["published_at"] else None,
    )


def _assignment_record(row) -> AssignmentRecord:
    return AssignmentRecord(
        id=str(row["id"]),
        releaseId=str(row["release_id"]),
        targetType=str(row["target_type"]),
        orgCode=str(row["org_code"]) if row["org_code"] else None,
        rolloutPct=int(row["rollout_pct"]),
        mandatory=bool(row["mandatory"]),
        status=str(row["status"]),
        createdBy=str(row["created_by"]) if row["created_by"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _package_record(row) -> PackageRecord:
    return PackageRecord(
        id=str(row["id"]),
        releaseId=str(row["release_id"]),
        platform=str(row["platform"]),
        fileName=str(row["file_name"] or ""),
        sizeBytes=int(row["size_bytes"]),
        sha512=str(row["sha512"] or ""),
        downloadUrl=str(row["download_url"] or ""),
        blockmapUrl=str(row["blockmap_url"]) if row["blockmap_url"] else None,
        downloadable=bool(row["downloadable"]),
        publishedAt=str(row["published_at"]) if row["published_at"] else None,
    )


def _feedback_record(row) -> FeedbackRecord:
    return FeedbackRecord(
        id=str(row["id"]),
        kind=str(row["kind"]),
        severity=str(row["severity"]),
        title=str(row["title"] or ""),
        description=str(row["description"] or ""),
        submitterUserId=str(row["submitter_user_id"]) if row["submitter_user_id"] else None,
        submitterName=str(row["submitter_name"] or ""),
        orgCode=str(row["org_code"]) if row["org_code"] else None,
        version=str(row["version"]) if row["version"] else None,
        page=str(row["page"]) if row["page"] else None,
        os=str(row["os"]) if row["os"] else None,
        screenshotUrl=str(row["screenshot_url"]) if row["screenshot_url"] else None,
        logExcerpt=str(row["log_excerpt"]) if row["log_excerpt"] else None,
        status=str(row["status"]),
        dupOf=str(row["dup_of"]) if row["dup_of"] else None,
        linkedTaskId=str(row["linked_task_id"]) if row["linked_task_id"] else None,
        linkedReleaseId=str(row["linked_release_id"]) if row["linked_release_id"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


class OrgSummaryRecord(BaseModel):
    id: str
    name: str
    code: str  # = organizations.slug, 定向推送用的组织码(客户端 beacon/update-policy 上报同一个值)
    memberCount: int = 0
    installCount: int = 0  # 占位:待客户端 beacon(app_installs)接通后填真值


def register_release_routes(app: FastAPI, state) -> None:
    # main 已完全加载, 此处函数级 import 不会循环
    from app.main import _log_audit, _require_admin, _require_auth, new_id, now_iso

    db = state.db

    def _release_or_404(release_id: str):
        row = db.fetchone("SELECT * FROM releases WHERE id = ?", (release_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="Release not found")
        return row

    # ════ 版本管理 (admin) ════
    @app.get("/api/v1/admin/releases", response_model=list[ReleaseRecord])
    def admin_list_releases(
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> list[ReleaseRecord]:
        rows = db.fetchall("SELECT * FROM releases ORDER BY created_at DESC")
        return [_release_record(r) for r in rows]

    @app.post("/api/v1/admin/releases", response_model=ReleaseRecord)
    def admin_create_release(
        payload: ReleaseCreatePayload,
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> ReleaseRecord:
        rid = new_id("rel")
        ts = now_iso()
        db.execute(
            """INSERT INTO releases (id, version, status, platforms_json, mandatory,
                   user_notes_json, internal_notes, screenshots_json, created_by, created_at, updated_at)
               VALUES (?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rid, payload.version.strip(), json.dumps(payload.platforms), 1 if payload.mandatory else 0,
             json.dumps(payload.userNotes), payload.internalNotes, json.dumps(payload.screenshots),
             current_user.id, ts, ts),
        )
        _log_audit(state, "release.created", actor_user_id=current_user.id, target_user_id=None,
                   detail={"releaseId": rid, "version": payload.version})
        return _release_record(_release_or_404(rid))

    @app.patch("/api/v1/admin/releases/{release_id}", response_model=ReleaseRecord)
    def admin_patch_release(
        release_id: str,
        payload: ReleasePatchPayload,
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> ReleaseRecord:
        row = _release_or_404(release_id)
        status = payload.status or str(row["status"])
        platforms_json = json.dumps(payload.platforms) if payload.platforms is not None else str(row["platforms_json"])
        mandatory = (1 if payload.mandatory else 0) if payload.mandatory is not None else int(row["mandatory"])
        user_notes_json = json.dumps(payload.userNotes) if payload.userNotes is not None else str(row["user_notes_json"])
        internal_notes = payload.internalNotes if payload.internalNotes is not None else str(row["internal_notes"])
        screenshots_json = json.dumps(payload.screenshots) if payload.screenshots is not None else str(row["screenshots_json"])
        published_at = row["published_at"]
        if status == "published" and not row["published_at"]:
            published_at = now_iso()
        ts = now_iso()
        db.execute(
            """UPDATE releases SET status=?, platforms_json=?, mandatory=?, user_notes_json=?,
                   internal_notes=?, screenshots_json=?, published_at=?, updated_at=? WHERE id=?""",
            (status, platforms_json, mandatory, user_notes_json, internal_notes, screenshots_json,
             published_at, ts, release_id),
        )
        _log_audit(state, "release.updated", actor_user_id=current_user.id, target_user_id=None,
                   detail={"releaseId": release_id, "status": status})
        return _release_record(_release_or_404(release_id))

    # ════ 定向推送 assignments (admin) ════
    @app.get("/api/v1/admin/releases/{release_id}/assignments", response_model=list[AssignmentRecord])
    def admin_list_assignments(
        release_id: str,
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> list[AssignmentRecord]:
        _release_or_404(release_id)
        rows = db.fetchall("SELECT * FROM release_assignments WHERE release_id=? ORDER BY updated_at DESC", (release_id,))
        return [_assignment_record(r) for r in rows]

    @app.post("/api/v1/admin/releases/{release_id}/assignments", response_model=AssignmentRecord)
    def admin_create_assignment(
        release_id: str,
        payload: AssignmentCreatePayload,
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> AssignmentRecord:
        _release_or_404(release_id)
        aid = new_id("asg")
        ts = now_iso()
        db.execute(
            """INSERT INTO release_assignments (id, release_id, target_type, org_code, rollout_pct,
                   mandatory, status, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
            (aid, release_id, payload.targetType, payload.orgCode, payload.rolloutPct,
             1 if payload.mandatory else 0, current_user.id, ts, ts),
        )
        _log_audit(state, "release.assigned", actor_user_id=current_user.id, target_user_id=None,
                   detail={"releaseId": release_id, "assignmentId": aid, "targetType": payload.targetType, "orgCode": payload.orgCode or ""})
        return _assignment_record(db.fetchone("SELECT * FROM release_assignments WHERE id=?", (aid,)))

    @app.patch("/api/v1/admin/releases/{release_id}/assignments/{assignment_id}", response_model=AssignmentRecord)
    def admin_patch_assignment(
        release_id: str,
        assignment_id: str,
        payload: AssignmentPatchPayload,
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> AssignmentRecord:
        row = db.fetchone("SELECT * FROM release_assignments WHERE id=? AND release_id=?", (assignment_id, release_id))
        if row is None:
            raise HTTPException(status_code=404, detail="Assignment not found")
        status = payload.status or str(row["status"])
        target_type = payload.targetType or str(row["target_type"])
        org_code = payload.orgCode if payload.orgCode is not None else row["org_code"]
        rollout_pct = payload.rolloutPct if payload.rolloutPct is not None else int(row["rollout_pct"])
        mandatory = (1 if payload.mandatory else 0) if payload.mandatory is not None else int(row["mandatory"])
        ts = now_iso()
        db.execute(
            """UPDATE release_assignments SET status=?, target_type=?, org_code=?, rollout_pct=?,
                   mandatory=?, updated_at=? WHERE id=?""",
            (status, target_type, org_code, rollout_pct, mandatory, ts, assignment_id),
        )
        _log_audit(state, "release.assignment_updated", actor_user_id=current_user.id, target_user_id=None,
                   detail={"assignmentId": assignment_id, "status": status})
        return _assignment_record(db.fetchone("SELECT * FROM release_assignments WHERE id=?", (assignment_id,)))

    # ════ 安装包元数据 (admin · 由 publish-to-tos 上传后回写) ════
    @app.post("/api/v1/admin/releases/{release_id}/packages", response_model=PackageRecord)
    def admin_upsert_package(
        release_id: str,
        payload: PackageUpsertPayload,
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> PackageRecord:
        _release_or_404(release_id)
        existing = db.fetchone(
            "SELECT * FROM release_packages WHERE release_id=? AND platform=?", (release_id, payload.platform)
        )
        ts = now_iso()
        if existing is not None:
            db.execute(
                """UPDATE release_packages SET file_name=?, size_bytes=?, sha512=?, download_url=?,
                       blockmap_url=?, downloadable=?, published_at=? WHERE id=?""",
                (payload.fileName, payload.sizeBytes, payload.sha512, payload.downloadUrl,
                 payload.blockmapUrl, 1 if payload.downloadable else 0, ts, str(existing["id"])),
            )
            pid = str(existing["id"])
        else:
            pid = new_id("pkg")
            db.execute(
                """INSERT INTO release_packages (id, release_id, platform, file_name, size_bytes, sha512,
                       download_url, blockmap_url, downloadable, published_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, release_id, payload.platform, payload.fileName, payload.sizeBytes, payload.sha512,
                 payload.downloadUrl, payload.blockmapUrl, 1 if payload.downloadable else 0, ts),
            )
        return _package_record(db.fetchone("SELECT * FROM release_packages WHERE id=?", (pid,)))

    # ════ 用户反馈 ════
    @app.post("/api/v1/feedback", response_model=FeedbackRecord)
    def client_submit_feedback(
        payload: FeedbackCreatePayload,
        current_user=Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> FeedbackRecord:
        fid = new_id("fb")
        ts = now_iso()
        org_code = payload.orgCode
        db.execute(
            """INSERT INTO feedback_items (id, kind, severity, title, description, submitter_user_id,
                   submitter_name, org_code, version, page, os, screenshot_url, log_excerpt, status,
                   created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
            (fid, payload.kind, payload.severity, payload.title.strip(), payload.description.strip(),
             current_user.id, current_user.fullName, org_code, payload.version, payload.page, payload.os,
             payload.screenshotUrl, payload.logExcerpt, ts, ts),
        )
        _log_audit(state, "feedback.created", actor_user_id=current_user.id, target_user_id=None,
                   detail={"feedbackId": fid, "kind": payload.kind, "severity": payload.severity})
        return _feedback_record(db.fetchone("SELECT * FROM feedback_items WHERE id=?", (fid,)))

    @app.get("/api/v1/admin/feedback", response_model=list[FeedbackRecord])
    def admin_list_feedback(
        status_filter: str | None = Query(default=None, alias="status"),
        kind: str | None = Query(default=None),
        severity: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> list[FeedbackRecord]:
        q = ["SELECT * FROM feedback_items WHERE 1=1"]
        params: list[object] = []
        if status_filter:
            q.append("AND status = ?")
            params.append(status_filter)
        if kind:
            q.append("AND kind = ?")
            params.append(kind)
        if severity:
            q.append("AND severity = ?")
            params.append(severity)
        q.append(
            "ORDER BY CASE severity WHEN 'blocker' THEN 0 WHEN 'impaired' THEN 1 ELSE 2 END,"
            " updated_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = db.fetchall(" ".join(q), tuple(params))
        return [_feedback_record(r) for r in rows]

    @app.patch("/api/v1/admin/feedback/{feedback_id}", response_model=FeedbackRecord)
    def admin_patch_feedback(
        feedback_id: str,
        payload: FeedbackPatchPayload,
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> FeedbackRecord:
        row = db.fetchone("SELECT * FROM feedback_items WHERE id=?", (feedback_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="Feedback not found")
        status = payload.status or str(row["status"])
        severity = payload.severity or str(row["severity"])
        dup_of = payload.dupOf if payload.dupOf is not None else row["dup_of"]
        linked_task_id = payload.linkedTaskId if payload.linkedTaskId is not None else row["linked_task_id"]
        linked_release_id = payload.linkedReleaseId if payload.linkedReleaseId is not None else row["linked_release_id"]
        ts = now_iso()
        db.execute(
            """UPDATE feedback_items SET status=?, severity=?, dup_of=?, linked_task_id=?,
                   linked_release_id=?, updated_at=? WHERE id=?""",
            (status, severity, dup_of, linked_task_id, linked_release_id, ts, feedback_id),
        )
        # 并入问题池: 关联到某 release 时同时登记多对多
        if linked_release_id:
            db.execute(
                "INSERT OR IGNORE INTO release_problem_links (release_id, feedback_id, created_at) VALUES (?, ?, ?)",
                (str(linked_release_id), feedback_id, ts),
            )
        _log_audit(state, "feedback.updated", actor_user_id=current_user.id, target_user_id=None,
                   detail={"feedbackId": feedback_id, "status": status})
        return _feedback_record(db.fetchone("SELECT * FROM feedback_items WHERE id=?", (feedback_id,)))

    # ════ 客户端更新解析 (org 感知, 免鉴权) ════
    def _resolve_release_for_org(org_code: str):
        # 1) 该组织专属 active 指派 + 已发布
        row = db.fetchone(
            """SELECT r.* FROM release_assignments a JOIN releases r ON r.id = a.release_id
               WHERE a.status='active' AND a.target_type='org' AND a.org_code=? AND r.status='published'
               ORDER BY a.updated_at DESC LIMIT 1""",
            (org_code,),
        )
        if row is not None:
            return row
        # 2) 全量 active 指派 + 已发布
        row = db.fetchone(
            """SELECT r.* FROM release_assignments a JOIN releases r ON r.id = a.release_id
               WHERE a.status='active' AND a.target_type='all' AND r.status='published'
               ORDER BY a.updated_at DESC LIMIT 1"""
        )
        if row is not None:
            return row
        # 3) 兜底: 最新已发布
        return db.fetchone("SELECT * FROM releases WHERE status='published' ORDER BY published_at DESC LIMIT 1")

    @app.get("/api/v1/updates/{org_code}/{platform}/latest-mac.yml", response_class=PlainTextResponse)
    def org_aware_update_feed(org_code: str, platform: str) -> PlainTextResponse:
        release = _resolve_release_for_org(org_code)
        if release is None:
            return PlainTextResponse("", status_code=404)
        pkg = db.fetchone(
            "SELECT * FROM release_packages WHERE release_id=? AND platform=? AND downloadable=1",
            (str(release["id"]), platform),
        )
        version = str(release["version"])
        if pkg is None:
            # 无包元数据时仅返回版本占位 (publish-to-tos 回写包后即完整)
            return PlainTextResponse(f"version: {version}\n")
        file_name = str(pkg["file_name"] or "")
        download_url = str(pkg["download_url"] or "")
        sha512 = str(pkg["sha512"] or "")
        size = int(pkg["size_bytes"])
        release_date = str(release["published_at"] or release["created_at"])
        # url 用【绝对 TOS 地址】→ electron-updater 直接从 TOS 下包(动态定向解析版本, 静态交付二进制);
        # feed base 是本云端 resolver, 故必须绝对 url, 否则会去云端路径找包。download_url 缺时回退文件名。
        file_url = download_url or file_name
        yml = (
            f"version: {version}\n"
            f"files:\n"
            f"  - url: {file_url}\n"
            f"    sha512: {sha512}\n"
            f"    size: {size}\n"
            f"path: {file_url}\n"
            f"sha512: {sha512}\n"
            f"releaseDate: '{release_date}'\n"
        )
        return PlainTextResponse(yml)

    @app.get("/api/v1/releases/latest", response_model=ReleaseRecord | None)
    def public_latest_release(platform: str = Query(default="mac")) -> ReleaseRecord | None:
        rows = db.fetchall("SELECT * FROM releases WHERE status='published' ORDER BY published_at DESC")
        for row in rows:
            platforms = json.loads(row["platforms_json"] or "[]")
            if not platforms or platform in platforms:
                return _release_record(row)
        return None

    # ════ 组织列表 (定向推送 console「组织表」: 组织名 + 唯一组织码 + 成员/安装数) ════
    # 注: 平台级操作(益语运营发版), v1 用 _require_admin; 后续应收紧到平台所有者粒度。
    @app.get("/api/v1/admin/organizations", response_model=list[OrgSummaryRecord])
    def admin_list_organizations(
        current_user=Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> list[OrgSummaryRecord]:
        rows = db.fetchall(
            """
            SELECT o.id, o.name, o.slug,
              (SELECT COUNT(1) FROM employee_accounts e WHERE e.organization_id = o.id) AS member_count
            FROM organizations o
            ORDER BY o.created_at DESC
            """
        )
        return [
            OrgSummaryRecord(
                id=str(r["id"]),
                name=str(r["name"]),
                code=str(r["slug"] or ""),
                memberCount=int(r["member_count"] or 0),
                installCount=0,
            )
            for r in rows
        ]
