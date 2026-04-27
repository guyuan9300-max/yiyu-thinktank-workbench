# 源码文件：`backend/app/main.py`（分片 02）

- 行号范围：2801-5600
- 总行数：   30416
- 导出时间：2026-04-20

```python
    def process_knowledge_job(job: dict[str, object]) -> None:
        job_id = str(job["id"])
        client_id = str(job["client_id"])
        job_type = str(job["job_type"])
        payload = from_json(str(job["payload_json"]), {})
        processed_items = 0
        if job_type == "ingest_import":
            import_id = str(payload.get("importId"))
            documents = payload.get("documents", [])
            docs = documents if isinstance(documents, list) else []
            state.db.execute("UPDATE imports SET status = 'processing' WHERE id = ?", (import_id,))
            ensure_standard_client_folders(client_id)
            for item in docs:
                if not isinstance(item, dict):
                    continue
                document_id = str(item.get("documentId", ""))
                path = Path(str(item.get("sourcePath", "")))
                original_source_path = Path(str(item.get("originalSourcePath", ""))).expanduser() if item.get("originalSourcePath") else path
                if not document_id or not path.exists():
                    if document_id:
                        append_knowledge_job_event(
                            job_id,
                            "warning",
                            "跳过缺失的原始文件",
                            {"documentId": document_id, "sourcePath": str(path)},
                        )
                    continue
                excerpt = build_excerpt(path)
                prepared = ingest_document_knowledge(
                    state.db,
                    data_dir=state.data_dir,
                    client_id=client_id,
                    import_id=import_id,
                    document_id=document_id,
                    source_path=path,
                    original_source_path=original_source_path,
                    title=str(item.get("title", path.name)),
                    kind=str(item.get("kind", path.suffix.lower().lstrip("."))),
                    source=str(item.get("source", payload.get("mode", "file"))),
                    fallback_excerpt=excerpt,
                    created_at=str(item.get("createdAt", now_iso())),
                    ai_service=state.ai,
                )
                record_imported_document_writeback(
                    state.db,
                    client_id=client_id,
                    document_id=document_id,
                    title=str(item.get("title", path.name)),
                    prepared=prepared,
                )
                prepared_title = str(prepared.get("title") or path.name)
                prepared_category = str(prepared.get("primary_category") or "其他资料")
                target_folder = state.db.fetchone(
                    "SELECT id FROM client_folders WHERE client_id = ? AND label = ?",
                    (client_id, prepared_category),
                )
                state.db.execute(
                    """
                    UPDATE documents
                    SET folder_id = ?
                    WHERE id = ?
                    """,
                    (
                        str(target_folder["id"]) if target_folder else None,
                        document_id,
                    ),
                )
                processed_items += 1
                state.db.execute(
                    "UPDATE imports SET imported_count = ?, status = 'processing' WHERE id = ?",
                    (processed_items, import_id),
                )
                update_knowledge_job_progress(job_id, processed_items, f"已处理 {prepared_title}")
            append_knowledge_job_event(job_id, "info", f"已完成 {V2_PIPELINE_VERSION} 文档索引、章节定位与原文切块")
            ensure_standard_client_folders(client_id)
            total_items = int(job.get("total_items") or len(docs))
            existing_import = state.db.fetchone("SELECT skipped_count FROM imports WHERE id = ?", (import_id,))
            existing_skipped = int(existing_import["skipped_count"] or 0) if existing_import else 0
            skipped_items = existing_skipped + max(0, total_items - processed_items)
            state.db.execute(
                "UPDATE imports SET status = 'completed', imported_count = ?, skipped_count = ? WHERE id = ?",
                (processed_items, skipped_items, import_id),
            )
            finish_knowledge_job(job_id, status="completed", processed_items=processed_items)
            maybe_enqueue_client_dna_generation_job(client_id)
            # Auto-rebuild client profile blocks after import completes
            if processed_items > 0:
                try:
                    build_client_profile(state.db, data_dir=state.data_dir, client_id=client_id, ai_service=state.ai)
                except Exception:
                    pass  # profile rebuild is best-effort
                try:
                    from app.services.memory_foundation import backfill_document_knowledge_to_memory
                    backfill_document_knowledge_to_memory(state.db)
                    refresh_organization_notebook_snapshot(state.db, client_id)
                except Exception:
                    pass
            return
        if job_type == "rebuild_client_knowledge":
            summary = backfill_knowledge_documents(
                state.db,
                data_dir=state.data_dir,
                client_id=client_id,
                ai_service=state.ai,
                progress_callback=lambda count: update_knowledge_job_progress(job_id, count, f"已回填 {count} 份文档"),
            )
            processed_items = int(summary.get("processed", 0))
            missing_items = int(summary.get("missing", 0))
            if missing_items > 0:
                append_knowledge_job_event(
                    job_id,
                    "warning",
                    "部分原始文件已丢失，已跳过缺失文件并继续重建",
                    {"missingItems": missing_items},
                )
            append_knowledge_job_event(job_id, "info", f"已完成 {V2_PIPELINE_VERSION} 文档索引、章节定位与原文切块")
            ensure_standard_client_folders(client_id)
            finish_knowledge_job(job_id, status="completed", processed_items=processed_items)
            maybe_enqueue_client_dna_generation_job(client_id)
            # Auto-rebuild client profile blocks after knowledge rebuild
            if processed_items > 0:
                try:
                    build_client_profile(state.db, data_dir=state.data_dir, client_id=client_id, ai_service=state.ai)
                except Exception:
                    pass
            return
        if job_type == "generate_client_dna_candidates":
            module_keys = payload.get("moduleKeys", [])
            module_key_list = [str(item) for item in module_keys] if isinstance(module_keys, list) else []
            refresh_generated = bool(payload.get("refreshGenerated"))
            if not module_key_list:
                module_key_list = [module.moduleKey for module in resolve_client_dna_modules_for_generation(client_id, refresh_generated=refresh_generated)]
            if not module_key_list:
                finish_knowledge_job(job_id, status="completed", processed_items=0)
                return
            for module_key in module_key_list:
                markdown_content, missing_items = build_client_dna_candidate_markdown(client_id, module_key)
                save_client_dna_module(
                    client_id,
                    module_key,
                    markdown_content=markdown_content,
                    file_name=f"{safe_filename(build_client_summary(client_id).name)}-{module_key}-candidate.md",
                    source_kind="generated",
                    updated_by="系统候选生成",
                    missing_info=missing_items,
                )
                processed_items += 1
                update_knowledge_job_progress(job_id, processed_items, f"已生成 {dict(CLIENT_DNA_MODULES).get(module_key, module_key)} 候选文档")
            finish_knowledge_job(job_id, status="completed", processed_items=processed_items)
            return
        finish_knowledge_job(job_id, status="failed", processed_items=0, last_error=f"未知任务类型：{job_type}")

    def knowledge_worker_loop() -> None:
        while not state.job_stop.is_set():
            job = claim_next_knowledge_job()
            if not job:
                time.sleep(0.5)
                continue
            try:
                process_knowledge_job(job)
            except Exception as error:
                finish_knowledge_job(str(job["id"]), status="failed", processed_items=int(job.get("processed_items") or 0), last_error=str(error))
            time.sleep(0.05)

    def analysis_job_worker_loop() -> None:
        worker_id = f"analysis-worker-{os.getpid()}"
        while not state.job_stop.is_set():
            job = claim_next_analysis_job(state.db, worker_id)
            if not job:
                time.sleep(0.75)
                continue
            try:
                workspace = workspace_for_client(job.clientId)
                execute_analysis_job_projection(
                    state.db,
                    job,
                    workspace,
                    notebook_summary=workspace.notebookSummary,
                    memory_status=workspace.memoryStatus,
                )
            except Exception as error:
                fail_analysis_job(
                    state.db,
                    job.id,
                    stage_name="analysis_pipeline",
                    error=str(error),
                )
            time.sleep(0.05)

    def build_health() -> HealthResponse:
        ai_health = state.ai.get_health()
        return HealthResponse(
            appName=APP_NAME,
            appVersion=APP_VERSION,
            buildVersion=APP_BUILD_VERSION,
            backendBuildHash=BACKEND_BUILD_HASH,
            backendSchemaVersion=state.db.get_schema_version(),
            runtimeMode=BACKEND_RUNTIME_MODE,
            startedAt=APP_STARTED_AT,
            featureFlags=BACKEND_FEATURE_FLAGS,
            dataDir=str(state.data_dir),
            stats={
                "clients": state.db.scalar("SELECT COUNT(1) AS count FROM clients"),
                "tasks": state.db.scalar("SELECT COUNT(1) AS count FROM tasks"),
                "topics": state.db.scalar("SELECT COUNT(1) AS count FROM topic_candidates"),
                "handbookEntries": state.db.scalar("SELECT COUNT(1) AS count FROM handbook_entries"),
                "analysisRuns": state.db.scalar("SELECT COUNT(1) AS count FROM analysis_runs"),
            },
            ai=HealthAiState(
                provider=ai_health.provider,  # type: ignore[arg-type]
                model=ai_health.model,
                ready=ai_health.ready,
                detail=ai_health.detail,
                credentialSource=ai_health.credential_source,
                fingerprint=ai_health.fingerprint,
            ),
        )

    def build_settings_response() -> SettingsResponse:
        operator = current_operator_row()
        ai_health = state.ai.get_health()
        settings = AppSettingsResponse(
            currentOperatorId=str(operator["id"]),
            aiProvider=state.ai.current_provider(),  # type: ignore[arg-type]
            aiModel=state.ai.current_model(),
            dataDir=str(state.data_dir),
            backupDir=str(state.backup_dir),
            cloudApiUrl=state.cloud_api_url,
            lastBackupAt=state.db.get_setting("last_backup_at", "") or None,
            foldersRootLabel=state.db.get_setting("folders_root_label", "桌面客户资料"),
            aiConfigured=bool(ai_health.fingerprint),
            aiCredentialSource=ai_health.credential_source,
            aiFingerprint=ai_health.fingerprint,
            demoDataLoaded=demo_data_loaded(state.db),
        )
        operators = [
            OperatorRecord(
                id=str(row["id"]),
                name=str(row["name"]),
                role=str(row["role"]),
                team=str(row["team"]),
                color=str(row["color"]),
                isCurrent=bool(row["is_current"]),
            )
            for row in state.db.fetchall("SELECT * FROM operators ORDER BY created_at")
        ]
        return SettingsResponse(settings=settings, operators=operators, health=build_health())

    def _has_persisted_cloud_session() -> bool:
        return bool(state.db.get_setting("cloud_access_token", "") or state.db.get_setting("cloud_refresh_token", ""))

    def get_cloud_token() -> str:
        token = state.db.get_setting("cloud_access_token", "")
        if token:
            state.cloud_session_persistent = True
            return token
        return state.volatile_cloud_access_token

    def get_cloud_refresh_token() -> str:
        token = state.db.get_setting("cloud_refresh_token", "")
        if token:
            state.cloud_session_persistent = True
            return token
        return state.volatile_cloud_refresh_token

    def set_cloud_session(token: str | None, user: SessionUserRecord | None, *, persist: bool = True) -> None:
        state.cloud_session_persistent = persist
        session_user_json = to_json(user.model_dump()) if user else ""
        if persist:
            state.db.set_setting("cloud_access_token", token or "")
            state.db.set_setting("cloud_session_user", session_user_json)
            state.volatile_cloud_access_token = ""
            state.volatile_cloud_session_user_json = ""
            return
        state.db.set_setting("cloud_access_token", "")
        state.db.set_setting("cloud_session_user", "")
        state.volatile_cloud_access_token = token or ""
        state.volatile_cloud_session_user_json = session_user_json

    def set_cloud_refresh_token(token: str | None, *, persist: bool = True) -> None:
        state.cloud_session_persistent = persist
        if persist:
            state.db.set_setting("cloud_refresh_token", token or "")
            state.volatile_cloud_refresh_token = ""
            return
        state.db.set_setting("cloud_refresh_token", "")
        state.volatile_cloud_refresh_token = token or ""

    def clear_cloud_session() -> None:
        set_cloud_session(None, None, persist=True)
        set_cloud_refresh_token(None, persist=True)
        state.volatile_cloud_access_token = ""
        state.volatile_cloud_refresh_token = ""
        state.volatile_cloud_session_user_json = ""
        state.cloud_session_persistent = False

    def get_cached_session_user() -> SessionUserRecord | None:
        raw = state.db.get_setting("cloud_session_user", "")
        if not raw:
            raw = state.volatile_cloud_session_user_json
        parsed = from_json(raw, {}) if raw else {}
        if not isinstance(parsed, dict) or not parsed:
            return None
        try:
            return SessionUserRecord(**parsed)
        except Exception:
            return None

    def current_session_is_admin() -> bool:
        session_user = get_cached_session_user()
        return bool(session_user and session_user.primaryRole == "admin")

    def _load_json_settings_record(key: str, default_factory, model_cls):
        raw = state.db.get_setting(key, "")
        if raw:
            parsed = from_json(raw, {})
            if isinstance(parsed, dict):
                try:
                    return model_cls(**parsed)
                except Exception:
                    pass
        record = default_factory()
        state.db.set_setting(key, to_json(record.model_dump()))
        return record

    def _save_json_settings_record(key: str, record) -> object:
        state.db.set_setting(key, to_json(record.model_dump()))
        return record

    def _default_client_workspace_settings() -> ClientWorkspaceSettingsRecord:
        return ClientWorkspaceSettingsRecord(
            meetingPublishDefaultListId=_local_default_list_id(),
            meetingPublishDefaultPriority="normal",
            updatedAt=now_iso(),
        )

    def _default_topics_settings() -> TopicsSettingsRecord:
        return TopicsSettingsRecord(updatedAt=now_iso())

    FUNDRAISING_MODE_GUIDES: dict[str, dict[str, object]] = {
        "platform_fundraising": {
            "learningTitle": "平台信任先于情绪推动",
            "learningBody": "先让人相信这件事真实、可验证、与自己相关，再去推动情绪共鸣。",
            "focusPoints": ["可信度与真实感", "情绪表达是否过度", "平台风险触发点", "热点与时机"],
        },
        "monthly_donor": {
            "learningTitle": "月捐不是一次成交",
            "learningBody": "长期关系型捐赠更看重持续价值、关系感和被看见的感觉，不是一次性冲动。",
            "focusPoints": ["长期价值主张", "关系感与认同感", "续捐与留存风险", "陪伴感是否成立"],
        },
        "key_person": {
            "learningTitle": "对的人先听到对的逻辑",
            "learningBody": "关键对象更关注判断框架是否匹配、证据是否扎实、合作逻辑是否站得住。",
            "focusPoints": ["对方关注点", "语言风格匹配", "证据与可信度", "合作逻辑"],
        },
    }

    def _normalize_line(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"^\s*(?:[-*•]|[0-9]+[.、）)]|[一二三四五六七八九十]+[、）)])\s*", "", value or "")).strip()

    def _unique_items(items: list[str], limit: int = 6) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = _normalize_line(item).rstrip("。；：")
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)
        return deduped[:limit]

    def _split_structured_items(value: str, limit: int = 6) -> list[str]:
        if not value.strip():
            return []
        normalized = value.replace("\r\n", "\n")
        normalized = re.sub(r"([。；])", r"\1\n", normalized)
        normalized = re.sub(r"\s+(?=\d+[.、）)])", "\n", normalized)
        return _unique_items([segment for segment in re.split(r"\n+", normalized) if segment.strip()], limit=limit)

    def _parse_markdownish_sections(content: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {
            "intro": [],
            "identity": [],
            "core": [],
            "support": [],
            "red": [],
            "evidence": [],
            "voice": [],
            "questions": [],
        }
        current = "intro"
        for raw_line in content.replace("\r\n", "\n").split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            heading = _normalize_line(re.sub(r"^#+\s*", "", line)).rstrip("：:")
            if re.search(r"基础身份|身份摘要|对象概况|人物概况|对象简介", heading):
                current = "identity"
                continue
            if re.search(r"核心偏好|看重什么|偏好|价值偏好", heading):
                current = "core"
                continue
            if re.search(r"支持触发器|支持理由|触发器|打动点|信任触发", heading):
                current = "support"
                continue
            if re.search(r"红线|反感点|风险触发|敏感点|雷区", heading):
                current = "red"
                continue
            if re.search(r"证据偏好|证据要求|信任证据|证明材料", heading):
                current = "evidence"
                continue
            if re.search(r"说话风格|语言风格|口吻|语气|表达偏好", heading):
                current = "voice"
                continue
            if re.search(r"常问问题|常见问题|典型问题|疑问", heading):
                current = "questions"
                continue
            sections[current].append(line)
        return sections

    def _extract_keywords(value: str) -> list[str]:
        return _unique_items(re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,20}", value or ""), limit=12)

    def _confidence_level_from_score(score: int) -> Literal["low", "medium", "high"]:
        if score >= 80:
            return "high"
        if score >= 55:
            return "medium"
        return "low"

    def _make_deep_dna_id(group_key: str, label: str) -> str:
        normalized = re.sub(r"[^a-z0-9_\u4e00-\u9fa5-]", "", re.sub(r"\s+", "_", label.strip().lower()))[:32]
        return f"dna:{group_key}:{normalized or uuid4().hex[:8]}"

    def _build_deep_dna_from_text(
        *,
        group_key: Literal["platform_fundraising", "monthly_donor", "key_person"],
        label: str,
        content: str,
        source_kind: Literal["manual", "import", "web"],
        authorization_status: Literal["public", "authorized_internal", "restricted"] = "authorized_internal",
        existing_id: str | None = None,
        file_name: str | None = None,
        file_path: str | None = None,
        source_url: str | None = None,
        search_query: str | None = None,
        status: Literal["draft", "published"] = "published",
        keep_created_at: str | None = None,
    ) -> DeepDnaRecord:
        sections = _parse_markdownish_sections(content)
        lines = [_normalize_line(item) for item in content.replace("\r\n", "\n").split("\n") if _normalize_line(item)]
        identity_summary = "；".join(_unique_items(sections["identity"] or sections["intro"], limit=2))
        core_preferences = _unique_items(sections["core"] or [line for line in lines if re.search(r"看重|偏好|价值|信任", line)], limit=5)
        support_triggers = _unique_items(sections["support"] or [line for line in lines if re.search(r"支持|打动|行动|愿意", line)], limit=5)
        red_flags = _unique_items(sections["red"] or [line for line in lines if re.search(r"风险|反感|敏感|质疑|避免|雷区", line)], limit=5)
        evidence_preferences = _unique_items(sections["evidence"] or [line for line in lines if re.search(r"证据|数据|预算|透明|证明", line)], limit=4)
        voice_style = _unique_items(sections["voice"] or [line for line in lines if re.search(r"语气|风格|表达|措辞|口吻", line)], limit=4)
        common_questions = _unique_items(sections["questions"] or [line for line in lines if line.endswith("？") or "为什么" in line or "如何" in line], limit=5)
        coverage_score = sum(1 for bucket in [identity_summary, core_preferences, support_triggers, red_flags, evidence_preferences, voice_style, common_questions] if bucket)
        confidence_score = min(96, 42 + coverage_score * 8 + min(len(lines), 16))
        created_at = keep_created_at or now_iso()
        return DeepDnaRecord(
            id=existing_id or _make_deep_dna_id(group_key, label),
            groupKey=group_key,
            label=label.strip(),
            status=status,
            sourceKind=source_kind,
            identitySummary=identity_summary or f"{label.strip()}对象档案已建立，建议继续补充核心偏好、证据偏好与常问问题。",
            corePreferences=core_preferences,
            supportTriggers=support_triggers,
            redFlags=red_flags,
            evidencePreferences=evidence_preferences,
            voiceStyle=voice_style,
            commonQuestions=common_questions,
            sources=[
                DeepDnaSourceRecord(
                    id=new_id("dna_src"),
                    kind=source_kind,
                    title=file_name or label.strip(),
                    excerpt="\n".join(lines[:8])[:420],
                    sourceUrl=source_url,
                    fileName=file_name,
                    filePath=file_path,
                    createdAt=created_at,
                )
            ],
            confidenceScore=confidence_score,
            confidenceLevel=_confidence_level_from_score(confidence_score),
            authorizationStatus=authorization_status,
            rawContent=content.strip(),
            searchQuery=search_query,
            createdAt=created_at,
            updatedAt=now_iso(),
        )

    def _deep_dna_to_profile_record(record: DeepDnaRecord, existing: DiagnosisProfileRecord | None = None) -> DiagnosisProfileRecord:
        file_name = existing.fileName if existing else f"{record.label}.md"
        file_path = existing.filePath if existing else ""
        return DiagnosisProfileRecord(
            id=existing.id if existing else record.id,
            groupKey=record.groupKey,
            deepDnaId=record.id,
            label=record.label,
            fileName=file_name,
            filePath=file_path,
            markdownContent=record.rawContent,
            summary=record.identitySummary,
            corePreferences=record.corePreferences,
            riskTriggers=record.redFlags,
            tonePreference="；".join(record.voiceStyle) if record.voiceStyle else None,
            updatedAt=record.updatedAt,
        )

    def _sync_diagnosis_profiles_with_deep_dna(settings: AnalysisWorkbenchSettingsRecord) -> AnalysisWorkbenchSettingsRecord:
        published = [record for record in settings.deepDnaLibrary if record.status == "published"]
        existing_by_deep_dna = {
            profile.deepDnaId: profile
            for profile in settings.diagnosisProfiles
            if profile.deepDnaId
        }
        profiles_by_id = {profile.id: profile for profile in settings.diagnosisProfiles}
        synced_profiles: list[DiagnosisProfileRecord] = []
        seen_profile_ids: set[str] = set()
        for record in published:
            existing = existing_by_deep_dna.get(record.id) or profiles_by_id.get(record.id)
            profile = _deep_dna_to_profile_record(record, existing=existing)
            if profile.id in seen_profile_ids:
                continue
            synced_profiles.append(profile)
            seen_profile_ids.add(profile.id)
        legacy_profiles = [profile for profile in settings.diagnosisProfiles if not profile.deepDnaId and profile.id not in seen_profile_ids]
        synced_profiles.extend(legacy_profiles)
        return settings.model_copy(update={"diagnosisProfiles": synced_profiles})

    def _seed_deep_dna_from_legacy_profiles(settings: AnalysisWorkbenchSettingsRecord) -> AnalysisWorkbenchSettingsRecord:
        if settings.deepDnaLibrary:
            return settings
        if not settings.diagnosisProfiles:
            return settings
        migrated_records = [
            _build_deep_dna_from_text(
                group_key=profile.groupKey,
                label=profile.label,
                content=profile.markdownContent or profile.summary,
                source_kind="import",
                authorization_status="authorized_internal",
                existing_id=profile.deepDnaId or profile.id,
                file_name=profile.fileName,
                file_path=profile.filePath,
                status="published",
                keep_created_at=profile.updatedAt,
            ).model_copy(
                update={
                    "identitySummary": profile.summary,
                    "corePreferences": profile.corePreferences,
                    "redFlags": profile.riskTriggers,
                    "voiceStyle": _unique_items((profile.tonePreference or "").split("；"), limit=4),
                    "updatedAt": profile.updatedAt,
                }
            )
            for profile in settings.diagnosisProfiles
        ]
        return settings.model_copy(update={"deepDnaLibrary": migrated_records})

    def _system_coach_cases() -> list[CoachCaseRecord]:
        timestamp = now_iso()
        return [
            CoachCaseRecord(
                id="system_case_platform_budget",
                title="平台筹款先给出预算与去向",
                summary="平台公域更信任能快速看懂用途、金额和执行闭环的表达。",
                whyEffective="先解决真实性与资金去向，再谈情绪，能显著降低公域疑虑。",
                takeaways=["先写钱怎么花", "用一条具体事实建立真实感", "把行动号召放在证据之后"],
                keyExcerpt="这笔捐款将直接用于 120 户家庭的应急粮包和 2 周配送，每一笔支出都会在页面持续公开。",
                scenes=["平台筹款"],
                tags=["可信度", "预算拆解", "透明度"],
                issueTypes=["可信度不足", "预算不清"],
                sourceType="system",
                sourceLabel="系统内置案例",
                createdAt=timestamp,
                updatedAt=timestamp,
            ),
            CoachCaseRecord(
                id="system_case_monthly_relationship",
                title="月捐转化强调持续陪伴而非一次性刺激",
                summary="月捐沟通更适合把关系、长期变化和反馈机制写实，而不是只做情绪冲刺。",
                whyEffective="长期承诺要建立在可持续参与感上，不能只靠一次情绪高峰。",
                takeaways=["说明长期价值", "给出陪伴反馈节奏", "降低一次性压迫感"],
                keyExcerpt="每个月 30 元，会让一个家庭在整个学期都持续收到作业辅导和家长支持回访。",
                scenes=["月捐人测试"],
                tags=["长期价值", "留存", "陪伴感"],
                issueTypes=["长期价值不清", "关系感不足"],
                sourceType="system",
                sourceLabel="系统内置案例",
                createdAt=timestamp,
                updatedAt=timestamp,
            ),
            CoachCaseRecord(
                id="system_case_key_person_logic",
                title="Key Person 提案先对齐判断框架",
                summary="关键对象更愿意先看到合作逻辑、结果路径和机构能力，而不是先看情绪渲染。",
                whyEffective="它先对齐了对方的判断框架，让后续案例和请求更容易被接受。",
                takeaways=["先说合作逻辑", "补能力与证据", "请求要与对方角色匹配"],
                keyExcerpt="我们希望与您共建的是一套可复制的学校支持机制，而不是一次性资助活动。",
                scenes=["Key Person"],
                tags=["合作逻辑", "提案", "证据链"],
                issueTypes=["合作逻辑不清", "对象不匹配"],
                sourceType="system",
                sourceLabel="系统内置案例",
                createdAt=timestamp,
                updatedAt=timestamp,
            ),
        ]

    def _extract_mode_from_input(title: str, input_text: str) -> Literal["platform_fundraising", "monthly_donor", "key_person", "incident_response", "preflight_release", "project_mechanism", "stakeholder_simulation", "methodology_review"] | None:
        match = re.search(r"\[\[DIAGNOSIS_CONTEXT\]\](.*?)\[\[/DIAGNOSIS_CONTEXT\]\]", input_text, re.DOTALL)
        if match:
            block = match.group(1)
            for line in block.splitlines():
                line = line.strip()
                if line.startswith("modeId="):
                    mode_id = line.split("=", 1)[1].strip()
                    if mode_id:
                        return mode_id  # type: ignore[return-value]
        haystack = f"{title}\n{input_text}"
        if "月捐" in haystack:
            return "monthly_donor"
        if re.search(r"基金会|CSR|关键|捐赠人|提案", haystack):
            return "key_person"
        if re.search(r"平台|腾讯公益|抖音公益|公域", haystack):
            return "platform_fundraising"
        return None

    def _match_coach_cases(
        cases: list[CoachCaseRecord],
        *,
        mode_id: str,
        issue_title: str,
        issue_body: str,
    ) -> list[CoachCaseRecord]:
        issue_tokens = set(_extract_keywords(f"{issue_title} {issue_body}"))
        matched: list[tuple[int, CoachCaseRecord]] = []
        for case in cases:
            score = 0
            if not case.scenes or any(scene in {"平台筹款", "月捐人测试", "Key Person"} for scene in case.scenes):
                if mode_id == "platform_fundraising" and any(scene in {"平台筹款"} for scene in case.scenes):
                    score += 4
                if mode_id == "monthly_donor" and any(scene in {"月捐人测试"} for scene in case.scenes):
                    score += 4
                if mode_id == "key_person" and any(scene in {"Key Person"} for scene in case.scenes):
                    score += 4
            for token in issue_tokens:
                if token and any(token in field for field in [case.title, case.summary, " ".join(case.issueTypes), " ".join(case.tags)]):
                    score += 2
            if score > 0:
                matched.append((score, case))
        matched.sort(key=lambda item: item[0], reverse=True)
        return [case for _, case in matched[:2]]

    def _build_coach_payload(
        *,
        run_id: str,
        output: AiStructuredResponse,
        title: str,
        input_text: str,
        mode_id: str | None,
        settings: AnalysisWorkbenchSettingsRecord,
    ) -> CoachPayload:
        if mode_id not in {"platform_fundraising", "monthly_donor", "key_person"}:
            return CoachPayload()
        guide = FUNDRAISING_MODE_GUIDES.get(mode_id, FUNDRAISING_MODE_GUIDES["platform_fundraising"])
        judgment_items = _split_structured_items(output.judgment, limit=3)
        action_items = _split_structured_items(output.actions, limit=4)
        analysis_items = _split_structured_items(output.analysis, limit=4)
        content_items = _split_structured_items(output.content, limit=3)
        seeds = judgment_items + (action_items or analysis_items or content_items)
        combined_cases = [*_system_coach_cases(), *settings.coachCaseLibrary]
        cards: list[CoachCardRecord] = []
        for index, seed in enumerate(_unique_items(seeds, limit=3)):
            issue_title = seed[:24] + ("…" if len(seed) > 24 else "")
            why_important = (analysis_items[index] if index < len(analysis_items) else output.analysis or output.judgment or seed).strip()
            matched_knowledge = next(
                (
                    entry for entry in settings.fundraisingKnowledgeLibrary
                    if any(token in f"{entry.title} {entry.summary} {' '.join(entry.tags)} {' '.join(entry.principles)} {' '.join(entry.riskSignals)}" for token in _extract_keywords(seed))
                ),
                None,
            )
            case_refs = _match_coach_cases(combined_cases, mode_id=mode_id, issue_title=issue_title, issue_body=why_important)
            cards.append(
                CoachCardRecord(
                    id=f"{run_id}:coach:{index}",
                    issueKey=_extract_keywords(seed)[0] if _extract_keywords(seed) else f"issue_{index + 1}",
                    insightTitle=issue_title,
                    issueWhat=seed,
                    whyImportant=why_important,
                    knowledgePointTitle=str(matched_knowledge.title if matched_knowledge else guide["learningTitle"]),
                    knowledgePointBody=(matched_knowledge.principles[0] if matched_knowledge and matched_knowledge.principles else str(guide["learningBody"])),
                    caseIds=[case.id for case in case_refs],
                    selfRewriteHint=(action_items[index] if index < len(action_items) else seed),
                    learningAction=f"按“{issue_title}”重写一版，再回看是否补上了{str(guide['focusPoints'][0]) if guide.get('focusPoints') else '核心判断'}。",
                    referenceDraft=None,
                )
            )
        text_haystack = f"{title}\n{input_text}\n{output.analysis}\n{output.actions}"
        triggered_reminders = [
            rule for rule in settings.coachReminderRules
            if (not rule.modeIds or mode_id in rule.modeIds)
            and (
                rule.knowledgeKey in text_haystack
                or rule.issuePattern in text_haystack
                or any(rule.knowledgeKey in card.issueWhat or rule.issuePattern in card.issueWhat for card in cards)
            )
        ]
        applied_norms = [
            norm for norm in settings.orgWritingNorms
            if (not norm.modeIds or mode_id in norm.modeIds)
            and (
                not norm.triggerKeywords
                or any(keyword and keyword in text_haystack for keyword in norm.triggerKeywords)
            )
        ]
        return CoachPayload(cards=cards, triggeredReminders=triggered_reminders[:3], appliedNorms=applied_norms[:3])

    def _build_run_comparison(current_run: AnalysisRunRecord, previous_run: AnalysisRunRecord | None) -> RunComparison:
        if not previous_run:
            return RunComparison(
                currentRunId=current_run.id,
                previousRunId=None,
                resultChanges=["当前还没有上一版可对比，后续从你自己改的一版开始会自动生成结构化对比。"],
                learningChanges=["先完成一轮“我来试改”，下一版会显示新增学习点、已解决问题和重复犯错。"],
            )
        current_cards = current_run.coachPayload.cards if current_run.coachPayload else []
        previous_cards = previous_run.coachPayload.cards if previous_run.coachPayload else []
        current_titles = [card.insightTitle for card in current_cards] or _split_structured_items(current_run.output.actions or current_run.output.judgment, limit=3)
        previous_titles = [card.insightTitle for card in previous_cards] or _split_structured_items(previous_run.output.actions or previous_run.output.judgment, limit=3)
        current_set = set(current_titles)
        previous_set = set(previous_titles)
        resolved = [item for item in previous_titles if item not in current_set][:3]
        new_issues = [item for item in current_titles if item not in previous_set][:3]
        repeated = [item for item in current_titles if item in previous_set][:3]
        current_learning = [card.knowledgePointTitle for card in current_cards if card.knowledgePointTitle]
        previous_learning = [card.knowledgePointTitle for card in previous_cards if card.knowledgePointTitle]
        result_changes: list[str] = []
        learning_changes: list[str] = []
        if resolved:
            result_changes.append(f"已解决：{'；'.join(resolved)}")
        if new_issues:
            result_changes.append(f"新增问题：{'；'.join(new_issues)}")
        if repeated:
            result_changes.append(f"仍需继续盯住：{'；'.join(repeated)}")
        new_learning = [item for item in current_learning if item not in set(previous_learning)][:3]
        repeated_learning = [item for item in current_learning if item in set(previous_learning)][:3]
        if new_learning:
            learning_changes.append(f"新学到：{'；'.join(new_learning)}")
        if repeated_learning:
            learning_changes.append(f"还在反复练：{'；'.join(repeated_learning)}")
        if not learning_changes:
            learning_changes.append("学习重点整体与上一版接近，说明你正在反复打磨同一类核心问题。")
        if not result_changes:
            result_changes.append("本轮结构化结果与上一版较接近，建议继续在最重要的三条修改上做更明显的版本差异。")
        return RunComparison(
            currentRunId=current_run.id,
            previousRunId=previous_run.id,
            resultChanges=result_changes,
            learningChanges=learning_changes,
            resolvedIssues=resolved,
            newIssues=new_issues,
            repeatedIssues=repeated,
        )

    def _default_analysis_workbench_settings() -> AnalysisWorkbenchSettingsRecord:
        template_ids = [str(row["id"]) for row in state.db.fetchall("SELECT id FROM analysis_templates ORDER BY created_at ASC")]
        return AnalysisWorkbenchSettingsRecord(
            enabledTemplateIds=template_ids,
            defaultTemplateId=template_ids[0] if template_ids else None,
            updatedAt=now_iso(),
        )

    def _default_handbook_settings() -> HandbookSettingsRecord:
        return HandbookSettingsRecord(updatedAt=now_iso())

    def _default_system_admin_settings() -> SystemAdminSettingsRecord:
        return SystemAdminSettingsRecord(updatedAt=now_iso())

    def _default_main_chain_stability_settings() -> MainChainStabilitySettingsRecord:
        return MainChainStabilitySettingsRecord(updatedAt=now_iso())

    def _load_json_int_setting_map(key: str) -> dict[str, int]:
        raw = state.db.get_setting(key, "")
        parsed = from_json(raw, {}) if raw else {}
        if not isinstance(parsed, dict):
            return {}
        normalized: dict[str, int] = {}
        for bucket, value in parsed.items():
            label = str(bucket or "").strip()
            if not label:
                continue
            try:
                normalized[label] = int(value or 0)
            except (TypeError, ValueError):
                normalized[label] = 0
        return normalized

    def _read_analysis_worker_counter_snapshot() -> AnalysisWorkerCounterSnapshotRecord:
        return AnalysisWorkerCounterSnapshotRecord(
            claimCounts=_load_json_int_setting_map("analysis.worker.claim_counts"),
            lockContention=_load_json_int_setting_map("analysis.worker.lock_contention"),
            backfillThrottle=_load_json_int_setting_map("analysis.worker.backfill_throttle"),
        )

    def _hydrate_main_chain_stability_settings(
        record: MainChainStabilitySettingsRecord,
    ) -> MainChainStabilitySettingsRecord:
        return record.model_copy(
            update={
                "backfillPaused": is_analysis_backfill_paused(state.db),
                "workerCounters": _read_analysis_worker_counter_snapshot(),
            }
        )

    def _normalize_brand_logo_data_url(value: str | None) -> str | None:
        normalized = (value or "").strip()
        if not normalized:
            return None
        if not normalized.startswith("data:image/png;base64,"):
            raise HTTPException(status_code=400, detail="品牌 Logo 目前只支持 PNG data URL")
        if len(normalized) > 1_500_000:
            raise HTTPException(status_code=400, detail="品牌 Logo 过大，请换更小的 PNG")
        return normalized

    def _normalize_feishu_user_binding_callback_url(value: str | None) -> str:
        normalized = (value or "").strip()
        if not normalized:
            return ""
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="飞书个人绑定回调 URL 必须是完整的 http(s) 地址。")
        if not parsed.path:
            raise HTTPException(status_code=400, detail="飞书个人绑定回调 URL 需要包含完整回调路径。")
        if parsed.fragment:
            raise HTTPException(status_code=400, detail="飞书个人绑定回调 URL 不能包含 # 片段。")
        return normalized

    def _is_public_feishu_callback_url(callback_url: str) -> bool:
        parsed = urlparse(callback_url)
        host = (parsed.hostname or "").strip().lower()
        if parsed.scheme != "https":
            return False
        if host in {"127.0.0.1", "localhost", "::1"} or host.endswith(".local"):
            return False
        return True

    def _default_feishu_bot_settings() -> FeishuBotSettingsRecord:
        return FeishuBotSettingsRecord(updatedAt=now_iso())

    def _fixed_review_department_records() -> list[ReviewDepartmentConfigRecord]:
        return [
            ReviewDepartmentConfigRecord(
                id=item.id,
                name=item.name,
                color=item.color,
                monthlyDna="",
                weeklyFocus="",
                leaders=[],
                members=[],
            )
            for item in list_department_catalog()
        ]

    def _default_review_governance_settings() -> ReviewGovernanceSettingsRecord:
        return ReviewGovernanceSettingsRecord(departments=_fixed_review_department_records(), updatedAt=now_iso())

    def _sanitize_review_governance_settings(
        departments: list[ReviewDepartmentConfigRecord],
        *,
        keep_updated_at: str | None = None,
    ) -> ReviewGovernanceSettingsRecord:
        fixed_departments = _fixed_review_department_records()
        incoming_by_id: dict[str, ReviewDepartmentConfigRecord] = {}
        for department in departments:
            matched = get_department_entry(department.id, department.name)
            if matched:
                incoming_by_id[matched.id] = department

        sanitized_departments: list[ReviewDepartmentConfigRecord] = []
        for fixed_department in fixed_departments:
            department = incoming_by_id.get(fixed_department.id, fixed_department)
            seen_leader_names: set[str] = set()
            leaders: list[ReviewDepartmentMemberRecord] = []
            for leader in department.leaders:
                full_name = leader.fullName.strip()
                if not full_name:
                    continue
                key = full_name.lower()
                if key in seen_leader_names:
                    continue
                seen_leader_names.add(key)
                leaders.append(
                    ReviewDepartmentMemberRecord(
                        id=leader.id.strip(),
                        fullName=full_name,
                        email=leader.email.strip() if leader.email else None,
                    )
                )
            sanitized_departments.append(
                ReviewDepartmentConfigRecord(
                    id=fixed_department.id,
                    name=fixed_department.name,
                    color=department.color.strip() or fixed_department.color,
                    monthlyDna=department.monthlyDna.strip(),
                    weeklyFocus=department.weeklyFocus.strip(),
                    leaders=leaders,
                    members=[],
                )
            )
        return ReviewGovernanceSettingsRecord(
            departments=sanitized_departments,
            updatedAt=keep_updated_at or now_iso(),
        )

    def get_review_governance_settings() -> ReviewGovernanceSettingsRecord:
        current = _load_json_settings_record(
            "settings.review_governance",
            _default_review_governance_settings,
            ReviewGovernanceSettingsRecord,
        )
        sanitized = _sanitize_review_governance_settings(current.departments, keep_updated_at=current.updatedAt)
        if sanitized.model_dump() != current.model_dump():
            state.db.set_setting("settings.review_governance", to_json(sanitized.model_dump()))
        return sanitized

    def _sync_review_governance_members(
        governance: ReviewGovernanceSettingsRecord,
        employees: list[EmployeeRecord],
    ) -> ReviewGovernanceSettingsRecord:
        employees_by_department: dict[str, list[ReviewDepartmentMemberRecord]] = {department.id: [] for department in governance.departments}
        seen_keys: dict[str, set[str]] = {department.id: set() for department in governance.departments}
        for employee in employees:
            department = get_department_entry(employee.departmentId, employee.departmentName)
            if not department or department.id not in employees_by_department:
                continue
            key = employee.id.strip() or employee.fullName.strip().lower()
            if not key or key in seen_keys[department.id]:
                continue
            seen_keys[department.id].add(key)
            employees_by_department[department.id].append(
                ReviewDepartmentMemberRecord(
                    id=employee.id,
                    fullName=employee.fullName,
                    email=employee.email,
                )
            )
        return governance.model_copy(
            update={
                "departments": [
                    department.model_copy(update={"members": employees_by_department.get(department.id, [])})
                    for department in governance.departments
                ]
            }
        )

    def _load_employee_directory_from_cloud() -> list[EmployeeRecord]:
        payload = cloud_request("GET", "/api/v1/employees/directory")
        if not isinstance(payload, list):
            raise HTTPException(status_code=502, detail="Invalid employee directory payload")
        employees: list[EmployeeRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            employees.append(EmployeeRecord(**item))
        return employees

    def _review_governance_with_members() -> ReviewGovernanceSettingsRecord:
        governance = get_review_governance_settings()
        token = get_cloud_token()
        if not token:
            return governance
        try:
            employees = _load_employee_directory_from_cloud()
        except HTTPException:
            return governance
        return _sync_review_governance_members(governance, employees)

    def _user_matches_department_member(member: ReviewDepartmentMemberRecord, *, user_id: str, full_name: str) -> bool:
        member_id = member.id.strip()
        member_name = member.fullName.strip().lower()
        return bool(
            (member_id and user_id and member_id == user_id)
            or (member_name and full_name and member_name == full_name.lower())
        )

    def _review_department_for_session_user(
        session_user: SessionUserRecord | None,
        governance: ReviewGovernanceSettingsRecord,
    ) -> ReviewDepartmentConfigRecord | None:
        if session_user is None:
            return None
        user_id = session_user.id.strip()
        full_name = session_user.fullName.strip()
        if not full_name and not user_id:
            return None
        for department in governance.departments:
            if any(_user_matches_department_member(leader, user_id=user_id, full_name=full_name) for leader in department.leaders):
                return department
        return None

    def _resolve_review_viewer_role(
        session_user: SessionUserRecord | None,
        governance: ReviewGovernanceSettingsRecord | None = None,
    ) -> Literal["employee", "department_lead", "admin"]:
        if session_user is None:
            return "employee"
        if session_user.primaryRole == "admin":
            return "admin"
        if governance is not None and _review_department_for_session_user(session_user, governance) is not None:
            return "department_lead"
        return "employee"

    def _normalize_department_name(value: str | None) -> str:
        return (value or "").strip().lower()

    def _resolve_agent_execution_department_scope(
        session_user: SessionUserRecord | None,
        governance: ReviewGovernanceSettingsRecord,
        requested_department: str | None,
    ) -> str | None:
        normalized_requested = _normalize_department_name(requested_department)
        if session_user and session_user.primaryRole == "admin":
            return requested_department.strip() if requested_department and requested_department.strip() else None

        viewer_department = _review_department_for_session_user(session_user, governance)
        if viewer_department is None:
            raise HTTPException(status_code=403, detail="Only department leaders or CEO can view agent execution")

        if normalized_requested and normalized_requested != _normalize_department_name(viewer_department.name):
            raise HTTPException(status_code=403, detail="Department leaders can only view their own department")

        return viewer_department.name

    def _hydrate_feishu_bot_settings(record: FeishuBotSettingsRecord) -> FeishuBotSettingsRecord:
        fingerprint: str | None = None
        source = "unconfigured"
        try:
            fingerprint = state.feishu_secret_store.get_api_key_fingerprint()
            source = state.feishu_secret_store.get_source_label() if fingerprint else "unconfigured"
        except Exception:
            source = "unavailable"
        has_app_secret = bool(fingerprint)
        return record.model_copy(
            update={
                "appId": record.appId.strip(),
                "receiverId": record.receiverId.strip(),
                "botName": record.botName.strip() or "罗茜茜",
                "userBindingCallbackUrl": _normalize_feishu_user_binding_callback_url(record.userBindingCallbackUrl),
                "ready": bool(record.appId.strip() and record.receiverId.strip() and has_app_secret),
                "hasAppSecret": has_app_secret,
                "secretSource": source,
                "secretFingerprint": fingerprint,
            }
        )

    def _persist_feishu_bot_settings(record: FeishuBotSettingsRecord) -> FeishuBotSettingsRecord:
        sanitized = record.model_copy(
            update={
                "appId": record.appId.strip(),
                "receiverId": record.receiverId.strip(),
                "botName": record.botName.strip() or "罗茜茜",
                "userBindingCallbackUrl": _normalize_feishu_user_binding_callback_url(record.userBindingCallbackUrl),
                "updatedAt": now_iso(),
            }
        )
        state.db.set_setting("settings.feishu_bot", to_json(sanitized.model_dump()))
        return _hydrate_feishu_bot_settings(sanitized)

    def get_client_workspace_settings() -> ClientWorkspaceSettingsRecord:
        return _load_json_settings_record("settings.client_workspace", _default_client_workspace_settings, ClientWorkspaceSettingsRecord)

    def _client_hidden_folders_key(client_id: str) -> str:
        return f"client.hidden_folders:{client_id}"

    def get_hidden_client_folders(client_id: str) -> set[str]:
        raw = state.db.get_setting(_client_hidden_folders_key(client_id), "")
        parsed = from_json(raw, []) if raw else []
        if not isinstance(parsed, list):
            return set()
        return {str(item).strip() for item in parsed if str(item).strip()}

    def save_hidden_client_folders(client_id: str, labels: set[str]) -> None:
        state.db.set_setting(_client_hidden_folders_key(client_id), to_json(sorted(labels)))

    def hide_client_folder_label(client_id: str, label: str) -> None:
        hidden = get_hidden_client_folders(client_id)
        hidden.add(label)
        save_hidden_client_folders(client_id, hidden)

    def unhide_client_folder_label(client_id: str, label: str) -> None:
        hidden = get_hidden_client_folders(client_id)
        if label in hidden:
            hidden.remove(label)
            save_hidden_client_folders(client_id, hidden)

    def get_topics_settings() -> TopicsSettingsRecord:
        return _load_json_settings_record("settings.topics", _default_topics_settings, TopicsSettingsRecord)

    def get_analysis_workbench_settings() -> AnalysisWorkbenchSettingsRecord:
        current = _load_json_settings_record("settings.analysis_workbench", _default_analysis_workbench_settings, AnalysisWorkbenchSettingsRecord)
        dirty = False
        if not current.enabledTemplateIds:
            template_ids = [str(row["id"]) for row in state.db.fetchall("SELECT id FROM analysis_templates ORDER BY created_at ASC")]
            current = current.model_copy(update={"enabledTemplateIds": template_ids, "defaultTemplateId": current.defaultTemplateId or (template_ids[0] if template_ids else None)})
            dirty = True
        migrated = _seed_deep_dna_from_legacy_profiles(current)
        if migrated != current:
            current = migrated
            dirty = True
        synced = _sync_diagnosis_profiles_with_deep_dna(current)
        if synced != current:
            current = synced
            dirty = True
        if dirty:
            _save_json_settings_record("settings.analysis_workbench", current)
        return current

    def save_analysis_workbench_settings(record: AnalysisWorkbenchSettingsRecord) -> AnalysisWorkbenchSettingsRecord:
        normalized = _sync_diagnosis_profiles_with_deep_dna(_seed_deep_dna_from_legacy_profiles(record))
        _save_json_settings_record("settings.analysis_workbench", normalized)
        return normalized

    def get_handbook_settings() -> HandbookSettingsRecord:
        return _load_json_settings_record("settings.handbook", _default_handbook_settings, HandbookSettingsRecord)

    def get_system_admin_settings() -> SystemAdminSettingsRecord:
        return _load_json_settings_record("settings.system_admin", _default_system_admin_settings, SystemAdminSettingsRecord)

    def get_main_chain_stability_settings() -> MainChainStabilitySettingsRecord:
        record = _load_json_settings_record(
            "settings.main_chain_stability",
            _default_main_chain_stability_settings,
            MainChainStabilitySettingsRecord,
        )
        return _hydrate_main_chain_stability_settings(record)

    def save_main_chain_stability_settings(
        payload: MainChainStabilitySettingsPayload,
    ) -> MainChainStabilitySettingsRecord:
        current = _load_json_settings_record(
            "settings.main_chain_stability",
            _default_main_chain_stability_settings,
            MainChainStabilitySettingsRecord,
        )
        next_payload = current.model_dump()
        updates = payload.model_dump(exclude_none=True)
        if "latestJudgmentsShadowOff" in updates:
            next_payload["latestJudgmentsShadowOff"] = bool(updates["latestJudgmentsShadowOff"])
        if "backfillPaused" in updates:
            set_analysis_backfill_paused(state.db, bool(updates["backfillPaused"]))
        if payload.lastCanaryObservation is not None:
            previous = current.lastCanaryObservation
            observation_payload = previous.model_dump() if previous is not None else {"recordedAt": now_iso()}
            observation_payload.update(payload.lastCanaryObservation.model_dump(exclude_none=True))
            observation_payload["recordedAt"] = now_iso()
            next_payload["lastCanaryObservation"] = observation_payload
        next_payload["backfillPaused"] = is_analysis_backfill_paused(state.db)
        next_payload["workerCounters"] = _read_analysis_worker_counter_snapshot().model_dump()
        next_payload["updatedAt"] = now_iso()
        next_record = MainChainStabilitySettingsRecord(**next_payload)
        _save_json_settings_record("settings.main_chain_stability", next_record)
        return _hydrate_main_chain_stability_settings(next_record)

    def _event_line_evidence_count_or_zero(value: object | None, *, default: int = 0) -> int:
        if value is None:
            return max(default, 0)
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return max(default, 0)

    def _default_local_input_memory() -> LocalInputMemoryResponse:
        return LocalInputMemoryResponse()

    def _remembered_cloud_auth_store(email: str):
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise HTTPException(status_code=400, detail="请先提供要记住的邮箱。")
        return build_secret_store(REMEMBERED_CLOUD_AUTH_SERVICE, account_name=normalized_email)

    def _remembered_ai_store():
        return build_secret_store(REMEMBERED_AI_INPUT_SERVICE)

    def _remembered_feishu_store():
        return build_secret_store(REMEMBERED_FEISHU_INPUT_SERVICE)

    def _get_local_input_memory_record() -> LocalInputMemoryResponse:
        return _load_json_settings_record(
            LOCAL_INPUT_MEMORY_SETTINGS_KEY,
            _default_local_input_memory,
            LocalInputMemoryResponse,
        )

    def _save_local_input_memory_record(record: LocalInputMemoryResponse) -> LocalInputMemoryResponse:
        _save_json_settings_record(LOCAL_INPUT_MEMORY_SETTINGS_KEY, record)
        return record

    def _hydrate_local_input_memory(record: LocalInputMemoryResponse | None = None) -> LocalInputMemoryResponse:
        raw_record = record or _get_local_input_memory_record()

        remembered_accounts: list[RememberedCloudAuthAccount] = []
        if raw_record.cloudAuth.rememberInputs:
            for account in raw_record.cloudAuth.accounts:
                password = ""
                try:
                    password = _remembered_cloud_auth_store(account.email).get_api_key()
                except Exception:
                    password = ""
                remembered_accounts.append(
                    account.model_copy(update={"password": password})
                )
        cloud_auth = LocalInputMemoryCloudAuth(
            rememberInputs=raw_record.cloudAuth.rememberInputs,
            lastEmail=raw_record.cloudAuth.lastEmail,
            accounts=remembered_accounts,
        )

        remembered_ai_key = ""
        if raw_record.aiSettings.rememberApiKey:
            try:
                remembered_ai_key = _remembered_ai_store().get_api_key()
            except Exception:
                remembered_ai_key = ""
        ai_settings = LocalInputMemoryAiSettings(
            rememberApiKey=raw_record.aiSettings.rememberApiKey,
            apiKey=remembered_ai_key,
        )

        remembered_feishu_secret = ""
        if raw_record.feishuIntegration.rememberInputs:
            try:
                remembered_feishu_secret = _remembered_feishu_store().get_api_key()
            except Exception:
                remembered_feishu_secret = ""
        feishu_integration = LocalInputMemoryFeishuIntegration(
            rememberInputs=raw_record.feishuIntegration.rememberInputs,
            appId=raw_record.feishuIntegration.appId,
            callbackMode=raw_record.feishuIntegration.callbackMode,
            customCallbackUrl=raw_record.feishuIntegration.customCallbackUrl,
            appSecret=remembered_feishu_secret,
        )

        return LocalInputMemoryResponse(
            cloudAuth=cloud_auth,
            aiSettings=ai_settings,
            feishuIntegration=feishu_integration,
        )

    def get_feishu_bot_settings() -> FeishuBotSettingsRecord:
        record = _load_json_settings_record("settings.feishu_bot", _default_feishu_bot_settings, FeishuBotSettingsRecord)
        return _hydrate_feishu_bot_settings(record)

    def _feishu_user_binding_key(user_id: str) -> str:
        return f"settings.feishu_user_binding:{user_id}"

    def _feishu_oauth_state_key(state_token: str) -> str:
        return f"settings.feishu_oauth_state:{state_token}"

    def _feishu_user_binding_pending_key(user_id: str) -> str:
        return f"settings.feishu_user_binding_pending:{user_id}"

    def _feishu_user_binding_authorization_ready() -> bool:
        settings = get_feishu_bot_settings()
        if not settings.appId.strip():
            return False
        try:
            return bool(state.feishu_secret_store.get_api_key().strip())
        except Exception:
            return False

    def _default_feishu_user_binding(user_id: str) -> FeishuUserBindingRecord:
        return FeishuUserBindingRecord(userId=user_id, appId=get_feishu_bot_settings().appId.strip())

    def get_feishu_user_binding(user_id: str) -> FeishuUserBindingRecord:
        raw = state.db.get_setting(_feishu_user_binding_key(user_id), "")
        if raw:
            parsed = from_json(raw, {})
            if isinstance(parsed, dict):
                try:
                    record = FeishuUserBindingRecord(**parsed)
                except Exception:
                    record = _default_feishu_user_binding(user_id)
            else:
                record = _default_feishu_user_binding(user_id)
        else:
            record = _default_feishu_user_binding(user_id)
        settings = get_feishu_bot_settings()
        return record.model_copy(
            update={
                "userId": user_id,
                "appId": settings.appId.strip(),
                "linked": bool(record.openId),
                "readyForAuthorization": _feishu_user_binding_authorization_ready(),
            }
        )

    def save_feishu_user_binding(record: FeishuUserBindingRecord) -> FeishuUserBindingRecord:
        sanitized = record.model_copy(
            update={
                "linked": bool(record.openId),
                "readyForAuthorization": _feishu_user_binding_authorization_ready(),
                "appId": get_feishu_bot_settings().appId.strip(),
                "lastError": record.lastError.strip() if record.lastError else None,
            }
        )
        state.db.set_setting(_feishu_user_binding_key(sanitized.userId), to_json(sanitized.model_dump()))
        return get_feishu_user_binding(sanitized.userId)

    def clear_feishu_user_binding(user_id: str) -> FeishuUserBindingRecord:
        state.db.set_setting(_feishu_user_binding_key(user_id), "")
        return get_feishu_user_binding(user_id)

    def save_feishu_oauth_state(state_token: str, user_id: str, expires_at: str) -> None:
        state.db.set_setting(
            _feishu_oauth_state_key(state_token),
            to_json({"userId": user_id, "expiresAt": expires_at, "createdAt": now_iso()}),
        )

    def pop_feishu_oauth_state(state_token: str) -> dict[str, str] | None:
        key = _feishu_oauth_state_key(state_token)
        raw = state.db.get_setting(key, "")
        state.db.set_setting(key, "")
        if not raw:
            return None
        parsed = from_json(raw, {})
        if not isinstance(parsed, dict):
            return None
        return {str(k): str(v) for k, v in parsed.items() if v is not None}

    def clear_feishu_oauth_state(state_token: str) -> None:
        state.db.set_setting(_feishu_oauth_state_key(state_token), "")

    def get_feishu_user_binding_pending(user_id: str) -> dict[str, str] | None:
        raw = state.db.get_setting(_feishu_user_binding_pending_key(user_id), "")
        if not raw:
            return None
        parsed = from_json(raw, {})
        if not isinstance(parsed, dict):
            return None
        return {str(key): str(value) for key, value in parsed.items() if value is not None}

    def save_feishu_user_binding_pending(user_id: str, *, state_token: str, expires_at: str, callback_url: str, mode: str) -> None:
        state.db.set_setting(
            _feishu_user_binding_pending_key(user_id),
            to_json(
                {
                    "state": state_token,
                    "expiresAt": expires_at,
                    "callbackUrl": callback_url,
                    "mode": mode,
                    "updatedAt": now_iso(),
                }
            ),
        )

    def clear_feishu_user_binding_pending(user_id: str) -> None:
        state.db.set_setting(_feishu_user_binding_pending_key(user_id), "")

    def _feishu_cloud_relay_callback_url() -> str:
        return f"{state.cloud_api_url.rstrip('/')}/api/v1/integrations/feishu/user-binding/callback"

    def _save_feishu_user_binding_error(user_id: str, message: str) -> FeishuUserBindingRecord:
        existing = get_feishu_user_binding(user_id)
        return save_feishu_user_binding(existing.model_copy(update={"lastError": message, "lastVerifiedAt": now_iso()}))

    def _finalize_feishu_user_binding(user_id: str, code: str) -> FeishuUserBindingRecord:
        settings = get_feishu_bot_settings()
        if not settings.appId.strip():
            raise HTTPException(status_code=400, detail="当前工作台还没有配置飞书 App ID。")
        try:
            app_secret = state.feishu_secret_store.get_api_key().strip()
        except Exception:
            app_secret = ""
        if not app_secret:
            raise HTTPException(status_code=400, detail="当前工作台还没有配置飞书 App Secret。")

        existing = get_feishu_user_binding(user_id)
        app_access_token, _ = fetch_app_access_token(app_id=settings.appId.strip(), app_secret=app_secret)
        token_payload = exchange_authorization_code(
            app_access_token=app_access_token,
            app_id=settings.appId.strip(),
            app_secret=app_secret,
            code=code.strip(),
        )
        user_access_token = str(token_payload.get("access_token") or "").strip()
        user_info = fetch_user_info(user_access_token=user_access_token)
        binding = save_feishu_user_binding(
            FeishuUserBindingRecord(
                linked=True,
                readyForAuthorization=True,
                appId=settings.appId.strip(),
                userId=user_id,
                openId=str(user_info.get("open_id") or token_payload.get("open_id") or "").strip() or None,
                unionId=str(user_info.get("union_id") or token_payload.get("union_id") or "").strip() or None,
                feishuUserId=str(user_info.get("user_id") or token_payload.get("user_id") or "").strip() or None,
                name=str(user_info.get("name") or "").strip() or None,
                enName=str(user_info.get("en_name") or "").strip() or None,
                avatarUrl=str(user_info.get("avatar_url") or "").strip() or None,
                email=str(user_info.get("email") or "").strip() or None,
                tenantKey=str(user_info.get("tenant_key") or token_payload.get("tenant_key") or "").strip() or None,
                boundAt=existing.boundAt or now_iso(),
                lastVerifiedAt=now_iso(),
                lastError=None,
            )
        )
        if not binding.openId:
            _save_feishu_user_binding_error(user_id, "飞书没有返回 open_id，无法完成绑定。")
            raise HTTPException(status_code=400, detail="飞书没有返回 open_id，当前无法把软件账号和飞书账号关联起来。")
        log_activity("feishu.user_binding.success", "settings", user_id, {"openId": binding.openId, "email": binding.email})
        return binding

    def _clear_feishu_cloud_relay_session(user_id: str) -> None:
        pending = get_feishu_user_binding_pending(user_id)
        if pending and pending.get("state"):
            clear_feishu_oauth_state(str(pending.get("state")))
        if not pending or pending.get("mode") != "cloud_relay" or not pending.get("state"):
            clear_feishu_user_binding_pending(user_id)
            return
        try:
            cloud_request("DELETE", f"/api/v1/integrations/feishu/user-binding/sessions/{pending['state']}")
        except HTTPException:
            pass
        clear_feishu_user_binding_pending(user_id)

    def sync_feishu_user_binding_from_cloud_relay(user_id: str) -> FeishuUserBindingRecord | None:
        pending = get_feishu_user_binding_pending(user_id)
        if not pending or pending.get("mode") != "cloud_relay":
            return None
        state_token = (pending.get("state") or "").strip()
        if not state_token:
            clear_feishu_user_binding_pending(user_id)
            return None
        expires_at = (pending.get("expiresAt") or "").strip()
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) <= datetime.now():
                    clear_feishu_oauth_state(state_token)
                    _clear_feishu_cloud_relay_session(user_id)
                    return _save_feishu_user_binding_error(user_id, "这次飞书扫码授权请求已经过期，请重新发起绑定。")
            except ValueError:
                clear_feishu_oauth_state(state_token)
                _clear_feishu_cloud_relay_session(user_id)
                return _save_feishu_user_binding_error(user_id, "飞书扫码授权状态已损坏，请重新发起绑定。")
        try:
            payload = cloud_request("GET", f"/api/v1/integrations/feishu/user-binding/sessions/{state_token}")
        except HTTPException as exc:
            if exc.status_code == 404:
                clear_feishu_oauth_state(state_token)
                _clear_feishu_cloud_relay_session(user_id)
                return None
            raise
        if not isinstance(payload, dict):
            return None
        status = str(payload.get("status") or "").strip()
        if status in {"", "pending"}:
            return None
        if status == "expired":
            clear_feishu_oauth_state(state_token)
            _clear_feishu_cloud_relay_session(user_id)
            return _save_feishu_user_binding_error(user_id, "这次飞书扫码授权请求已经过期，请重新发起绑定。")
        if status == "error":
            clear_feishu_oauth_state(state_token)
            _clear_feishu_cloud_relay_session(user_id)
            return _save_feishu_user_binding_error(user_id, str(payload.get("errorMessage") or "飞书扫码授权失败，请重新发起绑定。"))
        code = str(payload.get("code") or "").strip()
        if status != "authorized" or not code:
            return None
        try:
            binding = _finalize_feishu_user_binding(user_id, code)
        except FeishuApiError as exc:
            clear_feishu_oauth_state(state_token)
            _clear_feishu_cloud_relay_session(user_id)
            return _save_feishu_user_binding_error(user_id, str(exc))
        except HTTPException as exc:
            clear_feishu_oauth_state(state_token)
            _clear_feishu_cloud_relay_session(user_id)
            return _save_feishu_user_binding_error(user_id, str(exc.detail))
        clear_feishu_oauth_state(state_token)
        _clear_feishu_cloud_relay_session(user_id)
        return binding

    def _render_feishu_binding_callback_page(title: str, detail: str, *, success: bool) -> HTMLResponse:
        tone = "#16a34a" if success else "#dc2626"
        escaped_title = html.escape(title)
        escaped_detail = html.escape(detail)
        markup = f"""<!doctype html>
<html lang=\"zh-CN\">
  <head>
    <meta charset=\"utf-8\" />
    <title>{escaped_title}</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 32px; }}
      .card {{ max-width: 560px; margin: 8vh auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 24px; padding: 28px; box-shadow: 0 16px 48px rgba(15, 23, 42, 0.08); }}
      .badge {{ display: inline-flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 700; color: {tone}; background: rgba(91, 123, 254, 0.08); border-radius: 999px; padding: 6px 12px; }}
      h1 {{ font-size: 24px; line-height: 1.3; margin: 18px 0 12px; }}
      p {{ font-size: 14px; line-height: 1.75; color: #475569; margin: 0 0 12px; white-space: pre-wrap; }}
    </style>
  </head>
  <body>
    <div class=\"card\">
      <div class=\"badge\">{"绑定成功" if success else "绑定失败"}</div>
      <h1>{escaped_title}</h1>
      <p>{escaped_detail}</p>
      <p>现在可以回到益语智库自用平台继续操作；如果桌面端仍显示旧状态，点击一次“刷新绑定状态”。</p>
    </div>
  </body>
</html>"""
        return HTMLResponse(markup)

    def _default_feishu_test_message(bot_name: str) -> str:
        return f"{bot_name.strip() or '罗茜茜'} 已接通成功，现在可以给你发消息了。"

    def _default_feishu_inbound_reply(bot_name: str) -> str:
        resolved_name = bot_name.strip() or "罗茜茜"
        return f"我是{resolved_name}。飞书入站链路刚接通，现在先支持固定回复；客户上下文问答还没接上。"

    def update_feishu_bot_settings(payload: FeishuBotSettingsPayload) -> FeishuBotSettingsRecord:
        current = get_feishu_bot_settings()
        next_payload = current.model_dump()
        if payload.appId is not None:
            next_payload["appId"] = payload.appId.strip()
        if payload.receiveIdType is not None:
            next_payload["receiveIdType"] = payload.receiveIdType
        if payload.receiverId is not None:
            next_payload["receiverId"] = payload.receiverId.strip()
        if payload.botName is not None:
            next_payload["botName"] = payload.botName.strip() or "罗茜茜"

        if payload.userBindingCallbackUrl is not None:
            next_payload["userBindingCallbackUrl"] = _normalize_feishu_user_binding_callback_url(payload.userBindingCallbackUrl)

        next_record = FeishuBotSettingsRecord(**next_payload)

        try:
            if payload.clearAppSecret:
                state.feishu_secret_store.delete_api_key()
            elif payload.appSecret and payload.appSecret.strip():
                state.feishu_secret_store.set_api_key(payload.appSecret.strip())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"飞书密钥保存失败：{exc}") from exc

        if payload.sendTestMessage:
            app_id = next_record.appId.strip()
            receiver_id = next_record.receiverId.strip()
            bot_name = next_record.botName.strip() or "罗茜茜"
            app_secret = state.feishu_secret_store.get_api_key().strip()
            attempted_at = now_iso()
            if not app_id:
                next_record = next_record.model_copy(
                    update={
                        "lastConnectionStatus": "failed",
                        "lastConnectionMessage": "请先填写飞书 App ID。",
                        "lastConnectedAt": attempted_at,
                    }
                )
            elif not receiver_id:
                next_record = next_record.model_copy(
                    update={
                        "lastConnectionStatus": "failed",
                        "lastConnectionMessage": "请先填写接收方标识。",
                        "lastConnectedAt": attempted_at,
                    }
                )
            elif not app_secret:
                next_record = next_record.model_copy(
                    update={
                        "lastConnectionStatus": "failed",
                        "lastConnectionMessage": "请先保存飞书 App Secret。",
                        "lastConnectedAt": attempted_at,
                    }
                )
            else:
                try:
                    tenant_access_token, _ = fetch_tenant_access_token(app_id=app_id, app_secret=app_secret)
                    send_text_message(
                        tenant_access_token=tenant_access_token,
                        receive_id_type=next_record.receiveIdType,
                        receive_id=receiver_id,
                        text=(payload.testMessage or _default_feishu_test_message(bot_name)).strip() or _default_feishu_test_message(bot_name),
                    )
                    next_record = next_record.model_copy(
                        update={
                            "lastConnectionStatus": "success",
                            "lastConnectionMessage": f"{bot_name} 已经发出测试消息。",
                            "lastConnectedAt": attempted_at,
                            "lastTestMessageAt": attempted_at,
                        }
                    )
                except FeishuApiError as exc:
                    next_record = next_record.model_copy(
                        update={
                            "lastConnectionStatus": "failed",
                            "lastConnectionMessage": str(exc),
                            "lastConnectedAt": attempted_at,
                        }
                    )

        saved = _persist_feishu_bot_settings(next_record)
        log_activity("settings.feishu_bot.update", "settings", "feishu_bot", payload.model_dump(exclude_none=True, exclude={"appSecret"}))
        return saved

    def _parse_feishu_text_content(message_payload: dict[str, object]) -> str:
        content = message_payload.get("content")
        if isinstance(content, dict):
            return str(content.get("text") or "").strip()
        if not isinstance(content, str):
            return ""
        try:
            parsed = json.loads(content)
        except ValueError:
            return content.strip()
        if isinstance(parsed, dict):
            return str(parsed.get("text") or "").strip()
        return content.strip()

    def _send_feishu_text_message(receive_id_type: FeishuReceiveIdType, receive_id: str, text: str) -> None:
        settings = get_feishu_bot_settings()
        if not settings.appId.strip():
            raise FeishuApiError("飞书 App ID 未配置。")
        app_secret = state.feishu_secret_store.get_api_key().strip()
        if not app_secret:
            raise FeishuApiError("飞书 App Secret 未配置。")
        tenant_access_token, _ = fetch_tenant_access_token(app_id=settings.appId, app_secret=app_secret)
        send_text_message(
            tenant_access_token=tenant_access_token,
            receive_id_type=receive_id_type,
            receive_id=receive_id,
            text=text,
        )

    def _send_feishu_chat_text(chat_id: str, text: str) -> None:
        _send_feishu_text_message("chat_id", chat_id, text)

    def _resolve_feishu_meeting_delivery() -> tuple[Literal["bound_user", "configured_receiver", "none"], FeishuReceiveIdType | None, str | None, str | None]:
        session_user = get_cached_session_user()
        if session_user:
            binding = get_feishu_user_binding(session_user.id)
            if binding.linked and binding.openId:
                target_label = binding.name or binding.email or binding.openId
                return "bound_user", "open_id", binding.openId, target_label
        settings = get_feishu_bot_settings()
        app_secret = ""
        try:
            app_secret = state.feishu_secret_store.get_api_key().strip()
        except Exception:
            app_secret = ""
        if settings.appId.strip() and settings.receiverId.strip() and app_secret:
            return "configured_receiver", settings.receiveIdType, settings.receiverId.strip(), settings.receiverId.strip()
        return "none", None, None, None

    def _populate_meeting_extraction(meeting_id: str, text: str) -> tuple[int, int, int, int]:
        agenda, decisions, actions, risks, ambiguities = extract_meeting_content(text)
        state.db.execute("DELETE FROM agenda_items WHERE meeting_id = ?", (meeting_id,))
        state.db.execute("DELETE FROM decisions WHERE meeting_id = ?", (meeting_id,))
        state.db.execute("DELETE FROM action_items WHERE meeting_id = ?", (meeting_id,))
        state.db.execute("DELETE FROM risks WHERE meeting_id = ?", (meeting_id,))
        state.db.execute("DELETE FROM ambiguities WHERE meeting_id = ?", (meeting_id,))
        for index, item in enumerate(agenda):
            state.db.execute("INSERT INTO agenda_items(id, meeting_id, title, description, sort_order) VALUES(?, ?, ?, ?, ?)", (new_id("agenda"), meeting_id, item[:28], "抽取后的议程点", index))
        for item in decisions:
            state.db.execute("INSERT INTO decisions(id, meeting_id, summary, created_at) VALUES(?, ?, ?, ?)", (new_id("dec"), meeting_id, item[:120], now_iso()))
        for item, owner, confidence in actions:
            state.db.execute(
                "INSERT INTO action_items(id, meeting_id, title, owner_name, due_date, confidence, publish_status, created_at) VALUES(?, ?, ?, ?, ?, ?, 'draft', ?)",
                (new_id("act"), meeting_id, item[:120], owner, "本周", confidence, now_iso()),
            )
        for item, severity in risks:
            state.db.execute("INSERT INTO risks(id, meeting_id, summary, severity, created_at) VALUES(?, ?, ?, ?, ?)", (new_id("risk"), meeting_id, item[:120], severity, now_iso()))
        for item, candidates in ambiguities:
            state.db.execute(
                "INSERT INTO ambiguities(id, meeting_id, raw_text, candidates_json, status, created_at) VALUES(?, ?, ?, ?, 'pending', ?)",
                (new_id("amb"), meeting_id, item[:120], to_json(candidates), now_iso()),
            )
        return len(decisions), len(actions), len(risks), len(ambiguities)

    def _ingest_feishu_minutes_writeback(meeting_id: str, notes_text: str) -> MeetingDetail:
        state.db.execute(
            "UPDATE meetings SET transcript_text = ?, notes = ?, stage = 'ingested', updated_at = ? WHERE id = ?",
            (notes_text, notes_text, now_iso(), meeting_id),
        )
        state.db.execute("DELETE FROM meeting_sources WHERE meeting_id = ?", (meeting_id,))
        state.db.execute(
            "INSERT INTO meeting_sources(id, meeting_id, title, content_text, created_at) VALUES(?, ?, ?, ?, ?)",
            (new_id("ms"), meeting_id, "飞书纪要回写", notes_text, now_iso()),
        )
        decision_count, action_count, risk_count, ambiguity_count = _populate_meeting_extraction(meeting_id, notes_text)
        state.db.execute("UPDATE meetings SET stage = 'extracted', updated_at = ? WHERE id = ?", (now_iso(), meeting_id))
        log_activity(
            "feishu.meeting.writeback",
            "meeting",
            meeting_id,
            {
                "decisions": decision_count,
                "actions": action_count,
                "risks": risk_count,
                "ambiguities": ambiguity_count,
            },
        )
        return build_meeting_detail(meeting_id)

    def handle_feishu_event(payload: dict[str, object]) -> dict[str, object]:
        challenge = payload.get("challenge")
        if isinstance(challenge, str) and challenge.strip():
            return {"challenge": challenge}

        header = payload.get("header")
        header_dict = header if isinstance(header, dict) else {}
        event_type = str(header_dict.get("event_type") or payload.get("type") or "")
        event = payload.get("event")
        event_dict = event if isinstance(event, dict) else {}
        sender = event_dict.get("sender")
        sender_dict = sender if isinstance(sender, dict) else {}
        if str(sender_dict.get("sender_type") or "").strip().lower() == "app":
            return {"ok": True, "ignored": "self_message"}

        message = event_dict.get("message")
        message_dict = message if isinstance(message, dict) else {}
        chat_id = str(message_dict.get("chat_id") or "").strip()
        message_type = str(message_dict.get("message_type") or "").strip()
        message_text = _parse_feishu_text_content(message_dict)
        if event_type != "im.message.receive_v1":
            return {"ok": True, "ignored": f"unsupported_event:{event_type or 'unknown'}"}
        if message_type != "text":
            return {"ok": True, "ignored": f"unsupported_message_type:{message_type or 'unknown'}"}
        if not chat_id:
            return {"ok": True, "ignored": "missing_chat_id"}

        stripped_text = message_text.strip()
        if stripped_text.startswith("纪要回写") or stripped_text.startswith("会议纪要回写"):
            first_line, _, remainder = stripped_text.partition("\n")
            parts = first_line.split(maxsplit=1)
            if len(parts) < 2:
                try:
                    _send_feishu_chat_text(chat_id, "请按“纪要回写 meeting_xxx\\n纪要内容”发送会议纪要。")
                except FeishuApiError:
                    pass
                return {"ok": False, "error": "missing_meeting_id"}
            meeting_id = parts[1].strip()
            notes_body = remainder.strip()
            meeting_row = state.db.fetchone("SELECT id FROM meetings WHERE id = ?", (meeting_id,))
            if not meeting_row:
                try:
                    _send_feishu_chat_text(chat_id, f"没有找到会议 {meeting_id}，请确认编号后重试。")
                except FeishuApiError:
                    pass
                return {"ok": False, "error": "meeting_not_found"}
            if not notes_body:
                try:
                    _send_feishu_chat_text(chat_id, "纪要内容为空，请在第二行开始粘贴纪要正文。")
                except FeishuApiError:
                    pass
                return {"ok": False, "error": "empty_notes"}
            meeting = _ingest_feishu_minutes_writeback(meeting_id, notes_body)
            try:
                _send_feishu_chat_text(
                    chat_id,
                    f"已回写《{meeting.title}》的会议纪要，并完成结构化抽取。当前识别到 {len(meeting.actionItems)} 条行动项、{len(meeting.decisions)} 条结论。",
                )
            except FeishuApiError:
                pass
            return {"ok": True, "mode": "meeting_writeback", "meetingId": meeting_id}

        try:
            settings = get_feishu_bot_settings()
            if not settings.appId.strip():
                return {"ok": True, "ignored": "missing_app_id"}
            app_secret = state.feishu_secret_store.get_api_key().strip()
            if not app_secret:
                return {"ok": True, "ignored": "missing_app_secret"}
            _send_feishu_chat_text(chat_id, _default_feishu_inbound_reply(settings.botName))
            state.db.set_setting("settings.feishu_last_event_at", now_iso())
            log_activity("feishu.inbound.reply", "channel", chat_id, {"eventType": event_type, "messageType": message_type})
            return {"ok": True}
        except FeishuApiError as exc:
            log_activity("feishu.inbound.reply_failed", "channel", chat_id, {"eventType": event_type, "error": str(exc)})
            return {"ok": False, "error": str(exc)}

    def ensure_business_settings_editable() -> None:
        session_user = get_cached_session_user()
        if not session_user:
            return
        if session_user.primaryRole == "admin":
            return
        admin_settings = get_system_admin_settings()
        if not admin_settings.allowBusinessSettingsForEmployees:
            raise HTTPException(status_code=403, detail="当前账号不能编辑业务设置")

    def ensure_org_dna_editable() -> None:
        session_user = get_cached_session_user()
        if not session_user:
            return
        if session_user.primaryRole == "admin":
            return
        admin_settings = get_system_admin_settings()
        if not admin_settings.allowOrgDnaForEmployees:
            raise HTTPException(status_code=403, detail="当前账号不能编辑组织 DNA")

    def ensure_admin_for_sensitive_settings() -> None:
        session_user = get_cached_session_user()
        if not session_user:
            return
        if session_user.primaryRole != "admin":
            raise HTTPException(status_code=403, detail="只有管理员可以编辑该设置")

    def _organization_dna_record(module_key: str, module_title: str, row=None) -> OrganizationDnaModuleRecord:
        return OrganizationDnaModuleRecord(
            moduleKey=module_key,  # type: ignore[arg-type]
            title=module_title,
            markdownContent=str(row["markdown_content"]) if row else "",
            normalizedText=str(row["normalized_text"]) if row else "",
            summary=str(row["summary"]) if row else "",
            fileName=str(row["file_name"]) if row else None,
            contentHash=str(row["content_hash"]) if row else None,
            updatedAt=str(row["updated_at"]) if row else None,
            updatedBy=str(row["updated_by"]) if row else None,
            hasDocument=bool(row),
        )

    def _find_self_client_row():
        for candidate in SELF_CLIENT_NAME_CANDIDATES:
            row = state.db.fetchone(
                """
                SELECT *
                FROM clients
                WHERE name = ? OR alias = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (candidate, candidate),
            )
            if row:
                return row
        return None

    def _extract_readiness_evidence(text: str, keywords: list[str]) -> str | None:
        normalized_text = re.sub(r"\s+", " ", text).strip()
        if not normalized_text:
            return None
        for keyword in keywords:
            if not keyword:
                continue
            hit_index = normalized_text.find(keyword)
            if hit_index < 0:
                continue
            start = max(0, hit_index - 24)
            end = min(len(normalized_text), hit_index + 40)
            snippet = normalized_text[start:end].strip()
            if not snippet:
                continue
            if start > 0:
                snippet = f"…{snippet}"
            if end < len(normalized_text):
                snippet = f"{snippet}…"
            return snippet
        return None

    def _build_dna_readiness_questions(
        module_key: str,
        normalized_text: str,
        missing_info: list[str],
    ) -> list[DnaReadinessQuestionRecord]:
        rules = DNA_READINESS_RULES.get(module_key, [])
        if not rules:
            return []
        questions: list[DnaReadinessQuestionRecord] = []
        compact_text = normalized_text or ""
        for rule in rules:
            content_keywords = [str(item) for item in (rule.get("contentKeywords") or [])]
            missing_keywords = [str(item) for item in (rule.get("missingKeywords") or [])]
            has_content = any(keyword and keyword in compact_text for keyword in content_keywords)
            blocked = any(
                keyword and keyword in str(item)
                for item in missing_info
                for keyword in missing_keywords
            )
            answered = bool(has_content and not blocked)
            evidence = _extract_readiness_evidence(compact_text, content_keywords) if answered else None
            questions.append(
                DnaReadinessQuestionRecord(
                    question=str(rule.get("question") or ""),
                    answered=answered,
                    evidence=evidence,
                )
            )
        return questions

    def _build_organization_dna_readiness(
        base_module: OrganizationDnaModuleRecord,
        *,
        client_module=None,
        auto_enqueued: bool = False,
    ) -> OrganizationDnaModuleRecord:
        preferred_text = ""
        missing_info: list[str] = []
        readiness_source: str = "none"
        if client_module and client_module.hasDocument and client_module.normalizedText.strip():
            preferred_text = client_module.normalizedText
            missing_info = list(client_module.missingInfo or [])
            readiness_source = "client_dna"
        elif base_module.hasDocument and base_module.normalizedText.strip():
            preferred_text = base_module.normalizedText
            missing_info = extract_markdown_missing_info(base_module.markdownContent)
            readiness_source = "manual_document"
        elif auto_enqueued:
            readiness_source = "auto_enqueued"

        questions = _build_dna_readiness_questions(base_module.moduleKey, preferred_text, missing_info)
        answered_count = sum(1 for item in questions if item.answered)
        question_count = len(questions)
        readiness_status: Literal["ready", "missing"] = "missing"
        if question_count > 0 and answered_count >= (2 if question_count >= 3 else question_count):
            readiness_status = "ready"
        elif question_count == 0 and preferred_text.strip():
            readiness_status = "ready"

        if readiness_source == "client_dna":
            readiness_summary = f"优先采用客户 DNA，自动判定 {answered_count}/{question_count or 0} 项明确。"
        elif readiness_source == "manual_document":
            readiness_summary = f"当前采用手工上传文档，自动判定 {answered_count}/{question_count or 0} 项明确。"
        elif readiness_source == "auto_enqueued":
            readiness_summary = "客户 DNA 仍缺失，系统已自动发起补跑。"
        else:
            readiness_summary = "当前还没有客户 DNA，也没有补充文档。"

        return base_module.model_copy(
            update={
                "readinessStatus": readiness_status,
                "readinessAnsweredCount": answered_count,
                "readinessQuestionCount": question_count,
                "readinessSource": readiness_source,
                "readinessSummary": readiness_summary,
                "readinessQuestions": questions,
            }
        )

    def list_organization_dna_modules() -> list[OrganizationDnaModuleRecord]:
        records_by_key = {
            str(row["module_key"]): row
            for row in state.db.fetchall("SELECT * FROM organization_dna_documents")
        }
        base_modules = {
            module_key: _organization_dna_record(module_key, module_title, records_by_key.get(module_key))
            for module_key, module_title in ORGANIZATION_DNA_MODULES
        }
        self_client_row = _find_self_client_row()
        client_modules_by_key = {}
        auto_enqueued_keys: set[str] = set()
        if self_client_row:
            client_id = str(self_client_row["id"])
            client_modules = list_client_dna_modules(client_id)
            client_modules_by_key = {module.moduleKey: module for module in client_modules}
            required_keys = {"organization_intro", "business_intro", "team_intro"}
            missing_client_keys = {
                module_key
                for module_key in required_keys
                if not (
                    client_modules_by_key.get(module_key)
                    and client_modules_by_key[module_key].hasDocument
                    and client_modules_by_key[module_key].normalizedText.strip()
                )
            }
            if missing_client_keys:
                job = maybe_enqueue_client_dna_generation_job(client_id)
                if job is not None:
                    auto_enqueued_keys = set(missing_client_keys)

        return [
            _build_organization_dna_readiness(
                base_modules[module_key],
                client_module=client_modules_by_key.get(module_key),
                auto_enqueued=module_key in auto_enqueued_keys,
            )
            for module_key, _module_title in ORGANIZATION_DNA_MODULES
        ]

    def _is_supported_org_dna_file_name(file_name: str) -> bool:
        lower_name = file_name.strip().lower()
        return lower_name.endswith(".md") or lower_name.endswith(".markdown") or lower_name.endswith(".docx")

    def _sanitize_text_list(values: list[str] | None) -> list[str]:
        if not values:
            return []
        cleaned: list[str] = []
        for value in values:
            text = re.sub(r"\s+", " ", str(value or "")).strip()
            if not text or text in cleaned:
                continue
            cleaned.append(text)
        return cleaned

    def read_organization_document_payload(payload: OrganizationDnaUploadPayload) -> tuple[str, str]:
        document_content = (payload.markdownContent or "").strip()
        file_name = (payload.fileName or "").strip()
        if payload.filePath:
            source_path = Path(payload.filePath).expanduser()
            if not source_path.exists() or not source_path.is_file():
                raise HTTPException(status_code=400, detail="背景文件不存在")
            if not _is_supported_org_dna_file_name(source_path.name):
                raise HTTPException(status_code=400, detail="只允许上传 .md、.markdown 或 .docx 文件")
            if source_path.suffix.lower() == ".docx":
                document_content = extract_platform_dna_text(source_path).strip()
            else:
                document_content = source_path.read_text(encoding="utf-8")
            file_name = file_name or source_path.name
        if file_name and not _is_supported_org_dna_file_name(file_name):
            raise HTTPException(status_code=400, detail="只允许上传 .md、.markdown 或 .docx 文件")
        if not document_content.strip():
            raise HTTPException(status_code=400, detail="请提供可解析的背景内容")
        return document_content, file_name or "uploaded.md"

    def upsert_organization_dna_module(module_key: str, payload: OrganizationDnaUploadPayload) -> OrganizationDnaModuleRecord:
        module_map = dict(ORGANIZATION_DNA_MODULES)
        if module_key not in module_map:
            raise HTTPException(status_code=404, detail="未知的组织 DNA 模块")
        markdown_content, file_name = read_organization_document_payload(payload)
        normalized_text = normalize_markdown_text(markdown_content)
        summary = summarize_markdown_document(module_map[module_key], normalized_text)
        content_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()
        session_user = get_cached_session_user()
        updated_by = session_user.fullName if session_user else str(current_operator_row()["name"])
        timestamp = now_iso()
        state.db.execute(
            """
            INSERT INTO organization_dna_documents(
                module_key, title, markdown_content, normalized_text, summary, file_name, content_hash, updated_at, updated_by
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(module_key) DO UPDATE SET
                title = excluded.title,
                markdown_content = excluded.markdown_content,
                normalized_text = excluded.normalized_text,
                summary = excluded.summary,
                file_name = excluded.file_name,
                content_hash = excluded.content_hash,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (module_key, module_map[module_key], markdown_content, normalized_text, summary, file_name, content_hash, timestamp, updated_by),
        )
        row = state.db.fetchone("SELECT * FROM organization_dna_documents WHERE module_key = ?", (module_key,))
        if not row:
            raise HTTPException(status_code=500, detail="组织 DNA 保存失败")
        return _organization_dna_record(module_key, module_map[module_key], row)

    def build_organization_dna_context(max_chars: int = 2800) -> str:
        modules = [module for module in list_organization_dna_modules() if module.hasDocument and module.normalizedText.strip()]
        if not modules:
            return ""
        lines = ["组织 DNA：以下内容代表本组织的稳定背景、业务语境和市场定位。"]
        for module in modules:
            lines.append(f"[{module.title}]\n{module.normalizedText[:700]}")
        return "\n\n".join(lines)[:max_chars]

    def _client_dna_record(client_id: str, module_key: str, module_title: str, row=None) -> ClientDnaModuleRecord:
        return ClientDnaModuleRecord(
            clientId=client_id,
            moduleKey=module_key,  # type: ignore[arg-type]
            title=module_title,
            markdownContent=str(row["markdown_content"]) if row else "",
            normalizedText=str(row["normalized_text"]) if row else "",
            summary=str(row["summary"]) if row else "",
            fileName=str(row["file_name"]) if row else None,
            contentHash=str(row["content_hash"]) if row else None,
            sourceKind=str(row["source_kind"]) if row and row["source_kind"] else "manual",  # type: ignore[arg-type]
            missingInfo=_parse_json_list(row["missing_info_json"]) if row else [],
            updatedAt=str(row["updated_at"]) if row else None,
            updatedBy=str(row["updated_by"]) if row else None,
            hasDocument=bool(row),
        )

    def extract_markdown_missing_info(markdown_content: str) -> list[str]:
        sections = re.split(r"^#{1,6}\s+", markdown_content, flags=re.MULTILINE)
        target_section = ""
        for section in sections:
            stripped = section.strip()
            if not stripped:
                continue
            if stripped.startswith("缺失信息"):
                target_section = stripped[len("缺失信息"):].strip()
                break
        if not target_section:
            return []
        lines = []
        for raw_line in target_section.splitlines():
            line = re.sub(r"^\s*[-*•\d.]+\s*", "", raw_line).strip()
            if not line:
                continue
            if line.lower().startswith("暂无"):
                continue
            lines.append(line)
        return _sanitize_text_list(lines)

    def save_client_dna_module(
        client_id: str,
        module_key: str,
        *,
        markdown_content: str,
        file_name: str,
        source_kind: Literal["manual", "generated"],
        updated_by: str,
        missing_info: list[str] | None = None,
    ) -> ClientDnaModuleRecord:
        module_map = dict(CLIENT_DNA_MODULES)
        if module_key not in module_map:
            raise HTTPException(status_code=404, detail="未知的客户 DNA 模块")
        normalized_text = normalize_markdown_text(markdown_content)
        summary = summarize_markdown_document(module_map[module_key], normalized_text)
        content_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()
        timestamp = now_iso()
        final_missing_info = _sanitize_text_list(missing_info if missing_info is not None else extract_markdown_missing_info(markdown_content))
        state.db.execute(
            """
            INSERT INTO client_dna_documents(
                client_id, module_key, title, markdown_content, normalized_text, summary, file_name, content_hash,
                source_kind, missing_info_json, updated_at, updated_by
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id, module_key) DO UPDATE SET
                title = excluded.title,
                markdown_content = excluded.markdown_content,
                normalized_text = excluded.normalized_text,
                summary = excluded.summary,
                file_name = excluded.file_name,
                content_hash = excluded.content_hash,
                source_kind = excluded.source_kind,
                missing_info_json = excluded.missing_info_json,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (
                client_id,
                module_key,
                module_map[module_key],
                markdown_content,
                normalized_text,
                summary,
                file_name,
                content_hash,
                source_kind,
                to_json(final_missing_info),
                timestamp,
                updated_by,
            ),
        )
        record_client_dna_writeback(
            state.db,
            client_id=client_id,
            module_key=module_key,
            summary=summary,
            file_name=file_name,
            source_kind=source_kind,
            missing_info=final_missing_info,
        )
        row = state.db.fetchone(
            "SELECT * FROM client_dna_documents WHERE client_id = ? AND module_key = ?",
            (client_id, module_key),
        )
        if not row:
            raise HTTPException(status_code=500, detail="客户 DNA 保存失败")
        return _client_dna_record(client_id, module_key, module_map[module_key], row)

    def list_client_dna_modules(client_id: str) -> list[ClientDnaModuleRecord]:
        records_by_key = {
            str(row["module_key"]): row
            for row in state.db.fetchall(
                "SELECT * FROM client_dna_documents WHERE client_id = ?",
                (client_id,),
            )
        }
        return [
            _client_dna_record(client_id, module_key, module_title, records_by_key.get(module_key))
            for module_key, module_title in CLIENT_DNA_MODULES
        ]

    def upsert_client_dna_module(client_id: str, module_key: str, payload: OrganizationDnaUploadPayload) -> ClientDnaModuleRecord:
        build_client_summary(client_id)
        markdown_content, file_name = read_organization_document_payload(payload)
        session_user = get_cached_session_user()
        updated_by = session_user.fullName if session_user else str(current_operator_row()["name"])
        return save_client_dna_module(
            client_id,
            module_key,
            markdown_content=markdown_content,
            file_name=file_name,
            source_kind="manual",
            updated_by=updated_by,
        )

    def select_client_dna_generation_cards(client_id: str, module_key: str, *, limit: int = 8) -> list[DocumentCardRecord]:
        cards = [
            build_document_card_record(item)
            for item in fetch_document_cards(state.db, client_id, data_dir=state.data_dir, limit=32)
        ]
        if not cards:
            return []
        keyword_map: dict[str, list[str]] = {
            "organization_intro": ["组织", "机构", "公司", "使命", "历史", "定位", "介绍", "战略"],
            "business_intro": ["项目", "业务", "服务", "合作", "方案", "交付", "执行", "陪伴"],
            "team_intro": ["团队", "成员", "负责人", "岗位", "组织架构", "分工", "协作", "接口"],
            "market_intro": ["市场", "行业", "竞品", "需求", "用户", "趋势", "研究", "环境"],
        }
        keywords = keyword_map.get(module_key, [])
        if not keywords:
            return cards[:limit]

        def score(card: DocumentCardRecord) -> int:
            haystack = " ".join(
                [
                    card.title,
                    card.summary,
                    card.shortSummary,
                    card.logicalCategory or "",
                    card.logicalSubcategory or "",
                    " ".join(card.keywords),
                    " ".join(card.tags),
                    " ".join(card.entities),
                ]
            )
            total = 0
            for keyword in keywords:
                if keyword and keyword in haystack:
                    total += 1
            if card.needsReview:
                total -= 1
            return total

        prioritized = sorted(cards, key=lambda item: (score(item), item.classificationConfidence), reverse=True)
        selected = [item for item in prioritized if score(item) > 0][:limit]
        return selected or prioritized[:limit]

    def build_client_dna_candidate_markdown(client_id: str, module_key: str) -> tuple[str, list[str]]:
        module_map = dict(CLIENT_DNA_MODULES)
        module_title = module_map[module_key]
        client = build_client_summary(client_id)
        cards = select_client_dna_generation_cards(client_id, module_key)
        if not cards:
            raise RuntimeError("还没有可用于生成候选文档的资料，请先导入原始资料。")
        source_lines = []
        for index, card in enumerate(cards[:8], start=1):
            source_lines.append(
                "\n".join(
                    [
                        f"[资料 {index}] {card.title}",
                        f"分类：{card.logicalCategory or card.primaryCategory} / {card.logicalSubcategory or card.secondaryCategory}",
                        f"摘要：{card.summary or card.shortSummary}",
                        f"关键词：{'、'.join(card.keywords[:8]) if card.keywords else '无'}",
                        f"补充发现：{'；'.join(card.distinctFindings[:3]) if card.distinctFindings else '无'}",
                    ]
                )
            )
        prompt = (
            f"请基于下面资料，为项目《{client.name}》生成《{module_title}》候选 Markdown。\n"
            "输出约束：\n"
            "1. judgment 字段写“执行摘要”，100-200 字。\n"
            "2. content 字段只写 Markdown 正文，不要再包代码块。\n"
            "3. analysis 字段只写缺失信息，每行一条，不要编号解释。\n"
            "4. actions 字段写本次候选文档主要依据的资料标题，每行一条。\n"
            "5. timeline 字段写一句简短提醒，说明当前候选文档是否还需要继续补资料。\n"
            "6. 不要编造资料里没有的事实，信息不足就写进缺失信息。\n\n"
            f"资料摘录：\n{chr(10).join(source_lines)}"
        )
        system_instruction = (
            "你是企业项目资料整理助手。你的任务不是写宣传文案，而是基于已有资料，生成可被任务、日历、学习和问答系统稳定引用的项目背景候选稿。"
        )
        try:
            structured = state.ai.generate_structured(prompt, system_instruction, "")
            summary_text = re.sub(r"\s+", " ", str(structured.judgment or "")).strip() or f"{client.name} 的{module_title}候选摘要待补。"
            body_markdown = str(structured.content or "").strip() or f"## 1. 待补内容\n\n当前资料还不足以稳定生成《{module_title}》正文，建议继续补原始资料后重扫。"
            missing_items = _sanitize_text_list([line for line in str(structured.analysis or "").splitlines()])
            if not missing_items:
                missing_items = ["如果你发现内容仍偏空，请继续补充原始资料后重新扫描。"]
        except AiInvocationError:
            summary_sources = "；".join(
                _strategic_unique_non_empty([
                    (card.summary or card.shortSummary or "").strip()
                    for card in cards[:3]
                ])
            )
            summary_text = (
                summary_sources[:180]
                if summary_sources
                else f"{client.name} 的{module_title}候选摘要暂时回退为资料拼接稿，建议后续重试 AI 生成。"
            )
            fallback_sections: list[str] = []
            for index, card in enumerate(cards[:4], start=1):
                card_summary = (card.summary or card.shortSummary or "").strip() or "当前仅保留原始资料标题，摘要仍待补齐。"
                findings = "；".join(card.distinctFindings[:3]) if card.distinctFindings else ""
                hints = "；".join(card.coreQuestions[:2]) if card.coreQuestions else ""
                section_lines = [
                    f"## {index}. {card.title}",
                    "",
                    card_summary,
                ]
                if findings:
                    section_lines.extend(["", f"补充发现：{findings}"])
                if hints:
                    section_lines.extend(["", f"后续建议补问：{hints}"])
                fallback_sections.append("\n".join(section_lines))
            body_markdown = "\n\n".join(fallback_sections) or f"## 1. 待补内容\n\n当前资料还不足以稳定生成《{module_title}》正文，建议继续补原始资料后重扫。"
            missing_items = [
                "本次候选稿因 AI 结构化超时，已降级为资料拼接稿。",
                "建议后续在资料更完整或服务恢复后重新生成候选文档。",
            ]
        missing_section = "\n".join(f"- {item}" for item in missing_items)
        markdown_content = (
            f"# 执行摘要\n\n{summary_text}\n\n"
            f"# 正文\n\n{body_markdown}\n\n"
            f"# 缺失信息\n\n{missing_section}\n"
        )
        return markdown_content, missing_items

    def resolve_client_dna_modules_for_generation(client_id: str, *, refresh_generated: bool = False) -> list[ClientDnaModuleRecord]:
        modules = list_client_dna_modules(client_id)
        candidates: list[ClientDnaModuleRecord] = []
        for module in modules:
            if not module.hasDocument:
                candidates.append(module)
                continue
            if refresh_generated and module.sourceKind == "generated":
                candidates.append(module)
        return candidates

    def maybe_enqueue_client_dna_generation_job(client_id: str, *, refresh_generated: bool = False) -> KnowledgeJobRecord | None:
        target_modules = resolve_client_dna_modules_for_generation(client_id, refresh_generated=refresh_generated)
        if not target_modules:
            return None
        pending = state.db.fetchone(
            """
            SELECT * FROM knowledge_jobs
            WHERE client_id = ? AND job_type = 'generate_client_dna_candidates' AND status IN ('queued', 'running')
            ORDER BY created_at DESC LIMIT 1
            """,
            (client_id,),
        )
        if pending:
            return KnowledgeJobRecord(
                id=str(pending["id"]),
                clientId=str(pending["client_id"]),
                jobType=str(pending["job_type"]),
                status=str(pending["status"]),  # type: ignore[arg-type]
                totalItems=int(pending["total_items"]),
                processedItems=int(pending["processed_items"]),
                lastError=str(pending["last_error"]) if pending["last_error"] else None,
                createdAt=str(pending["created_at"]),
                startedAt=str(pending["started_at"]) if pending["started_at"] else None,
                finishedAt=str(pending["finished_at"]) if pending["finished_at"] else None,
                updatedAt=str(pending["updated_at"]),
            )
        return enqueue_knowledge_job(
            client_id,
            "generate_client_dna_candidates",
            {
                "clientId": client_id,
                "moduleKeys": [module.moduleKey for module in target_modules],
                "refreshGenerated": refresh_generated,
            },
            total_items=len(target_modules),
        )

    def _project_module_record(row) -> ProjectModuleRecord:
        return ProjectModuleRecord(
            id=str(row["id"]),
            clientId=str(row["client_id"]),
            name=str(row["name"]),
            alias=str(row["alias"]) if row["alias"] else None,
            goal=str(row["goal"] or ""),
            description=str(row["description"] or ""),
            ownerName=str(row["owner_name"]) if row["owner_name"] else None,
            deliverables=_parse_json_list(row["deliverables_json"]),
            keywords=_parse_json_list(row["keywords_json"]),
            templateTasksJson=str(row["template_tasks_json"]) if row["template_tasks_json"] else None,
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def list_project_modules(client_id: str) -> list[ProjectModuleRecord]:
        build_client_summary(client_id)
        return [
            _project_module_record(row)
            for row in state.db.fetchall(
                "SELECT * FROM project_modules WHERE client_id = ? ORDER BY updated_at DESC, created_at DESC",
                (client_id,),
            )
        ]

    def _project_flow_record(row, module_name: str | None = None) -> ProjectFlowRecord:
        resolved_module_name = module_name
        if not resolved_module_name and row["module_id"]:
            module_row = state.db.fetchone("SELECT name FROM project_modules WHERE id = ?", (str(row["module_id"]),))
            resolved_module_name = str(module_row["name"]) if module_row and module_row["name"] else None
        return ProjectFlowRecord(
            id=str(row["id"]),
            clientId=str(row["client_id"]),
            moduleId=str(row["module_id"]),
            moduleName=resolved_module_name,
            name=str(row["name"]),
            description=str(row["description"] or ""),
            scenario=str(row["scenario"] or ""),
            triggerCondition=str(row["trigger_condition"] or ""),
            steps=_parse_json_list(row["steps_json"]),
            inputs=_parse_json_list(row["inputs_json"]),
            outputs=_parse_json_list(row["outputs_json"]),
            collaborators=_parse_json_list(row["collaborators_json"]),
            riskPoints=_parse_json_list(row["risk_points_json"]),
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def list_project_flows(client_id: str) -> list[ProjectFlowRecord]:
        build_client_summary(client_id)
        rows = state.db.fetchall(
            """
            SELECT f.*, m.name AS module_name
            FROM project_flows f
            LEFT JOIN project_modules m ON m.id = f.module_id
            WHERE f.client_id = ?
            ORDER BY f.updated_at DESC, f.created_at DESC
            """,
            (client_id,),
        )
        return [_project_flow_record(row, str(row["module_name"]) if row["module_name"] else None) for row in rows]

    def build_project_structure(client_id: str) -> ProjectStructureResponse:
        return ProjectStructureResponse(modules=list_project_modules(client_id), flows=list_project_flows(client_id))

    def get_project_module_detail(client_id: str, module_id: str) -> ProjectModuleDetailRecord:
        module_row = state.db.fetchone(
            "SELECT * FROM project_modules WHERE id = ? AND client_id = ?",
            (module_id, client_id),
        )
        if not module_row:
            raise HTTPException(status_code=404, detail="项目模块不存在")
        module_record = _project_module_record(module_row)
        flow_rows = state.db.fetchall(
            "SELECT id, name FROM project_flows WHERE client_id = ? AND module_id = ? ORDER BY updated_at DESC, created_at DESC",
            (client_id, module_id),
        )
        task_rows = state.db.fetchall(
            """
            SELECT id, title
            FROM tasks
            WHERE client_id = ? AND project_module_id = ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 8
            """,
            (client_id, module_id),
        )
        return ProjectModuleDetailRecord(
            **module_record.model_dump(),
            relatedTaskIds=[str(row["id"]) for row in task_rows],
            relatedTaskTitles=[str(row["title"]) for row in task_rows],
            flowIds=[str(row["id"]) for row in flow_rows],
            flowNames=[str(row["name"]) for row in flow_rows],
            contextSummary=(
                f"当前模块「{module_record.name}」聚焦 {module_record.goal or '关键交付'}，"
                f"已挂接 {len(flow_rows)} 条流程、{len(task_rows)} 条相关任务。"
            ),
        )

    def get_project_flow_detail(client_id: str, flow_id: str) -> ProjectFlowDetailRecord:
        flow_row = state.db.fetchone(
            """
            SELECT f.*, m.name AS module_name
            FROM project_flows f
            LEFT JOIN project_modules m ON m.id = f.module_id
            WHERE f.id = ? AND f.client_id = ?
            """,
            (flow_id, client_id),
        )
        if not flow_row:
            raise HTTPException(status_code=404, detail="项目流程不存在")
        flow_record = _project_flow_record(flow_row, str(flow_row["module_name"]) if flow_row["module_name"] else None)
        task_rows = state.db.fetchall(
            """
            SELECT id, title
            FROM tasks
            WHERE client_id = ? AND project_flow_id = ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 8
            """,
            (client_id, flow_id),
        )
        return ProjectFlowDetailRecord(
            **flow_record.model_dump(),
            relatedTaskIds=[str(row["id"]) for row in task_rows],
            relatedTaskTitles=[str(row["title"]) for row in task_rows],
            contextSummary=(
                f"当前流程「{flow_record.name}」位于模块「{flow_record.moduleName or '未命名模块'}」，"
                f"已挂接 {len(task_rows)} 条相关任务。"
            ),
        )

    def resolve_project_structure_refs(
        client_id: str | None,
        project_module_id: str | None,
        project_flow_id: str | None,
        *,
        strict: bool = True,
    ) -> tuple[ProjectModuleRecord | None, ProjectFlowRecord | None]:
        if not project_module_id and not project_flow_id:
            return None, None
        if not client_id:
            if strict:
                raise HTTPException(status_code=400, detail="选择模块或流程前请先关联项目")
            return None, None
        module_record: ProjectModuleRecord | None = None
        flow_record: ProjectFlowRecord | None = None
        if project_module_id:
            module_row = state.db.fetchone(
                "SELECT * FROM project_modules WHERE id = ? AND client_id = ?",
                (project_module_id, client_id),
            )
            if not module_row:
                if strict:
                    raise HTTPException(status_code=400, detail="所选任务模块不存在或不属于当前项目")
                return None, None
            module_record = _project_module_record(module_row)
        if project_flow_id:
            flow_row = state.db.fetchone(
                """
                SELECT f.*, m.name AS module_name
                FROM project_flows f
                LEFT JOIN project_modules m ON m.id = f.module_id
                WHERE f.id = ? AND f.client_id = ?
                """,
                (project_flow_id, client_id),
            )
            if not flow_row:
                if strict:
                    raise HTTPException(status_code=400, detail="所选流程不存在或不属于当前项目")
                return module_record, None
            flow_record = _project_flow_record(flow_row, str(flow_row["module_name"]) if flow_row["module_name"] else None)
            if module_record and flow_record.moduleId != module_record.id:
                if strict:
                    raise HTTPException(status_code=400, detail="所选流程不属于当前任务模块")
                return module_record, None
            if not module_record:
                module_row = state.db.fetchone("SELECT * FROM project_modules WHERE id = ?", (flow_record.moduleId,))
                module_record = _project_module_record(module_row) if module_row else None
        return module_record, flow_record

    def _tokenize_scope_text(value: str | None, min_length: int = 2, max_length: int = 18) -> list[str]:
        return [
            item
            for item in (
                part.strip().lower()
                for part in re.split(r"[，。；、,\n\s/·\-]+", value or "")
            )
            if min_length <= len(item) <= max_length
        ]

    def _infer_task_client(
        title: str,
        desc: str,
        clients: list[ClientSummary],
    ) -> tuple[str | None, str]:
        text = f"{title}\n{desc}".strip().lower()
        normalized_clients: list[tuple[ClientSummary, list[str], list[str]]] = []
        for client in clients:
            domain = client.domain.replace("https://", "").replace("http://", "").replace("www.", "").strip()
            domain_parts = [item for item in re.split(r"[/.]+", domain) if item]
            exact_tokens = [
                item
                for item in ((client.name or "").strip().lower(), (client.alias or "").strip().lower())
                if len(item) >= 2
            ]
            support_tokens = list(
                dict.fromkeys(
                    item
                    for item in [domain.lower(), *[part.lower() for part in domain_parts]]
                    if len(item) >= 2
                )
            )
            normalized_clients.append((client, exact_tokens, support_tokens))
        if not text:
            return None, "系统暂未识别到明确项目。"
        ranked: list[tuple[int, int, ClientSummary, list[str], list[str]]] = []
        for client, exact_tokens, support_tokens in normalized_clients:
            exact_hits = [token for token in exact_tokens if token in text]
            support_hits = [token for token in support_tokens if token in text]
            score = len(exact_hits) * 3 + len(support_hits)
            if score <= 0:
                continue
            ranked.append((score, len(client.name), client, exact_hits, support_hits))
        ranked.sort(key=lambda item: (-item[0], -item[1]))
        if not ranked:
            return None, "系统暂未识别到明确项目。"
        _, _, winner, exact_hits, support_hits = ranked[0]
        confidence = "high" if exact_hits else "medium" if len(support_hits) > 1 else "low"
        if confidence == "low":
            return None, f"命中项目弱信号“{(support_hits or [winner.name])[0]}”，暂不自动回填。"
        hits = [*exact_hits, *support_hits][:2]
        return winner.id, f"系统自动识别项目：命中“{'、'.join(hits) or winner.name}”。"

    def _infer_task_event_line(
        title: str,
        desc: str,
        event_lines: list[EventLineRecord],
        *,
        current_client_id: str | None = None,
    ) -> tuple[str | None, str]:
        text = f"{title}\n{desc}".strip().lower()
        scoped_event_lines = [
            item for item in event_lines if current_client_id and (item.primaryClientId or "").strip() == current_client_id
        ] if current_client_id else []
        candidate_lines = scoped_event_lines or event_lines
        if not candidate_lines:
            return None, "当前还没有可选事件线。"
        if not text:
            if current_client_id and len(scoped_event_lines) == 1:
                return scoped_event_lines[0].id, f"当前项目下仅有一条事件线，先预填为“{scoped_event_lines[0].name}”。"
            return None, f"当前范围内共有 {len(candidate_lines)} 条事件线，可继续手动调整。"
        ranked: list[tuple[int, str, EventLineRecord, list[str], list[str]]] = []
        for event_line in candidate_lines:
            exact_tokens = [item for item in [event_line.name.strip().lower()] if len(item) >= 2]
            flattened_support = list(
                dict.fromkeys(
                    token
                    for value in (event_line.summary, event_line.intent, event_line.nextStep, event_line.stage)
                    for token in _tokenize_scope_text(value, 3, 14)
                )
            )
            exact_hits = [token for token in exact_tokens if token in text]
            support_hits = [token for token in flattened_support if token in text]
            score = len(exact_hits) * 4 + len(support_hits)
            if score <= 0:
                continue
            ranked.append((score, event_line.updatedAt, event_line, exact_hits, support_hits))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        if ranked:
            _, _, winner, exact_hits, support_hits = ranked[0]
            hits = [*exact_hits, *support_hits][:2]
            scope_label = "当前项目" if current_client_id and scoped_event_lines else "可选范围"
            hit_suffix = f"，命中“{'、'.join(hits)}”" if hits else ""
            return winner.id, f"系统已在{scope_label}内匹配到事件线“{winner.name}”{hit_suffix}。"
        if current_client_id and len(scoped_event_lines) == 1:
            return scoped_event_lines[0].id, f"当前项目下仅有一条事件线，先预填为“{scoped_event_lines[0].name}”。"
        return None, f"当前范围内共有 {len(candidate_lines)} 条事件线，可继续手动调整。"

    def _infer_task_project_module(
        title: str,
        desc: str,
        modules: list[ProjectModuleRecord],
        *,
        event_line: EventLineRecord | None = None,
    ) -> tuple[str | None, str]:
        if not modules:
            return None, "当前项目下还没有任务模块。"
        text = "\n".join(
            item
            for item in [title, desc, event_line.name if event_line else None, event_line.summary if event_line else None, event_line.intent if event_line else None, event_line.nextStep if event_line else None]
            if item
        ).strip().lower()
        if not text:
            if len(modules) == 1:
                return modules[0].id, f"当前项目下仅有 1 个模块，先预填为“{modules[0].name}”。"
            return None, f"当前项目下已有 {len(modules)} 个模块，可继续手动调整。"
        ranked: list[tuple[int, str, ProjectModuleRecord, list[str], list[str]]] = []
        for module in modules:
            exact_tokens = [
                item
                for item in ((module.name or "").strip().lower(), (module.alias or "").strip().lower())
                if len(item) >= 2
            ]
            support_tokens = list(
                dict.fromkeys(
                    token
                    for value in [module.goal, module.description, module.ownerName, *module.deliverables, *module.keywords]
                    for token in _tokenize_scope_text(value, 2, 18)
                )
            )
            exact_hits = [token for token in exact_tokens if token in text]
            support_hits = [token for token in support_tokens if token in text]
            score = len(exact_hits) * 5 + len(support_hits) * 2
            if score <= 0:
                continue
            ranked.append((score, module.name, module, exact_hits, support_hits))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        if ranked:
            _, _, winner, exact_hits, support_hits = ranked[0]
            hits = [*exact_hits, *support_hits][:3]
            hit_suffix = f"，命中“{'、'.join(hits)}”" if hits else ""
            return winner.id, f"系统建议挂到模块“{winner.name}”{hit_suffix}。"
        if len(modules) == 1:
            return modules[0].id, f"当前项目下仅有 1 个模块，先预填为“{modules[0].name}”。"
        return None, f"当前项目下共有 {len(modules)} 个模块，可继续手动调整。"

    def _infer_task_project_flow(
        title: str,
        desc: str,
        flows: list[ProjectFlowRecord],
        *,
        selected_module_id: str | None = None,
        event_line: EventLineRecord | None = None,
    ) -> tuple[str | None, str]:
        scoped_flows = [item for item in flows if selected_module_id and item.moduleId == selected_module_id] if selected_module_id else flows
        if not scoped_flows:
            return None, "当前模块下还没有标准流程。"
        text = "\n".join(
            item
            for item in [title, desc, event_line.name if event_line else None, event_line.summary if event_line else None, event_line.intent if event_line else None, event_line.nextStep if event_line else None]
            if item
        ).strip().lower()
        if not text:
            if len(scoped_flows) == 1:
                return scoped_flows[0].id, f"当前范围内仅有 1 条流程，先预填为“{scoped_flows[0].name}”。"
            return None, f"当前范围内已有 {len(scoped_flows)} 条流程，可继续手动调整。"
        ranked: list[tuple[int, str, ProjectFlowRecord, list[str], list[str]]] = []
        for flow in scoped_flows:
            exact_tokens = [
                item
                for item in ((flow.name or "").strip().lower(), (flow.moduleName or "").strip().lower())
                if len(item) >= 2
            ]
            support_tokens = list(
                dict.fromkeys(
                    token
                    for value in [flow.description, flow.scenario, flow.triggerCondition, *flow.steps, *flow.inputs, *flow.outputs, *flow.collaborators, *flow.riskPoints]
                    for token in _tokenize_scope_text(value, 2, 18)
                )
            )
            exact_hits = [token for token in exact_tokens if token in text]
            support_hits = [token for token in support_tokens if token in text]
            score = len(exact_hits) * 5 + len(support_hits) * 2
            if score <= 0:
                continue
            ranked.append((score, flow.name, flow, exact_hits, support_hits))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        if ranked:
            _, _, winner, exact_hits, support_hits = ranked[0]
            hits = [*exact_hits, *support_hits][:3]
            hit_suffix = f"，命中“{'、'.join(hits)}”" if hits else ""
            return winner.id, f"系统建议挂到流程“{winner.name}”{hit_suffix}。"
        if len(scoped_flows) == 1:
            return scoped_flows[0].id, f"当前范围内仅有 1 条流程，先预填为“{scoped_flows[0].name}”。"
        return None, f"当前范围内共有 {len(scoped_flows)} 条流程，可继续手动调整。"

    def _normalize_task_client_and_event_line_refs(
        client_id: str | None,
        event_line_id: str | None,
    ) -> tuple[str | None, str | None]:
        normalized_client_id = (client_id or "").strip() or None
        normalized_event_line_id = (event_line_id or "").strip() or None
        if not normalized_event_line_id:
            return normalized_client_id, None
        event_line_row = state.db.fetchone(
            "SELECT id, primary_client_id FROM event_lines WHERE id = ?",
            (normalized_event_line_id,),
        )
        if not event_line_row and get_cloud_token():
            # Event line exists on cloud but not locally — sync it
            try:
                cloud_el = cloud_request("GET", f"/api/v1/event-lines/{normalized_event_line_id}")
                if isinstance(cloud_el, dict) and cloud_el.get("id"):
                    state.db.execute(
                        """INSERT OR IGNORE INTO event_lines(id, name, kind, status, primary_client_id, primary_client_name, owner_id, owner_name, created_at, updated_at)
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            str(cloud_el["id"]),
                            str(cloud_el.get("name", "")),
                            str(cloud_el.get("kind", "custom")),
                            str(cloud_el.get("status", "active")),
                            str(cloud_el.get("primaryClientId") or ""),
                            str(cloud_el.get("primaryClientName") or ""),
                            str(cloud_el.get("ownerId") or ""),
                            str(cloud_el.get("ownerName") or ""),
                            str(cloud_el.get("createdAt", "")),
                            str(cloud_el.get("updatedAt", "")),
                        ),
                    )
                    event_line_row = state.db.fetchone(
                        "SELECT id, primary_client_id FROM event_lines WHERE id = ?",
                        (normalized_event_line_id,),
                    )
            except Exception:
                pass
        if not event_line_row:
            raise HTTPException(status_code=400, detail="任务绑定的事件线无效")
        event_line_client_id = (
            str(event_line_row["primary_client_id"]).strip()
            if event_line_row["primary_client_id"]
            else None
        )
        if event_line_client_id and normalized_client_id != event_line_client_id:
            normalized_client_id = event_line_client_id
        return normalized_client_id, normalized_event_line_id

    def _build_task_scope_refresh_payload(
        task: TaskRecord,
        clients: list[ClientSummary],
        event_lines: list[EventLineRecord],

```
