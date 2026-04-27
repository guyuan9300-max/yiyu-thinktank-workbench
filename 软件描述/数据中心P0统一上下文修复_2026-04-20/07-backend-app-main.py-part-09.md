# 源码文件：`backend/app/main.py`（分片 09）

- 行号范围：22401-25200
- 总行数：   30416
- 导出时间：2026-04-20

```python

        def _attachment_family_label(att: dict) -> str:
            mime = str(att.get("mimeType") or att.get("mime_type") or "")
            title = str(att.get("title") or "")
            lower_title = title.lower()
            if mime.startswith("image/") or lower_title.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                return "图像证据"
            if lower_title.endswith(".pdf"):
                return "PDF 资料"
            if lower_title.endswith((".doc", ".docx")):
                return "Word 文档"
            if lower_title.endswith((".xls", ".xlsx")):
                return "表格资料"
            if lower_title.endswith((".ppt", ".pptx")):
                return "汇报材料"
            return "补充资料"

        def _dedupe_texts(items: list[str]) -> list[str]:
            seen: set[str] = set()
            results: list[str] = []
            for item in items:
                normalized = _clean_text(item)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                results.append(normalized)
            return results

        def _build_core_judgment(
            blocker_text: str,
            decision_text: str,
            next_step_text: str,
            latest_signals: list[str],
        ) -> str:
            if decision_text and next_step_text:
                return f"已形成“{_truncate_text(decision_text, 28)}”，当前要把“{_truncate_text(next_step_text, 28)}”继续推进到明确结果。"
            if blocker_text and next_step_text:
                return f"当前卡点是“{_truncate_text(blocker_text, 28)}”，需要围绕“{_truncate_text(next_step_text, 28)}”继续收束责任人与时间点。"
            if decision_text:
                return f"最近已经形成“{_truncate_text(decision_text, 34)}”，下一步重点是确认这个判断是否真正带动了后续推进。"
            if next_step_text:
                return f"当前最需要盯住的是“{_truncate_text(next_step_text, 34)}”，确保这一步不再停留在口头判断。"
            if len(latest_signals) >= 2:
                return f"最近的关键推进集中在“{_truncate_text(latest_signals[0], 26)}”和“{_truncate_text(latest_signals[1], 26)}”。"
            if len(latest_signals) == 1:
                return f"目前最值得关注的进展是“{_truncate_text(latest_signals[0], 40)}”。"
            return "当前资料不足，建议先补活动记录、阶段判断或附件材料，再生成对外汇报。"

        # ── Page setup ──
        section = doc.sections[0]
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

        event_line_name = str(draft.get("eventLineName", "事件线汇报"))
        summary = str(draft.get("summary", ""))
        participants = draft.get("participantNames", [])
        snapshot_at = str(draft.get("snapshotAt", now_iso()))

        # ── Gather cover data ──
        el_row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
        client_name = ""
        owner_name = ""
        stage = ""
        created_at = ""
        event_line_status = "archived"
        event_line_kind = "custom"
        event_line_intent = ""
        event_line_summary = ""
        current_blocker = ""
        recent_decision = ""
        next_step = ""
        if el_row:
            client_name = str(el_row["primary_client_name"] or "")
            owner_name = str(el_row["owner_name"] or "")
            stage = str(el_row["stage"] or "")
            created_at = str(el_row["created_at"] or "")[:10]
            event_line_status = str(el_row["status"] or "archived")
            event_line_kind = str(el_row["kind"] or "custom")
            event_line_intent = str(el_row["intent"] or "")
            event_line_summary = str(el_row["summary"] or "")
            current_blocker = str(el_row["current_blocker"] or "")
            recent_decision = str(el_row["recent_decision"] or "")
            next_step = str(el_row["next_step"] or "")

        activities = draft.get("activities", [])
        visible_activities = [a for a in activities if not a.get("hidden")]
        attachments = draft.get("attachments", [])
        tasks = draft.get("tasks", [])

        sorted_visible_activities = sorted(visible_activities, key=lambda item: str(item.get("happenedAt", "")))
        meaningful_activities = [item for item in sorted_visible_activities if not _is_bootstrap_activity(item)]
        key_activities = [item for item in meaningful_activities if _is_key(item)]
        milestone_source = key_activities or meaningful_activities
        latest_milestone = milestone_source[-1] if milestone_source else None
        latest_milestone_signal = (_activity_summary(latest_milestone) or _activity_title(latest_milestone)) if latest_milestone else ""
        latest_signals = [
            (_activity_summary(item) or _activity_title(item))
            for item in reversed(milestone_source[-2:])
        ]
        kind_label = event_line_kind_labels.get(event_line_kind, "事件线")
        status_label = event_line_status_labels.get(event_line_status, event_line_status or "已归档")
        report_subtitle = f"{client_name} · {kind_label}汇报" if _clean_text(client_name) else f"{kind_label}汇报"
        task_count = len(tasks)
        attachment_count = len(attachments)
        has_narrative_evidence = any(
            len(_clean_text(value)) >= 6
            for value in [
                event_line_intent,
                summary,
                event_line_summary,
                current_blocker,
                recent_decision,
                next_step,
            ]
        )
        has_renderable_content = (
            len(meaningful_activities) >= 2
            or (len(meaningful_activities) >= 1 and (attachment_count > 0 or task_count > 0))
            or has_narrative_evidence
            or attachment_count > 0
            or task_count >= 2
        )
        event_line_name = _clean_text(event_line_name or (str(el_row["name"]) if el_row else "")) or "事件线汇报"
        summary_fallback = "当前资料不足，暂无法生成模拟汇报。请先补充活动说明、阶段判断或附件材料。"
        summary_source = (
            _clean_text(event_line_intent)
            or _clean_text(summary)
            or _clean_text(event_line_summary)
            or (latest_milestone_signal if has_renderable_content else "")
        )
        summary = _truncate_text(
            summary_source or summary_fallback,
            180,
        ) or summary_fallback
        core_judgment = _build_core_judgment(
            _clean_text(current_blocker),
            _clean_text(recent_decision),
            _clean_text(next_step),
            latest_signals,
        )
        core_judgment_note = " · ".join(_dedupe_texts([
            f"最近决策：{_truncate_text(recent_decision, 28)}" if _clean_text(recent_decision) else "",
            f"当前阻点：{_truncate_text(current_blocker, 28)}" if _clean_text(current_blocker) else "",
            f"下一步：{_truncate_text(next_step, 28)}" if _clean_text(next_step) else "",
            f"最近关键活动 {len(milestone_source)} 条" if milestone_source else "",
        ])[:2]) or "当前仅能基于已有快照生成基础判断，建议继续补充活动说明与附件。"
        completed_task_count = sum(1 for task in tasks if str(task.get("status", "")) == "done")
        pending_task_count = sum(1 for task in tasks if str(task.get("status", "")) not in {"done", "rejected"})

        family_counts: dict[str, int] = {}
        for attachment in attachments:
            family = _attachment_family_label(attachment)
            family_counts[family] = family_counts.get(family, 0) + 1
        family_entries = sorted(family_counts.items(), key=lambda item: (-item[1], item[0]))
        family_summary = "、".join([f"{label}{count}份" for label, count in family_entries[:3]]) if family_entries else "暂无附件材料"

        # Count by source type
        source_counts: dict[str, int] = {}
        for a in visible_activities:
            st = str(a.get("sourceType", ""))
            source_counts[st] = source_counts.get(st, 0) + 1

        source_labels_cn = {
            "task_activity": "任务动态",
            "meeting": "会议纪要",
            "support_request": "支持请求",
            "review": "复核审批",
            "attachment": "文档附件",
            "manual_note": "工作备注",
        }
        category_parts = [f"{source_labels_cn.get(k, k)} {v}" for k, v in source_counts.items() if v > 0]

        export_date = snapshot_at[:10]
        start_date = str(sorted_visible_activities[0].get("happenedAt", ""))[:10] if sorted_visible_activities else (created_at or export_date)
        end_date = str(sorted_visible_activities[-1].get("happenedAt", ""))[:10] if sorted_visible_activities else export_date
        review_window = f"{_format_doc_date(start_date)} - {_format_doc_date(end_date)}"
        stage_badge = " · ".join([part for part in [_clean_text(stage), status_label] if part]) or kind_label
        content_scale_value = f"关键 {len(milestone_source)} / 活动 {len(sorted_visible_activities)}"
        content_scale_note = f"附件 {attachment_count} · 任务 {task_count}"
        org_model_profile = _load_org_model_profile_safe()
        organization_label = ""
        if org_model_profile:
            organization_label = _clean_text(org_model_profile.organization.name)
        if not organization_label:
            organization_label = _clean_text(client_name) or "当前组织"

        # Days span
        try:
            from datetime import datetime as _dt
            d1 = _dt.fromisoformat(start_date)
            d2 = _dt.fromisoformat(end_date)
            days_span = max((d2 - d1).days, 1)
        except Exception:
            days_span = 0

        brand_color = RGBColor(0x5B, 0x7B, 0xFE)
        dark_color = RGBColor(0x1A, 0x1A, 0x1A)
        mid_gray = RGBColor(0x6B, 0x72, 0x80)
        light_gray = RGBColor(0x9C, 0xA3, 0xAF)

        # ══════════════════════════════════════════════
        #  COVER PAGE
        # ══════════════════════════════════════════════

        # ── Top line: 组织名 · 事件线汇报 ──
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(organization_label)
        run.font.size = Pt(11)
        run.font.color.rgb = brand_color
        run.font.bold = True
        run = p.add_run("  ·  事件线汇报")
        run.font.size = Pt(11)
        run.font.color.rgb = light_gray

        # ── Brand color thin line ──
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(0)
        pPr = p._p.get_or_add_pPr()
        pBdr = pPr.makeelement(qn("w:pBdr"), {})
        bottom = pBdr.makeelement(qn("w:bottom"), {
            qn("w:val"): "single",
            qn("w:sz"): "4",
            qn("w:space"): "1",
            qn("w:color"): "5B7BFE",
        })
        pBdr.append(bottom)
        pPr.append(pBdr)

        # ── Spacer ──
        for _ in range(3):
            sp = doc.add_paragraph()
            sp.paragraph_format.space_before = Pt(0)
            sp.paragraph_format.space_after = Pt(0)
            sp.add_run(" ").font.size = Pt(6)

        # ── Subtitle ──
        if report_subtitle:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(report_subtitle)
            run.font.size = Pt(12)
            run.font.color.rgb = mid_gray

        # ── Main title ──
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run(event_line_name)
        run.font.size = Pt(36)
        run.font.bold = True
        run.font.color.rgb = dark_color

        # ── Stage badge ──
        if stage_badge:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(12)
            run = p.add_run(f"  {stage_badge}  ")
            run.font.size = Pt(10)
            run.font.bold = True
            run.font.color.rgb = brand_color
            # Use shading as badge background
            shd = run._r.get_or_add_rPr().makeelement(qn("w:shd"), {
                qn("w:val"): "clear",
                qn("w:color"): "auto",
                qn("w:fill"): "E8EEFF",
            })
            run._r.get_or_add_rPr().append(shd)

        # ── Summary (max 3 lines) ──
        if summary:
            lines = summary.strip().split("\n")[:3]
            display_summary = "\n".join(lines)
            if len(summary.strip().split("\n")) > 3:
                display_summary += "……"
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(20)
            run = p.add_run(display_summary[:200])
            run.font.size = Pt(12)
            run.font.color.rgb = mid_gray

        # ── Current judgment ──
        if core_judgment:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run(core_judgment)
            run.font.size = Pt(20)
            run.font.bold = True
            run.font.color.rgb = dark_color

        if core_judgment_note:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(14)
            run = p.add_run(core_judgment_note[:180])
            run.font.size = Pt(10)
            run.font.color.rgb = light_gray

        # ── Spacer before stats ──
        for _ in range(2):
            sp = doc.add_paragraph()
            sp.paragraph_format.space_before = Pt(0)
            sp.paragraph_format.space_after = Pt(0)
            sp.add_run(" ").font.size = Pt(6)

        # ── Thin line before stats ──
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(12)
        pPr = p._p.get_or_add_pPr()
        pBdr = pPr.makeelement(qn("w:pBdr"), {})
        top_line = pBdr.makeelement(qn("w:top"), {
            qn("w:val"): "single",
            qn("w:sz"): "4",
            qn("w:space"): "1",
            qn("w:color"): "5B7BFE",
        })
        pBdr.append(top_line)
        pPr.append(pBdr)

        # ── Stats row — 3 columns table ──
        stat_items = [
            ("汇报类型", "事件线汇报", f"{kind_label} · {status_label}"),
            ("时间范围", review_window, f"快照日期 {_format_doc_date(snapshot_at)}"),
            ("内容规模", content_scale_value, content_scale_note),
        ]
        stats_table = doc.add_table(rows=3, cols=3)
        stats_table.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for i, (label, value, note) in enumerate(stat_items):
            cell = stats_table.cell(0, i)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(label)
            run.font.size = Pt(9)
            run.font.bold = True
            run.font.color.rgb = light_gray

            cell = stats_table.cell(1, i)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(value)
            run.font.size = Pt(18)
            run.font.bold = True
            run.font.color.rgb = dark_color

            cell = stats_table.cell(2, i)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(note)
            run.font.size = Pt(9)
            run.font.color.rgb = light_gray
        # Style: remove borders, add light background
        for row in stats_table.rows:
            for cell in row.cells:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                # Light blue background
                shd = tcPr.makeelement(qn("w:shd"), {
                    qn("w:val"): "clear",
                    qn("w:color"): "auto",
                    qn("w:fill"): "F0F3FF",
                })
                tcPr.append(shd)
                # Remove borders
                tcBorders = tcPr.makeelement(qn("w:tcBorders"), {})
                for edge in ("top", "left", "bottom", "right"):
                    border = tcBorders.makeelement(qn(f"w:{edge}"), {
                        qn("w:val"): "none", qn("w:sz"): "0", qn("w:space"): "0", qn("w:color"): "auto",
                    })
                    tcBorders.append(border)
                tcPr.append(tcBorders)

        # ── Category breakdown ──
        if category_parts:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(8)
            run = p.add_run(" · ".join(category_parts))
            run.font.size = Pt(9)
            run.font.color.rgb = light_gray

        # ── Spacer before bottom ──
        for _ in range(4):
            sp = doc.add_paragraph()
            sp.paragraph_format.space_before = Pt(0)
            sp.paragraph_format.space_after = Pt(0)
            sp.add_run(" ").font.size = Pt(6)

        # ── Bottom info bar ──
        bottom_parts = []
        if owner_name:
            bottom_parts.append(f"负责人：{owner_name}")
        bottom_parts.append(f"时间范围：{review_window}")
        bottom_parts.append(f"导出日期：{_format_doc_date(export_date)}")
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(16)
        run = p.add_run("  |  ".join(bottom_parts))
        run.font.size = Pt(9)
        run.font.color.rgb = light_gray

        # ── Bottom brand ──
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"— {organization_label} —")
        run.font.size = Pt(10)
        run.font.color.rgb = brand_color
        run.font.bold = True

        # ── Page break after cover ──
        doc.add_page_break()

        # ══════════════════════════════════════════════
        #  CONTENT PAGES — mirrors the preview exactly
        # ══════════════════════════════════════════════

        from io import BytesIO as _BytesIO

        source_labels_word = {
            "task_activity": "任务",
            "meeting": "会议",
            "support_request": "支持请求",
            "review": "复核",
            "attachment": "附件",
            "manual_note": "备注",
        }

        def _file_type_label(filename: str) -> str:
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            return {"doc": "Word", "docx": "Word", "xls": "Excel", "xlsx": "Excel",
                    "ppt": "PPT", "pptx": "PPT", "pdf": "PDF", "txt": "TXT", "md": "TXT",
                    "jpg": "JPG", "jpeg": "JPEG", "png": "PNG", "gif": "GIF", "webp": "WEBP"}.get(ext, ext.upper() or "文件")

        def _size_label(size_bytes: int) -> str:
            if size_bytes < 1024:
                return f"{size_bytes} B"
            if size_bytes < 1024 * 1024:
                return f"{size_bytes // 1024} KB"
            return f"{size_bytes / (1024 * 1024):.1f} MB"

        def _styled_para(text: str, size: int = 11, bold: bool = False, color: RGBColor = dark_color,
                         space_before: int = 0, space_after: int = 4, align: int | None = None):
            p = doc.add_paragraph()
            if align is not None:
                p.alignment = align
            p.paragraph_format.space_before = Pt(space_before)
            p.paragraph_format.space_after = Pt(space_after)
            run = p.add_run(text)
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
            return p

        def _add_thin_border_para():
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
            pPr = p._p.get_or_add_pPr()
            pBdr = pPr.makeelement(qn("w:pBdr"), {})
            b = pBdr.makeelement(qn("w:bottom"), {
                qn("w:val"): "single", qn("w:sz"): "2", qn("w:space"): "1", qn("w:color"): "E5E7EB",
            })
            pBdr.append(b)
            pPr.append(pBdr)

        # Read preview display state
        show_system = bool(draft.get("showSystemTraces", False))
        docs_expanded_ids = set(draft.get("docsExpandedActivityIds", []))
        images_expanded_ids = set(draft.get("imagesExpandedActivityIds", []))

        # Build task lookup
        task_map: dict[str, dict] = {}
        for t in tasks:
            tid = str(t.get("id", ""))
            if tid:
                task_map[tid] = t

        # Build attachment lookup by activity (same logic as frontend)
        att_by_activity: dict[str, list[dict]] = {}
        for att in attachments:
            att_task_id = str(att.get("taskId", ""))
            matched_activity_id = ""
            for a in activities:
                meta = a.get("metadata") or {}
                if isinstance(meta, dict):
                    if meta.get("taskId") and str(meta["taskId"]) == att_task_id:
                        matched_activity_id = str(a.get("id", ""))
                        break
                    if meta.get("attachmentId") and str(meta["attachmentId"]) == str(att.get("id", "")):
                        matched_activity_id = str(a.get("id", ""))
                        break
                if a.get("sourceType") == "attachment" and str(a.get("sourceId", "")) == str(att.get("id", "")):
                    matched_activity_id = str(a.get("id", ""))
                    break
            if matched_activity_id:
                att_by_activity.setdefault(matched_activity_id, []).append(att)

        # ── Content header ──
        _styled_para(event_line_name, size=20, bold=True, space_before=0, space_after=8)
        if summary:
            _styled_para(summary, size=11, color=mid_gray, space_after=4)
        meta_parts_str = f"导出时间：{snapshot_at[:16].replace('T', ' ')}"
        if participants:
            meta_parts_str += f"  |  参与者：{', '.join(str(n) for n in participants)}"
        _styled_para(meta_parts_str, size=9, color=light_gray, space_after=12)

        # Determine which activities to show (matching preview filter)
        def _is_key(act: dict) -> bool:
            if act.get("isKey") is not None:
                return bool(act["isKey"])
            st = str(act.get("sourceType", ""))
            if st in ("manual_note", "attachment"):
                return True
            if st == "task_activity":
                meta = act.get("metadata") or {}
                if isinstance(meta, dict) and meta.get("eventType") == "created":
                    return True
            return False

        display_activities = [a for a in activities if not a.get("hidden") and (show_system or _is_key(a))]

        if not display_activities:
            _styled_para("（无活动记录）", size=11, color=light_gray)

        for activity in display_activities:
            activity_id = str(activity.get("id", ""))
            title = str(activity.get("editedTitle") or activity.get("title", ""))
            summary_text = str(activity.get("editedSummary") or activity.get("summary", ""))
            happened_at = str(activity.get("happenedAt", ""))[:16].replace("T", " ")
            actor = str(activity.get("actorName", ""))
            source_type = str(activity.get("sourceType", ""))
            label = source_labels_word.get(source_type, source_type)

            # ── Activity title (bold) ──
            _styled_para(title, size=12, bold=True, space_before=10, space_after=2)

            # ── Type badge + time + actor ──
            meta_line = f"[{label}]  {happened_at}"
            if actor:
                meta_line += f"  — {actor}"
            _styled_para(meta_line, size=9, color=light_gray, space_after=4)

            # ── Summary ──
            if summary_text:
                _styled_para(summary_text, size=10, color=mid_gray, space_after=4)

            # ── Task detail (if linked) ──
            task_id = activity.get("sourceId", "") if source_type == "task_activity" else ""
            if not task_id:
                meta = activity.get("metadata") or {}
                if isinstance(meta, dict):
                    task_id = str(meta.get("taskId", ""))
            linked_task = task_map.get(task_id) if task_id else None
            if linked_task:
                task_desc = str(linked_task.get("desc") or linked_task.get("description") or "")
                if task_desc:
                    # Shaded box for task detail
                    p = doc.add_paragraph()
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(2)
                    # Indent to visually distinguish
                    p.paragraph_format.left_indent = Cm(0.5)
                    run = p.add_run(str(linked_task.get("title", "")))
                    run.font.size = Pt(10)
                    run.font.bold = True
                    run.font.color.rgb = mid_gray
                    shd = run._r.get_or_add_rPr().makeelement(qn("w:shd"), {
                        qn("w:val"): "clear", qn("w:color"): "auto", qn("w:fill"): "F8FAFC",
                    })
                    run._r.get_or_add_rPr().append(shd)
                    p2 = doc.add_paragraph()
                    p2.paragraph_format.space_before = Pt(0)
                    p2.paragraph_format.space_after = Pt(6)
                    p2.paragraph_format.left_indent = Cm(0.5)
                    run2 = p2.add_run(task_desc[:500])
                    run2.font.size = Pt(9)
                    run2.font.color.rgb = light_gray

            # ── Attachments for this activity ──
            activity_atts = att_by_activity.get(activity_id, [])
            is_docs_expanded = activity_id in docs_expanded_ids
            is_images_expanded = activity_id in images_expanded_ids

            if activity_atts:
                for att in activity_atts:
                    att_title = str(att.get("title", ""))
                    att_id = str(att.get("id", ""))
                    mime = str(att.get("mimeType") or "").lower()
                    is_image = mime.startswith("image/") or att_title.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
                    is_doc_file = att_title.lower().endswith((".docx", ".doc", ".md", ".txt", ".pdf", ".xlsx", ".xls", ".pptx", ".ppt"))
                    download_url = str(att.get("downloadUrl", ""))

                    if is_image and is_images_expanded:
                        # Show image inline (like preview expanded)
                        try:
                            if download_url:
                                img_resp = httpx.get(f"{state.cloud_api_url}{download_url}", timeout=15.0)
                                if img_resp.status_code == 200:
                                    img_stream = _BytesIO(img_resp.content)
                                    doc.add_picture(img_stream, width=Inches(4.5))
                                    _styled_para(att_title, size=9, color=light_gray, space_after=6)
                        except Exception:
                            _styled_para(f"（图片加载失败：{att_title}）", size=9, color=light_gray)

                    elif is_doc_file and is_docs_expanded:
                        # Show file card with summary (like preview expanded DocContentViewer)
                        type_label = _file_type_label(att_title)
                        size_str = _size_label(int(att.get("sizeBytes", 0)))
                        p = doc.add_paragraph()
                        p.paragraph_format.space_before = Pt(4)
                        p.paragraph_format.space_after = Pt(2)
                        run = p.add_run(f"[{type_label}]  ")
                        run.font.size = Pt(9)
                        run.font.bold = True
                        run.font.color.rgb = brand_color
                        run = p.add_run(f"{att_title}  ({size_str})")
                        run.font.size = Pt(10)
                        run.font.color.rgb = dark_color

                        # Fetch document summary
                        try:
                            text_resp = httpx.get(
                                f"{state.cloud_api_url}/api/public/task-attachments/{att_id}/text-content",
                                timeout=15.0,
                            )
                            doc_text = ""
                            if text_resp.status_code == 200:
                                text_data = text_resp.json()
                                raw = str(text_data.get("text", "")).strip()
                                if raw and "提取失败" not in raw and "No module" not in raw:
                                    doc_text = raw
                            if doc_text:
                                _styled_para(doc_text, size=9, color=mid_gray, space_after=6)
                            else:
                                _styled_para("（暂无文档摘要）", size=9, color=light_gray, space_after=6)
                        except Exception:
                            _styled_para("（文档摘要加载失败）", size=9, color=light_gray, space_after=6)

                    else:
                        # Collapsed — just show file type + full name (like preview)
                        type_label = _file_type_label(att_title)
                        p = doc.add_paragraph()
                        p.paragraph_format.space_before = Pt(1)
                        p.paragraph_format.space_after = Pt(1)
                        run = p.add_run(f"[{type_label}] ")
                        run.font.size = Pt(9)
                        run.font.bold = True
                        run.font.color.rgb = brand_color
                        run = p.add_run(att_title)
                        run.font.size = Pt(9)
                        run.font.color.rgb = mid_gray

            # ── Separator between activities ──
            _add_thin_border_para()

        import tempfile
        safe_name = safe_filename(f"{event_line_name[:30]}_汇报.docx")
        tmp_dir = os.path.join(tempfile.gettempdir(), "yiyu_exports")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, safe_name)
        doc.save(tmp_path)
        return {"filePath": tmp_path, "fileName": safe_name}

    @app.patch("/api/v1/event-lines/{event_line_id}", response_model=EventLineRecord)
    def update_event_line(event_line_id: str, payload: EventLineUpdatePayload) -> EventLineRecord:
        cloud_response_payload: dict[str, object] | None = None
        if get_cloud_token():
            try:
                response = cloud_request("PATCH", f"/api/v1/event-lines/{event_line_id}", json_body=payload.model_dump(exclude_unset=True))
                if not isinstance(response, dict):
                    raise HTTPException(status_code=502, detail="Invalid event line payload")
                cloud_response_payload = response
            except HTTPException:
                pass
        row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
        if not row:
            if cloud_response_payload is not None:
                return build_cloud_event_line(cloud_response_payload)
            raise HTTPException(status_code=404, detail="Event line not found")
        updates = payload.model_dump(exclude_unset=True)
        previous_client_id = str(row["primary_client_id"]).strip() if row["primary_client_id"] else None
        previous_client_name = str(row["primary_client_name"]).strip() if row["primary_client_name"] else None
        next_client_id = str(updates.get("primaryClientId")).strip() if updates.get("primaryClientId") else (str(row["primary_client_id"]) if row["primary_client_id"] else None)
        client_row = state.db.fetchone("SELECT name FROM clients WHERE id = ?", (next_client_id,)) if next_client_id else None
        next_client_name = str(client_row["name"]).strip() if client_row and client_row["name"] else (str(row["primary_client_name"]).strip() if row["primary_client_name"] else None)
        should_sync_linked_task_client_ids = (
            bool(updates.get("syncLinkedTaskClientIds"))
            and bool(next_client_id)
            and next_client_id != previous_client_id
        )
        participant_ids = updates.get("participantIds")
        updated_at = now_iso()
        state.db.execute(
            """
            UPDATE event_lines
            SET name = ?, kind = ?, status = ?, business_category = ?, stage = ?, summary = ?, intent = ?,
                current_blocker = ?, recent_decision = ?, next_step = ?, evidence_count = ?, owner_id = ?, owner_name = ?,
                primary_client_id = ?, primary_client_name = ?, primary_department_id = ?, primary_department_name = ?,
                participant_ids_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updates.get("name", row["name"]),
                updates.get("kind", row["kind"]),
                updates.get("status", row["status"]),
                updates.get("businessCategory", row["business_category"]),
                updates.get("stage", row["stage"]),
                updates.get("summary", row["summary"]),
                updates.get("intent", row["intent"]),
                updates.get("currentBlocker", row["current_blocker"]),
                updates.get("recentDecision", row["recent_decision"]),
                updates.get("nextStep", row["next_step"]),
                _event_line_evidence_count_or_zero(
                    updates["evidenceCount"] if "evidenceCount" in updates else row["evidence_count"],
                    default=int(row["evidence_count"] or 0),
                ),
                updates.get("ownerId", row["owner_id"]),
                updates.get("ownerName", row["owner_name"]),
                next_client_id,
                str(client_row["name"]) if client_row else (updates.get("primaryClientName", row["primary_client_name"])),
                updates.get("primaryDepartmentId", row["primary_department_id"]),
                updates.get("primaryDepartmentName", row["primary_department_name"]),
                to_json(participant_ids if participant_ids is not None else from_json(row["participant_ids_json"], [])),
                updated_at,
                event_line_id,
            ),
        )
        if should_sync_linked_task_client_ids:
            state.db.execute(
                "UPDATE tasks SET client_id = ?, updated_at = ? WHERE event_line_id = ?",
                (next_client_id, updated_at, event_line_id),
            )
            task_rows = state.db.fetchall(
                "SELECT id FROM tasks WHERE event_line_id = ?",
                (event_line_id,),
            )
            for task_row in task_rows:
                task_id = str(task_row["id"])
                _sync_task_attachment_scope(
                    state.db,
                    state.data_dir,
                    build_task_attachment,
                    build_attachment_event_line_activity,
                    ensure_standard_client_folders,
                    task_id,
                    next_client_id,
                    event_line_id,
                    cloud=False,
                )
                _sync_task_attachment_scope(
                    state.db,
                    state.data_dir,
                    build_task_attachment,
                    build_attachment_event_line_activity,
                    ensure_standard_client_folders,
                    task_id,
                    next_client_id,
                    event_line_id,
                    cloud=True,
                )
            _sync_event_line_client_scope_records(
                state.db,
                event_line_id=event_line_id,
                client_id=next_client_id,
                client_name=next_client_name,
                updated_at=updated_at,
            )
            if previous_client_id and next_client_name:
                rehome_event_line_memory(
                    state.data_dir,
                    previous_client_id,
                    next_client_id,
                    event_line_id,
                    str(updates.get("name", row["name"])),
                    next_client_name,
                )
            for affected_client_id in {previous_client_id, next_client_id}:
                if affected_client_id:
                    refresh_organization_notebook_snapshot(state.db, affected_client_id)
            refresh_event_line_memory_snapshot(state.db, event_line_id)
            _invalidate_event_line_snapshot_cache(event_line_id)
        updated_row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
        if not updated_row:
            raise HTTPException(status_code=500, detail="Event line update failed")
        if cloud_response_payload is not None:
            return build_cloud_event_line(cloud_response_payload)
        return build_event_line(updated_row)

    def _event_line_dependency_counts(event_line_id: str) -> dict[str, int]:
        task_count = state.db.fetchone("SELECT COUNT(1) AS cnt FROM tasks WHERE event_line_id = ?", (event_line_id,))
        activity_count = state.db.fetchone("SELECT COUNT(1) AS cnt FROM event_line_activities WHERE event_line_id = ?", (event_line_id,))
        attachment_count = state.db.fetchone("SELECT COUNT(1) AS cnt FROM event_line_attachments WHERE event_line_id = ?", (event_line_id,))
        memory_count = state.db.fetchone("SELECT COUNT(1) AS cnt FROM event_line_memory_snapshots WHERE event_line_id = ?", (event_line_id,))
        weekly_count = state.db.fetchone("SELECT COUNT(1) AS cnt FROM event_line_weekly_snapshots WHERE event_line_id = ?", (event_line_id,))
        approval_count = state.db.fetchone("SELECT COUNT(1) AS cnt FROM event_line_approval_nodes WHERE event_line_id = ?", (event_line_id,))
        return {
            "tasks": int(task_count["cnt"] if task_count else 0),
            "activities": int(activity_count["cnt"] if activity_count else 0),
            "attachments": int(attachment_count["cnt"] if attachment_count else 0),
            "memorySnapshots": int(memory_count["cnt"] if memory_count else 0),
            "weeklySnapshots": int(weekly_count["cnt"] if weekly_count else 0),
            "approvalNodes": int(approval_count["cnt"] if approval_count else 0),
        }

    @app.post("/api/v1/event-lines/{event_line_id}/close")
    def close_event_line(event_line_id: str) -> dict:
        cloud_result: dict | None = None
        if get_cloud_token():
            # Try dedicated /close first; if 404/405, fall back to PATCH status=archived
            try:
                resp = cloud_request("POST", f"/api/v1/event-lines/{event_line_id}/close")
                if isinstance(resp, dict):
                    cloud_result = resp
            except HTTPException as exc:
                if exc.status_code not in (404, 405):
                    raise
                # Fallback: use PATCH to set status=archived
                try:
                    resp = cloud_request("PATCH", f"/api/v1/event-lines/{event_line_id}", json_body={"status": "archived"})
                    if isinstance(resp, dict):
                        cloud_result = {"status": "archived"}
                except HTTPException:
                    pass
        # Always sync local copy
        row = state.db.fetchone("SELECT id, status FROM event_lines WHERE id = ?", (event_line_id,))
        if row and str(row["status"]) not in ("done", "archived"):
            timestamp = now_iso()
            state.db.execute(
                "UPDATE event_lines SET status = 'archived', closed_at = ?, closed_by_user_id = ?, updated_at = ? WHERE id = ?",
                (timestamp, current_operator_name(), timestamp, event_line_id),
            )
        if cloud_result:
            return cloud_result
        if not row:
            raise HTTPException(status_code=404, detail="Event line not found")
        return {"status": "archived"}

    @app.post("/api/v1/event-lines/{event_line_id}/reopen")
    def reopen_event_line(event_line_id: str) -> dict:
        cloud_result: dict | None = None
        if get_cloud_token():
            # Try dedicated /reopen first; if 404/405, fall back to PATCH status=active
            try:
                resp = cloud_request("POST", f"/api/v1/event-lines/{event_line_id}/reopen")
                if isinstance(resp, dict):
                    cloud_result = resp
            except HTTPException as exc:
                if exc.status_code not in (404, 405):
                    raise
                try:
                    resp = cloud_request("PATCH", f"/api/v1/event-lines/{event_line_id}", json_body={"status": "active"})
                    if isinstance(resp, dict):
                        cloud_result = {"status": "active"}
                except HTTPException:
                    pass
        # Always sync local copy
        row = state.db.fetchone("SELECT id FROM event_lines WHERE id = ?", (event_line_id,))
        if row:
            timestamp = now_iso()
            state.db.execute(
                "UPDATE event_lines SET status = 'active', closed_at = NULL, closed_by_user_id = NULL, updated_at = ? WHERE id = ?",
                (timestamp, event_line_id),
            )
        if cloud_result:
            return cloud_result
        if not row:
            raise HTTPException(status_code=404, detail="Event line not found")
        return {"status": "active"}

    @app.delete("/api/v1/event-lines/{event_line_id}")
    def delete_event_line(event_line_id: str) -> dict:
        cloud_deleted = False
        if get_cloud_token():
            # Try real DELETE first; if cloud returns 405 (not supported), fall back to PATCH archived
            for attempt_method in ("DELETE", "PATCH_ARCHIVED"):
                try:
                    if attempt_method == "DELETE":
                        resp = cloud_request("DELETE", f"/api/v1/event-lines/{event_line_id}")
                    else:
                        resp = cloud_request("PATCH", f"/api/v1/event-lines/{event_line_id}", json_body={"status": "archived"})
                    cloud_deleted = True
                    break
                except HTTPException as exc:
                    if exc.status_code == 403:
                        raise
                    if exc.status_code == 405 and attempt_method == "DELETE":
                        continue  # try PATCH fallback
                    break  # 404 or other — cloud doesn't have it
        # Always clean local copy
        row = state.db.fetchone("SELECT id, visibility_scope FROM event_lines WHERE id = ?", (event_line_id,))
        if row and not cloud_deleted:
            # Local-only fallback: only admin can delete
            if not current_session_is_admin():
                raise HTTPException(status_code=403, detail="只有管理员可以删除事件线。")
            task_count = int(state.db.scalar("SELECT COUNT(1) FROM tasks WHERE event_line_id = ?", (event_line_id,)) or 0)
            if task_count > 0:
                raise HTTPException(status_code=403, detail="事件线已有关联任务，不能删除，请使用「结束事件线」功能进行归档。")
        if row:
            state.db.execute("UPDATE tasks SET event_line_id = NULL, updated_at = ? WHERE event_line_id = ?", (now_iso(), event_line_id))
            state.db.execute("DELETE FROM event_line_activities WHERE event_line_id = ?", (event_line_id,))
            state.db.execute("DELETE FROM event_line_attachments WHERE event_line_id = ?", (event_line_id,))
            state.db.execute("DELETE FROM event_lines WHERE id = ?", (event_line_id,))
        if not row and not cloud_deleted:
            raise HTTPException(status_code=404, detail="Event line not found")
        return {"status": "deleted"}

    @app.post("/api/v1/event-lines/{event_line_id}/notes")
    def add_event_line_note(event_line_id: str, payload: dict = Body(...)) -> dict:
        note_text = str(payload.get("text", "")).strip()
        if not note_text:
            raise HTTPException(status_code=400, detail="Note text is required")
        row = state.db.fetchone("SELECT id FROM event_lines WHERE id = ?", (event_line_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Event line not found")
        activity_id = new_id("ela")
        timestamp = now_iso()
        state.db.execute(
            """
            INSERT INTO event_line_activities(
                id, event_line_id, source_type, source_id, happened_at, actor_id, actor_name, title, summary, metadata_json, is_key, created_at
            ) VALUES(?, ?, 'manual_note', ?, ?, NULL, ?, ?, ?, ?, 1, ?)
            """,
            (
                activity_id,
                event_line_id,
                activity_id,
                timestamp,
                current_operator_name(),
                "补充备注",
                note_text,
                to_json({}),
                timestamp,
            ),
        )
        log_activity("event_line.note", "event_line", event_line_id, {"noteLength": len(note_text)})
        return {
            "id": activity_id,
            "eventLineId": event_line_id,
            "text": note_text[:500],
            "createdAt": timestamp,
        }

    @app.get("/api/v1/task-views", response_model=TaskViewsResponse)
    def list_task_views() -> TaskViewsResponse:
        views = _ensure_builtin_task_views()
        rows = state.db.fetchall(
            """
            SELECT *
            FROM task_views
            ORDER BY built_in DESC,
                     CASE kind WHEN 'custom' THEN 1 ELSE 0 END,
                     updated_at DESC,
                     name ASC
            """
        )
        views = [_task_view_record_from_row(row) for row in rows]
        return TaskViewsResponse(
            views=views,
            presets=_task_view_presets(views),
        )

    @app.post("/api/v1/task-views", response_model=TaskViewDefinitionRecord)
    def create_task_view(payload: TaskViewMutationPayload) -> TaskViewDefinitionRecord:
        _ensure_builtin_task_views()
        if payload.kind != "custom":
            raise HTTPException(status_code=400, detail="Only custom task views can be created")
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Task view name is required")
        timestamp = now_iso()
        view_id = new_id("tview")
        state.db.execute(
            """
            INSERT INTO task_views(
                id, name, kind, description, calendar_scope, shareability, sort_by, sort_direction,
                visible_fields_json, filter_set_json, built_in, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                view_id,
                name,
                payload.kind,
                payload.description,
                payload.calendarScope,
                payload.shareability,
                payload.sortBy,
                payload.sortDirection,
                to_json(payload.visibleFields),
                to_json(payload.filterSet.model_dump()),
                timestamp,
                timestamp,
            ),
        )
        row = state.db.fetchone("SELECT * FROM task_views WHERE id = ?", (view_id,))
        if not row:
            raise HTTPException(status_code=500, detail="Task view creation failed")
        return _task_view_record_from_row(row)

    @app.patch("/api/v1/task-views/{view_id}", response_model=TaskViewDefinitionRecord)
    def update_task_view(view_id: str, payload: TaskViewMutationPayload) -> TaskViewDefinitionRecord:
        _ensure_builtin_task_views()
        row = state.db.fetchone("SELECT * FROM task_views WHERE id = ?", (view_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Task view not found")
        if str(row["kind"]) != "custom":
            raise HTTPException(status_code=400, detail="Built-in task views cannot be edited")
        timestamp = now_iso()
        next_name = payload.name.strip() if payload.name is not None else str(row["name"])
        if not next_name:
            raise HTTPException(status_code=400, detail="Task view name is required")
        next_filter_set = payload.filterSet.model_dump() if payload.filterSet is not None else from_json(row["filter_set_json"], {})
        next_visible_fields = payload.visibleFields if payload.visibleFields is not None else from_json(row["visible_fields_json"], [])
        state.db.execute(
            """
            UPDATE task_views
            SET name = ?, description = ?, filter_set_json = ?, sort_by = ?, sort_direction = ?, visible_fields_json = ?,
                calendar_scope = ?, shareability = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                next_name,
                payload.description if payload.description is not None else str(row["description"] or ""),
                to_json(next_filter_set),
                payload.sortBy or str(row["sort_by"]),
                payload.sortDirection or str(row["sort_direction"]),
                to_json(next_visible_fields),
                payload.calendarScope or str(row["calendar_scope"]),
                payload.shareability or str(row["shareability"]),
                timestamp,
                view_id,
            ),
        )
        updated_row = state.db.fetchone("SELECT * FROM task_views WHERE id = ?", (view_id,))
        if not updated_row:
            raise HTTPException(status_code=500, detail="Task view update failed")
        return _task_view_record_from_row(updated_row)

    @app.get("/api/v1/reviews/dashboard/drill-target", response_model=ReviewDashboardDrillTargetResponse)
    def get_review_dashboard_drill_target(
        targetType: str,
        targetId: str,
        targetLabel: str | None = None,
        targetFilters: str | None = None,
    ) -> ReviewDashboardDrillTargetResponse:
        parsed_filters: dict[str, object] = {}
        if targetFilters:
            try:
                candidate = json.loads(targetFilters)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail="Invalid targetFilters payload") from exc
            if not isinstance(candidate, dict):
                raise HTTPException(status_code=400, detail="targetFilters must be an object")
            parsed_filters = candidate
        target = ReviewDashboardCardTargetRecord(
            targetType=targetType,
            targetId=targetId,
            targetLabel=targetLabel,
            targetFilters=parsed_filters,
        )
        if target.targetType == "event_line":
            return _drill_target_response_for_event_line(target)
        if target.targetType == "task_view":
            return _drill_target_response_for_task_view(target)
        if target.targetType == "meeting":
            return _drill_target_response_for_meeting(target)
        if target.targetType == "support_request":
            return _drill_target_response_for_support_request(target)
        if target.targetType == "attachment_group":
            return _drill_target_response_for_attachment_group(target)
        raise HTTPException(status_code=400, detail=f"Unsupported dashboard drill target: {target.targetType}")

    @app.get("/api/v1/tasks/{task_id}/plan-link", response_model=TaskPlanLinkRecord | None)
    def read_task_plan_link(task_id: str) -> TaskPlanLinkRecord | None:
        response = cloud_request("GET", f"/api/v1/tasks/{task_id}/plan-link")
        if response is None:
            return None
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid task plan link payload")
        return TaskPlanLinkRecord(**response)

    @app.post("/api/v1/tasks/{task_id}/plan-link/recompute", response_model=TaskPlanLinkRecord | None)
    def recompute_task_plan_link(task_id: str) -> TaskPlanLinkRecord | None:
        response = cloud_request("POST", f"/api/v1/tasks/{task_id}/plan-link/recompute")
        if response is None:
            return None
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid task plan link payload")
        return TaskPlanLinkRecord(**response)

    @app.patch("/api/v1/tasks/{task_id}/plan-link", response_model=TaskPlanLinkRecord | None)
    def patch_task_plan_link(task_id: str, payload: TaskPlanLinkUpsertPayload) -> TaskPlanLinkRecord | None:
        response = cloud_request("PATCH", f"/api/v1/tasks/{task_id}/plan-link", json_body=payload.model_dump())
        if response is None:
            return None
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid task plan link payload")
        return TaskPlanLinkRecord(**response)

    @app.get("/api/v1/support-requests", response_model=list[SupportRequestRecord])
    def list_support_requests(status: str | None = Query(default=None), taskId: str | None = Query(default=None)) -> list[SupportRequestRecord]:
        query = []
        if status:
            query.append(f"status={quote(status)}")
        if taskId:
            query.append(f"taskId={quote(taskId)}")
        suffix = f"?{'&'.join(query)}" if query else ""
        response = cloud_request("GET", f"/api/v1/support-requests{suffix}")
        if not isinstance(response, list):
            raise HTTPException(status_code=502, detail="Invalid support request payload")
        return [SupportRequestRecord(**item) for item in response if isinstance(item, dict)]

    @app.post("/api/v1/support-requests", response_model=SupportRequestRecord)
    def create_support_request(payload: SupportRequestCreatePayload) -> SupportRequestRecord:
        response = cloud_request("POST", "/api/v1/support-requests", json_body=payload.model_dump())
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid support request payload")
        return SupportRequestRecord(**response)

    @app.post("/api/v1/support-requests/{request_id}/resolve", response_model=SupportRequestRecord)
    def resolve_support_request(request_id: str, payload: SupportRequestResolvePayload) -> SupportRequestRecord:
        response = cloud_request("POST", f"/api/v1/support-requests/{request_id}/resolve", json_body=payload.model_dump())
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid support request payload")
        record = SupportRequestRecord(**response)
        # Write support_request activity to the related event line (if task has one)
        if record.taskId:
            task_row = state.db.fetchone("SELECT event_line_id, title FROM tasks WHERE id = ?", (record.taskId,))
            if task_row and task_row["event_line_id"]:
                sr_ts = now_iso()
                state.db.execute(
                    """
                    INSERT INTO event_line_activities(
                        id, event_line_id, source_type, source_id, happened_at, actor_id, actor_name, title, summary, metadata_json, is_key, created_at
                    ) VALUES(?, ?, 'support_request', ?, ?, NULL, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        new_id("ela"),
                        str(task_row["event_line_id"]),
                        request_id,
                        sr_ts,
                        current_operator_name(),
                        f"支持请求已处理：{record.requestType}",
                        f"针对任务「{task_row['title']}」的{record.requestType}请求已{record.status}。" + (f" 处理说明：{record.resolutionNote[:80]}" if record.resolutionNote else ""),
                        to_json({"taskId": record.taskId, "requestType": record.requestType, "status": record.status}),
                        sr_ts,
                    ),
                )
        return record

    @app.post("/api/v1/admin/employees/{employee_id}/approve", response_model=EmployeeRecord)
    def approve_employee(employee_id: str, payload: EmployeeRolePayload) -> EmployeeRecord:
        response = cloud_request("POST", f"/api/v1/admin/employees/{employee_id}/approve", json_body=payload.model_dump())
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid employee payload")
        return EmployeeRecord(**response)

    @app.post("/api/v1/admin/employees/{employee_id}/reject", response_model=EmployeeRecord)
    def reject_employee(employee_id: str, payload: EmployeeRejectPayload) -> EmployeeRecord:
        response = cloud_request("POST", f"/api/v1/admin/employees/{employee_id}/reject", json_body=payload.model_dump())
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid employee payload")
        return EmployeeRecord(**response)

    @app.post("/api/v1/admin/employees/{employee_id}/disable", response_model=EmployeeRecord)
    def disable_employee(employee_id: str) -> EmployeeRecord:
        response = cloud_request("POST", f"/api/v1/admin/employees/{employee_id}/disable")
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid employee payload")
        return EmployeeRecord(**response)

    @app.post("/api/v1/admin/employees/{employee_id}/reset-password")
    def admin_reset_password(employee_id: str, payload: dict) -> dict:
        response = cloud_request("POST", f"/api/v1/admin/employees/{employee_id}/reset-password", json_body=payload)
        return response if isinstance(response, dict) else {"message": "密码已重置"}

    @app.patch("/api/v1/admin/employees/{employee_id}/role", response_model=EmployeeRecord)
    def patch_employee_role(employee_id: str, payload: EmployeeRolePayload) -> EmployeeRecord:
        response = cloud_request("PATCH", f"/api/v1/admin/employees/{employee_id}/role", json_body=payload.model_dump())
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid employee payload")
        return EmployeeRecord(**response)

    @app.patch("/api/v1/admin/employees/{employee_id}/department", response_model=EmployeeRecord)
    def patch_employee_department(employee_id: str, payload: EmployeeDepartmentPayload) -> EmployeeRecord:
        response = cloud_request("PATCH", f"/api/v1/admin/employees/{employee_id}/department", json_body=payload.model_dump())
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid employee payload")
        return EmployeeRecord(**response)

    @app.get("/api/v1/employees/mention-candidates", response_model=list[MentionCandidateRecord])
    def get_mention_candidates(q: str = Query(default="")) -> list[MentionCandidateRecord]:
        payload = cloud_request("GET", f"/api/v1/employees/mention-candidates?q={q}")
        if not isinstance(payload, list):
            raise HTTPException(status_code=502, detail="Invalid mention payload")
        return [MentionCandidateRecord(**item) for item in payload if isinstance(item, dict)]

    @app.get("/api/v1/settings", response_model=SettingsResponse)
    def get_settings() -> SettingsResponse:
        return build_settings_response()

    @app.get("/api/v1/settings/logs", response_model=list[ActivityLogRecord])
    def get_activity_logs() -> list[ActivityLogRecord]:
        return [
            ActivityLogRecord(
                id=str(row["id"]),
                actorName=str(row["actor_name"]),
                action=str(row["action"]),
                entityType=str(row["entity_type"]),
                entityId=str(row["entity_id"]),
                detail=from_json(row["detail_json"], {}),
                createdAt=str(row["created_at"]),
            )
            for row in state.db.fetchall("SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 30")
        ]

    # ── System Log Endpoints ───────────────────────────────────────
    @app.get("/api/v1/logs")
    def get_system_logs(
        startDate: str | None = Query(default=None),
        endDate: str | None = Query(default=None),
        level: str | None = Query(default=None),
        source: str | None = Query(default=None),
        keyword: str | None = Query(default=None),
        limit: int = Query(default=500, le=5000),
    ) -> dict:
        if not state.system_logger:
            return {"entries": [], "dates": [], "total": 0}
        entries = state.system_logger.query(
            start_date=startDate, end_date=endDate, level=level,
            source=source, keyword=keyword, limit=limit,
        )
        dates = state.system_logger.list_log_dates()
        return {"entries": entries, "dates": dates, "total": len(entries)}

    @app.get("/api/v1/logs/export")
    def export_system_logs(
        startDate: str | None = Query(default=None),
        endDate: str | None = Query(default=None),
        level: str | None = Query(default=None),
        keyword: str | None = Query(default=None),
    ) -> Response:
        if not state.system_logger:
            return Response(content="# 无日志数据", media_type="text/markdown")
        md = state.system_logger.export_markdown(
            start_date=startDate, end_date=endDate, level=level, keyword=keyword,
        )
        date_label = startDate or "today"
        return Response(
            content=md,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="yiyu-logs-{date_label}.md"'},
        )

    @app.get("/api/v1/logs/dates")
    def get_log_dates() -> list[str]:
        if not state.system_logger:
            return []
        return state.system_logger.list_log_dates()

    @app.get("/api/v1/tasks/agent-worklogs", response_model=AgentWorklogResponse)
    def get_agent_worklogs(month: str | None = Query(default=None)) -> AgentWorklogResponse:
        target_month = month or datetime.now().strftime("%Y-%m")
        if not current_session_is_admin():
            return AgentWorklogResponse(month=target_month)
        try:
            return build_agent_worklog_response(
                db=state.db,
                month_label=target_month,
                thread_sync_path=THREAD_SYNC_DOC_PATH,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/v1/tasks/agent-weekly-plans/{week_label}/{agent_key}", response_model=AgentWeeklyPlanRecord)
    def update_agent_weekly_plan(
        week_label: str,
        agent_key: str,
        payload: AgentWeeklyPlanPayload,
    ) -> AgentWeeklyPlanRecord:
        if not current_session_is_admin():
            raise HTTPException(status_code=403, detail="只有机构负责人可以调整机器人部门周计划。")
        if payload.weekLabel != week_label or payload.agentKey != agent_key:
            raise HTTPException(status_code=400, detail="路径参数和计划内容不一致。")
        user = require_session_user()
        upsert_agent_weekly_plan_override(
            db=state.db,
            payload=payload,
            updated_by=user.fullName,
        )
        log_activity(
            "agent.plan.update",
            "agent_weekly_plan",
            f"{week_label}:{agent_key}",
            {
                "weekLabel": week_label,
                "agentKey": agent_key,
                "planItemCount": len(payload.planItems),
                "updatedBy": user.fullName,
            },
        )
        plans = build_agent_weekly_plans(
            db=state.db,
            week_label=week_label,
            thread_sync_path=THREAD_SYNC_DOC_PATH,
        )
        for plan in plans:
            if plan.agentKey == agent_key:
                return plan
        raise HTTPException(status_code=404, detail="未找到对应的机器人部门计划。")

    @app.post("/api/v1/settings", response_model=SettingsResponse)
    def update_settings(payload: AppSettingsPayload) -> SettingsResponse:
        wants_sensitive_update = any(
            value is not None and value != ""
            for value in [payload.aiProvider, payload.aiModel, payload.apiKey]
        ) or payload.clearApiKey
        if wants_sensitive_update and get_system_admin_settings().protectAiAndCloud:
            ensure_admin_for_sensitive_settings()
        elif payload.currentOperatorId:
            ensure_business_settings_editable()
        if payload.currentOperatorId:
            operator = state.db.fetchone("SELECT * FROM operators WHERE id = ?", (payload.currentOperatorId,))
            if not operator:
                raise HTTPException(status_code=404, detail="Operator not found")
            state.db.set_setting("current_operator_id", payload.currentOperatorId)
            state.db.execute("UPDATE operators SET is_current = CASE WHEN id = ? THEN 1 ELSE 0 END", (payload.currentOperatorId,))
        state.ai.configure(payload.aiProvider, payload.aiModel, payload.apiKey, payload.clearApiKey)
        log_activity("settings.update", "settings", "app", payload.model_dump(exclude_none=True))
        return build_settings_response()

    @app.get("/api/v1/settings/tasks", response_model=TaskSettingsRecord)
    def get_task_settings() -> TaskSettingsRecord:
        if get_cloud_token():
            try:
                payload = cloud_request("GET", "/api/v1/settings/tasks")
                if isinstance(payload, dict):
                    return TaskSettingsRecord(**payload)
            except Exception:
                pass  # cloud down — fall back to local
        return _get_local_task_settings()

    @app.post("/api/v1/settings/tasks", response_model=TaskSettingsRecord)
    def update_task_settings(payload: TaskSettingsPayload) -> TaskSettingsRecord:
        ensure_business_settings_editable()
        if get_cloud_token():
            response = cloud_request("POST", "/api/v1/settings/tasks", json_body=payload.model_dump(exclude_none=True))
            if not isinstance(response, dict):
                raise HTTPException(status_code=502, detail="Invalid task settings payload")
            return TaskSettingsRecord(**response)
        operator_id = str(current_operator_row()["id"])
        current = _get_local_task_settings(operator_id)
        next_default_list_id = payload.defaultListId if payload.defaultListId is not None else current.defaultListId
        if next_default_list_id:
            list_row = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (next_default_list_id,))
            if not list_row or list_row["archived_at"]:
                raise HTTPException(status_code=400, detail="默认清单无效")
        timestamp = now_iso()
        next_record = TaskSettingsRecord(
            defaultListId=next_default_list_id,
            defaultPriority=payload.defaultPriority or current.defaultPriority,
            defaultDueDatePreset=payload.defaultDueDatePreset or current.defaultDueDatePreset,
            defaultViewMode=payload.defaultViewMode or current.defaultViewMode,
            listSortMode=payload.listSortMode or current.listSortMode,
            showCompletedTasks=payload.showCompletedTasks if payload.showCompletedTasks is not None else current.showCompletedTasks,
            defaultReviewScope=payload.defaultReviewScope or current.defaultReviewScope,
            autoAssignSelf=payload.autoAssignSelf if payload.autoAssignSelf is not None else current.autoAssignSelf,
            updatedAt=timestamp,
        )
        state.db.execute(
            """
            INSERT OR REPLACE INTO task_settings(
                operator_id, default_list_id, default_priority, default_due_date_preset,
                default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
                auto_assign_self, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                operator_id,
                next_record.defaultListId,
                next_record.defaultPriority,
                next_record.defaultDueDatePreset,
                next_record.defaultViewMode,
                next_record.listSortMode,
                1 if next_record.showCompletedTasks else 0,
                next_record.defaultReviewScope,
                1 if next_record.autoAssignSelf else 0,
                next_record.updatedAt,
            ),
        )
        if next_record.defaultListId:
            state.db.execute(
                "UPDATE task_lists SET is_default = CASE WHEN id = ? THEN 1 ELSE 0 END",
                (next_record.defaultListId,),
        )
        log_activity("settings.tasks.update", "settings", operator_id, payload.model_dump(exclude_none=True))
        return _get_local_task_settings(operator_id)

    @app.get("/api/v1/settings/review-governance", response_model=ReviewGovernanceSettingsRecord)
    def read_review_governance_settings() -> ReviewGovernanceSettingsRecord:
        ensure_admin_for_sensitive_settings()
        return _review_governance_with_members()

    @app.post("/api/v1/settings/review-governance", response_model=ReviewGovernanceSettingsRecord)
    def update_review_governance_settings(payload: ReviewGovernanceSettingsPayload) -> ReviewGovernanceSettingsRecord:
        ensure_admin_for_sensitive_settings()
        record = _sanitize_review_governance_settings(payload.departments)
        state.db.set_setting("settings.review_governance", to_json(record.model_dump()))
        log_activity(
            "settings.review_governance.update",
            "settings",
            "review_governance",
            {"departmentCount": len(record.departments)},
        )
        return record

    @app.get("/api/v1/settings/org-dna", response_model=OrganizationDnaResponse)
    def get_organization_dna() -> OrganizationDnaResponse:
        return OrganizationDnaResponse(modules=list_organization_dna_modules())

    @app.get("/api/v1/settings/org-dna/{module_key}", response_model=OrganizationDnaModuleRecord)
    def get_organization_dna_module(module_key: str) -> OrganizationDnaModuleRecord:
        modules = {module.moduleKey: module for module in list_organization_dna_modules()}
        module = modules.get(module_key)
        if not module:
            raise HTTPException(status_code=404, detail="未知的组织 DNA 模块")
        return module

    @app.post("/api/v1/settings/org-dna/{module_key}", response_model=OrganizationDnaModuleRecord)
    def update_organization_dna_module(module_key: str, payload: OrganizationDnaUploadPayload) -> OrganizationDnaModuleRecord:
        ensure_org_dna_editable()
        record = upsert_organization_dna_module(module_key, payload)
        log_activity("settings.org_dna.update", "settings", module_key, {"moduleKey": module_key, "fileName": record.fileName, "contentHash": record.contentHash})
        return record

    @app.get("/api/v1/settings/client-workspace", response_model=ClientWorkspaceSettingsRecord)
    def read_client_workspace_settings() -> ClientWorkspaceSettingsRecord:
        return get_client_workspace_settings()

    @app.post("/api/v1/settings/client-workspace", response_model=ClientWorkspaceSettingsRecord)
    def update_client_workspace_settings(payload: ClientWorkspaceSettingsPayload) -> ClientWorkspaceSettingsRecord:
        ensure_business_settings_editable()
        current = get_client_workspace_settings()
        next_payload = current.model_dump()
        next_payload.update(payload.model_dump(exclude_none=True))
        next_payload["updatedAt"] = now_iso()
        next_record = ClientWorkspaceSettingsRecord(**next_payload)
        if next_record.meetingPublishDefaultListId:
            list_row = state.db.fetchone("SELECT id, archived_at FROM task_lists WHERE id = ?", (next_record.meetingPublishDefaultListId,))
            if not list_row or list_row["archived_at"]:
                raise HTTPException(status_code=400, detail="默认会议任务清单无效")
        _save_json_settings_record("settings.client_workspace", next_record)
        log_activity("settings.client_workspace.update", "settings", "client_workspace", payload.model_dump(exclude_none=True))
        return next_record

    @app.get("/api/v1/settings/topics", response_model=TopicsSettingsRecord)
    def read_topics_settings() -> TopicsSettingsRecord:
        return get_topics_settings()

    @app.post("/api/v1/settings/topics", response_model=TopicsSettingsRecord)
    def update_topics_settings(payload: TopicsSettingsPayload) -> TopicsSettingsRecord:
        ensure_business_settings_editable()
        current = get_topics_settings()
        next_payload = current.model_dump()
        next_payload.update(payload.model_dump(exclude_none=True))
        next_payload["updatedAt"] = now_iso()
        next_record = TopicsSettingsRecord(**next_payload)
        _save_json_settings_record("settings.topics", next_record)
        log_activity("settings.topics.update", "settings", "topics", payload.model_dump(exclude_none=True))
        return next_record

    @app.get("/api/v1/settings/analysis-workbench", response_model=AnalysisWorkbenchSettingsRecord)
    def read_analysis_workbench_settings() -> AnalysisWorkbenchSettingsRecord:
        return get_analysis_workbench_settings()

    @app.post("/api/v1/settings/analysis-workbench", response_model=AnalysisWorkbenchSettingsRecord)
    def update_analysis_workbench_settings(payload: AnalysisWorkbenchSettingsPayload) -> AnalysisWorkbenchSettingsRecord:
        ensure_business_settings_editable()
        current = get_analysis_workbench_settings()
        next_payload = current.model_dump()
        next_payload.update(payload.model_dump(exclude_none=True))
        next_payload["updatedAt"] = now_iso()
        enabled_ids = [str(item) for item in next_payload.get("enabledTemplateIds", [])]
        known_ids = {str(row["id"]) for row in state.db.fetchall("SELECT id FROM analysis_templates")}
        if enabled_ids:
            unknown_ids = [item for item in enabled_ids if item not in known_ids]
            if unknown_ids:
                raise HTTPException(status_code=400, detail=f"未知的分析模板：{'、'.join(unknown_ids)}")
        default_template_id = next_payload.get("defaultTemplateId")
        if default_template_id and default_template_id not in known_ids:
            raise HTTPException(status_code=400, detail="默认分析模板无效")
        next_record = AnalysisWorkbenchSettingsRecord(**next_payload)
        next_record = save_analysis_workbench_settings(next_record)
        log_activity("settings.analysis_workbench.update", "settings", "analysis_workbench", payload.model_dump(exclude_none=True))
        return next_record

    @app.get("/api/v1/settings/handbook", response_model=HandbookSettingsRecord)
    def read_handbook_settings() -> HandbookSettingsRecord:
        return get_handbook_settings()

    @app.post("/api/v1/settings/handbook", response_model=HandbookSettingsRecord)
    def update_handbook_settings(payload: HandbookSettingsPayload) -> HandbookSettingsRecord:
        ensure_business_settings_editable()
        current = get_handbook_settings()
        next_payload = current.model_dump()
        next_payload.update(payload.model_dump(exclude_none=True))
        next_payload["updatedAt"] = now_iso()
        next_record = HandbookSettingsRecord(**next_payload)
        _save_json_settings_record("settings.handbook", next_record)
        log_activity("settings.handbook.update", "settings", "handbook", payload.model_dump(exclude_none=True))
        return next_record

    @app.get("/api/v1/settings/system-admin", response_model=SystemAdminSettingsRecord)
    def read_system_admin_settings() -> SystemAdminSettingsRecord:
        return get_system_admin_settings()

    @app.post("/api/v1/settings/system-admin", response_model=SystemAdminSettingsRecord)
    def update_system_admin_settings(payload: SystemAdminSettingsPayload) -> SystemAdminSettingsRecord:
        ensure_admin_for_sensitive_settings()
        current = get_system_admin_settings()
        next_payload = current.model_dump()
        updates = payload.model_dump(exclude_none=True)
        if "brandLogoDataUrl" in updates:
            updates["brandLogoDataUrl"] = _normalize_brand_logo_data_url(updates.get("brandLogoDataUrl"))
        next_payload.update(updates)
        next_payload["updatedAt"] = now_iso()
        next_record = SystemAdminSettingsRecord(**next_payload)
        _save_json_settings_record("settings.system_admin", next_record)
        logged_updates = dict(updates)
        if "brandLogoDataUrl" in logged_updates:
            logged_updates["brandLogoDataUrl"] = "[PNG data URL omitted]" if logged_updates["brandLogoDataUrl"] else None
        log_activity("settings.system_admin.update", "settings", "system_admin", logged_updates)
        return next_record

    @app.get("/api/v1/settings/main-chain-stability", response_model=MainChainStabilitySettingsRecord)
    def read_main_chain_stability_settings() -> MainChainStabilitySettingsRecord:
        return get_main_chain_stability_settings()

    @app.post("/api/v1/settings/main-chain-stability", response_model=MainChainStabilitySettingsRecord)
    def update_main_chain_stability_settings(payload: MainChainStabilitySettingsPayload) -> MainChainStabilitySettingsRecord:
        ensure_admin_for_sensitive_settings()
        record = save_main_chain_stability_settings(payload)
        log_activity("settings.main_chain_stability.update", "settings", "main_chain_stability", payload.model_dump(exclude_none=True))
        return record

    @app.get("/api/v1/settings/feishu-bot", response_model=FeishuBotSettingsRecord)
    def read_feishu_bot_settings() -> FeishuBotSettingsRecord:
        return get_feishu_bot_settings()

    @app.post("/api/v1/settings/feishu-bot", response_model=FeishuBotSettingsRecord)
    def save_feishu_bot_settings(payload: FeishuBotSettingsPayload) -> FeishuBotSettingsRecord:
        ensure_admin_for_sensitive_settings()
        return update_feishu_bot_settings(payload)

    @app.get("/api/v1/settings/feishu-user-binding", response_model=FeishuUserBindingRecord)
    def read_feishu_user_binding() -> FeishuUserBindingRecord:
        user = require_session_user()
        sync_feishu_user_binding_from_cloud_relay(user.id)
        return get_feishu_user_binding(user.id)

    @app.post("/api/v1/settings/feishu-user-binding/start", response_model=FeishuUserBindingStartResponse)
    def start_feishu_user_binding(request: Request) -> FeishuUserBindingStartResponse:
        user = require_session_user()
        settings = get_feishu_bot_settings()
        if not settings.appId.strip():
            raise HTTPException(status_code=400, detail="请先在系统设置里配置飞书 App ID。")
        try:
            app_secret = state.feishu_secret_store.get_api_key().strip()
        except Exception:
            app_secret = ""
        if not app_secret:
            raise HTTPException(status_code=400, detail="请先在系统设置里保存飞书 App Secret。")
        _clear_feishu_cloud_relay_session(user.id)
        expires_at = (datetime.now() + timedelta(minutes=10)).replace(microsecond=0).isoformat()
        state_token = new_id("fs_state")
        save_feishu_oauth_state(state_token, user.id, expires_at)
        configured_callback_url = settings.userBindingCallbackUrl.strip()
        local_callback_url = f"{str(request.base_url).rstrip('/')}/api/v1/auth/feishu/callback"
        cloud_callback_url = _feishu_cloud_relay_callback_url()
        callback_url = configured_callback_url or local_callback_url
        pending_mode = "local"
        if _is_public_feishu_callback_url(configured_callback_url):
            callback_url = configured_callback_url
        elif _is_public_feishu_callback_url(cloud_callback_url):
            cloud_request(
                "POST",
                "/api/v1/integrations/feishu/user-binding/sessions",
                json_body={"state": state_token, "expiresAt": expires_at},
            )
            callback_url = cloud_callback_url
            pending_mode = "cloud_relay"
        save_feishu_user_binding_pending(
            user.id,
            state_token=state_token,
            expires_at=expires_at,
            callback_url=callback_url,
            mode=pending_mode,
        )
        authorize_url = build_user_authorize_url(app_id=settings.appId.strip(), redirect_uri=callback_url, state=state_token)
        qr_ready = _is_public_feishu_callback_url(callback_url)
        qr_blocked_reason = None if qr_ready else "当前回调地址仍是本机地址或非 HTTPS 地址，手机扫码后无法把授权结果回传到这台工作台。请先配置可公网访问的 HTTPS 回调地址，或直接在当前电脑浏览器完成授权。"
        log_activity("feishu.user_binding.start", "settings", user.id, {"callbackUrl": callback_url})
        return FeishuUserBindingStartResponse(
            authorizeUrl=authorize_url,
            state=state_token,
            expiresAt=expires_at,
            callbackUrl=callback_url,
            qrReady=qr_ready,
            qrBlockedReason=qr_blocked_reason,
        )

    @app.delete("/api/v1/settings/feishu-user-binding", response_model=FeishuUserBindingRecord)
    def delete_feishu_user_binding() -> FeishuUserBindingRecord:
        user = require_session_user()
        _clear_feishu_cloud_relay_session(user.id)
        cleared = clear_feishu_user_binding(user.id)
        log_activity("feishu.user_binding.clear", "settings", user.id, {})
        return cleared

    @app.get("/api/v1/auth/feishu/callback", response_class=HTMLResponse)
    def receive_feishu_auth_callback(
        code: str | None = Query(default=None),
        state_token: str | None = Query(default=None, alias="state"),
    ) -> HTMLResponse:
        if not state_token:
            return _render_feishu_binding_callback_page("飞书绑定失败", "缺少 state，无法确认这次授权属于哪个工作台会话。", success=False)
        oauth_state = pop_feishu_oauth_state(state_token)
        if not oauth_state:
            return _render_feishu_binding_callback_page("飞书绑定失败", "这次授权状态已失效，请回到工作台重新发起绑定。", success=False)
        expires_at = oauth_state.get("expiresAt", "")
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) <= datetime.now():
                    return _render_feishu_binding_callback_page("飞书绑定失败", "这次授权请求已经过期，请回到工作台重新发起绑定。", success=False)
            except ValueError:
                return _render_feishu_binding_callback_page("飞书绑定失败", "授权状态已损坏，请回到工作台重新发起绑定。", success=False)
        user_id = oauth_state.get("userId", "").strip()
        if not user_id:
            return _render_feishu_binding_callback_page("飞书绑定失败", "这次授权缺少用户信息，请重新发起绑定。", success=False)
        if not code or not code.strip():
            return _render_feishu_binding_callback_page("飞书绑定失败", "飞书没有返回有效授权码，请重新发起绑定。", success=False)

        try:
            binding = _finalize_feishu_user_binding(user_id, code.strip())
            clear_feishu_user_binding_pending(user_id)
            return _render_feishu_binding_callback_page("飞书账号绑定成功", f"已绑定 {binding.name or binding.email or binding.openId}。后续在任务与日历里发起飞书会议时，会优先按当前登录员工的绑定身份发送。", success=True)
        except FeishuApiError as exc:
            _save_feishu_user_binding_error(user_id, str(exc))
            clear_feishu_user_binding_pending(user_id)
            return _render_feishu_binding_callback_page("飞书绑定失败", str(exc), success=False)
        except HTTPException as exc:
            _save_feishu_user_binding_error(user_id, str(exc.detail))
            clear_feishu_user_binding_pending(user_id)
            return _render_feishu_binding_callback_page("飞书绑定失败", str(exc.detail), success=False)

    @app.post("/api/v1/channels/feishu/events")
    async def receive_feishu_events(request: Request) -> dict[str, object]:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Invalid Feishu event payload")
        return handle_feishu_event(payload)

    @app.post("/api/v1/settings/backup", response_model=BackupResponse)
    def create_backup() -> BackupResponse:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = state.backup_dir / f"yiyu-workbench-{timestamp}.db"
        state.db.backup_to(backup_path)
        state.db.set_setting("last_backup_at", now_iso())
        log_activity("settings.backup", "backup", timestamp, {"path": str(backup_path)})
        return BackupResponse(backupPath=str(backup_path), createdAt=now_iso())

    @app.post("/api/v1/settings/demo-data/load", response_model=DemoDataResponse)
    def load_demo_dataset_endpoint() -> DemoDataResponse:
        response = load_demo_dataset(state)
        log_activity("settings.demo.load", "settings", "demo_data", response.model_dump())
        return response

    @app.post("/api/v1/settings/demo-data/clear", response_model=DemoDataResponse)
    def clear_demo_dataset_endpoint() -> DemoDataResponse:
        response = clear_demo_dataset(state)
        log_activity("settings.demo.clear", "settings", "demo_data", response.model_dump())
        return response

    @app.post("/api/v1/settings/legacy-scan", response_model=LegacyScanResponse)
    def legacy_scan(payload: LegacyScanRequest) -> LegacyScanResponse:
        target = Path(payload.path).expanduser()
        if not target.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        entries: list[LegacyScanEntry] = []
        for path in target.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".db", ".sqlite", ".json", ".csv"}:
                suffix = path.suffix.lower()
                entries.append(
                    LegacyScanEntry(
                        path=str(path),
                        kind=suffix.lstrip("."),
                        importable=suffix in LEGACY_IMPORT_EXTENSIONS,
                    )
                )
        return LegacyScanResponse(
            path=str(target),
            found=[item.path for item in entries[:30]],
            entries=entries[:30],
            message="已完成旧数据候选扫描。JSON/CSV 可导入到资料缓冲池，DB/SQLite 仅保留扫描结果供后续适配。",
        )

    @app.get("/api/v1/clients", response_model=list[ClientSummary])
    def list_clients() -> list[ClientSummary]:
        return [build_client_summary(str(row["id"])) for row in state.db.fetchall("SELECT id FROM clients ORDER BY updated_at DESC")]

    @app.post("/api/v1/clients", response_model=ClientSummary)
    def create_client(payload: ClientMutationPayload) -> ClientSummary:
        client_id = new_id("client")
        timestamp = now_iso()
        client_color = (payload.color or "").strip() or "#5B7BFE"
        state.db.execute(
            """
            INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                payload.name,
                payload.alias,
                payload.domain,
                payload.type,
                payload.intro,
                payload.stage,
                client_color,
                timestamp,
                timestamp,
            ),
        )
        thread_id = new_id("thread")
        state.db.execute(
            "INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
            (thread_id, client_id, "默认研判线程", timestamp, timestamp),
        )
        ensure_standard_client_folders(client_id)
        log_activity("client.create", "client", client_id, payload.model_dump())
        return build_client_summary(client_id)

    @app.put("/api/v1/clients/{client_id}", response_model=ClientSummary)
    def update_client(client_id: str, payload: ClientMutationPayload) -> ClientSummary:
        row = state.db.fetchone("SELECT color FROM clients WHERE id = ?", (client_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Client not found")
        client_color = (payload.color or "").strip() or str(row["color"] or "#5B7BFE")
        state.db.execute(
            """
            UPDATE clients
            SET name = ?, alias = ?, domain = ?, type = ?, intro = ?, stage = ?, color = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name,
                payload.alias,
                payload.domain,
                payload.type,
                payload.intro,
                payload.stage,
                client_color,
                now_iso(),
                client_id,
            ),
        )
        ensure_standard_client_folders(client_id)
        log_activity("client.update", "client", client_id, payload.model_dump())
        return build_client_summary(client_id)

    @app.delete("/api/v1/clients/{client_id}/folders/{folder_id}")
    def delete_client_folder(client_id: str, folder_id: str) -> dict[str, bool]:
        build_client_summary(client_id)
        ensure_standard_client_folders(client_id)
        row = state.db.fetchone("SELECT * FROM client_folders WHERE id = ? AND client_id = ?", (folder_id, client_id))
        if not row:
            raise HTTPException(status_code=404, detail="Folder not found")
        label = str(row["label"])
        file_count = int(row["file_count"] or 0)
        if file_count > 0:
            raise HTTPException(status_code=400, detail="该文件夹下还有文件，暂时不能移除")
        hide_client_folder_label(client_id, label)
        log_activity("client.folder.hide", "client_folder", folder_id, {"clientId": client_id, "label": label})
        return {"deleted": True}

    @app.delete("/api/v1/clients/{client_id}")
    def delete_client(client_id: str) -> dict[str, bool]:
        row = state.db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Client not found")
        client_name = str(row["name"] or client_id)
        workspace_root = state.data_dir / "client_workspace" / client_id
        vector_root = state.data_dir / "vector_store" / client_id
        state.db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        for target in (workspace_root, vector_root):
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
        log_activity("client.delete", "client", client_id, {"name": client_name})
        return {"deleted": True}

    @app.get("/api/v1/clients/{client_id}/workspace", response_model=ClientWorkspaceResponse)
    def get_client_workspace(client_id: str) -> ClientWorkspaceResponse:
        return workspace_for_client(client_id)

    @app.post("/api/v1/analysis/jobs", response_model=AnalysisJobRecord)
    def create_analysis_job_endpoint(payload: AnalysisJobCreatePayload) -> AnalysisJobRecord:
        build_client_summary(payload.clientId)
        workspace = workspace_for_client(payload.clientId)
        return create_analysis_job(
            state.db,
            payload,
            source_snapshot={
                "clientId": workspace.client.id,
                "scopeType": payload.scopeType or "client",
                "scopeId": payload.scopeId,
                "question": payload.question,
                "sourceScope": payload.sourceScope,
                "featureFlags": payload.featureFlags,
                "documents": [(item.id, item.updatedAt) for item in workspace.documentCards[:60]],
                "meetings": [(item.id, item.updatedAt) for item in workspace.meetings[:24]],
                "tasks": [
                    (item.id, item.updatedAt, item.status, item.eventLineId, item.projectModuleId, item.projectFlowId)
                    for item in workspace.relatedTasks[:80]
                ],
            },
        )

    @app.post("/api/v1/analysis/backfill-main-chain", response_model=AnalysisBackfillMainChainResultRecord)
    def queue_analysis_main_chain_backfill(payload: AnalysisBackfillMainChainPayload) -> AnalysisBackfillMainChainResultRecord:
        for client_id in payload.clientIds:
            build_client_summary(client_id)
        return queue_main_chain_backfill(state.db, payload)

    @app.get("/api/v1/analysis/jobs/{jobId}", response_model=AnalysisJobRecord)
    def get_analysis_job_endpoint(jobId: str) -> AnalysisJobRecord:
        job = get_analysis_job(state.db, jobId)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        return job

    @app.get("/api/v1/analysis/jobs/{jobId}/stages", response_model=list[AnalysisJobStageRunRecord])
    def get_analysis_job_stages_endpoint(jobId: str) -> list[AnalysisJobStageRunRecord]:
        job = get_analysis_job(state.db, jobId)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        return list_analysis_job_stages(state.db, jobId)

    @app.get("/api/v1/runtime/run-log/{runId}", response_model=RuntimeRunLogRecord)
    def get_runtime_run_log_endpoint(runId: str) -> RuntimeRunLogRecord:
        run_log = get_runtime_run_log(state.db, runId)
        if run_log is None:
            raise HTTPException(status_code=404, detail="Run log not found")
        return run_log

    @app.post("/api/v1/memory/dna/delta", response_model=DnaDeltaRecord)
    def create_dna_delta_endpoint(payload: DnaDeltaCreatePayload) -> DnaDeltaRecord:
        build_client_summary(payload.clientId)
        return create_dna_delta(state.db, payload)

    @app.post("/api/v1/memory/judgments/confirm", response_model=JudgmentVersionRecord)
    def confirm_judgment_endpoint(payload: JudgmentConfirmPayload) -> JudgmentVersionRecord:
        session_user = get_cached_session_user()
        operator = current_operator_row()
        try:
            return confirm_judgment(
                state.db,
                payload,
                actor_id=session_user.id if session_user else operator["id"],
                actor_name=session_user.fullName if session_user else operator["name"],
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/approvals/decide", response_model=ApprovalRecordRecord)
    def decide_approval_endpoint(payload: ApprovalDecisionPayload) -> ApprovalRecordRecord:
        session_user = get_cached_session_user()
        operator = current_operator_row()
        try:
            return decide_approval(
                state.db,
                payload,
                actor_id=session_user.id if session_user else operator["id"],
                actor_name=session_user.fullName if session_user else operator["name"],
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/clients/{client_id}/judgments", response_model=list[JudgmentVersionRecord])
    def get_client_judgments(client_id: str) -> list[JudgmentVersionRecord]:
        build_client_summary(client_id)
        return list_judgment_versions(state.db, client_id)

    @app.get("/api/v1/clients/{client_id}/topics", response_model=list[ThemeClusterRecord])
    def get_client_topics(client_id: str) -> list[ThemeClusterRecord]:
        build_client_summary(client_id)
        return list_theme_clusters(state.db, client_id)

    @app.get("/api/v1/clients/{client_id}/conflicts", response_model=list[ConflictGroupRecord])
    def get_client_conflicts(client_id: str) -> list[ConflictGroupRecord]:
        build_client_summary(client_id)
        return list_conflict_groups(state.db, client_id)

    @app.get("/api/v1/clients/{client_id}/open-questions", response_model=list[OpenQuestionRecord])
    def get_client_open_questions(client_id: str) -> list[OpenQuestionRecord]:
        build_client_summary(client_id)
        return list_open_questions(state.db, client_id)

    @app.get("/api/v1/clients/{client_id}/runtime-run-logs", response_model=list[RuntimeRunLogRecord])
    def get_client_runtime_run_logs(client_id: str) -> list[RuntimeRunLogRecord]:
        build_client_summary(client_id)
        return list_runtime_run_logs(state.db, client_id)

    @app.get("/api/v1/runtime/analysis-migration-metrics", response_model=AnalysisMigrationMetricsRecord)
    def get_analysis_migration_metrics_endpoint() -> AnalysisMigrationMetricsRecord:
        return get_analysis_migration_metrics(state.db)

    @app.get("/api/v1/strategic/thoughts", response_model=StrategicThoughtsResponseRecord)
    def get_strategic_thoughts(
        clientId: str | None = Query(default=None),
        includeDismissed: bool = Query(default=False),
        limit: int = Query(default=20, ge=1, le=60),
    ) -> StrategicThoughtsResponseRecord:
        selected_client_id = (clientId or "").strip() or None
        if selected_client_id:
            build_client_summary(selected_client_id)
        thoughts = _build_strategic_thoughts(
            selected_client_id=selected_client_id,
            include_dismissed=includeDismissed,
            limit=limit,
        )
        return StrategicThoughtsResponseRecord(
            items=thoughts,
            total=len(thoughts),
            generatedAt=now_iso(),
            selectedClientId=selected_client_id,
            usingMockData=False,
        )

    @app.post("/api/v1/strategic/thoughts/{thought_id}/review", response_model=StrategicThoughtRecord)
    def review_strategic_thought(thought_id: str, payload: StrategicThoughtReviewPayload) -> StrategicThoughtRecord:
        thought = _find_strategic_thought_by_id(thought_id)
        if thought is None:
            raise HTTPException(status_code=404, detail="Thought not found")

        operator = current_operator_row()
        session_user = get_cached_session_user()
        reviewer_id = session_user.id if session_user else str(operator["id"] or "")
        reviewer_name = (
            session_user.fullName
            if session_user and session_user.fullName
            else str(operator["name"] or "系统")
        )
        note = (payload.note or "").strip()

        if payload.action == "mark_task_created" and not (payload.taskId or "").strip():
            raise HTTPException(status_code=400, detail="taskId is required when action=mark_task_created")

        status_map: dict[str, Literal["confirmed", "dismissed", "task_created"]] = {
            "confirm": "confirmed",
            "dismiss": "dismissed",
            "mark_task_created": "task_created",
        }
        review_status = status_map[payload.action]
        judgment_id: str | None = None
        if payload.action == "confirm" and payload.createJudgment:
            for source in thought.sources:
                if source.sourceType == "judgment_version" and source.sourceId:
                    try:
                        confirmed = confirm_judgment(
                            state.db,
                            JudgmentConfirmPayload(
                                judgmentId=source.sourceId,
                                action="approved",
                                note=note,
                            ),
                            actor_id=reviewer_id,
                            actor_name=reviewer_name,
                        )
                        judgment_id = confirmed.id
                        break
                    except ValueError:
                        continue

        review = _save_strategic_thought_review(
            thought=thought,
            status=review_status,
            note=note,
            task_id=(payload.taskId or "").strip() or None,
            judgment_id=judgment_id,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
        )
        thought.status = review.status
        thought.review = review
        return thought

    @app.get("/api/v1/clients/{client_id}/strategic-cockpit", response_model=StrategicCockpitSnapshotRecord)
    def get_strategic_cockpit(client_id: str) -> StrategicCockpitSnapshotRecord:
        build_client_summary(client_id)
        return build_strategic_cockpit_snapshot(client_id)

    @app.get("/api/v1/clients/{client_id}/strategic-cockpit/lines/{line_id}", response_model=StrategicLineDetailRecord)
    def get_strategic_line_detail(client_id: str, line_id: str) -> StrategicLineDetailRecord:
        build_client_summary(client_id)
        snapshot = build_strategic_cockpit_snapshot(client_id)
        line = next((item for item in snapshot.strategicLines if item.id == line_id), None)
        if line is None:
            raise HTTPException(status_code=404, detail="战略线不存在")
        task_rows = state.db.fetchall(
            """
            SELECT id, title
            FROM tasks
            WHERE client_id = ?
              AND (
                LOWER(COALESCE(title, '')) LIKE '%' || LOWER(?) || '%'
                OR LOWER(COALESCE(description, '')) LIKE '%' || LOWER(?) || '%'
                OR LOWER(COALESCE(recent_decision, '')) LIKE '%' || LOWER(?) || '%'
                OR LOWER(COALESCE(current_blocker, '')) LIKE '%' || LOWER(?) || '%'
              )
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 8
            """,
            (client_id, line.title, line.title, line.title, line.title),
        )
        return StrategicLineDetailRecord(
            **line.model_dump(),
            clientId=snapshot.clientId,
            clientName=snapshot.clientName,
            stageLabel=snapshot.stageLabel,
            relatedTaskIds=[str(row["id"]) for row in task_rows],
            relatedTaskTitles=[str(row["title"]) for row in task_rows],
            contextSummary=f"战略线「{line.title}」当前处在「{line.stage or snapshot.stageLabel}」，下一步是「{line.nextStep}」。",
        )

    @app.post("/api/v1/clients/{client_id}/strategic-cockpit/confirm", response_model=StrategicCockpitSnapshotRecord)
    def confirm_strategic_cockpit(client_id: str, payload: StrategicCockpitConfirmPayload) -> StrategicCockpitSnapshotRecord:
        build_client_summary(client_id)
        session_user = _require_strategic_ceo()
        save_strategic_cockpit_snapshot(client_id, payload, session_user)
        snapshot = build_strategic_cockpit_snapshot(client_id)
        growth_user_id, growth_user_name = resolve_growth_actor()
        ingest_strategic_growth_candidate(
            state.db,
            user_id=growth_user_id,
            user_name=growth_user_name,
            snapshot=snapshot,
            source_type="strategic_confirm",
            source_id=client_id,
            created_at=now_iso(),
        )
        return snapshot

    @app.post("/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack", response_model=MeetingPipelineResponse)
    def create_strategic_meeting_pack(client_id: str) -> MeetingPipelineResponse:
        build_client_summary(client_id)
        _require_strategic_ceo()
        meeting = _create_strategic_meeting_pack(client_id)
        return MeetingPipelineResponse(meeting=meeting, message="战略陪伴周会草稿已创建，并已把周会清单正式写入会议对象。")

    @app.post("/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack/{meeting_id}/apply", response_model=StrategicCockpitSnapshotRecord)
    def apply_strategic_meeting_pack(client_id: str, meeting_id: str) -> StrategicCockpitSnapshotRecord:
        build_client_summary(client_id)
        session_user = _require_strategic_ceo()
        meeting = build_meeting_detail(meeting_id)
        if meeting.clientId != client_id:
            raise HTTPException(status_code=404, detail="Meeting not found")
        has_post_meeting_content = bool(
            meeting.transcriptText.strip()
            or meeting.decisions
            or meeting.actionItems
            or meeting.risks
            or meeting.ambiguities
        )
        if not has_post_meeting_content:
            raise HTTPException(status_code=400, detail="当前会议还没有会后内容，无法回填战略判断。")
        payload = _build_strategic_payload_from_meeting(client_id, meeting)
        save_strategic_cockpit_snapshot(client_id, payload, session_user)
        record_meeting_publish_writeback(
            state.db,
            client_id=client_id,
            meeting_id=meeting_id,
            meeting_title=meeting.title,
            event_line_ids=_strategic_meeting_event_line_ids(client_id, meeting.title, meeting_id=meeting_id),
        )
        log_activity("strategic_cockpit.apply_meeting_pack", "meeting", meeting_id, {"clientId": client_id})
        snapshot = build_strategic_cockpit_snapshot(client_id)
        growth_user_id, growth_user_name = resolve_growth_actor()
        ingest_strategic_growth_candidate(
            state.db,
            user_id=growth_user_id,
            user_name=growth_user_name,
            snapshot=snapshot,
            source_type="strategic_meeting_apply",
            source_id=meeting_id,
            meeting_id=meeting_id,
            created_at=now_iso(),
        )
        return snapshot

    @app.get("/api/v1/clients/{client_id}/notebook", response_model=ClientNotebookResponse)
    def get_client_notebook(client_id: str) -> ClientNotebookResponse:
        build_client_summary(client_id)
        return get_client_notebook_response(state.db, client_id)

    @app.get("/api/v1/clients/{client_id}/memory-status", response_model=MemoryStatus)
    def get_client_memory_status_route(client_id: str) -> MemoryStatus:
        build_client_summary(client_id)
        return get_client_memory_status(state.db, client_id)

    @app.post("/api/v1/memory/backfill", response_model=MemoryBackfillResultRecord)
    def backfill_memory_foundation_route() -> MemoryBackfillResultRecord:
        # 先把文档知识灌入记忆
        from app.services.memory_foundation import backfill_document_knowledge_to_memory
        doc_stats = backfill_document_knowledge_to_memory(state.db)
        if state.system_logger:
            state.system_logger.info("memory", f"文档知识回流完成: {doc_stats}")
        # 再执行原有的记忆回填
        result = backfill_memory_foundation(state.db)
        return result

    @app.post("/api/v1/memory/backfill-documents")
    def backfill_document_knowledge_route() -> dict:
        """单独触发文档知识→记忆回流。"""
        from app.services.memory_foundation import backfill_document_knowledge_to_memory
        stats = backfill_document_knowledge_to_memory(state.db)
        # 回流完后刷新所有客户的 notebook
        clients = state.db.fetchall("SELECT id FROM clients")
        refreshed = 0
        for client in clients:
            try:
                refresh_organization_notebook_snapshot(state.db, str(client["id"]))
                refreshed += 1
            except Exception:
                pass
        stats["notebooks_refreshed"] = refreshed
        if state.system_logger:
            state.system_logger.info("memory", f"文档知识回流+notebook刷新: {stats}")
        return stats

    @app.post("/api/v1/clarifications", response_model=ClarificationRecord)
    def create_clarification(payload: ClarificationCreatePayload) -> ClarificationRecord:
        if payload.scopeType == "client":
            build_client_summary(payload.scopeId)
        elif payload.scopeType == "event_line" and not state.db.fetchone("SELECT id FROM event_lines WHERE id = ?", (payload.scopeId,)):
            raise HTTPException(status_code=404, detail="Event line not found")
        return create_clarification_record(state.db, payload)

    @app.post("/api/v1/clarifications/{clarification_id}/answer", response_model=ClarificationRecord)
    def answer_clarification(clarification_id: str, payload: ClarificationAnswerPayload) -> ClarificationRecord:
        try:
            return answer_clarification_record(state.db, clarification_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Clarification not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/clients/{client_id}/knowledge/reclass-events", response_model=list[FileReclassEventRecord])
    def list_reclass_events(client_id: str) -> list[FileReclassEventRecord]:
        build_client_summary(client_id)
        return [FileReclassEventRecord(**item) for item in fetch_recent_reclass_events(state.db, client_id, limit=50)]

    @app.get("/api/v1/clients/{client_id}/knowledge/status", response_model=KnowledgeStatusRecord)
    def get_client_knowledge_status(client_id: str) -> KnowledgeStatusRecord:
        build_client_summary(client_id)
        ensure_standard_client_folders(client_id)
        return build_knowledge_status_record(client_id)

    @app.post("/api/v1/clients/{client_id}/knowledge/rebuild", response_model=KnowledgeJobRecord)
    def rebuild_client_knowledge(client_id: str) -> KnowledgeJobRecord:
        build_client_summary(client_id)
        primary_job_types = (*MAIN_KNOWLEDGE_STATUS_JOB_TYPES, "rebuild_client_knowledge")
        placeholders = ", ".join("?" for _ in primary_job_types)
        pending = state.db.fetchone(
            f"""
            SELECT *
            FROM knowledge_jobs
            WHERE client_id = ? AND job_type IN ({placeholders}) AND status IN ('queued', 'running')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (client_id, *primary_job_types),
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
        total_items = int(state.db.scalar("SELECT COUNT(1) AS count FROM documents WHERE client_id = ?", (client_id,)))
        job = enqueue_knowledge_job(
            client_id,
            "rebuild_client_knowledge",
            {"clientId": client_id},
            total_items=total_items,
        )
        log_activity("knowledge.rebuild", "client", client_id, {"jobId": job.id})
        return job

    @app.post("/api/v1/clients/{client_id}/knowledge/search", response_model=KnowledgeSearchResponse)
    def search_client_knowledge(client_id: str, payload: ChatRequest) -> KnowledgeSearchResponse:
        build_client_summary(client_id)
        query = payload.prompt.strip()
        retrieval_started = perf_counter()
        bundle = build_retrieval_bundle(client_id, query)
        retrieval_elapsed_ms = round((perf_counter() - retrieval_started) * 1000, 2)
        hits = [
            KnowledgeSearchHitRecord(
                title=item.title,
                excerpt=item.excerpt,
                score=item.score,
                stage={"master_index": "master_index", "surrogate": "surrogate"}.get(item.source_stage, "raw_chunk"),  # type: ignore[arg-type]
                path=item.path,
                sectionLabel=item.section_label,
                matchedTerms=item.matched_terms,
            )
            for item in bundle.citations
        ]
        preview_evidence = [
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
            for item in bundle.citations
        ]
        retrieval_meta = bundle.retrieval_summary if isinstance(bundle.retrieval_summary, dict) else {}
        preview_summary = build_retrieval_preview_summary(client_id, query, preview_evidence, bundle)
        work_trace = build_answer_work_trace(query, preview_evidence, bundle)
        bundle.retrieval_summary = {
            **retrieval_meta,
            "previewSummary": preview_summary,
            "workTrace": work_trace,
        }
        retrieval_meta = bundle.retrieval_summary
        search_id = persist_retrieval_bundle(client_id, query, payload.threadId, bundle, retrieval_elapsed_ms)
        return KnowledgeSearchResponse(
            searchId=search_id,
            clientId=client_id,
            query=query,
            coverage=bundle.coverage,
            matchedTerms=bundle.matched_terms,
            masterHitCount=int(retrieval_meta.get("masterHitCount", 0) or 0),
            surrogateHitCount=int(retrieval_meta.get("surrogateHitCount", 0) or 0),
            rawChunkHitCount=int(retrieval_meta.get("rawChunkHitCount", 0) or 0),
            drillthroughUsed=bool(retrieval_meta.get("drillthroughUsed", False)),
            strategicMode=bool(retrieval_meta.get("strategicMode", False)),
            categoryCoverage=[str(item) for item in retrieval_meta.get("categoryCoverage", []) if str(item).strip()] if isinstance(retrieval_meta.get("categoryCoverage"), list) else [],
            preferredCategories=[str(item) for item in retrieval_meta.get("preferredCategories", []) if str(item).strip()] if isinstance(retrieval_meta.get("preferredCategories"), list) else [],
            phase="grounding",
            progress=38.0,
            progressFloor=25.0,
            progressCeiling=55.0,
            stageLabel="庆华已经整理好当前问题所需的背景材料，准备调用千问组织答案",
            lastUpdatedAt=now_iso(),
            failureReason=bundle.failure_reason,
            hits=hits,
            previewSummary=preview_summary,
        )

    @app.get("/api/v1/clients/{client_id}/goals", response_model=list[GoalRecord])
    def list_client_goals(client_id: str) -> list[GoalRecord]:
        return workspace_for_client(client_id).goals

    @app.post("/api/v1/clients/{client_id}/goals", response_model=GoalRecord)
    def create_goal(client_id: str, payload: GoalPayload) -> GoalRecord:
        build_client_summary(client_id)
        goal_id = new_id("goal")
        timestamp = now_iso()
        state.db.execute(
            """
            INSERT INTO goal_records(id, client_id, title, quarter, progress, owner_name, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (goal_id, client_id, payload.title, payload.quarter, payload.progress, payload.ownerName, timestamp, timestamp),
        )
        log_activity("goal.create", "goal", goal_id, payload.model_dump())
        return GoalRecord(id=goal_id, clientId=client_id, title=payload.title, quarter=payload.quarter, progress=payload.progress, ownerName=payload.ownerName)

    @app.get("/api/v1/clients/{client_id}/dna-documents", response_model=ClientDnaModulesResponse)
    def list_client_dna_documents(client_id: str) -> ClientDnaModulesResponse:
        build_client_summary(client_id)
        return ClientDnaModulesResponse(modules=list_client_dna_modules(client_id))

    @app.post("/api/v1/clients/{client_id}/dna-documents/generate", response_model=KnowledgeJobRecord)
    def generate_client_dna_documents(client_id: str, payload: ClientDnaGeneratePayload) -> KnowledgeJobRecord:
        build_client_summary(client_id)
        ensure_standard_client_folders(client_id)
        job = maybe_enqueue_client_dna_generation_job(client_id, refresh_generated=payload.refreshGenerated)
        if job is not None:
            log_activity(
                "client.dna_document.generate",
                "client",
                client_id,
                {"refreshGenerated": payload.refreshGenerated, "jobId": job.id},
            )
            return job
        return KnowledgeJobRecord(
            id=new_id("kjob"),
            clientId=client_id,
            jobType="generate_client_dna_candidates",
            status="completed",
            totalItems=0,
            processedItems=0,
            createdAt=now_iso(),
            updatedAt=now_iso(),
        )

    @app.get("/api/v1/clients/{client_id}/dna-documents/{module_key}", response_model=ClientDnaModuleRecord)
    def get_client_dna_document(client_id: str, module_key: str) -> ClientDnaModuleRecord:
        build_client_summary(client_id)
        modules = {module.moduleKey: module for module in list_client_dna_modules(client_id)}
        module = modules.get(module_key)
        if not module:
            raise HTTPException(status_code=404, detail="未知的客户 DNA 模块")
        return module

    @app.post("/api/v1/clients/{client_id}/dna-documents/{module_key}", response_model=ClientDnaModuleRecord)
    def update_client_dna_document(client_id: str, module_key: str, payload: OrganizationDnaUploadPayload) -> ClientDnaModuleRecord:
        build_client_summary(client_id)
        record = upsert_client_dna_module(client_id, module_key, payload)
        log_activity(
            "client.dna_document.update",
            "dna_document",
            f"{client_id}:{module_key}",
            {"clientId": client_id, "moduleKey": module_key, "fileName": record.fileName, "contentHash": record.contentHash},
        )
        return record

    @app.get("/api/v1/clients/{client_id}/project-structure", response_model=ProjectStructureResponse)
    def get_client_project_structure(client_id: str) -> ProjectStructureResponse:
        return build_project_structure(client_id)

    @app.get("/api/v1/clients/{client_id}/project-modules/{module_id}", response_model=ProjectModuleDetailRecord)
    def get_client_project_module_detail(client_id: str, module_id: str) -> ProjectModuleDetailRecord:
        build_client_summary(client_id)
        return get_project_module_detail(client_id, module_id)

    @app.post("/api/v1/clients/{client_id}/project-modules", response_model=ProjectModuleRecord)
    def create_client_project_module(client_id: str, payload: ProjectModulePayload) -> ProjectModuleRecord:
        build_client_summary(client_id)
        timestamp = now_iso()
        module_id = new_id("pmodule")
        alias = payload.alias.strip() if payload.alias else None
        owner_name = payload.ownerName.strip() if payload.ownerName else None
        deliverables = _sanitize_text_list(payload.deliverables)
        keywords = _sanitize_text_list(payload.keywords)
        state.db.execute(
            """
            INSERT INTO project_modules(
                id, client_id, name, alias, goal, description, owner_name, deliverables_json, keywords_json, template_tasks_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                module_id,
                client_id,
                payload.name.strip(),
                alias,
                (payload.goal or "").strip(),
                (payload.description or "").strip(),
                owner_name,
                to_json(deliverables),
                to_json(keywords),
                payload.templateTasksJson if hasattr(payload, 'templateTasksJson') and payload.templateTasksJson else None,
                timestamp,
                timestamp,
            ),
        )
        row = state.db.fetchone("SELECT * FROM project_modules WHERE id = ?", (module_id,))
        if not row:
            raise HTTPException(status_code=500, detail="任务模块创建失败")
        log_activity("project.module.create", "project_module", module_id, {"clientId": client_id, "name": payload.name.strip()})
        return _project_module_record(row)

    @app.patch("/api/v1/clients/{client_id}/project-modules/{module_id}", response_model=ProjectModuleRecord)
    def update_client_project_module(client_id: str, module_id: str, payload: ProjectModulePayload) -> ProjectModuleRecord:
        build_client_summary(client_id)
        row = state.db.fetchone("SELECT * FROM project_modules WHERE id = ? AND client_id = ?", (module_id, client_id))
        if not row:
            raise HTTPException(status_code=404, detail="任务模块不存在")
        merged = {
            "name": payload.name.strip(),
            "alias": payload.alias.strip() if payload.alias else None,
            "goal": (payload.goal or "").strip(),
            "description": (payload.description or "").strip(),
            "owner_name": payload.ownerName.strip() if payload.ownerName else None,
            "deliverables_json": to_json(_sanitize_text_list(payload.deliverables)),
            "keywords_json": to_json(_sanitize_text_list(payload.keywords)),
            "template_tasks_json": payload.templateTasksJson if payload.templateTasksJson else None,
            "updated_at": now_iso(),
        }
        state.db.execute(
            """
            UPDATE project_modules
            SET name = ?, alias = ?, goal = ?, description = ?, owner_name = ?, deliverables_json = ?, keywords_json = ?, template_tasks_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                merged["name"],
                merged["alias"],
                merged["goal"],
                merged["description"],
                merged["owner_name"],
                merged["deliverables_json"],
                merged["keywords_json"],
                merged["template_tasks_json"],
                merged["updated_at"],
                module_id,
            ),
        )
        updated = state.db.fetchone("SELECT * FROM project_modules WHERE id = ?", (module_id,))
        if not updated:
            raise HTTPException(status_code=500, detail="任务模块更新失败")
        log_activity("project.module.update", "project_module", module_id, {"clientId": client_id, "name": merged["name"]})
        return _project_module_record(updated)

    @app.delete("/api/v1/clients/{client_id}/project-modules/{module_id}")
    def delete_client_project_module(client_id: str, module_id: str) -> dict:
        row = state.db.fetchone("SELECT * FROM project_modules WHERE id = ? AND client_id = ?", (module_id, client_id))
        if not row:
            raise HTTPException(status_code=404, detail="任务模块不存在")
        state.db.execute("DELETE FROM project_flows WHERE module_id = ? AND client_id = ?", (module_id, client_id))
        state.db.execute("DELETE FROM project_modules WHERE id = ?", (module_id,))
        log_activity("project.module.delete", "project_module", module_id, {"clientId": client_id, "name": str(row["name"])})
        return {"status": "deleted"}

    @app.get("/api/v1/clients/{client_id}/project-flows/{flow_id}", response_model=ProjectFlowDetailRecord)
    def get_client_project_flow_detail(client_id: str, flow_id: str) -> ProjectFlowDetailRecord:
        build_client_summary(client_id)
        return get_project_flow_detail(client_id, flow_id)

    @app.post("/api/v1/clients/{client_id}/project-flows", response_model=ProjectFlowRecord)
    def create_client_project_flow(client_id: str, payload: ProjectFlowPayload) -> ProjectFlowRecord:
        build_client_summary(client_id)
        module_row = state.db.fetchone("SELECT * FROM project_modules WHERE id = ? AND client_id = ?", (payload.moduleId, client_id))
        if not module_row:
            raise HTTPException(status_code=400, detail="请先选择当前项目下的任务模块")
        timestamp = now_iso()
        flow_id = new_id("pflow")
        state.db.execute(
            """
            INSERT INTO project_flows(
                id, client_id, module_id, name, description, scenario, trigger_condition, steps_json, inputs_json, outputs_json, collaborators_json, risk_points_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                flow_id,
                client_id,
                payload.moduleId,
                payload.name.strip(),
                (payload.description or "").strip(),
                (payload.scenario or "").strip(),
                (payload.triggerCondition or "").strip(),
                to_json(_sanitize_text_list(payload.steps)),
                to_json(_sanitize_text_list(payload.inputs)),
                to_json(_sanitize_text_list(payload.outputs)),
                to_json(_sanitize_text_list(payload.collaborators)),
                to_json(_sanitize_text_list(payload.riskPoints)),
                timestamp,
                timestamp,
            ),
        )
        row = state.db.fetchone(
            """
            SELECT f.*, m.name AS module_name
            FROM project_flows f
            LEFT JOIN project_modules m ON m.id = f.module_id
            WHERE f.id = ?
            """,
            (flow_id,),
        )
        if not row:
            raise HTTPException(status_code=500, detail="流程创建失败")
        log_activity("project.flow.create", "project_flow", flow_id, {"clientId": client_id, "moduleId": payload.moduleId, "name": payload.name.strip()})
        return _project_flow_record(row, str(row["module_name"]) if row["module_name"] else None)

    @app.patch("/api/v1/clients/{client_id}/project-flows/{flow_id}", response_model=ProjectFlowRecord)
    def update_client_project_flow(client_id: str, flow_id: str, payload: ProjectFlowPayload) -> ProjectFlowRecord:
        build_client_summary(client_id)
        module_row = state.db.fetchone("SELECT * FROM project_modules WHERE id = ? AND client_id = ?", (payload.moduleId, client_id))
        if not module_row:
            raise HTTPException(status_code=400, detail="请先选择当前项目下的任务模块")
        row = state.db.fetchone("SELECT * FROM project_flows WHERE id = ? AND client_id = ?", (flow_id, client_id))
        if not row:
            raise HTTPException(status_code=404, detail="流程不存在")
        state.db.execute(
            """
            UPDATE project_flows
            SET module_id = ?, name = ?, description = ?, scenario = ?, trigger_condition = ?, steps_json = ?, inputs_json = ?, outputs_json = ?, collaborators_json = ?, risk_points_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.moduleId,
                payload.name.strip(),
                (payload.description or "").strip(),
                (payload.scenario or "").strip(),
                (payload.triggerCondition or "").strip(),
                to_json(_sanitize_text_list(payload.steps)),
                to_json(_sanitize_text_list(payload.inputs)),
                to_json(_sanitize_text_list(payload.outputs)),
                to_json(_sanitize_text_list(payload.collaborators)),
                to_json(_sanitize_text_list(payload.riskPoints)),
                now_iso(),
                flow_id,
            ),
        )
        updated = state.db.fetchone(
            """
            SELECT f.*, m.name AS module_name
            FROM project_flows f
            LEFT JOIN project_modules m ON m.id = f.module_id
            WHERE f.id = ?
            """,
            (flow_id,),
        )
        if not updated:
            raise HTTPException(status_code=500, detail="流程更新失败")
        log_activity("project.flow.update", "project_flow", flow_id, {"clientId": client_id, "moduleId": payload.moduleId, "name": payload.name.strip()})
        return _project_flow_record(updated, str(updated["module_name"]) if updated["module_name"] else None)

    @app.get("/api/v1/clients/{client_id}/dna", response_model=list[DnaTerm])
    def list_client_dna(client_id: str) -> list[DnaTerm]:
        return workspace_for_client(client_id).dnaTerms

    @app.post("/api/v1/clients/{client_id}/dna", response_model=DnaTerm)
    def upsert_client_dna(client_id: str, payload: DnaTermPayload) -> DnaTerm:
        build_client_summary(client_id)
        existing = state.db.fetchone(
            "SELECT * FROM dna_terms WHERE client_id = ? AND canonical_name = ?",
            (client_id, payload.canonicalName),
        )
        timestamp = now_iso()
        if existing:
            state.db.execute(
                """
                UPDATE dna_terms
                SET category = ?, aliases_json = ?, description = ?, updated_at = ?
                WHERE id = ?
                """,
                (payload.category, to_json(payload.aliases), payload.description, timestamp, existing["id"]),
            )
            term_id = str(existing["id"])
        else:
            term_id = new_id("dna")
            state.db.execute(
                """
                INSERT INTO dna_terms(id, client_id, category, canonical_name, aliases_json, description, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (term_id, client_id, payload.category, payload.canonicalName, to_json(payload.aliases), payload.description, timestamp, timestamp),
            )
        log_activity("dna.upsert", "dna", term_id, payload.model_dump())
        return DnaTerm(
            id=term_id,
            clientId=client_id,
            category=payload.category,
            canonicalName=payload.canonicalName,
            aliases=payload.aliases,
            description=payload.description,
            sourceLevel="client",
        )

    @app.post("/api/v1/imports", response_model=list[ImportRecord])
    def import_documents(payload: ImportPayload) -> list[ImportRecord]:
        build_client_summary(payload.clientId)
        ensure_standard_client_folders(payload.clientId)
        results: list[ImportRecord] = []
        allowed_extensions = set(SUPPORTED_IMPORT_EXTENSIONS)
        if payload.allowLegacy:
            allowed_extensions.update(LEGACY_IMPORT_EXTENSIONS)
        for raw_path in payload.paths:
            source_path = Path(raw_path).expanduser()
            if not source_path.exists():
                continue
            import_id = new_id("imp")
            timestamp = now_iso()
            queued = 0
            skipped = 0
            state.db.execute(
                """
                INSERT INTO imports(id, client_id, source_path, mode, status, imported_count, skipped_count, created_at)
                VALUES(?, ?, ?, ?, 'queued', 0, 0, ?)
                """,
                (import_id, payload.clientId, str(source_path), payload.mode, timestamp),
            )
            if payload.mode == "folder":
                candidates = [path for path in source_path.rglob("*") if path.is_file()]
            else:
                candidates = [source_path]
            ensure_source_tree_snapshot(
                state.db,
                import_id=import_id,
                client_id=payload.clientId,
                source_path=source_path,
                mode=payload.mode,
                created_at=timestamp,
            )
            queued_documents: list[dict[str, object]] = []
            for path in candidates:
                if path.suffix.lower() not in allowed_extensions:
                    skipped += 1
                    continue
                if state.db.fetchone(
                    """
                    SELECT 1
                    FROM knowledge_documents
                    WHERE client_id = ?
                      AND (import_source_path = ? OR current_human_path = ? OR original_path = ?)
                    """,
                    (payload.clientId, str(path), str(path), str(path)),
                ):
                    skipped += 1
                    continue
                managed_import_path = stage_import_copy(state.data_dir, payload.clientId, import_id, path)
                excerpt = build_excerpt(path)
                document_id = new_id("doc")
                state.db.execute(
                    """
                    INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        payload.clientId,
                        None,
                        path.name,
                        str(managed_import_path),
                        str(path),
                        path.suffix.lower().lstrip("."),
                        payload.mode,
                        excerpt,
                        to_json([path.suffix.lower().lstrip(".")]),
                        timestamp,
                    ),
                )
                queued_documents.append(
                    {
                        "documentId": document_id,
                        "sourcePath": str(managed_import_path),
                        "originalSourcePath": str(path),
                        "title": path.name,
                        "kind": path.suffix.lower().lstrip("."),
                        "source": payload.mode,
                        "createdAt": timestamp,
                    }
                )
                queued += 1
            state.db.execute(
                "UPDATE imports SET skipped_count = ? WHERE id = ?",
                (skipped, import_id),
            )
            if queued == 0:
                state.db.execute(
                    "UPDATE imports SET status = 'completed', imported_count = 0, skipped_count = ? WHERE id = ?",
                    (skipped, import_id),
                )
                log_activity("import.create", "import", import_id, {"clientId": payload.clientId, "sourcePath": str(source_path), "queued": queued, "skipped": skipped, "jobId": None})
                results.append(
                    ImportRecord(
                        id=import_id,
                        clientId=payload.clientId,
                        sourcePath=str(source_path),
                        mode=payload.mode,
                        status="completed",
                        importedCount=0,
                        skippedCount=skipped,
                        createdAt=timestamp,
                    )
                )
                continue
            job = enqueue_knowledge_job(
                payload.clientId,
                "ingest_import",
                {
                    "clientId": payload.clientId,
                    "importId": import_id,
                    "mode": payload.mode,
                    "documents": queued_documents,
                },
                total_items=queued,
            )
            log_activity("import.create", "import", import_id, {"clientId": payload.clientId, "sourcePath": str(source_path), "queued": queued, "skipped": skipped, "jobId": job.id})
            results.append(
                ImportRecord(
                    id=import_id,
                    clientId=payload.clientId,
                    sourcePath=str(source_path),
                    mode=payload.mode,
                    status="queued",
                    importedCount=queued,
                    skippedCount=skipped,
                    createdAt=timestamp,
                )
            )
        return results

    def ensure_chat_thread(client_id: str, thread_id: str | None, prompt: str, timestamp: str) -> str:
        existing_thread_id = thread_id
        if existing_thread_id and state.db.fetchone("SELECT 1 FROM chat_threads WHERE id = ?", (existing_thread_id,)):
            return existing_thread_id
        next_thread_id = new_id("thread")
        state.db.execute(
            "INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
            (next_thread_id, client_id, prompt[:16], timestamp, timestamp),
        )
        return next_thread_id

    def insert_user_chat_message(thread_id: str, prompt: str, timestamp: str) -> str:
        message_id = new_id("msg")
        state.db.execute(
            """
            INSERT INTO chat_messages(
                id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
                answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json, status, created_at
            )
            VALUES(?, ?, 'user', ?, NULL, NULL, 0, NULL, NULL, NULL, NULL, '{}', '{}', '[]', 'success', ?)
            """,
            (message_id, thread_id, prompt, timestamp),
        )
        return message_id

    def phase_progress_window(phase: str) -> tuple[float, float]:
        if phase == "retrieving":
            return 0.0, 25.0
        if phase == "grounding":
            return 25.0, 55.0
        if phase == "generating":
            return 55.0, 92.0
        return 100.0, 100.0

    def insert_loading_assistant_message(thread_id: str, retrieval_summary: dict[str, object], timestamp: str) -> str:
        assistant_id = new_id("msg")
        provider_used = state.ai.current_provider()
        merged_summary = dict(retrieval_summary)
        merged_summary.setdefault("startedAt", timestamp)
        phase = str(merged_summary.get("phase") or "").strip()
        if not phase:
            has_hits = any(int(merged_summary.get(key, 0) or 0) > 0 for key in ("masterHitCount", "surrogateHitCount", "rawChunkHitCount"))
            phase = "grounding" if has_hits else "retrieving"
        merged_summary["phase"] = phase
        merged_summary.setdefault("progress", 36.0 if phase == "grounding" else 6.0)
        floor, ceiling = phase_progress_window(phase)
        merged_summary["progressFloor"] = float(merged_summary.get("progressFloor", floor) or floor)
        merged_summary["progressCeiling"] = float(merged_summary.get("progressCeiling", ceiling) or ceiling)
        merged_summary.setdefault(
            "stageLabel",
            "背景材料已整理完成，正在准备调用千问组织答案" if phase == "grounding" else "正在整理客户背景材料",
        )
        merged_summary["lastUpdatedAt"] = timestamp
        loading_content = str(merged_summary.get("stageLabel") or "庆华正在整理背景材料，并组织分析答案……")
        state.db.execute(
            """
            INSERT INTO chat_messages(
                id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
                answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json, status, created_at
            )
            VALUES(?, ?, 'assistant', ?, NULL, ?, 0, ?, NULL, NULL, NULL, '{}', ?, '[]', 'loading', ?)
            """,
            (
                assistant_id,
                thread_id,
                loading_content,
                f"AI · {provider_used}",
                provider_used,
                to_json(merged_summary),
                timestamp,
            ),
        )
        return assistant_id

    def update_loading_assistant_message(
        assistant_id: str,

```
