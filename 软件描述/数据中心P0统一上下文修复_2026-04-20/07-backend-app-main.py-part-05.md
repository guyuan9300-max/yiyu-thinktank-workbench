# 源码文件：`backend/app/main.py`（分片 05）

- 行号范围：11201-14000
- 总行数：   30416
- 导出时间：2026-04-20

```python
        request: ConsultationKnowledgeRequestRecord,
    ) -> ClientTextDocumentResponse:
        client_id = (request.clientId or "").strip()
        if not client_id:
            raise HTTPException(status_code=400, detail="沉淀请求缺少 clientId，无法写入本地综合库")

        client = build_client_summary(client_id)
        title = build_consultation_knowledge_title(request)
        if request.target == "vector_memory":
            source_links = []
            if request.taskId:
                source_links.append(
                    {
                        "title": f"关联任务 {request.taskId}",
                        "documentId": request.taskId,
                        "path": None,
                        "sectionLabel": "任务上下文",
                    }
                )
            if request.eventLineId:
                source_links.append(
                    {
                        "title": f"关联事件线 {request.eventLineId}",
                        "documentId": request.eventLineId,
                        "path": None,
                        "sectionLabel": "事件线上下文",
                    }
                )
            create_memory_surrogate_from_answer(
                state.db,
                data_dir=state.data_dir,
                client_id=client_id,
                title=f"{client.name} · {title}",
                content=request.answer,
                actions="",
                analysis=request.question.strip(),
                source_links=source_links,
                created_at=now_iso(),
                ai_service=state.ai,
            )
            generated = create_consultation_memory_document(client_id, request)
            log_activity(
                "consultation.knowledge.vector_memory",
                "knowledge_memory",
                generated.documentId,
                {
                    "requestId": request.id,
                    "clientId": client_id,
                    "taskId": request.taskId or "",
                    "eventLineId": request.eventLineId or "",
                    "path": generated.path,
                },
            )
            return generated

        generated = create_client_text_document(
            client_id,
            ClientTextDocumentPayload(
                title=f"{client.name} · {title}",
                content=build_consultation_archive_content(request),
            ),
        )
        log_activity(
            "consultation.knowledge.document_archive",
            "document",
            generated.documentId,
            {
                "requestId": request.id,
                "clientId": client_id,
                "taskId": request.taskId or "",
                "eventLineId": request.eventLineId or "",
                "path": generated.path,
            },
        )
        return generated

    def infer_text_document_title(content: str) -> str:
        normalized = re.sub(r"\s+", " ", content).strip()
        if not normalized:
            return "未命名新增文档"
        for raw_line in content.splitlines():
            line = re.sub(r"^[#>*\-\d\.\)\s]+", "", raw_line).strip()
            if len(line) < 4:
                continue
            candidate = re.split(r"[。！？!?]", line, maxsplit=1)[0].strip() or line
            return candidate[:28]
        return normalized[:28]

    def create_client_text_document(client_id: str, payload: ClientTextDocumentPayload) -> ClientTextDocumentResponse:
        client = build_client_summary(client_id)
        ensure_standard_client_folders(client_id)
        folders = ensure_client_workspace(state.data_dir, client_id)
        target_dir = (folders.get("项目与业务") or next(iter(folders.values()))) / "手动新增文档"
        target_dir.mkdir(parents=True, exist_ok=True)

        normalized_content = str(payload.content or "").replace("\r\n", "\n").strip()
        if not normalized_content:
            raise HTTPException(status_code=400, detail="请先粘贴文档内容。")

        resolved_title = str(payload.title or "").strip() or infer_text_document_title(normalized_content)
        safe_stem = safe_filename(resolved_title or "新增文档")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = target_dir / f"{timestamp}_{safe_stem}.docx"
        if target_path.exists():
            target_path = target_dir / f"{timestamp}_{safe_stem}_{uuid4().hex[:6]}.docx"

        document = WordDocument()
        document.add_heading(resolved_title, level=1)
        for block in re.split(r"\n\s*\n+", normalized_content):
            text = block.strip()
            if not text:
                continue
            heading_match = re.match(r"^(#{1,4})\s+(.+)$", text)
            if heading_match:
                level = min(len(heading_match.group(1)) + 1, 4)
                document.add_heading(heading_match.group(2).strip(), level=level)
                continue
            document.add_paragraph(text)
        document.save(target_path)

        timestamp_iso = now_iso()
        folder_row = state.db.fetchone(
            "SELECT id FROM client_folders WHERE client_id = ? AND label = ?",
            (client_id, "项目与业务"),
        )
        document_id = new_id("doc")
        excerpt = normalized_content[:140] or f"{resolved_title} 已进入当前项目文档库。"
        state.db.execute(
            """
            INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                client_id,
                str(folder_row["id"]) if folder_row else None,
                target_path.name,
                str(target_path),
                str(target_path),
                "docx",
                "manual_text_doc",
                excerpt,
                to_json(["manual_text_doc", "docx"]),
                timestamp_iso,
            ),
        )
        ingest_document_knowledge(
            state.db,
            data_dir=state.data_dir,
            client_id=client_id,
            import_id=None,
            document_id=document_id,
            source_path=target_path,
            original_source_path=target_path,
            title=target_path.name,
            kind="docx",
            source="manual_text_doc",
            fallback_excerpt=excerpt,
            created_at=timestamp_iso,
            ai_service=None,
        )
        log_activity(
            "client.document.create_from_text",
            "document",
            document_id,
            {
                "clientId": client_id,
                "clientName": client.name,
                "title": resolved_title,
                "path": str(target_path),
            },
        )
        document_row = state.db.fetchone("SELECT path FROM documents WHERE id = ?", (document_id,))
        resolved_path = str(document_row["path"]) if document_row and document_row["path"] else str(target_path)
        return ClientTextDocumentResponse(
            clientId=client_id,
            documentId=document_id,
            title=resolved_title,
            fileName=Path(resolved_path).name,
            path=resolved_path,
        )

    def build_template_fill_context(
        client_id: str,
        template_name: str,
        field_label: str,
        *,
        field_type: str = "general",
        evidence_limit: int = 12,
        excerpt_limit: int = 2200,
        evidence_char_budget: int = 18000,
        dna_max_chars: int = 2200,
        allow_web_supplement: bool = True,
    ) -> tuple[str, list[EvidenceItem], list[TemplateWebSource]]:
        def collect_template_fill_public_hints(max_rows: int = 60) -> tuple[list[str], list[str]]:
            rows = state.db.fetchall(
                """
                SELECT file_name, preview_text
                FROM v2_documents
                WHERE client_id = ?
                  AND COALESCE(parse_status, 'ready') = 'ready'
                ORDER BY
                  CASE
                    WHEN preview_text LIKE '%http%' OR preview_text LIKE '%.org%' OR preview_text LIKE '%.cn%' THEN 0
                    WHEN file_name LIKE '%中国%' OR preview_text LIKE '%中国%' THEN 1
                    WHEN file_name LIKE '%基金会论坛%' OR preview_text LIKE '%基金会论坛%' THEN 1
                    ELSE 2
                  END,
                  updated_at DESC,
                  id DESC
                LIMIT ?
                """,
                (client_id, max_rows),
            )
            titles: list[str] = []
            snippets: list[str] = []
            for row in rows or []:
                try:
                    title = str(row["file_name"] or "").strip()
                except Exception:
                    title = str((row[0] if len(row) > 0 else "") or "").strip()
                try:
                    snippet = str(row["preview_text"] or "").strip()
                except Exception:
                    snippet = str((row[1] if len(row) > 1 else "") or "").strip()
                if title and title not in titles:
                    titles.append(title)
                if snippet and snippet not in snippets:
                    snippets.append(snippet)
            return titles, snippets

        client_summary = build_client_summary(client_id)
        retrieval_bundle = build_retrieval_bundle(
            client_id,
            build_template_fill_retrieval_query(
                client_name=client_summary.name,
                template_name=template_name,
                field_label=field_label,
                field_type=field_type,
            ),
        )
        evidence = [
            EvidenceItem(
                id=new_id("ev"),
                title=item.title,
                excerpt=item.excerpt,
                sourceType="knowledge_chunk" if item.chunk_id else "knowledge_document",
                documentId=item.knowledge_document_id,
                path=item.path,
                score=item.score,
                coverage=item.coverage,
                sectionLabel=item.section_label,
                retrievalStage={"master_index": "master_index", "surrogate": "surrogate"}.get(item.source_stage, "raw_chunk"),
                isFallback=item.source_stage == "master_index",
                matchedTerms=item.matched_terms,
            )
            for item in retrieval_bundle.citations
        ]
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}
        preferred_categories = [
            str(item)
            for item in retrieval_meta.get("preferredCategories", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("preferredCategories"), list) else []
        curated_evidence = select_high_signal_evidence(
            evidence,
            limit=evidence_limit,
            prompt=field_label,
            preferred_categories=preferred_categories,
        )
        client_name = client_summary.name
        lines = [
            f"当前客户：{client_name}",
            f"模板：{template_name}",
            f"待填写字段：{field_label}",
        ]
        client_dna_context = build_client_dna_context(client_id, field_label, max_chars=dna_max_chars)
        if client_dna_context:
            lines.append(client_dna_context)
        if curated_evidence:
            blocks: list[str] = []
            used_chars = 0
            for index, item in enumerate(curated_evidence, start=1):
                label = item.title
                if item.sectionLabel:
                    label = f"{label} / {item.sectionLabel}"
                compact_excerpt = re.sub(r"\s+", " ", item.excerpt or "").strip()[:excerpt_limit]
                block = (
                    f"[参考证据 {index}]\n"
                    f"标题：{label}\n"
                    f"片段：{compact_excerpt}"
                )
                if blocks and used_chars + len(block) > evidence_char_budget:
                    break
                blocks.append(block)
                used_chars += len(block)
            if blocks:
                lines.append("可参考的客户资料：\n" + "\n\n".join(blocks))
        web_sources: list[TemplateWebSource] = []
        if allow_web_supplement and should_enable_template_fill_web_supplement(field_type, len(curated_evidence), field_label=field_label):
            public_hint_titles, public_hint_snippets = collect_template_fill_public_hints()
            combined_titles = list(
                dict.fromkeys([item.title for item in curated_evidence] + public_hint_titles)
            )
            combined_snippets = list(
                dict.fromkeys([item.excerpt for item in curated_evidence if item.excerpt] + public_hint_snippets)
            )
            web_sources = fetch_template_fill_web_sources(
                client_name=client_name,
                field_label=field_label,
                template_name=template_name,
                client_domain=client_summary.domain,
                evidence_titles=combined_titles,
                evidence_snippets=combined_snippets,
                max_items=2,
                field_type=field_type,
            )
            if web_sources:
                web_blocks = []
                for index, item in enumerate(web_sources, start=1):
                    web_blocks.append(
                        f"[网页补充 {index}]\n"
                        f"标题：{item.title}\n"
                        f"链接：{item.url}\n"
                        f"摘要：{item.snippet}"
                    )
                lines.append("联网补充（公开网页，仅作弱证据）：\n" + "\n\n".join(web_blocks))
        return "\n\n".join(lines).strip(), curated_evidence, web_sources

    def summarize_template_field_basis(value: str, evidence_titles: list[str], web_titles: list[str] | None = None) -> str:
        web_titles = [str(item).strip() for item in (web_titles or []) if str(item).strip()]
        if str(value or "").startswith("【待确认】"):
            if evidence_titles:
                return f"当前已检索到 {len(evidence_titles)} 份相关资料，但不足以直接确认该字段。"
            if web_titles:
                return f"当前仅补到 {len(web_titles)} 条公开网页线索，仍不足以正式确认该字段。"
            return "当前未检索到可直接支撑该字段的客户资料。"
        if evidence_titles:
            return "主要参考：" + "；".join(evidence_titles[:2])
        if web_titles:
            return "网页补充：" + "；".join(web_titles[:2])
        return "本字段由模板链路自动生成，但未记录到明确证据标题。"

    def estimate_template_field_confidence(
        *,
        field_type: str,
        value_kind: str,
        evidence_count: int,
        review_required: bool,
    ) -> float:
        if value_kind == "missing":
            return 0.0
        base = {
            "precise_fact": 0.9,
            "quantitative_result": 0.82,
            "governance_mechanism": 0.62,
            "structural_summary": 0.72,
            "attachment_material": 0.5,
            "general": 0.6,
        }.get(field_type, 0.6)
        if evidence_count <= 0:
            base -= 0.22
        elif evidence_count == 1:
            base -= 0.08
        if review_required:
            base -= 0.18
        if value_kind == "inference":
            base -= 0.15
        return round(max(0.0, min(0.98, base)), 2)

    def create_client_template_fill_run(client_id: str, template_path_raw: str) -> ClientTemplateFillRunRecord:
        template_path = Path(template_path_raw).expanduser()
        timestamp = now_iso()
        run_id = new_id("tmplfill")
        state.db.execute(
            """
            INSERT INTO client_template_fill_runs(
                id, client_id, template_name, template_path, status, phase, progress, stage_label, elapsed_ms,
                field_count, processed_count, filled_count, missing_count, current_field_label, evidence_titles_json, fields_json, output_path, error_message,
                created_at, updated_at
            )
            VALUES(?, ?, ?, ?, 'queued', 'queued', 0, '等待开始识别模板字段', 0, 0, 0, 0, 0, NULL, '[]', '[]', NULL, NULL, ?, ?)
            """,
            (run_id, client_id, template_path.name, str(template_path), timestamp, timestamp),
        )
        row = state.db.fetchone("SELECT * FROM client_template_fill_runs WHERE id = ?", (run_id,))
        assert row is not None
        return build_client_template_fill_run(row)

    def _normalize_template_fill_path(template_path_raw: str) -> str:
        return str(Path(template_path_raw).expanduser().resolve(strict=False))

    def fetch_active_client_template_fill_run(
        client_id: str,
        *,
        template_path_raw: str | None = None,
    ) -> ClientTemplateFillRunRecord | None:
        expire_stuck_template_fill_runs()
        active_rows = state.db.fetchall(
            """
            SELECT *
            FROM client_template_fill_runs
            WHERE client_id = ? AND status IN ('queued', 'running')
            ORDER BY created_at DESC
            """,
            (client_id,),
        )
        if not active_rows:
            return None
        if template_path_raw is None:
            return build_client_template_fill_run(active_rows[0])
        normalized_target = _normalize_template_fill_path(template_path_raw)
        for row in active_rows:
            existing_path = str(row["template_path"] or "")
            if _normalize_template_fill_path(existing_path) == normalized_target:
                return build_client_template_fill_run(row)
        return None

    def update_client_template_fill_run(
        run_id: str,
        *,
        status: str | None = None,
        phase: str | None = None,
        progress: float | None = None,
        stage_label: str | None = None,
        elapsed_ms: float | None = None,
        field_count: int | None = None,
        processed_count: int | None = None,
        filled_count: int | None = None,
        missing_count: int | None = None,
        current_field_label: str | None = None,
        clear_current_field_label: bool = False,
        evidence_titles: list[str] | None = None,
        fields: list[ClientTemplateFillFieldRecord] | None = None,
        output_path: str | None = None,
        error_message: str | None = None,
    ) -> None:
        row = state.db.fetchone("SELECT * FROM client_template_fill_runs WHERE id = ?", (run_id,))
        if not row:
            return
        state.db.execute(
            """
            UPDATE client_template_fill_runs
            SET status = ?, phase = ?, progress = ?, stage_label = ?, elapsed_ms = ?,
                field_count = ?, processed_count = ?, filled_count = ?, missing_count = ?, current_field_label = ?, evidence_titles_json = ?, fields_json = ?,
                output_path = ?, error_message = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status or str(row["status"]),
                phase or str(row["phase"]),
                float(progress if progress is not None else row["progress"]),
                stage_label if stage_label is not None else (str(row["stage_label"]) if row["stage_label"] else None),
                float(elapsed_ms if elapsed_ms is not None else row["elapsed_ms"]),
                int(field_count if field_count is not None else row["field_count"]),
                int(processed_count if processed_count is not None else row["processed_count"]),
                int(filled_count if filled_count is not None else row["filled_count"]),
                int(missing_count if missing_count is not None else row["missing_count"]),
                None
                if clear_current_field_label
                else (
                    current_field_label
                    if current_field_label is not None
                    else (str(row["current_field_label"]) if row["current_field_label"] else None)
                ),
                to_json(evidence_titles if evidence_titles is not None else from_json(str(row["evidence_titles_json"] or "[]"), [])),
                to_json([field.model_dump() for field in fields] if fields is not None else from_json(str(row["fields_json"] or "[]"), [])),
                output_path if output_path is not None else (str(row["output_path"]) if row["output_path"] else None),
                error_message if error_message is not None else (str(row["error_message"]) if row["error_message"] else None),
                now_iso(),
                run_id,
            ),
        )

    def build_client_template_fill_run(row) -> ClientTemplateFillRunRecord:
        evidence_titles = from_json(str(row["evidence_titles_json"] or "[]"), [])
        fields_data = from_json(str(row["fields_json"] or "[]"), [])
        template_path = Path(str(row["template_path"] or "")).expanduser()
        fields = [
            ClientTemplateFillFieldRecord(**item)
            for item in fields_data
            if isinstance(item, dict)
        ]
        review_field_count = sum(1 for item in fields if item.reviewRequired or item.status == "missing")
        attachment_checklist = extract_docx_attachment_checklist(template_path) if template_path.exists() and template_path.suffix.lower() == ".docx" else []
        return ClientTemplateFillRunRecord(
            id=str(row["id"]),
            clientId=str(row["client_id"]),
            templateName=str(row["template_name"]),
            templatePath=str(row["template_path"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            phase=str(row["phase"]),  # type: ignore[arg-type]
            progress=float(row["progress"] or 0.0),
            stageLabel=str(row["stage_label"]) if row["stage_label"] else None,
            elapsedMs=float(row["elapsed_ms"] or 0.0),
            fieldCount=int(row["field_count"] or 0),
            processedCount=int(row["processed_count"] or 0),
            filledCount=int(row["filled_count"] or 0),
            missingCount=int(row["missing_count"] or 0),
            reviewFieldCount=review_field_count,
            currentFieldLabel=str(row["current_field_label"]) if row["current_field_label"] else None,
            evidenceTitles=[str(item) for item in evidence_titles] if isinstance(evidence_titles, list) else [],
            attachmentChecklist=attachment_checklist,
            fields=fields,
            outputPath=str(row["output_path"]) if row["output_path"] else None,
            errorMessage=str(row["error_message"]) if row["error_message"] else None,
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def fetch_client_template_fill_run(client_id: str, run_id: str) -> ClientTemplateFillRunRecord:
        row = state.db.fetchone(
            "SELECT * FROM client_template_fill_runs WHERE id = ? AND client_id = ?",
            (run_id, client_id),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Template fill run not found")
        return build_client_template_fill_run(row)

    def _fill_client_template_docx_impl(
        client_id: str,
        template_path_raw: str,
        progress_callback: Callable[[str, float, str, int, int, int, int, str | None, list[str], list[ClientTemplateFillFieldRecord]], None] | None = None,
    ) -> ClientTemplateFillResponse:
        client = build_client_summary(client_id)
        template_path = Path(template_path_raw).expanduser()
        if not template_path.exists() or not template_path.is_file():
            raise HTTPException(status_code=400, detail="模板文件不存在。")
        if template_path.suffix.lower() != ".docx":
            raise HTTPException(status_code=400, detail="当前模板自动填写 MVP 只支持 .docx。")
        fields = extract_docx_template_fields(template_path)
        if not fields:
            raise HTTPException(status_code=400, detail="没有识别到可自动填写的字段。请在 docx 中使用 {{字段名}} 占位符，或使用“标题列 + 空白答案列”的两列表格。")

        ordered_labels: list[str] = []
        seen_labels: set[str] = set()
        for field in fields:
            if field.label in seen_labels:
                continue
            seen_labels.add(field.label)
            ordered_labels.append(field.label)

        values: dict[str, str] = {}
        field_records: list[ClientTemplateFillFieldRecord] = []
        total_fields = len(ordered_labels)
        field_types = {label: infer_template_field_type(label) for label in ordered_labels}
        attachment_checklist = extract_docx_attachment_checklist(template_path)
        compact_template_mode = total_fields >= 24
        batch_size = 5 if compact_template_mode else 4
        context_evidence_limit = 3 if compact_template_mode else 4
        context_excerpt_limit = 520 if compact_template_mode else 900
        context_evidence_char_budget = 1800 if compact_template_mode else 4200
        context_dna_max_chars = 600 if compact_template_mode else 900
        allow_web_supplement = not compact_template_mode
        if compact_template_mode and state.system_logger:
            state.system_logger.info(
                "template_fill",
                "模板字段较多，自动切换到快速模式：缩短证据上下文并跳过联网补充",
                clientId=client_id,
                templateName=template_path.name,
                fieldCount=total_fields,
            )
        if progress_callback:
            progress_callback("parsing", 12.0, f"已识别 {total_fields} 个待填写字段", total_fields, 0, 0, 0, ordered_labels[0] if ordered_labels else None, [], [])

        def build_fast_missing_value(label: str, field_type: str | None) -> str:
            hint = build_template_follow_up_question(field_type or "general", label) or f"请补充更直接支撑“{normalize_template_label(label)}”的客户资料。"
            hint = str(hint).strip().rstrip("。")
            return f"【待确认】{hint}。"

        for batch_start in range(0, total_fields, batch_size):
            batch_labels = ordered_labels[batch_start : batch_start + batch_size]
            batch_contexts: list[tuple[str, str]] = []
            batch_evidence: dict[str, list[EvidenceItem]] = {}
            batch_web_sources: dict[str, list[TemplateWebSource]] = {}
            batch_label = "、".join(batch_labels[:2]) + (" 等" if len(batch_labels) > 2 else "")
            for label in batch_labels:
                context_summary, evidence, web_sources = build_template_fill_context(
                    client_id,
                    template_path.name,
                    label,
                    field_type=field_types.get(label, "general"),
                    evidence_limit=context_evidence_limit,
                    excerpt_limit=context_excerpt_limit,
                    evidence_char_budget=context_evidence_char_budget,
                    dna_max_chars=context_dna_max_chars,
                    allow_web_supplement=allow_web_supplement,
                )
                batch_contexts.append((label, context_summary))
                batch_evidence[label] = evidence
                batch_web_sources[label] = web_sources
            if progress_callback:
                current_titles = list(
                    dict.fromkeys(
                        [
                            *[title for record in field_records for title in record.evidenceTitles],
                            *[title for record in field_records for title in record.webSourceTitles],
                            *[item.title for label in batch_labels for item in batch_evidence.get(label, [])[:2]],
                            *[item.title for label in batch_labels for item in batch_web_sources.get(label, [])[:1]],
                        ]
                    )
                )[:8]
                processed = len(field_records)
                progress = min(78.0, 18.0 + (processed / max(total_fields, 1)) * 52.0)
                progress_callback(
                    "retrieving",
                    progress,
                    f"正在检索第 {batch_start + 1}-{batch_start + len(batch_labels)} 个字段所需资料",
                    total_fields,
                    batch_start,
                    sum(1 for item in field_records if item.status == "filled"),
                    sum(1 for item in field_records if item.status == "missing"),
                    batch_label,
                    current_titles,
                            field_records,
                        )
            try:
                if progress_callback:
                    progress = min(84.0, 30.0 + ((batch_start + len(batch_labels)) / max(total_fields, 1)) * 42.0)
                    progress_callback(
                        "ai",
                        progress,
                        f"正在为第 {batch_start + 1}-{batch_start + len(batch_labels)} 个字段生成候选答案",
                        total_fields,
                        batch_start,
                        sum(1 for item in field_records if item.status == "filled"),
                        sum(1 for item in field_records if item.status == "missing"),
                        batch_label,
                        current_titles,
                        field_records,
                    )
                if state.system_logger:
                    state.system_logger.info(
                        "template_fill",
                        f"开始批量生成字段答案: {batch_start + 1}-{batch_start + len(batch_labels)}/{total_fields}",
                        clientId=client_id,
                        templateName=template_path.name,
                        batchLabel=batch_label,
                    )
                batch_values = state.ai.generate_template_field_values_batch(
                    template_name=template_path.name,
                    client_name=client.name,
                    field_contexts=batch_contexts,
                    field_types=field_types,
                )
                for label in batch_labels:
                    value = str(batch_values.get(label) or "【待确认】当前缺少可直接填写该字段的资料。").strip()
                    field_type = field_types.get(label, "general")
                    evidence_titles = list(dict.fromkeys(item.title for item in batch_evidence.get(label, [])[:3]))
                    web_titles = list(dict.fromkeys(item.title for item in batch_web_sources.get(label, [])[:2]))
                    value_kind = infer_template_value_kind(value, field_type)
                    review_required = value_kind in {"missing", "inference"} or value.startswith("【待确认】")
                    values[label] = value
                    field_records.append(
                        ClientTemplateFillFieldRecord(
                            label=label,
                            value=value,
                            status="missing" if value.startswith("【待确认】") else "filled",
                            evidenceTitles=evidence_titles,
                            webSourceTitles=web_titles,
                            fieldType=field_type,
                            valueKind=value_kind,
                            confidence=estimate_template_field_confidence(
                                field_type=field_type,
                                value_kind=value_kind,
                                evidence_count=len(evidence_titles),
                                review_required=review_required,
                            ),
                            basisSummary=summarize_template_field_basis(value, evidence_titles, web_titles),
                            followUpQuestion=build_template_follow_up_question(field_type, label) if review_required else None,
                            suggestedSources=build_template_suggested_sources(field_type, label),
                            reviewRequired=review_required,
                        )
                    )
                    if progress_callback:
                        filled_count = sum(1 for item in field_records if item.status == "filled")
                        missing_count = len(field_records) - filled_count
                        progress = min(92.0, 42.0 + (len(field_records) / max(total_fields, 1)) * 48.0)
                        progress_callback(
                            "writing",
                            progress,
                            f"正在写入字段：{label}",
                            total_fields,
                            len(field_records),
                            filled_count,
                            missing_count,
                            label,
                            list(
                                dict.fromkeys(
                                    [title for record in field_records for title in record.evidenceTitles]
                                    + [title for record in field_records for title in record.webSourceTitles]
                                )
                            )[:8],
                            field_records,
                        )
            except AiInvocationError as error:
                if state.system_logger:
                    state.system_logger.error(
                        "template_fill",
                        f"批量字段生成失败，转快速待确认兜底: {batch_start + 1}-{batch_start + len(batch_labels)}/{total_fields}",
                        clientId=client_id,
                        templateName=template_path.name,
                        batchLabel=batch_label,
                        error=str(error.detail),
                    )
                for label in batch_labels:
                    field_type = field_types.get(label, "general")
                    evidence = batch_evidence.get(label, [])
                    evidence_titles = list(dict.fromkeys(item.title for item in evidence[:3]))
                    web_titles = list(dict.fromkeys(item.title for item in batch_web_sources.get(label, [])[:2]))
                    value = build_fast_missing_value(label, field_type)
                    value_kind = infer_template_value_kind(value, field_type)
                    review_required = value_kind in {"missing", "inference"} or value.startswith("【待确认】")
                    values[label] = value
                    field_records.append(
                        ClientTemplateFillFieldRecord(
                            label=label,
                            value=value,
                            status="missing" if value.startswith("【待确认】") else "filled",
                            evidenceTitles=evidence_titles,
                            webSourceTitles=web_titles,
                            fieldType=field_type,
                            valueKind=value_kind,
                            confidence=estimate_template_field_confidence(
                                field_type=field_type,
                                value_kind=value_kind,
                                evidence_count=len(evidence_titles),
                                review_required=review_required,
                            ),
                            basisSummary=summarize_template_field_basis(value, evidence_titles, web_titles),
                            followUpQuestion=build_template_follow_up_question(field_type, label) if review_required else None,
                            suggestedSources=build_template_suggested_sources(field_type, label),
                            reviewRequired=review_required,
                        )
                    )
                    if progress_callback:
                        filled_count = sum(1 for item in field_records if item.status == "filled")
                        missing_count = len(field_records) - filled_count
                        progress = min(92.0, 42.0 + (len(field_records) / max(total_fields, 1)) * 48.0)
                        progress_callback(
                            "writing",
                            progress,
                            f"正在写入字段：{label}",
                            total_fields,
                            len(field_records),
                            filled_count,
                            missing_count,
                            label,
                            list(
                                dict.fromkeys(
                                    [title for record in field_records for title in record.evidenceTitles]
                                    + [title for record in field_records for title in record.webSourceTitles]
                                )
                            )[:8],
                            field_records,
                        )
            except HTTPException:
                raise
            except Exception as error:
                batch_end = min(total_fields, batch_start + len(batch_labels))
                raise HTTPException(
                    status_code=500,
                    detail=f"字段批次填写失败（{batch_start + 1}-{batch_end}/{total_fields}）。{error}",
                ) from error
        folders = ensure_client_workspace(state.data_dir, client_id)
        target_dir = folders["战略陪伴"] / "自动填写文档"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = target_dir / f"{safe_filename(template_path.stem)}_已填写_{timestamp}.docx"
        apply_docx_template_values(template_path, target_path, values)
        filled_count = sum(1 for item in field_records if item.status == "filled")
        missing_count = len(field_records) - filled_count
        if progress_callback:
            progress_callback(
                "completed",
                100.0,
                f"已生成结果文档，共 {filled_count} 项自动填写，{missing_count} 项待确认",
                len(field_records),
                len(field_records),
                filled_count,
                missing_count,
                None,
                list(
                    dict.fromkeys(
                        [title for record in field_records for title in record.evidenceTitles]
                        + [title for record in field_records for title in record.webSourceTitles]
                    )
                )[:8],
                field_records,
            )
        log_activity(
            "document.template_fill",
            "document",
            str(target_path),
            {"clientId": client_id, "templatePath": str(template_path), "fieldCount": len(field_records), "filledCount": filled_count},
        )
        return ClientTemplateFillResponse(
            path=str(target_path),
            fileName=target_path.name,
            fieldCount=len(field_records),
            filledCount=filled_count,
            missingCount=missing_count,
            reviewFieldCount=sum(1 for item in field_records if item.reviewRequired or item.status == "missing"),
            attachmentChecklist=attachment_checklist,
            fields=field_records,
        )

    def fill_client_template_docx(client_id: str, template_path_raw: str) -> ClientTemplateFillResponse:
        return _fill_client_template_docx_impl(client_id, template_path_raw)

    def run_client_template_fill(client_id: str, run_id: str, template_path_raw: str) -> None:
        started_at = perf_counter()
        update_client_template_fill_run(
            run_id,
            status="running",
            phase="parsing",
            progress=4.0,
            stage_label="正在识别模板字段",
            elapsed_ms=0.0,
            processed_count=0,
            current_field_label=None,
        )

        def _progress(
            phase: str,
            progress: float,
            stage_label: str,
            field_count: int,
            processed_count: int,
            filled_count: int,
            missing_count: int,
            current_field_label: str | None,
            evidence_titles: list[str],
            fields: list[ClientTemplateFillFieldRecord],
        ) -> None:
            update_client_template_fill_run(
                run_id,
                status="running" if phase not in {"completed", "failed"} else ("completed" if phase == "completed" else "failed"),
                phase=phase,
                progress=progress,
                stage_label=stage_label,
                elapsed_ms=(perf_counter() - started_at) * 1000,
                field_count=field_count,
                processed_count=processed_count,
                filled_count=filled_count,
                missing_count=missing_count,
                current_field_label=current_field_label,
                evidence_titles=evidence_titles,
                fields=fields,
            )

        try:
            result = _fill_client_template_docx_impl(client_id, template_path_raw, _progress)
            update_client_template_fill_run(
                run_id,
                status="completed",
                phase="completed",
                progress=100.0,
                stage_label="填写完成",
                elapsed_ms=(perf_counter() - started_at) * 1000,
                field_count=result.fieldCount,
                processed_count=result.fieldCount,
                filled_count=result.filledCount,
                missing_count=result.missingCount,
                clear_current_field_label=True,
                evidence_titles=list(dict.fromkeys(title for field in result.fields for title in field.evidenceTitles))[:8],
                fields=result.fields,
                output_path=result.path,
                error_message=None,
            )
        except HTTPException as error:
            last_phase = str(state.db.scalar("SELECT phase FROM client_template_fill_runs WHERE id = ?", (run_id,)) or "parsing")
            update_client_template_fill_run(
                run_id,
                status="failed",
                phase=last_phase,
                progress=max(8.0, min(float(state.db.scalar("SELECT progress FROM client_template_fill_runs WHERE id = ?", (run_id,)) or 0.0), 96.0)),
                stage_label="模板填写失败",
                elapsed_ms=(perf_counter() - started_at) * 1000,
                processed_count=int(state.db.scalar("SELECT processed_count FROM client_template_fill_runs WHERE id = ?", (run_id,)) or 0),
                clear_current_field_label=True,
                error_message=str(error.detail),
            )
        except Exception as error:
            last_phase = str(state.db.scalar("SELECT phase FROM client_template_fill_runs WHERE id = ?", (run_id,)) or "parsing")
            update_client_template_fill_run(
                run_id,
                status="failed",
                phase=last_phase,
                progress=max(8.0, min(float(state.db.scalar("SELECT progress FROM client_template_fill_runs WHERE id = ?", (run_id,)) or 0.0), 96.0)),
                stage_label="模板填写失败",
                elapsed_ms=(perf_counter() - started_at) * 1000,
                processed_count=int(state.db.scalar("SELECT processed_count FROM client_template_fill_runs WHERE id = ?", (run_id,)) or 0),
                clear_current_field_label=True,
                error_message=str(error),
            )

    def workspace_for_client(client_id: str) -> ClientWorkspaceResponse:
        client = build_client_summary(client_id)
        ensure_standard_client_folders(client_id)
        hidden_labels = get_hidden_client_folders(client_id)
        document_limit = 200
        folder_rows = {
            str(row["label"]): row
            for row in state.db.fetchall(
                "SELECT * FROM client_folders WHERE client_id = ?",
                (client_id,),
            )
            if str(row["label"]) in HUMAN_VISIBLE_CATEGORIES and str(row["label"]) not in hidden_labels
        }
        folders = [
            ClientFolder(
                id=str(folder_rows[label]["id"]),
                clientId=str(folder_rows[label]["client_id"]),
                label=str(folder_rows[label]["label"]),
                path=str(folder_rows[label]["path"]),
                fileCount=int(folder_rows[label]["file_count"]),
                lastScannedAt=str(folder_rows[label]["last_scanned_at"]) if folder_rows[label]["last_scanned_at"] else None,
            )
            for label in HUMAN_VISIBLE_CATEGORIES
            if label not in hidden_labels
            if label in folder_rows
        ]
        documents = [
            DocumentRecord(
                id=str(row["id"]),
                clientId=str(row["client_id"]),
                folderId=str(row["folder_id"]) if row["folder_id"] else None,
                title=str(row["title"]),
                path=str(row["path"]),
                kind=str(row["kind"]),
                source=str(row["source"]),
                excerpt=str(row["excerpt"]),
                tags=_parse_json_list(row["tags_json"]),
                importedAt=str(row["created_at"]),
            )
            for row in state.db.fetchall("SELECT * FROM documents WHERE client_id = ? ORDER BY created_at DESC LIMIT ?", (client_id, document_limit))
        ]
        imports = [
            ImportRecord(
                id=str(row["id"]),
                clientId=str(row["client_id"]),
                sourcePath=str(row["source_path"]),
                mode=str(row["mode"]),  # type: ignore[arg-type]
                status=str(row["status"]),  # type: ignore[arg-type]
                importedCount=int(row["imported_count"]),
                skippedCount=int(row["skipped_count"]),
                createdAt=str(row["created_at"]),
            )
            for row in state.db.fetchall("SELECT * FROM imports WHERE client_id = ? ORDER BY created_at DESC LIMIT 10", (client_id,))
        ]
        threads = [
            ChatThread(
                id=str(row["id"]),
                clientId=str(row["client_id"]),
                title=str(row["title"]),
                createdAt=str(row["created_at"]),
                updatedAt=str(row["updated_at"]),
            )
            for row in state.db.fetchall("SELECT * FROM chat_threads WHERE client_id = ? ORDER BY updated_at DESC", (client_id,))
        ]
        messages = [
            build_chat_message(row)
            for row in state.db.fetchall(
                """
                SELECT recent.*
                FROM (
                    SELECT m.*
                    FROM chat_messages m
                    JOIN chat_threads t ON t.id = m.thread_id
                    WHERE t.client_id = ?
                    ORDER BY m.created_at DESC
                    LIMIT 50
                ) recent
                ORDER BY recent.created_at ASC
                """,
                (client_id,),
            )
        ]
        analysis_runs = [
            build_client_analysis_run(row)
            for row in state.db.fetchall(
                "SELECT * FROM client_analysis_runs WHERE client_id = ? ORDER BY updated_at DESC LIMIT 12",
                (client_id,),
            )
        ]
        meetings = [
            build_meeting_summary(row)
            for row in state.db.fetchall("SELECT * FROM meetings WHERE client_id = ? ORDER BY updated_at DESC", (client_id,))
        ]
        goals = [
            GoalRecord(
                id=str(row["id"]),
                clientId=str(row["client_id"]),
                title=str(row["title"]),
                quarter=str(row["quarter"]),
                progress=int(row["progress"]),
                ownerName=str(row["owner_name"]),
            )
            for row in state.db.fetchall("SELECT * FROM goal_records WHERE client_id = ? ORDER BY updated_at DESC", (client_id,))
        ]
        dna_modules = list_client_dna_modules(client_id)
        project_modules = list_project_modules(client_id)
        project_flows = list_project_flows(client_id)
        dna_terms = [
            DnaTerm(
                id=str(row["id"]),
                clientId=str(row["client_id"]),
                category=str(row["category"]),
                canonicalName=str(row["canonical_name"]),
                aliases=_parse_json_list(row["aliases_json"]),
                description=str(row["description"]),
                sourceLevel="client",
            )
            for row in state.db.fetchall("SELECT * FROM dna_terms WHERE client_id = ? ORDER BY updated_at DESC", (client_id,))
        ]
        document_cards = [
            build_document_card_record(item)
            for item in fetch_document_cards(state.db, client_id, data_dir=state.data_dir, limit=document_limit)
        ]
        knowledge_jobs = [KnowledgeJobRecord(**item) for item in fetch_recent_knowledge_jobs(state.db, client_id, limit=8)]
        recent_reclass_events = [FileReclassEventRecord(**item) for item in fetch_recent_reclass_events(state.db, client_id, limit=8)]
        knowledge_status = build_knowledge_status_record(client_id)
        notebook_summary = get_client_notebook_response(state.db, client_id).organizationNotebookSnapshot
        memory_status = get_client_memory_status(state.db, client_id)
        related_tasks = fetch_tasks(
            """
            t.client_id = ?
            OR t.event_line_id IN (SELECT id FROM event_lines WHERE primary_client_id = ?)
            OR t.source_id = ?
            OR t.source_id IN (SELECT id FROM meetings WHERE client_id = ?)
            """,
            (client_id, client_id, client_id, client_id),
        )
        workspace_seed = ClientWorkspaceResponse(
            client=client,
            folders=folders,
            documents=documents,
            documentCards=document_cards,
            imports=imports,
            knowledgeStatus=knowledge_status,
            knowledgeJobs=knowledge_jobs,
            recentReclassEvents=recent_reclass_events,
            surrogateCount=knowledge_status.surrogateCount,
            memoryDocCount=knowledge_status.memoryDocCount,
            threads=threads,
            recentMessages=messages,
            analysisRuns=analysis_runs,
            meetings=meetings,
            goals=goals,
            dnaModules=dna_modules,
            projectModules=project_modules,
            projectFlows=project_flows,
            dnaTerms=dna_terms,
            relatedTasks=related_tasks,
            notebookSummary=notebook_summary,
            memoryStatus=memory_status,
        )
        analysis_projection = get_client_analysis_bundle(state.db, workspace_seed)
        main_chain_settings = get_main_chain_stability_settings()
        workspace_response = ClientWorkspaceResponse(
            client=client,
            folders=folders,
            documents=documents,
            documentCards=document_cards,
            imports=imports,
            knowledgeStatus=knowledge_status,
            knowledgeJobs=knowledge_jobs,
            recentReclassEvents=recent_reclass_events,
            surrogateCount=knowledge_status.surrogateCount,
            memoryDocCount=knowledge_status.memoryDocCount,
            threads=threads,
            recentMessages=messages,
            analysisRuns=analysis_runs,
            meetings=meetings,
            goals=goals,
            dnaModules=dna_modules,
            projectModules=project_modules,
            projectFlows=project_flows,
            dnaTerms=dna_terms,
            relatedTasks=related_tasks,
            notebookSummary=notebook_summary,
            memoryStatus=memory_status,
            analysisCenter=analysis_projection.summary,
            latestContextPack=analysis_projection.latest_context_pack,
            judgmentBundle=analysis_projection.judgment_bundle,
            latestResolutionTrace=analysis_projection.latest_resolution_trace,
            latestJudgments=[] if main_chain_settings.latestJudgmentsShadowOff else analysis_projection.latest_judgments,
            latestTopics=analysis_projection.latest_topics,
            latestConflicts=analysis_projection.latest_conflicts,
            latestOpenQuestions=analysis_projection.latest_open_questions,
            latestRunLogs=analysis_projection.latest_run_logs,
        )
        workspace_response.stateProjection = build_workspace_state_projection(workspace_response)
        return workspace_response

    def _workspace_state_compact(value: str | None, *, limit: int = 88) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 1)].rstrip()}…"

    def _workspace_state_date_label(value: str | None) -> str:
        if not value:
            return "最近"
        raw = str(value).strip()
        return raw[:10] if len(raw) >= 10 else raw

    def _workspace_state_payload_summary(payload: dict[str, object]) -> str:
        for key in ("summary", "headline", "overview", "currentFocus", "mainFinding", "situation"):
            raw = payload.get(key)
            if isinstance(raw, str) and raw.strip():
                return _workspace_state_compact(raw, limit=120)
        for key in ("highlights", "keyPoints", "signals", "focusItems"):
            raw = payload.get(key)
            if isinstance(raw, list):
                items = [_workspace_state_compact(str(item), limit=40) for item in raw if str(item).strip()]
                if items:
                    return "；".join(items[:3])
        if payload:
            compact_json = _workspace_state_compact(json.dumps(payload, ensure_ascii=False), limit=120)
            if compact_json:
                return compact_json
        return ""

    def _workspace_state_first_text(*values: object, fallback: str = "") -> str:
        for raw in values:
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return fallback

    def _workspace_state_safe_json(value: object, *, limit: int = 160) -> str:
        if value in (None, "", {}, []):
            return ""
        try:
            serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            serialized = repr(value)
        return _workspace_state_compact(serialized, limit=limit)

    def _workspace_state_normalize_run_log(run_log: RuntimeRunLogRecord) -> dict[str, str | bool]:
        detail = run_log.detail if isinstance(run_log.detail, dict) else {}
        latest_change_summary = _workspace_state_compact(
            _workspace_state_first_text(
                detail.get("latestRunSummary"),
                detail.get("outputSummary"),
                run_log.summary,
                fallback="",
            ),
            limit=96,
        )
        title = _workspace_state_compact(
            _workspace_state_first_text(
                run_log.summary,
                fallback="最近分析运行",
            ),
            limit=48,
        )
        noise_haystack = " ".join(
            part
            for part in (
                title,
                latest_change_summary,
                _workspace_state_safe_json(detail, limit=160),
            )
            if part
        )
        noise_terms = (
            "generic",
            "运维",
            "索引",
            "缓存",
            "导入",
            "fallback",
            "retry",
            "sync",
            "pipeline",
            "job",
            "queue",
        )
        return {
            "title": title,
            "latestChangeSummary": latest_change_summary,
            "noiseHaystack": noise_haystack,
            "isLikelyNoise": any(term in noise_haystack.lower() for term in noise_terms),
            "runId": run_log.id,
            "createdAt": run_log.createdAt,
        }

    def _workspace_bundle_judgment_candidates(workspace: ClientWorkspaceResponse) -> list[JudgmentVersionRecord]:
        judgment_candidates: list[JudgmentVersionRecord] = []
        seen: set[str] = set()
        for item in [
            *([workspace.judgmentBundle.baselineJudgment] if workspace.judgmentBundle and workspace.judgmentBundle.baselineJudgment else []),
            *(workspace.judgmentBundle.overlayDeltas if workspace.judgmentBundle else []),
        ]:
            if not item or item.id in seen:
                continue
            seen.add(item.id)
            judgment_candidates.append(item)
        return judgment_candidates

    def _workspace_state_is_polluted_judgment(item: JudgmentVersionRecord) -> bool:
        return looks_like_attachment_ingest_boilerplate(item.summary)

    def _workspace_state_judgments(workspace: ClientWorkspaceResponse) -> tuple[list[JudgmentVersionRecord], list[JudgmentVersionRecord]]:
        judgment_candidates = [
            item
            for item in _workspace_bundle_judgment_candidates(workspace)
            if not _workspace_state_is_polluted_judgment(item)
        ]
        approved = [
            item
            for item in judgment_candidates
            if item.authorityLevel == "approved" or item.status == "approved"
        ]
        approved_ids = {item.id for item in approved}
        candidates = [item for item in judgment_candidates if item.id not in approved_ids]
        return approved, candidates

    def _workspace_run_log_is_noise(run_log: RuntimeRunLogRecord) -> bool:
        normalized = _workspace_state_normalize_run_log(run_log)
        return bool(normalized["isLikelyNoise"])

    def build_workspace_state_projection(workspace: ClientWorkspaceResponse) -> WorkspaceStateProjectionRecord:
        change_items: list[WorkspaceStateItemRecord] = []
        progress_items: list[WorkspaceStateItemRecord] = []
        signal_noise_flags: list[str] = []
        boundary_notes: list[str] = []
        seen_keys: set[str] = set()

        def push(bucket: list[WorkspaceStateItemRecord], item: WorkspaceStateItemRecord) -> None:
            key = f"{item.signalType}:{item.sourceType}:{item.sourceId}:{item.title}"
            if key in seen_keys:
                return
            seen_keys.add(key)
            bucket.append(item)

        raw_bundle_judgments = _workspace_bundle_judgment_candidates(workspace)
        approved_judgments, candidate_judgments = _workspace_state_judgments(workspace)
        if workspace.latestContextPack:
            context_summary = _workspace_state_payload_summary(workspace.latestContextPack.payload)
            if context_summary:
                push(
                    change_items,
                    WorkspaceStateItemRecord(
                        id=workspace.latestContextPack.id,
                        signalType="change",
                        sourceType="context_pack",
                        sourceId=workspace.latestContextPack.id,
                        title="最新状态包",
                        summary=context_summary,
                        authority="approved" if workspace.latestContextPack.authorityLevel == "approved" else "candidate",
                        updatedAt=workspace.latestContextPack.updatedAt,
                    ),
                )

        for item in approved_judgments[:3]:
            push(
                change_items,
                WorkspaceStateItemRecord(
                    id=item.id,
                    signalType="judgment",
                    sourceType="judgment",
                    sourceId=item.id,
                    title=item.topic,
                    summary=_workspace_state_compact(item.summary, limit=120),
                    authority="approved",
                    updatedAt=item.updatedAt,
                ),
            )
        for item in candidate_judgments[:3]:
            push(
                change_items,
                WorkspaceStateItemRecord(
                    id=item.id,
                    signalType="judgment",
                    sourceType="judgment",
                    sourceId=item.id,
                    title=item.topic,
                    summary=_workspace_state_compact(item.summary, limit=120),
                    authority="candidate",
                    updatedAt=item.updatedAt,
                ),
            )
        for meeting in workspace.meetings[:3]:
            push(
                change_items,
                WorkspaceStateItemRecord(
                    id=meeting.id,
                    signalType="meeting",
                    sourceType="meeting",
                    sourceId=meeting.id,
                    title=meeting.title,
                    summary=f"{_workspace_state_date_label(meeting.updatedAt or meeting.scheduledAt)} · 阶段 {meeting.stage}",
                    authority="approved" if meeting.stage in {"resolved", "published"} else "informational",
                    updatedAt=meeting.updatedAt,
                ),
            )
        active_tasks = [task for task in workspace.relatedTasks if task.status in {"doing", "todo"}]
        done_tasks = [task for task in workspace.relatedTasks if task.status == "done"]
        for task in active_tasks[:4]:
            progress_bits = [task.nextAction, task.currentBlocker, task.recentDecision, task.desc]
            progress_summary = next((_workspace_state_compact(item, limit=120) for item in progress_bits if item and str(item).strip()), "")
            push(
                progress_items,
                WorkspaceStateItemRecord(
                    id=task.id,
                    signalType="task",
                    sourceType="task",
                    sourceId=task.id,
                    title=task.title,
                    summary=progress_summary or f"状态 {task.status}",
                    authority="informational",
                    updatedAt=task.updatedAt,
                ),
            )
        for task in done_tasks[:2]:
            push(
                progress_items,
                WorkspaceStateItemRecord(
                    id=task.id,
                    signalType="progress",
                    sourceType="task",
                    sourceId=task.id,
                    title=task.title,
                    summary=_workspace_state_compact(task.recentDecision or task.desc or "任务已完成", limit=120),
                    authority="informational",
                    updatedAt=task.updatedAt,
                ),
            )
        for item in workspace.latestConflicts[:3]:
            push(
                change_items,
                WorkspaceStateItemRecord(
                    id=item.id,
                    signalType="risk",
                    sourceType="conflict",
                    sourceId=item.id,
                    title=item.title,
                    summary=_workspace_state_compact(item.summary, limit=120),
                    authority="warning",
                    updatedAt=item.updatedAt,
                ),
            )
        for item in workspace.latestOpenQuestions[:3]:
            question_summary = item.question
            if item.reason:
                question_summary = f"{item.question}；原因：{item.reason}"
            push(
                change_items,
                WorkspaceStateItemRecord(
                    id=item.id,
                    signalType="question",
                    sourceType="open_question",
                    sourceId=item.id,
                    title=_workspace_state_compact(item.question, limit=40),
                    summary=_workspace_state_compact(question_summary, limit=120),
                    authority="warning" if item.blockerLevel == "high" else "candidate",
                    updatedAt=item.updatedAt,
                ),
            )
        for item in workspace.latestRunLogs[:3]:
            normalized = _workspace_state_normalize_run_log(item)
            latest_change = str(normalized["latestChangeSummary"] or "")
            if _workspace_run_log_is_noise(item):
                if latest_change:
                    signal_noise_flags.append(latest_change)
                continue
            if latest_change:
                push(
                    progress_items,
                    WorkspaceStateItemRecord(
                        id=item.id,
                        signalType="change",
                        sourceType="run_log",
                        sourceId=item.id,
                        title=str(normalized["title"]),
                        summary=latest_change,
                        authority="informational",
                        updatedAt=str(normalized["createdAt"]),
                    ),
                )

        if not approved_judgments:
            boundary_notes.append("当前还没有足够稳定的正式判断，待确认判断不能当作既成事实。")
        if workspace.latestOpenQuestions:
            boundary_notes.append("存在未决问题，回答时需要把风险和缺失信息与正式结论分开。")
        if not active_tasks and not workspace.meetings:
            boundary_notes.append("最近缺少任务或会议推进信号，涉及时间推进的问题可能只能回答到资料层。")
        if signal_noise_flags:
            boundary_notes.append("generic 运维信号和弱相关日志已被降噪，不作为主回答依据。")

        state_confidence: Literal["low", "medium", "high"] = "low"
        if approved_judgments and (active_tasks or workspace.meetings):
            state_confidence = "high"
        elif change_items or progress_items:
            state_confidence = "medium"
        return WorkspaceStateProjectionRecord(
            changeItems=change_items[:8],
            progressItems=progress_items[:8],
            signalNoiseFlags=list(dict.fromkeys(signal_noise_flags))[:6],
            boundaryNotes=list(dict.fromkeys(boundary_notes))[:5],
            stateConfidence=state_confidence,
        )

    def build_state_query_plan(prompt: str) -> StateQueryPlanRecord:
        normalized = re.sub(r"\s+", "", str(prompt or ""))
        primary_intent: Literal["overview", "changes", "progress", "risk", "questions", "judgment", "timeline"] = "overview"
        if any(token in normalized for token in ("最近", "变化", "更新", "发生了什么")):
            primary_intent = "changes"
        if any(
            token in normalized
            for token in (
                "本周",
                "推进",
                "进展",
                "在做什么",
                "下一步",
                "最重要",
                "重点",
                "优先",
                "最值得关注",
                "关注点",
                "关注事项",
            )
        ):
            primary_intent = "progress"
        if any(token in normalized for token in ("风险", "卡点", "阻力", "阻塞", "blocker")):
            primary_intent = "risk"
        if any(token in normalized for token in ("待确认", "未决", "不知道", "问题", "缺口", "不足")):
            primary_intent = "questions"
        if any(token in normalized for token in ("判断", "结论", "怎么看", "dna")):
            primary_intent = "judgment"
        if any(token in normalized for token in ("时间线", "先后", "timeline")):
            primary_intent = "timeline"

        focus_areas: list[str] = []
        if any(token in normalized for token in ("会议", "纪要", "会里")):
            focus_areas.append("meetings")
        if any(token in normalized for token in ("任务", "推进", "待办", "动作", "下一步", "最重要", "重点", "优先", "关注")):
            focus_areas.append("tasks")
        if any(token in normalized for token in ("判断", "结论", "dna")):
            focus_areas.append("judgments")
        if any(token in normalized for token in ("风险", "卡点", "阻塞", "blocker")):
            focus_areas.append("risks")
        if any(token in normalized for token in ("待确认", "未决", "缺失", "缺口", "不足")):
            focus_areas.append("questions")
        if not focus_areas:
            focus_areas = ["judgments", "tasks", "meetings", "risks", "questions"]
        return StateQueryPlanRecord(
            primaryIntent=primary_intent,
            focusAreas=focus_areas,
            needsBoundaryGuard=True,
        )

    def build_state_answer_context_pack(workspace: ClientWorkspaceResponse, prompt: str) -> StateAnswerContextPackRecord:
        projection = workspace.stateProjection or build_workspace_state_projection(workspace)
        raw_bundle_judgments = _workspace_bundle_judgment_candidates(workspace)
        approved_judgments, candidate_judgments = _workspace_state_judgments(workspace)
        active_tasks = [task for task in workspace.relatedTasks if task.status in {"doing", "todo"}]
        completed_tasks = [task for task in workspace.relatedTasks if task.status == "done"]
        plan = build_state_query_plan(prompt)
        hits: list[StateQueryHitRecord] = []
        seen: set[str] = set()

        def add_hit(
            *,
            source_type: str,
            source_id: str,
            label: str,
            summary: str,
            signal_kind: Literal["change", "progress", "risk", "question", "judgment", "timeline"],
            authority_level: Literal["approved", "candidate", "informational", "warning"] = "informational",
        ) -> None:
            key = f"{source_type}:{source_id}:{signal_kind}:{label}"
            if key in seen or not summary.strip():
                return
            seen.add(key)
            hits.append(
                StateQueryHitRecord(
                    sourceType=source_type,
                    sourceId=source_id,
                    label=label,
                    summary=_workspace_state_compact(summary, limit=144),
                    signalKind=signal_kind,
                    authorityLevel=authority_level,
                )
            )

        for item in approved_judgments[:3]:
            add_hit(
                source_type="judgment",
                source_id=item.id,
                label=item.topic,
                summary=item.summary,
                signal_kind="judgment",
                authority_level="approved",
            )
        for item in candidate_judgments[:3]:
            add_hit(
                source_type="judgment",
                source_id=item.id,
                label=item.topic,
                summary=item.summary,
                signal_kind="judgment",
                authority_level="candidate",
            )
        for task in active_tasks[:4]:
            add_hit(
                source_type="task",
                source_id=task.id,
                label=task.title,
                summary=task.nextAction or task.currentBlocker or task.recentDecision or task.desc or f"状态 {task.status}",
                signal_kind="progress",
                authority_level="informational",
            )
        for task in completed_tasks[:2]:
            add_hit(
                source_type="task",
                source_id=task.id,
                label=task.title,
                summary=task.recentDecision or task.desc or "最近已完成",
                signal_kind="progress",
                authority_level="informational",
            )
        for meeting in workspace.meetings[:3]:
            add_hit(
                source_type="meeting",
                source_id=meeting.id,
                label=meeting.title,
                summary=f"{_workspace_state_date_label(meeting.updatedAt or meeting.scheduledAt)} · 阶段 {meeting.stage}",
                signal_kind="timeline" if plan.primaryIntent in {"timeline", "changes"} else "change",
                authority_level="approved" if meeting.stage in {"resolved", "published"} else "informational",
            )
        for item in workspace.latestConflicts[:3]:
            add_hit(
                source_type="conflict",
                source_id=item.id,
                label=item.title,
                summary=item.summary,
                signal_kind="risk",
                authority_level="warning",
            )
        for item in workspace.latestOpenQuestions[:3]:
            add_hit(
                source_type="open_question",
                source_id=item.id,
                label=item.question,
                summary=item.reason or item.question,
                signal_kind="question",
                authority_level="warning" if item.blockerLevel == "high" else "candidate",
            )
        for item in workspace.latestRunLogs[:2]:
            if _workspace_run_log_is_noise(item):
                continue
            normalized = _workspace_state_normalize_run_log(item)
            add_hit(
                source_type="run_log",
                source_id=item.id,
                label=str(normalized["title"]),
                summary=str(normalized["latestChangeSummary"] or ""),
                signal_kind="change",
                authority_level="informational",
            )

        approved_lines = [
            f"{item.topic}：{_workspace_state_compact(item.summary, limit=100)}"
            for item in approved_judgments[:3]
            if _workspace_state_compact(item.summary, limit=100)
        ]
        candidate_lines = [
            f"{item.topic}：{_workspace_state_compact(item.summary, limit=100)}"
            for item in candidate_judgments[:3]
            if _workspace_state_compact(item.summary, limit=100)
        ]
        task_action_lines = [
            f"{task.title}：{_workspace_state_compact(task.nextAction or task.currentBlocker or task.recentDecision or task.desc or task.status, limit=100)}"
            for task in (active_tasks[:3] + completed_tasks[:1])
        ]
        meeting_action_lines = [
            f"{meeting.title}：{_workspace_state_date_label(meeting.updatedAt or meeting.scheduledAt)} · 阶段 {meeting.stage}"
            for meeting in workspace.meetings[:2]
        ]
        action_lines = list(task_action_lines)
        if plan.primaryIntent in {"changes", "timeline"}:
            action_lines = list(dict.fromkeys(meeting_action_lines + task_action_lines))
        risk_lines = [
            f"{_workspace_state_compact(item.title, limit=40)}：{_workspace_state_compact(item.summary, limit=96)}"
            for item in workspace.latestConflicts[:3]
        ]
        unknown_lines = [
            f"{_workspace_state_compact(item.question, limit=52)}"
            + (f"：{_workspace_state_compact(item.reason, limit=88)}" if item.reason else "")
            for item in workspace.latestOpenQuestions[:3]
        ]
        if projection.signalNoiseFlags:
            unknown_lines.append(f"已降噪的弱相关信号：{'；'.join(projection.signalNoiseFlags[:2])}")
        if not approved_lines:
            unknown_lines.append("目前没有足够稳定的正式判断，candidate 只能作为提醒。")
        if not action_lines and workspace.meetings:
            action_lines = meeting_action_lines

        sections_record = StateAnswerSectionsRecord(
            official=approved_lines[:4],
            candidate=candidate_lines[:4],
            actions=action_lines[:4],
            risks=risk_lines[:4],
            unknowns=unknown_lines[:4],
        )
        source_summary = StateSourceSummaryRecord(
            judgments=sum(1 for hit in hits if hit.sourceType == "judgment"),
            meetings=sum(1 for hit in hits if hit.sourceType == "meeting"),
            tasks=sum(1 for hit in hits if hit.sourceType == "task"),
            openQuestions=sum(1 for hit in hits if hit.sourceType == "open_question"),
            conflicts=sum(1 for hit in hits if hit.sourceType == "conflict"),
            documents=0,
        )
        polluted_candidate_count = sum(
            1
            for item in raw_bundle_judgments
            if _workspace_state_is_polluted_judgment(item)
        )
        candidate_leakage_count = polluted_candidate_count + (1 if any(
            hit.authorityLevel != "approved"
            for hit in hits
            if hit.sourceType == "judgment" and any(hit.summary in section for section in sections_record.official)
        ) else 0)
        sections: list[str] = []
        if sections_record.official:
            sections.append("[正式判断]\n" + "\n".join(f"- {item}" for item in sections_record.official))
        if sections_record.candidate:
            sections.append("[待确认判断]\n" + "\n".join(f"- {item}" for item in sections_record.candidate))
        if sections_record.actions:
            sections.append("[本周动作]\n" + "\n".join(f"- {item}" for item in sections_record.actions))
        if sections_record.risks:
            sections.append("[风险提醒]\n" + "\n".join(f"- {item}" for item in sections_record.risks))
        if sections_record.unknowns:
            sections.append("[缺失信息]\n" + "\n".join(f"- {item}" for item in sections_record.unknowns))

        state_sources = list(dict.fromkeys(hit.sourceType for hit in hits))
        fallback_reason = None if hits else "state_pool_empty"
        summary = ""
        if sections:
            summary = (
                "客户状态池（analysis-first，优先作为回答依据，不要退回到纯资料摘录）：\n"
                + "\n\n".join(sections)
            )[:2200]
        return StateAnswerContextPackRecord(
            plan=plan,
            summary=summary,
            stateSources=state_sources,
            boundaryNotes=projection.boundaryNotes,
            stateConfidence=projection.stateConfidence,
            hits=hits[:12],
            sections=sections_record,
            sourceSummary=source_summary,
            candidateLeakageCount=candidate_leakage_count,
            fallbackReason=fallback_reason,
        )

    def _hybrid_add_unique(lines: list[str], value: str | None, *, limit: int = 120) -> None:
        text = _workspace_state_compact(value, limit=limit) if value else ""
        if text and text not in lines:
            lines.append(text)

    def _hybrid_dna_staleness_note(updated_at: str | None, *, stale_after_days: int = 180) -> tuple[bool, str | None]:
        moment = _parse_iso_moment(updated_at)
        if moment is None:
            return False, None
        if moment.tzinfo is not None:
            moment = moment.astimezone().replace(tzinfo=None)
        age_days = max((datetime.now() - moment).days, 0)
        if age_days < stale_after_days:
            return False, None
        return True, f"{moment.strftime('%Y-%m-%d')} 更新，当前偏旧，仅作弱支撑"

    def _fetch_context_pack_summaries(client_id: str, context_pack_ids: list[str]) -> dict[str, tuple[str, str | None]]:
        if not context_pack_ids:
            return {}
        unique_ids = list(dict.fromkeys([item for item in context_pack_ids if item]))
        placeholders = _sql_placeholders(unique_ids)
        rows = state.db.fetchall(
            f"""
            SELECT id, payload_json, updated_at
            FROM context_packs
            WHERE client_id = ? AND id IN ({placeholders})
            """,
            (client_id, *unique_ids),
        )
        output: dict[str, tuple[str, str | None]] = {}
        for row in rows:
            payload = from_json(str(row["payload_json"] or "{}"), {})
            summary = _workspace_state_payload_summary(payload if isinstance(payload, dict) else {})
            if summary:
                output[str(row["id"])] = (summary, str(row["updated_at"]) if row["updated_at"] else None)
        return output

    def _fetch_evidence_support_items(client_id: str, evidence_ids: list[str]) -> list[EvidenceSupportItemRecord]:
        if not evidence_ids:
            return []
        unique_ids = list(dict.fromkeys([item for item in evidence_ids if item]))
        placeholders = _sql_placeholders(unique_ids)
        rows = state.db.fetchall(
            f"""
            SELECT id, source_type, source_id, source_ref, quote, normalized_claim, confidence, time_anchor, review_state, updated_at
            FROM evidence_cards
            WHERE client_id = ? AND id IN ({placeholders})
            ORDER BY updated_at DESC
            """,
            (client_id, *unique_ids),
        )
        items: list[EvidenceSupportItemRecord] = []
        for row in rows:
            summary = _workspace_state_compact(
                str(row["normalized_claim"] or row["quote"] or "").strip(),
                limit=120,
            )
            if not summary:
                continue
            review_state = str(row["review_state"] or "").strip().lower()
            authority: Literal["approved", "candidate", "radar", "raw"] = (
                "approved"
                if review_state == "approved"
                else "candidate"
                if review_state in {"candidate", "pending_review", "awaiting_review", "draft"}
                else "radar"
            )
            items.append(
                EvidenceSupportItemRecord(
                    title=_workspace_state_compact(str(row["source_ref"] or row["source_type"] or "证据卡"), limit=48),
                    summary=summary,
                    sourceType="evidence_card",
                    sourceId=str(row["id"]),
                    sourceRef=str(row["source_ref"] or "") or None,
                    authority=authority,
                    timeAnchor=str(row["time_anchor"]) if row["time_anchor"] else (str(row["updated_at"]) if row["updated_at"] else None),
                    confidence=float(row["confidence"] or 0.0) if row["confidence"] is not None else None,
                )
            )
        return items

    def _build_linked_evidence_support_items(
        workspace: ClientWorkspaceResponse,
        prompt: str,
    ) -> list[EvidenceSupportItemRecord]:
        approved_judgments, candidate_judgments = _workspace_state_judgments(workspace)
        evidence_ids: list[str] = []
        context_pack_ids: list[str] = []
        for item in [*approved_judgments[:4], *candidate_judgments[:4]]:
            evidence_ids.extend(item.evidenceIds[:6])
            if item.contextPackId:
                context_pack_ids.append(item.contextPackId)
        for item in workspace.latestConflicts[:3]:
            evidence_ids.extend(item.evidenceIds[:4])
        if workspace.latestContextPack:
            context_pack_ids.append(workspace.latestContextPack.id)

        support_items = _fetch_evidence_support_items(workspace.client.id, evidence_ids)
        context_summaries = _fetch_context_pack_summaries(workspace.client.id, context_pack_ids)
        for context_pack_id, (summary, updated_at) in context_summaries.items():
            support_items.append(
                EvidenceSupportItemRecord(
                    title="状态包摘要",
                    summary=summary,
                    sourceType="context_pack",
                    sourceId=context_pack_id,
                    sourceRef=context_pack_id,
                    authority="candidate",
                    timeAnchor=updated_at,
                )
            )

        prompt_tokens = tokenize(prompt)

        def module_rank(module: ClientDnaModuleRecord) -> tuple[int, int, str]:
            text = f"{module.title}\n{module.summary}\n{module.normalizedText[:1200]}".lower()
            match_count = sum(1 for token in prompt_tokens if token and token in text)
            return (1 if match_count > 0 else 0, match_count, module.updatedAt or "")

        dna_modules = sorted(
            [module for module in workspace.dnaModules if module.hasDocument and (module.summary.strip() or module.normalizedText.strip())],
            key=module_rank,
            reverse=True,
        )
        for module in dna_modules[:3]:
            module_summary = _workspace_state_compact(module.summary or module.normalizedText, limit=112)
            dna_confidence = 0.62
            is_stale_dna, stale_note = _hybrid_dna_staleness_note(module.updatedAt)
            if is_stale_dna and stale_note:
                module_summary = _workspace_state_compact(f"{module_summary}（{stale_note}）", limit=120)
                dna_confidence = 0.35
            support_items.append(
                EvidenceSupportItemRecord(
                    title=_workspace_state_compact(module.title, limit=48),
                    summary=module_summary,
                    sourceType="dna",
                    sourceId=module.moduleKey,
                    sourceRef=module.fileName or module.title,
                    authority="candidate",
                    timeAnchor=module.updatedAt,
                    confidence=dna_confidence,
                )
            )

        for meeting in workspace.meetings[:3]:
            support_items.append(
                EvidenceSupportItemRecord(
                    title=_workspace_state_compact(meeting.title, limit=48),
                    summary=f"{_workspace_state_date_label(meeting.updatedAt or meeting.scheduledAt)} · 阶段 {meeting.stage}",
                    sourceType="meeting",
                    sourceId=meeting.id,
                    sourceRef=meeting.title,
                    authority="radar",
                    timeAnchor=meeting.updatedAt or meeting.scheduledAt,
                )
            )

        active_tasks = [task for task in workspace.relatedTasks if task.status in {"doing", "todo"}]
        for task in active_tasks[:3]:
            task_support = (
                (task.projectContext.sourceEvidence[0] if task.projectContext and task.projectContext.sourceEvidence else "")
                or task.nextAction
                or task.currentBlocker
                or task.recentDecision
                or task.desc
            )
            if not str(task_support or "").strip():
                continue
            support_items.append(
                EvidenceSupportItemRecord(
                    title=_workspace_state_compact(task.title, limit=48),
                    summary=_workspace_state_compact(str(task_support), limit=120),
                    sourceType="task",
                    sourceId=task.id,
                    sourceRef=task.title,
                    authority="radar",
                    timeAnchor=task.updatedAt,
                )
            )

        for item in workspace.latestOpenQuestions[:2]:
            support_items.append(
                EvidenceSupportItemRecord(
                    title=_workspace_state_compact(item.question, limit=48),
                    summary=_workspace_state_compact(item.reason or item.question, limit=120),
                    sourceType="open_question",
                    sourceId=item.id,
                    sourceRef=item.question,
                    authority="radar",
                    timeAnchor=item.updatedAt,
                )
            )

        for item in workspace.latestConflicts[:2]:
            support_items.append(
                EvidenceSupportItemRecord(
                    title=_workspace_state_compact(item.title, limit=48),
                    summary=_workspace_state_compact(item.summary, limit=120),
                    sourceType="conflict",
                    sourceId=item.id,
                    sourceRef=item.title,
                    authority="radar",
                    timeAnchor=item.updatedAt,
                )
            )

        deduped: list[EvidenceSupportItemRecord] = []
        seen: set[str] = set()
        for item in support_items:
            key = f"{item.sourceType}:{item.sourceId or item.title}:{item.summary}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:10]

    def _linked_support_items_to_retrieval_bundle(
        support_items: list[EvidenceSupportItemRecord],
        *,
        evidence_support_mode: EvidenceSupportMode,
    ):
        return deserialize_retrieval_bundle(
            {
                "citations": [
                    {
                        "knowledge_document_id": item.sourceId or f"linked-{index}",
                        "chunk_id": None,
                        "title": item.title,
                        "excerpt": item.summary,
                        "score": float(item.confidence or 0.72),
                        "coverage": 0.12,
                        "section_label": item.sourceRef,
                        "source_stage": "surrogate",
                        "drillthrough_used": False,
                        "matched_terms": [],
                        "path": item.sourceRef,
                    }
                    for index, item in enumerate(support_items, start=1)
                ],
                "coverage": min(1.0, 0.18 * len(support_items)),
                "retrieval_summary": {
                    "linkedEvidenceCount": len(support_items),
                    "linkedEvidenceTrail": [
                        {
                            "title": item.title,
                            "summary": item.summary,
                            "sourceType": item.sourceType,
                            "sourceRef": item.sourceRef or "",
                            "authority": item.authority,
                        }
                        for item in support_items
                    ],
                    "evidenceSupportMode": evidence_support_mode,
                },
                "context_text": "\n".join(f"{item.title}：{item.summary}" for item in support_items),
                "matched_terms": [],
                "failure_reason": None,
            }
        )

    def _merge_retrieval_bundles(primary_bundle, secondary_bundle, *, evidence_support_mode: EvidenceSupportMode):
        primary_payload = serialize_retrieval_bundle(primary_bundle)
        secondary_payload = serialize_retrieval_bundle(secondary_bundle)
        citations_payload = [
            *secondary_payload.get("citations", []),
            *primary_payload.get("citations", []),
        ]
        deduped_citations: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in citations_payload:
            key = "|".join(
                [
                    str(item.get("knowledge_document_id") or ""),
                    str(item.get("chunk_id") or ""),
                    str(item.get("title") or ""),
                    str(item.get("excerpt") or "")[:120],
                ]
            )
            if key in seen:
                continue
            seen.add(key)
            deduped_citations.append(item)
        merged_summary = {
            **(secondary_bundle.retrieval_summary if isinstance(secondary_bundle.retrieval_summary, dict) else {}),
            **(primary_bundle.retrieval_summary if isinstance(primary_bundle.retrieval_summary, dict) else {}),
            "evidenceSupportMode": evidence_support_mode,
            "linkedEvidenceCount": len(primary_bundle.citations),
            "genericEvidenceCount": len(secondary_bundle.citations),
            "linkedEvidenceTrail": (
                (primary_bundle.retrieval_summary or {}).get("linkedEvidenceTrail", [])
                if isinstance(primary_bundle.retrieval_summary, dict)
                else []
            ),
        }
        return deserialize_retrieval_bundle(
            {
                "citations": deduped_citations,
                "coverage": max(float(primary_bundle.coverage or 0.0), float(secondary_bundle.coverage or 0.0)),
                "retrieval_summary": merged_summary,
                "context_text": "\n\n".join(
                    part
                    for part in (
                        str(primary_bundle.context_text or "").strip(),
                        str(secondary_bundle.context_text or "").strip(),
                    )
                    if part
                ),
                "matched_terms": list(dict.fromkeys([*primary_bundle.matched_terms, *secondary_bundle.matched_terms])),
                "failure_reason": secondary_bundle.failure_reason or primary_bundle.failure_reason,
            }
        )

    def _build_hybrid_synthesized_candidate_findings(
        workspace: ClientWorkspaceResponse,
        support_items: list[EvidenceSupportItemRecord],
        *,
        registered_candidate_judgments: list[str],
    ) -> list[str]:
        if registered_candidate_judgments:
            return []
        findings: list[str] = []
        if workspace.latestContextPack:
            context_summary = _workspace_state_payload_summary(workspace.latestContextPack.payload)
            _hybrid_add_unique(findings, f"基于最新状态包，当前更接近的判断是：{context_summary}", limit=132)
        for item in support_items:
            if item.sourceType in {"dna", "meeting", "task", "evidence_card", "context_pack", "raw_doc"}:
                _hybrid_add_unique(findings, f"现有资料共同指向：{item.summary}", limit=132)
            if len(findings) >= 3:
                break
        return findings[:3]

    def build_hybrid_judgment_context_pack(
        workspace: ClientWorkspaceResponse,
        prompt: str,
        *,
        judgment_query_mode: JudgmentQueryMode,
        evidence_support_mode: EvidenceSupportMode,
        support_items: list[EvidenceSupportItemRecord],
        evidence: list[EvidenceItem],
    ) -> HybridJudgmentContextPackRecord:
        projection = workspace.stateProjection or build_workspace_state_projection(workspace)
        approved_judgments, candidate_judgments = _workspace_state_judgments(workspace)
        approved_lines = [
            f"{item.topic}：{_workspace_state_compact(item.summary, limit=108)}"
            for item in approved_judgments[:4]
            if _workspace_state_compact(item.summary, limit=108)
        ]
        registered_candidate_lines = [
            f"{item.topic}：{_workspace_state_compact(item.summary, limit=108)}"
            for item in candidate_judgments[:4]
            if _workspace_state_compact(item.summary, limit=108)
        ]
        synthesized_candidate_findings = _build_hybrid_synthesized_candidate_findings(
            workspace,
            support_items,
            registered_candidate_judgments=registered_candidate_lines,
        )
        dna_signals = [
            f"{item.title}：{item.summary}"
            for item in support_items
            if item.sourceType == "dna"
        ][:3]
        meeting_signals = [
            f"{item.title}：{item.summary}"
            for item in support_items
            if item.sourceType == "meeting"
        ][:3]
        task_signals = [
            f"{item.title}：{item.summary}"
            for item in support_items
            if item.sourceType == "task"
        ][:3]
        open_question_signals = [
            f"{item.title}：{item.summary}"
            for item in support_items
            if item.sourceType == "open_question"
        ][:3]
        conflict_signals = [
            f"{item.title}：{item.summary}"
            for item in support_items
            if item.sourceType == "conflict"
        ][:3]
        evidence_support_lines = [
            f"{item.title}：{item.summary}"
            + (f"（{item.sourceType}）" if item.sourceType not in {"task", "meeting", "dna"} else "")
            for item in support_items[:6]
        ]
        raw_excerpts = [
            f"{item.title}：{_workspace_state_compact(item.excerpt, limit=120)}"
            for item in evidence
            if item.retrievalStage == "raw_chunk" and _workspace_state_compact(item.excerpt, limit=120)
        ][:5]
        if raw_excerpts:
            evidence_support_lines = list(dict.fromkeys([*evidence_support_lines, *raw_excerpts[:3]]))
        actions = list(dict.fromkeys([*task_signals, *meeting_signals]))[:4]
        risks = list(dict.fromkeys([*conflict_signals, *open_question_signals]))[:4]
        unknowns = list(dict.fromkeys([
            *projection.boundaryNotes,
            *(
                [
                    "当前系统内已批准的正式判断仍为空；如需进入正式层，需要走判断提案或审批流程。"
                    if not approved_lines
                    else ""
                ]
            ),
            *(
                [
                    "当前缺少更直接的支撑证据；建议补相关会议纪要、任务上下文或原始资料摘录。"
                    if not evidence_support_lines
                    else ""
                ]
            ),
            *(
                [
                    "建议下一步：如需沉淀为正式层，请生成 judgment proposal 并补充引用证据。"
                    if registered_candidate_lines or synthesized_candidate_findings
                    else "建议下一步：先补齐资料、会议或任务上下文，再形成可提交确认的判断草稿。"
                ]
            ),
        ]))
        unknowns = [item for item in unknowns if item][:4]
        sections = StateAnswerSectionsRecord(
            official=approved_lines[:4],
            candidate=registered_candidate_lines[:4],
            draftFindings=synthesized_candidate_findings[:4],
            evidenceSupport=evidence_support_lines[:6],
            actions=actions,
            risks=risks,
            unknowns=unknowns,
        )
        summary_blocks: list[str] = [
            f"用户问题：{prompt}",
            "Judgment 回答模式：analysis-first hybrid。正式判断只来自已批准 registry；待确认判断需要明确区分已登记候选与本次综合草稿。",
            "[已登记正式判断]\n" + ("\n".join(f"- {item}" for item in sections.official) if sections.official else "- 当前暂无已登记正式判断。"),
            "[待确认判断 / 判断草稿]\n"
            + (
                "\n".join(
                    f"- {item}"
                    for item in [*sections.candidate, *sections.draftFindings]
                )
                if sections.candidate or sections.draftFindings
                else "- 当前还没有足够支撑形成待确认判断或判断草稿。"
            ),
            "[支撑证据摘要]\n" + ("\n".join(f"- {item}" for item in sections.evidenceSupport) if sections.evidenceSupport else "- 当前还没有稳定的支撑证据摘要。"),
            "[本周动作 / 当前推进]\n" + ("\n".join(f"- {item}" for item in sections.actions) if sections.actions else "- 当前暂无可展示内容。"),
            "[风险提醒 / 未决问题]\n" + ("\n".join(f"- {item}" for item in sections.risks) if sections.risks else "- 当前暂无可展示内容。"),
            "[缺失信息 / 下一步建议]\n" + ("\n".join(f"- {item}" for item in sections.unknowns) if sections.unknowns else "- 当前暂无可展示内容。"),
        ]
        if raw_excerpts:
            summary_blocks.append("[原文回引]\n" + "\n".join(f"- {item}" for item in raw_excerpts))
        source_summary = StateSourceSummaryRecord(
            judgments=len(approved_lines) + len(registered_candidate_lines),
            meetings=len(meeting_signals),
            tasks=len(task_signals),
            openQuestions=len(open_question_signals),
            conflicts=len(conflict_signals),
            documents=len(raw_excerpts),
        )
        state_sources = ["judgment"]
        if dna_signals:
            state_sources.append("dna")
        if meeting_signals:
            state_sources.append("meeting")
        if task_signals:
            state_sources.append("task")
        if open_question_signals:
            state_sources.append("open_question")
        if conflict_signals:
            state_sources.append("conflict")

        return HybridJudgmentContextPackRecord(
            judgmentQueryMode=judgment_query_mode,
            evidenceSupportMode=evidence_support_mode,
            summary="\n\n".join(block for block in summary_blocks if block).strip(),
            stateSources=list(dict.fromkeys(state_sources)),
            boundaryNotes=projection.boundaryNotes,
            stateConfidence=projection.stateConfidence,
            sections=sections,
            sourceSummary=source_summary,
            evidenceSupportItems=support_items[:10],
            approvedJudgments=approved_lines,
            registeredCandidateJudgments=registered_candidate_lines,
            synthesizedCandidateFindings=synthesized_candidate_findings,
            dnaSignals=dna_signals,
            meetingSignals=meeting_signals,
            taskSignals=task_signals,
            openQuestionSignals=open_question_signals,
            conflictSignals=conflict_signals,
            rawExcerpts=raw_excerpts,
            unknownsAndNextSteps=unknowns,
            fallbackReason=None if (approved_lines or registered_candidate_lines or synthesized_candidate_findings or evidence_support_lines) else "hybrid_pack_thin",
        )

    def generate_hybrid_judgment_answer(
        prompt: str,
        hybrid_pack: HybridJudgmentContextPackRecord,
        *,
        on_partial=None,
    ) -> AiStructuredResponse:
        instruction = (
            "你是益语智库的客户状态顾问。"
            "当前问题属于 judgment 类 analysis-first hybrid 回答。"
            "请严格区分：已登记正式判断、已登记待确认判断、本次综合出的判断草稿、支撑证据摘要、本周动作、风险提醒、缺失信息与下一步建议。"
            "official 只来自已批准 registry，不能因为资料强就自动上升为正式判断。"
            "判断草稿必须写成“更接近”“可以形成”“仍待确认”这类边界清晰的表述。"
            "不要解释系统过程，不要输出 JSON，不要输出 Markdown 代码块。"
        )
        return state.ai.generate_chat_response(
            prompt,
            instruction,
            hybrid_pack.summary,
            on_partial=on_partial,
        )

    def build_hybrid_judgment_local_fallback(
        prompt: str,
        hybrid_pack: HybridJudgmentContextPackRecord,
        *,
        failure_detail: str,
    ) -> AiStructuredResponse:
        return AiStructuredResponse(
            content="当前已保留结构化判断卡片，延展长文未完整完成。",
            judgment=(
                hybrid_pack.sections.official[0]
                if hybrid_pack.sections.official
                else "当前系统内已批准的正式判断仍为空；以下仅保留待确认判断和判断草稿。"
            ),
            analysis=(
                f"围绕“{prompt}”，当前已优先使用 analysis-first hybrid judgment pack 组织回答。"
                f"正式生成阶段未完整完成，已回退到本地结构化结果。失败详情：{failure_detail}"
            ),
            actions=(
                hybrid_pack.sections.actions[0]
                if hybrid_pack.sections.actions
                else "建议优先补齐会议、任务或资料上下文，再决定是否生成 judgment proposal。"
            ),
            timeline=(
                hybrid_pack.sections.unknowns[0]
                if hybrid_pack.sections.unknowns
                else "后续可继续补证据并把判断草稿推进到提案或审批流程。"
            ),
        )

    def _render_state_sections_text(sections: StateAnswerSectionsRecord) -> str:
        candidate_and_drafts = list(dict.fromkeys([*sections.candidate, *sections.draftFindings]))
        ordered_sections = [
            ("一、已登记的正式判断", sections.official),
            ("二、待确认判断 / 判断草稿", candidate_and_drafts),
            ("三、支撑证据摘要", sections.evidenceSupport),
            ("四、本周动作 / 当前推进", sections.actions),
            ("五、风险提醒 / 未决问题", sections.risks),
            ("六、缺失信息 / 下一步建议", sections.unknowns),
        ]
        chunks: list[str] = []
        for title, items in ordered_sections:
            if items:
                body = "\n".join(f"- {item}" for item in items)
            else:
                body = "- 当前暂无可展示内容。"
            chunks.append(f"{title}\n{body}")
        return "\n\n".join(chunks).strip()

    def build_state_only_local_fallback(
        prompt: str,
        sections: StateAnswerSectionsRecord,
        source_summary: StateSourceSummaryRecord,
        boundary_notes: list[str],
        *,
        failure_detail: str,
    ) -> AiStructuredResponse:
        source_bits: list[str] = []
        if source_summary.judgments:
            source_bits.append(f"{source_summary.judgments} 条判断")
        if source_summary.meetings:
            source_bits.append(f"{source_summary.meetings} 次会议")
        if source_summary.tasks:
            source_bits.append(f"{source_summary.tasks} 条任务")
        if source_summary.openQuestions:
            source_bits.append(f"{source_summary.openQuestions} 个未决问题")
        if source_summary.conflicts:
            source_bits.append(f"{source_summary.conflicts} 个风险/冲突")
        source_summary_text = "、".join(source_bits) if source_bits else "当前客户状态池"
        lead_lines = [f"围绕“{prompt}”，当前先基于 {source_summary_text} 给出一版边界清晰的状态回答。"]
        if sections.official:
            lead_lines.append(f"较稳定的正式判断是：{sections.official[0]}")
        elif sections.candidate:
            lead_lines.append(f"现阶段更接近待确认判断的是：{sections.candidate[0]}")
        if sections.actions:
            lead_lines.append(f"最值得继续推进的是：{sections.actions[0]}")
        if sections.unknowns:
            lead_lines.append(f"当前仍需补齐的是：{sections.unknowns[0]}")
        return AiStructuredResponse(
            content="\n\n".join(lead_lines).strip(),
            judgment=sections.official[0] if sections.official else "当前先保留边界清晰的状态回答，正式判断仍待更多稳定证据支持。",
            analysis=(
                f"已优先基于 {source_summary_text} 生成结构化状态回答。"
                "本轮延展分析没有成功完成，但不影响当前主回答可用。"
            ),
            actions=sections.actions[0] if sections.actions else "建议继续围绕当前状态回答追问“哪份原文支持当前判断”。",
            timeline=(
                sections.unknowns[0]
                if sections.unknowns
                else (boundary_notes[0] if boundary_notes else "当前以状态池回答为主，后续可按需补充原文证据。")
            ),
        )

    def _strategic_unique_non_empty(values: list[str | None]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for raw in values:
            text = (raw or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    def _strategic_first_non_empty(values: list[str | None], fallback: str) -> str:
        ordered = _strategic_unique_non_empty(values)
        return ordered[0] if ordered else fallback

    def _strategic_truncate(value: str | None, limit: int = 88) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        return text if len(text) <= limit else f"{text[:limit - 1]}…"

    def _strategic_format_date_label(value: str | None) -> str:
        if not value:
            return "待补"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d")
        except ValueError:
            return value[:10]

    def _strategic_is_placeholder_context_text(value: str | None) -> bool:
        text = (value or "").strip()
        if not text:
            return True
        return any(pattern in text for pattern in STRATEGIC_PLACEHOLDER_CONTEXT_PATTERNS)

    def _strategic_is_relationship_task(task: TaskRecord) -> bool:
        task_text = " ".join([task.title, task.desc or ""])
        return any(keyword in task_text for keyword in STRATEGIC_RELATIONSHIP_TASK_KEYWORDS)

    def _strategic_has_contextual_description(task: TaskRecord) -> bool:
        description = (task.desc or "").strip()
        if len(description) < 20 or _strategic_is_placeholder_context_text(description):
            return False
        keyword_hits = sum(1 for keyword in STRATEGIC_CONTEXTUAL_DESCRIPTION_KEYWORDS if keyword in description)
        return keyword_hits >= 2 or len(description) >= 42

    def _strategic_background_signal_score(task: TaskRecord) -> float:
        score = 0.0
        readiness = task.backgroundReadiness
        if readiness:
            score = max(score, float(readiness.score or 0.0))
            if readiness.backgroundSources:
                score += 0.08
            if readiness.level == "high":
                score += 0.08
            elif readiness.level == "medium":
                score += 0.04
        if task.eventLineId or task.eventLineName:
            score += 0.22
        if task.projectModuleId or task.projectModuleName or task.projectFlowId or task.projectFlowName:
            score += 0.16
        if task.memoryHints:
            score += 0.08
        if task.linkedFactsPreview:
            score += 0.12
        if task.attachments:
            score += 0.08
        if _strategic_has_contextual_description(task):
            score += 0.18
        return round(min(score, 1.0), 2)

    def _strategic_has_meaningful_task_background(task: TaskRecord) -> bool:
        project_context = task.projectContext
        if task.eventLineId or task.eventLineName or task.projectModuleId or task.projectModuleName or task.projectFlowId or task.projectFlowName:
            return True
        background_score = _strategic_background_signal_score(task)
        if _strategic_is_relationship_task(task):
            readiness_sources = set(task.backgroundReadiness.backgroundSources) if task.backgroundReadiness else set()
            has_non_self_memory = any(
                fact.sourceType != "task" or fact.sourceId != task.id
                for fact in task.linkedFactsPreview
            )
            if has_non_self_memory and (
                {"event_line_memory", "event_line_facts", "client_facts"} & readiness_sources
            ) and background_score >= 0.55:
                return True
            if _strategic_has_contextual_description(task):
                return True
            return False
        if background_score >= 0.5:
            return True
        if _strategic_has_contextual_description(task):
            return True
        if (task.tags or task.attachments) and background_score >= 0.28:
            return True
        if not project_context:
            return False
        return any(
            not _strategic_is_placeholder_context_text(item)
            for item in [
                project_context.backgroundSummary,
                project_context.currentFocus,
                project_context.currentBlocker,
                project_context.nextAction,
                project_context.recentProgress,
            ]
        )

    def _load_org_model_profile_safe() -> OrgModelProfileRecord | None:
        if not get_cloud_token():
            return None
        try:
            payload = cloud_request("GET", "/api/v1/settings/org-model/profile")
        except HTTPException:
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return OrgModelProfileRecord(**payload)
        except Exception:
            return None

    def _load_strategic_snapshot_row(client_id: str):
        return state.db.fetchone("SELECT * FROM strategic_cockpit_snapshots WHERE client_id = ?", (client_id,))

    def _strategic_meeting_event_line_ids(client_id: str, meeting_title: str, *, meeting_id: str | None = None) -> list[str]:
        line_ids = _strategic_unique_non_empty(
            [
                *(
                    [
                        str(row["event_line_id"]).strip()
                        for row in state.db.fetchall(
                            """
                            SELECT DISTINCT event_line_id
                            FROM tasks
                            WHERE source_type = 'meeting' AND source_id = ? AND event_line_id IS NOT NULL AND TRIM(event_line_id) <> ''
                            """,
                            (meeting_id,),
                        )
                    ]
                    if meeting_id
                    else []
                ),
                *(
                    [item.id for item in list_linked_event_lines(state.db, client_id)]
                    if any(keyword in meeting_title for keyword in STRATEGIC_WEEKLY_MEETING_KEYWORDS)
                    else []
                ),
            ]
        )
        return line_ids[:12]

    def _strategic_task_pool(client_id: str, workspace: ClientWorkspaceResponse) -> list[TaskRecord]:
        task_map: dict[str, TaskRecord] = {task.id: task for task in workspace.relatedTasks}
        if get_cloud_token():
            _pull_cloud_tasks_to_local()
        task_candidates = fetch_tasks("t.source_type != ?", (AGENT_AUTO_SOURCE_TYPE,))
        for task in task_candidates:
            if task.clientId == client_id or (task.projectContext and task.projectContext.clientId == client_id):
                task_map[task.id] = task
        return sorted(task_map.values(), key=lambda item: item.updatedAt, reverse=True)

    def _strategic_priority(probability: str | None) -> Literal["high", "medium", "low"]:
        if probability == "high":
            return "high"
        if probability == "medium":
            return "medium"
        return "low"

    def _strategic_health_status(score: int, *, calibrated: bool) -> Literal["healthy", "watch", "risk", "uncalibrated"]:
        if not calibrated:
            return "uncalibrated"
        if score >= 75:
            return "healthy"
        if score >= 45:
            return "watch"
        return "risk"

    def _strategic_thought_topic_key(value: str) -> str:
        normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
        normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "_", normalized).strip("_")
        return normalized[:80] or "general"

    def _strategic_thought_id(
        *,
        scope: Literal["client", "system"],
        client_id: str | None,
        source_type: str,
        source_id: str | None,
        topic_key: str,
    ) -> str:
        raw = f"strategic_thought:{scope}:{client_id or ''}:{source_type}:{source_id or ''}:{topic_key}"
        return f"thought_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]}"

    def _normalize_text_for_matching(text: str | None) -> str:
        compact = re.sub(r"\s+", " ", (text or "").strip())
        compact = compact.replace("：", ":").replace("，", ",").replace("。", ".")
        return compact.strip()

    def _normalize_text_for_dedupe(text: str | None) -> str:
        compact = re.sub(r"\s+", "", (text or "").strip().lower())
        compact = re.sub(r"[，,。.;；:：!?！？（）()\\[\\]{}<>《》“”‘’'\"`·—-]+", "", compact)
        return compact

    def _is_internal_topic_key(text: str) -> bool:
        normalized = _normalize_text_for_matching(text).lower()
        normalized = normalized.strip("_")
        if not normalized:
            return False
        if normalized in STRATEGIC_INTERNAL_TOPIC_KEYS:
            return True
        return re.fullmatch(r"[a-z]+(?:_[a-z0-9]+)+", normalized) is not None

    def _is_placeholder_text(text: str) -> bool:
        normalized = _normalize_text_for_matching(text)
        if not normalized:
            return True
        if _is_internal_topic_key(normalized):
            return True
        compact = normalized.replace(" ", "")
        lowered = compact.lower()
        if lowered in STRATEGIC_PLACEHOLDER_THOUGHT_TEXTS_NORMALIZED:
            return True
        if lowered in {"none", "n/a", "na", "todo", "tbd"}:
            return True
        if re.fullmatch(r"(待确认|待补充|待澄清|暂无|未知|未定|不明)", compact):
            return True
        if 2 <= len(compact) <= 4 and re.fullmatch(r"[\u4e00-\u9fff]{2,4}", compact):
            return compact in {"暂无", "待补", "待补充", "待确认", "待澄清", "未知"}
        return False

    def _humanize_candidate_topic(topic: str, summary: str) -> str:
        normalized = _normalize_text_for_matching(topic).lower()
        topic_map = {
            "client_overview": "客户概况判断",
            "org_overview": "组织概况判断",
            "project_overview": "项目概况判断",
            "main_contradiction": "主矛盾判断",
            "core_breakthrough": "关键突破判断",
            "pending_material": "资料缺口判断",
            "pending_decision": "待拍板判断",
        }
        if normalized in topic_map:
            return topic_map[normalized]
        if topic and not _is_internal_topic_key(topic) and not _is_placeholder_text(topic):
            return _strategic_truncate(topic, 26)
        summary_text = _normalize_text_for_matching(summary)
        if summary_text:
            summary_text = re.sub(r"^[a-z0-9_\\-\\s]+[:：]", "", summary_text, flags=re.I).strip()
            if summary_text and not _is_placeholder_text(summary_text):
                return _strategic_truncate(summary_text, 28)
        return "待确认判断"

    def _looks_specific_line_title(title: str) -> bool:
        text = _normalize_text_for_matching(title)
        if not text:
            return False
        broad_titles = {
            "战略陪伴",
            "项目进度",
            "项目推进",
            "项目状态",
            "推进状态",
            "业务推进",
            "总体推进",
            "日常推进",
        }
        if text in broad_titles:
            return False
        if len(text) <= 4 and text in {"推进", "状态", "项目", "战略"}:
            return False
        return True

    def _evidence_level(
        evidence_count: int,
        sources: list[StrategicThoughtSourceRecord],
        has_meaningful_summary: bool,
        has_actionable_next_step: bool,
    ) -> Literal["none", "weak", "medium", "strong"]:
        source_types = {item.sourceType for item in sources}
        if evidence_count <= 0 and not has_meaningful_summary:
            return "none"
        if source_types and source_types <= {"strategic_cockpit"} and not has_meaningful_summary:
            return "none"
        strong_sources = {"meeting", "review", "event_line", "judgment_version"}
        if (
            has_meaningful_summary
            and has_actionable_next_step
            and evidence_count >= 2
            and len(source_types) >= 2
            and bool(source_types & strong_sources)
        ):
            return "strong"
        if has_meaningful_summary and (has_actionable_next_step or evidence_count >= 2):
            return "medium"
        if has_meaningful_summary or has_actionable_next_step or evidence_count > 0:
            return "weak"
        return "none"

    def _cap_confidence_by_evidence(
        confidence: int | None,
        confidence_level: Literal["low", "medium", "high", "none"],
        evidence_level: Literal["none", "weak", "medium", "strong"],
        *,
        status: Literal["draft", "waiting_evidence"] = "draft",
    ) -> tuple[int | None, Literal["low", "medium", "high", "none"]]:
        if status == "waiting_evidence":
            return None, "none"
        if confidence is None or confidence_level == "none":
            return None, "none"
        if evidence_level == "none":
            return None, "none"
        if evidence_level == "weak":
            capped = min(confidence, 40)
            return (capped if capped > 0 else None), ("low" if capped > 0 else "none")
        if evidence_level == "medium":
            capped = min(confidence, 65)
            if capped >= 45:
                return capped, "medium"
            if capped > 0:
                return capped, "low"
            return None, "none"
        # strong
        if confidence >= 75:
            return confidence, "high"
        if confidence >= 45:
            return confidence, "medium"
        if confidence > 0:
            return confidence, "low"
        return None, "none"

    def _strategic_thought_confidence(
        *,
        readiness_score: int,
        readiness_status: Literal["ready", "insufficient"],
        evidence_count: int,
        has_line_evidence: bool = False,
        has_meeting_or_review: bool = False,
        has_confirmed_headline: bool = False,
        has_meaningful_summary: bool = True,
        has_actionable_next_step: bool = True,
    ) -> tuple[int | None, Literal["low", "medium", "high", "none"]]:
        score = readiness_score if readiness_score > 0 else 30
        if has_line_evidence:
            score += 10
        if has_meeting_or_review:
            score += 10
        if has_confirmed_headline:
            score += 10
        if readiness_status == "insufficient":
            score -= 20
        if evidence_count == 0:
            score -= 15
        if not has_meaningful_summary:
            score -= 15
        if not has_actionable_next_step:
            score -= 12
        score = max(0, min(95, score))
        if score <= 0:
            return None, "none"
        if score >= 75:
            return score, "high"
        if score >= 45:
            return score, "medium"
        return score, "low"

    def _source_strength(thought: StrategicThoughtRecord) -> int:
        source_types = {item.sourceType for item in thought.sources}
        if "judgment_version" in source_types:
            return 3
        if source_types & {"event_line", "meeting", "review"}:
            return 2
        if source_types:
            return 1
        return 0

    def _evidence_level_weight(level: str | None) -> int:
        if level == "strong":
            return 4
        if level == "medium":
            return 3
        if level == "weak":
            return 2
        return 1

    def _status_weight(status: str) -> int:
        if status == "confirmed":
            return 5
        if status == "task_created":
            return 4
        if status == "draft":
            return 3
        if status == "waiting_evidence":
            return 2
        return 1

    def _status_group(status: str) -> str:
        if status == "waiting_evidence":
            return "waiting_evidence"
        if status in {"confirmed", "task_created"}:
            return "confirmed_like"
        return "draft_like"

    def _specificity_weight(thought: StrategicThoughtRecord) -> int:
        joined = f"{thought.line} {thought.observation} {thought.suggestion}"
        if _is_placeholder_text(joined):
            return 0
        return min(200, len(joined))

    def _dedupe_strategic_thoughts(thoughts: list[StrategicThoughtRecord]) -> list[StrategicThoughtRecord]:
        selected: dict[tuple[str, str, str], StrategicThoughtRecord] = {}
        for item in thoughts:
            key = (
                item.clientId or "__system__",
                _status_group(item.status),
                _normalize_text_for_dedupe(f"{item.line}|{item.observation}|{item.suggestion}")[:140],
            )
            existing = selected.get(key)
            if existing is None:
                selected[key] = item
                continue
            item_score = (
                _status_weight(item.status),
                _source_strength(item),
                _evidence_level_weight(item.evidenceLevel if hasattr(item, "evidenceLevel") else "none"),
                item.confidence or 0,
                _specificity_weight(item),
            )
            existing_score = (
                _status_weight(existing.status),
                _source_strength(existing),
                _evidence_level_weight(existing.evidenceLevel if hasattr(existing, "evidenceLevel") else "none"),
                existing.confidence or 0,
                _specificity_weight(existing),
            )
            if item_score > existing_score:
                selected[key] = item
        return list(selected.values())

    def _strategic_thought_review_from_row(row: sqlite3.Row) -> StrategicThoughtReviewRecord:
        status_raw = str(row["status"] or "draft")
        status = (
            status_raw
            if status_raw in {"draft", "confirmed", "dismissed", "task_created", "waiting_evidence"}
            else "draft"
        )
        reviewed_by = str(row["reviewed_by_name"] or row["reviewed_by_id"] or "").strip() or None
        return StrategicThoughtReviewRecord(
            thoughtId=str(row["thought_id"]),
            status=status,  # type: ignore[arg-type]
            note=str(row["note"] or ""),
            taskId=str(row["task_id"]) if row["task_id"] else None,
            judgmentId=str(row["judgment_id"]) if row["judgment_id"] else None,
            reviewedAt=str(row["reviewed_at"]) if row["reviewed_at"] else None,
            reviewedBy=reviewed_by,
        )

    def _list_strategic_thought_review_map() -> dict[str, sqlite3.Row]:
        rows = state.db.fetchall(
            """
            SELECT *
            FROM strategic_thought_reviews
            ORDER BY updated_at DESC
            """
        )
        review_map: dict[str, sqlite3.Row] = {}
        for row in rows:
            thought_id = str(row["thought_id"] or "").strip()
            if thought_id and thought_id not in review_map:
                review_map[thought_id] = row
        return review_map

    def _merge_strategic_thought_reviews(
        thoughts: list[StrategicThoughtRecord],
        *,
        include_dismissed: bool,
    ) -> list[StrategicThoughtRecord]:
        review_map = _list_strategic_thought_review_map()
        merged: list[StrategicThoughtRecord] = []
        for thought in thoughts:
            review_row = review_map.get(thought.id)
            if review_row is not None:
                review = _strategic_thought_review_from_row(review_row)
                thought.review = review
                thought.status = review.status
            if thought.status == "dismissed" and not include_dismissed:
                continue
            merged.append(thought)
        return merged

    def _build_waiting_evidence_thought(
        *,
        client_id: str,
        client_name: str,
        readiness_summary: str,
        gaps: list[str],
        source_type: Literal["strategic_cockpit", "system"] = "strategic_cockpit",
    ) -> StrategicThoughtRecord:
        line = f"{client_name}：等待补证"
        topic_key = _strategic_thought_topic_key(f"{client_id}:{line}")
        source_id = client_id if source_type == "strategic_cockpit" else f"{client_id}:waiting_evidence"
        thought_id = _strategic_thought_id(
            scope="client",
            client_id=client_id,
            source_type=source_type,
            source_id=source_id,
            topic_key=topic_key,
        )
        gap_preview = "；".join(gaps[:2]) if gaps else "关键资料与结构化信号不足。"
        return StrategicThoughtRecord(
            id=thought_id,
            scope="client",
            clientId=client_id,
            clientName=client_name,
            line=line,
            observation=f"系统目前只看到：{readiness_summary}",
            suggestion=f"还缺：{gap_preview} 建议先补会议记录、周复盘或关键任务背景，再生成正式研判。",
            confidence=None,
            confidenceLevel="none",
            status="waiting_evidence",
            isSystem=False,
            dueDateHint="本周",
            tags=["等待补证", "资料不足"],
            sources=[
                StrategicThoughtSourceRecord(
                    sourceType=source_type,
                    sourceId=source_id,
                    label="战略驾驶舱",
                    detail=readiness_summary,
                )
            ],
            evidenceCount=0,
            generatedAt=now_iso(),
            staleReason=gap_preview,

```
