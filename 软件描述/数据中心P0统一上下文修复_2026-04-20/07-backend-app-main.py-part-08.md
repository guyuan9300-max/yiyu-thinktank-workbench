# 源码文件：`backend/app/main.py`（分片 08）

- 行号范围：19601-22400
- 总行数：   30416
- 导出时间：2026-04-20

```python
                                    if not cid:
                                        cid = str(erow["primary_client_id"] or "")
                                        cname = client_name_local
                                    break
                                # Match by event line name first 2-4 chars as substring
                                el_short = el_name[:4] if len(el_name) >= 4 else el_name[:2]
                                if el_short and len(el_short) >= 2 and el_short in title:
                                    el_id = eid
                                    if not cid:
                                        cid = str(erow["primary_client_id"] or "")
                                        cname = str(erow["primary_client_name"] or "")
                                    break

                        # If still no client, try keyword matching against client names
                        if not cid:
                            client_rows = state.db.fetchall("SELECT id, name FROM clients")
                            for cr in client_rows:
                                cn = str(cr["name"])
                                if cn and len(cn) >= 2 and cn in title:
                                    cid = str(cr["id"])
                                    cname = cn
                                    break

                        # Use event line's client as fallback
                        if not cid and el_id and el_id in el_map:
                            erow = el_map[el_id]
                            cid = str(erow["primary_client_id"] or "")
                            cname = str(erow["primary_client_name"] or "")

                        if not cid:
                            cid = "general"
                            cname = "通用"

                        by_client.setdefault(cid, (cname, []))[1].append((title, note))

                        # Write event line memory if we found an event line
                        if el_id and el_id in el_map:
                            erow = el_map[el_id]
                            el_cid = str(erow["primary_client_id"] or cid)
                            el_cname = str(erow["primary_client_name"] or cname)
                            el_name = str(erow["name"])
                            write_event_line_memory(
                                state.data_dir, el_cid, el_id, el_name, el_cname,
                                f"## {el_name}\n\n### 本周复盘：{title}\n{note}",
                            )

                    # Write per-client project memory
                    for cid, (cname, notes) in by_client.items():
                        content = f"## {target_week} 复盘记录\n\n" + "\n\n".join(
                            f"### {t}\n{n}" for t, n in notes
                        )
                        write_project_memory(state.data_dir, cid, cname, content)

                    # Extract golden quotes from all review notes
                    from app.services.local_memory import extract_quotes_from_text, save_pending_quotes
                    all_review_text = "\n\n".join(f"【{t}】{n}" for t, n in all_notes if len(n) > 30)
                    if all_review_text:
                        quotes = extract_quotes_from_text(state.ai, all_review_text, "周复盘")
                        if quotes:
                            save_pending_quotes(state.db, quotes)
                except Exception:
                    pass
            _mem_thr.Thread(target=_bg_write_review_memory, daemon=True).start()

        if session_user is None:
            return response.model_copy(
                update={
                    "workAnalysis": work_analysis,
                    "personalAnalysis": personal_analysis,
                    "selfReport": self_report,
                }
            )
        if session_user.primaryRole != "admin":
            return response.model_copy(
                update={
                    "workAnalysis": work_analysis,
                    "personalAnalysis": personal_analysis,
                    "selfReport": self_report,
                    "executiveOrgReport": None,
                    "departmentReports": department_reports,
                    "agentDepartmentDigests": [],
                    "agentDepartmentPlans": [],
                    "simulationBundle": None,
                }
            )
        agent_department_digests = build_agent_weekly_digests(
            db=state.db,
            week_label=target_week,
            thread_sync_path=THREAD_SYNC_DOC_PATH,
        )
        agent_department_plans = build_agent_weekly_plans(
            db=state.db,
            week_label=target_week,
            thread_sync_path=THREAD_SYNC_DOC_PATH,
        )
        return response.model_copy(
            update={
                "workAnalysis": work_analysis,
                "personalAnalysis": personal_analysis,
                "selfReport": self_report,
                "executiveOrgReport": executive_org_report,
                "departmentReports": department_reports,
                "agentDepartmentDigests": agent_department_digests,
                "agentDepartmentPlans": agent_department_plans,
                "simulationBundle": simulation_bundle,
            }
        )

    def local_review_dashboard_base(week_label: str | None = None) -> ReviewResponse:
        target_week = week_label or current_review_week_label()
        review_row = local_review_row_for_week(target_week)
        review_entries = local_review_entries_by_task(str(review_row["id"])) if review_row else {}
        tasks_in_week = [task for task in fetch_tasks() if _task_in_week(task, target_week)]
        tasks_by_id = {task.id: task for task in tasks_in_week}
        for task_id in review_entries:
            if task_id in tasks_by_id:
                continue
            task_rows = fetch_tasks("t.id = ?", (task_id,))
            if task_rows:
                tasks_by_id[task_id] = task_rows[0]
        org_modules = list_organization_dna_modules()
        session_user = get_cached_session_user()
        governance = _review_governance_with_members() if session_user else None
        viewer_role = _resolve_review_viewer_role(session_user, governance)
        work_items: list[WeeklyReviewTaskEntryRecord] = []
        personal_items: list[WeeklyReviewTaskEntryRecord] = []
        for task in tasks_by_id.values():
            stored = review_entries.get(task.id)
            note = str(stored["note"]) if stored else ""
            structured_note = coerce_review_structured_note(stored.get("structured_note_json")) if stored else empty_review_structured_note()
            if not note and stored:
                note = compose_review_note(structured_note, "")
            reviewed_at = str(stored["reviewed_at"]) if stored else None
            snapshot = from_json(str(stored["task_snapshot_json"]), {}) if stored else None
            merged_snapshot = {
                **_task_snapshot_from_task(task, state.db),
                **(snapshot if isinstance(snapshot, dict) else {}),
            } if stored else None
            content_domain = "personal" if is_private_task(task) else "work"
            item = _review_entry_from_task(
                task=task,
                week_label=target_week,
                content_domain=content_domain,
                review_id=str(review_row["id"]) if review_row else None,
                note=note,
                structured_note=structured_note,
                reviewed_at=reviewed_at,
                snapshot=merged_snapshot,
                db=state.db,
            )
            if content_domain == "personal":
                personal_items.append(item)
            else:
                work_items.append(item)
        for task_id, stored in review_entries.items():
            if task_id in tasks_by_id:
                continue
            note = str(stored["note"] or "")
            structured_note = coerce_review_structured_note(stored.get("structured_note_json"))
            if not note:
                note = compose_review_note(structured_note, "")
            snapshot = from_json(str(stored["task_snapshot_json"] or "{}"), {})
            if not isinstance(snapshot, dict) or not snapshot:
                continue
            content_domain = str(stored.get("content_domain") or "work")
            item = WeeklyReviewTaskEntryRecord(
                id=str(stored["id"]),
                reviewId=str(stored["review_id"]),
                taskId=task_id,
                weekLabel=target_week,
                contentDomain=content_domain,  # type: ignore[arg-type]
                note=note,
                structuredNote=structured_note,
                reviewedAt=str(stored["reviewed_at"]) if stored["reviewed_at"] else None,
                taskSnapshot=snapshot,  # type: ignore[arg-type]
            )
            if content_domain == "personal":
                personal_items.append(item)
            else:
                work_items.append(item)
        current_review = build_local_review_record(review_row) if review_row else build_preview_review_record(target_week)
        work_analysis, personal_analysis = build_review_analyses(
            target_week,
            work_items,
            personal_items,
            org_modules,
            viewer_role=viewer_role,
        )
        self_report = None
        base_response = ReviewResponse(
            currentReview=current_review,
            workItems=work_items,
            personalItems=personal_items,
            workAnalysis=work_analysis,
            personalAnalysis=personal_analysis,
            selfReport=self_report,
            plans=[],
        )
        return base_response

    def local_review_dashboard(week_label: str | None = None) -> ReviewResponse:
        target_week = week_label or current_review_week_label()
        base_response = local_review_dashboard_base(target_week)
        return augment_review_response(base_response, target_week)

    # ── Attachment local cache ──
    def _att_cache_dir() -> Path:
        d = Path(state.data_dir) / "cache" / "event-line-attachments"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _att_cache_path(attachment_id: str, suffix: str = "") -> Path:
        """Return cache file path. suffix examples: '', '.thumb', '.text.json', '.ocr.json'"""
        safe_id = attachment_id.replace("/", "_").replace("..", "_")
        return _att_cache_dir() / f"{safe_id}{suffix}"

    def _att_cache_read(attachment_id: str, suffix: str = "") -> bytes | None:
        p = _att_cache_path(attachment_id, suffix)
        if p.exists() and p.stat().st_size > 0:
            return p.read_bytes()
        return None

    def _att_cache_write(attachment_id: str, data: bytes, suffix: str = "") -> None:
        p = _att_cache_path(attachment_id, suffix)
        p.write_bytes(data)

    @app.get("/api/public/task-attachments/{attachment_id}")
    def proxy_cloud_task_attachment(attachment_id: str) -> Response:
        # Check local cache first
        cached = _att_cache_read(attachment_id)
        if cached:
            # Guess content type from cached metadata
            meta_path = _att_cache_path(attachment_id, ".meta")
            ct = "application/octet-stream"
            cd = ""
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    ct = meta.get("content_type", ct)
                    cd = meta.get("content_disposition", "")
                except Exception:
                    pass
            headers = {}
            if cd:
                headers["Content-Disposition"] = cd
            return Response(content=cached, media_type=ct, headers=headers)

        if not get_cloud_token():
            raise HTTPException(status_code=404, detail="Attachment not found")
        try:
            token = get_cloud_token()
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            resp = httpx.get(
                f"{state.cloud_api_url}/api/public/task-attachments/{attachment_id}",
                headers=headers,
                timeout=30.0,
                follow_redirects=True,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail="Attachment not found")
            content_type = resp.headers.get("content-type", "application/octet-stream")
            content_disposition = resp.headers.get("content-disposition", "")
            # Write to cache
            _att_cache_write(attachment_id, resp.content)
            _att_cache_write(attachment_id, json.dumps({"content_type": content_type, "content_disposition": content_disposition}).encode(), suffix=".meta")
            response_headers = {}
            if content_disposition:
                response_headers["Content-Disposition"] = content_disposition
            return Response(content=resp.content, media_type=content_type, headers=response_headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Cloud attachment unavailable: {exc}") from exc

    @app.get("/api/public/task-attachments/{attachment_id}/thumbnail")
    def proxy_cloud_attachment_thumbnail(attachment_id: str) -> Response:
        cached = _att_cache_read(attachment_id, ".thumb")
        if cached:
            return Response(content=cached, media_type="image/jpeg")

        if not get_cloud_token():
            raise HTTPException(status_code=404, detail="Not found")
        try:
            resp = httpx.get(
                f"{state.cloud_api_url}/api/public/task-attachments/{attachment_id}/thumbnail",
                timeout=15.0,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail="Not found")
            _att_cache_write(attachment_id, resp.content, suffix=".thumb")
            return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Thumbnail unavailable: {exc}") from exc

    @app.get("/api/public/task-attachments/{attachment_id}/text-content")
    def proxy_cloud_attachment_text(attachment_id: str) -> dict:
        cached = _att_cache_read(attachment_id, ".text.json")
        if cached:
            try:
                data = json.loads(cached)
                # Only serve cache if it was a successful extraction
                text = str(data.get("text", ""))
                if text and "提取失败" not in text and "No module" not in text:
                    return data
            except Exception:
                pass

        if not get_cloud_token():
            raise HTTPException(status_code=404, detail="Not found")
        try:
            resp = httpx.get(f"{state.cloud_api_url}/api/public/task-attachments/{attachment_id}/text-content", timeout=15.0)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail="Not found")
            result = resp.json()
            # Cache successful extractions
            text = str(result.get("text", ""))
            if text and "提取失败" not in text and "No module" not in text:
                _att_cache_write(attachment_id, json.dumps(result, ensure_ascii=False).encode("utf-8"), suffix=".text.json")
            return result
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Text content unavailable: {exc}") from exc

    @app.get("/api/public/task-attachments/{attachment_id}/ocr-summary")
    def proxy_cloud_attachment_ocr(attachment_id: str) -> dict:
        def _is_good_ocr(data: dict) -> bool:
            s = str(data.get("summary", ""))
            return bool(s) and not data.get("unsupported") and "识别失败" not in s and "不可用" not in s and "未登录" not in s

        cached = _att_cache_read(attachment_id, ".ocr.json")
        if cached:
            try:
                data = json.loads(cached)
                if _is_good_ocr(data):
                    return data
            except Exception:
                pass

        if not get_cloud_token():
            return {"title": "", "summary": "未登录", "unsupported": True}
        try:
            resp = httpx.get(f"{state.cloud_api_url}/api/public/task-attachments/{attachment_id}/ocr-summary", timeout=20.0)
            if resp.status_code >= 400:
                return {"title": "", "summary": "OCR 不可用"}
            result = resp.json()
            if _is_good_ocr(result):
                _att_cache_write(attachment_id, json.dumps(result, ensure_ascii=False).encode("utf-8"), suffix=".ocr.json")
            return result
        except Exception:
            return {"title": "", "summary": "OCR 不可用"}

    @app.post("/api/v1/event-lines/{event_line_id}/attachments/download-zip")
    def proxy_event_line_zip(event_line_id: str, payload: dict | None = None) -> Response:
        if not get_cloud_token():
            raise HTTPException(status_code=400, detail="需要登录云端")
        token = get_cloud_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {}
        try:
            resp = httpx.post(
                f"{state.cloud_api_url}/api/v1/event-lines/{event_line_id}/attachments/download-zip",
                headers=headers,
                json=payload or {},
                timeout=60.0,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail="下载失败")
            return Response(
                content=resp.content,
                media_type="application/zip",
                headers={"Content-Disposition": resp.headers.get("content-disposition", 'attachment; filename="attachments.zip"')},
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Zip download unavailable: {exc}") from exc

    @app.get("/api/v1/brain/dashboard")
    def get_brain_dashboard() -> dict:
        """Strategic brain dashboard — aggregate pulse metrics from all subsystems."""
        client_rows = state.db.fetchall("SELECT id, name, stage, intro FROM clients ORDER BY updated_at DESC")
        task_count = int(state.db.scalar("SELECT COUNT(*) FROM tasks") or 0)
        chat_count = int(state.db.scalar("SELECT COUNT(*) FROM chat_messages WHERE role = 'user'") or 0)
        event_line_count = int(state.db.scalar("SELECT COUNT(*) FROM event_lines") or 0)
        review_count = int(state.db.scalar("SELECT COUNT(*) FROM weekly_reviews") or 0)
        meeting_count = int(state.db.scalar("SELECT COUNT(*) FROM meetings") or 0)
        handbook_count = int(state.db.scalar("SELECT COUNT(*) FROM handbook_entries") or 0)
        memory_fact_count = int(state.db.scalar("SELECT COUNT(*) FROM memory_facts") or 0)
        badge_count = int(state.db.scalar("SELECT COUNT(*) FROM growth_evidence_records WHERE validation_state IN ('validated','institutionalized')") or 0)
        doc_count = int(state.db.scalar("SELECT COUNT(*) FROM documents") or 0)
        dna_count = int(state.db.scalar("SELECT COUNT(*) FROM client_dna_documents WHERE summary != '' AND summary IS NOT NULL") or 0)
        first_client_row = state.db.fetchone("SELECT MIN(created_at) AS val FROM clients")
        first_client_at = str(first_client_row["val"]) if first_client_row and first_client_row["val"] else None
        days_accompanied = 0
        if first_client_at:
            try:
                from datetime import datetime as _dt
                first = _dt.fromisoformat(first_client_at.replace("Z", "+00:00").split("+")[0])
                days_accompanied = max(0, (_dt.now() - first).days)
            except Exception:
                pass
        weekly_new_facts = int(state.db.scalar(
            "SELECT COUNT(*) FROM memory_facts WHERE created_at >= date('now', '-7 days')"
        ) or 0)
        clients_data = []
        for row in client_rows:
            cid = str(row["id"])
            client_docs = int(state.db.scalar("SELECT COUNT(*) FROM documents WHERE client_id = ?", (cid,)) or 0)
            client_dna = int(state.db.scalar("SELECT COUNT(*) FROM client_dna_documents WHERE client_id = ? AND summary != '' AND summary IS NOT NULL", (cid,)) or 0)
            client_elines = int(state.db.scalar("SELECT COUNT(*) FROM event_lines WHERE primary_client_id = ?", (cid,)) or 0)
            client_facts = int(state.db.scalar("SELECT COUNT(*) FROM memory_facts WHERE scope_type = 'client' AND scope_id = ?", (cid,)) or 0)
            notebook = get_client_notebook_response(state.db, cid)
            confidence = float(notebook.organizationNotebookSnapshot.confidence) if notebook.organizationNotebookSnapshot else 0.0
            clients_data.append({
                "id": cid,
                "name": str(row["name"]),
                "confidence": round(confidence, 2),
                "stage": str(row["stage"] or ""),
                "intro": str(row["intro"] or "")[:200],
                "docs": client_docs,
                "dna": client_dna,
                "eventLines": client_elines,
                "memoryFacts": client_facts,
            })
        return {
            "pulse": {
                "memoryCount": memory_fact_count,
                "docCount": doc_count,
                "taskCount": task_count,
                "chatCount": chat_count,
                "eventLineCount": event_line_count,
                "dnaCount": dna_count,
                "badgeCount": badge_count,
                "handbookCount": handbook_count,
                "daysAccompanied": days_accompanied,
                "reviewCount": review_count,
                "meetingCount": meeting_count,
                "weeklyNewFacts": weekly_new_facts,
            },
            "clients": clients_data,
        }

    @app.get("/api/v1/system/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        # Opportunistically sync pending tasks on health check (non-blocking)
        Thread(target=sync_pending_tasks_if_due, daemon=True).start()
        return build_health()

    # ── 自修复系统 ──────────────────────────────────────────

    from app.services.self_heal import SelfHealEngine

    _heal_engine: SelfHealEngine | None = None

    def _get_heal_engine() -> SelfHealEngine:
        nonlocal _heal_engine
        if _heal_engine is None:
            _heal_engine = SelfHealEngine(state.db, state.data_dir, state.ai)
        return _heal_engine

    @app.get("/api/v1/system/health-check")
    def system_health_check() -> dict:
        engine = _get_heal_engine()
        probes = engine.run_health_check()
        healthy_count = sum(1 for p in probes if p["healthy"])
        sick_count = len(probes) - healthy_count
        return {
            "timestamp": now_iso(),
            "totalProbes": len(probes),
            "healthy": healthy_count,
            "sick": sick_count,
            "probes": probes,
        }

    @app.post("/api/v1/system/self-heal")
    def system_self_heal(remedy_id: str | None = None) -> dict:
        engine = _get_heal_engine()
        if remedy_id:
            record = engine.heal(remedy_id=remedy_id, diagnosis="手动触发")
            return {"mode": "manual", "records": [asdict(record)]}
        records = engine.auto_heal()
        return {
            "mode": "auto",
            "records": [asdict(r) for r in records],
            "healed": sum(1 for r in records if r.status == "healed"),
            "failed": sum(1 for r in records if r.status == "failed"),
            "skipped": sum(1 for r in records if r.status == "skipped"),
        }

    @app.post("/api/v1/system/diagnose")
    def system_diagnose(error_logs: list[str] = Body(default=[])) -> dict:
        engine = _get_heal_engine()
        logs = error_logs
        if not logs:
            rows = state.db.fetchall(
                "SELECT action, detail_json, created_at FROM activity_logs WHERE action LIKE '%.error%' ORDER BY created_at DESC LIMIT 20"
            )
            logs = [f"[{row['created_at']}] {row['action']}: {row['detail_json']}" for row in rows]
        if not logs:
            return {"matched": False, "reason": "无错误日志可分析"}
        return engine.diagnose_with_ai(logs)

    @app.get("/api/v1/system/heal-log")
    def system_heal_log(limit: int = 50) -> dict:
        engine = _get_heal_engine()
        return {"records": engine.get_heal_log(limit)}

    def _sync_org_ai_config_from_cloud() -> None:
        """Pull org-level AI config from cloud and apply locally (background, non-blocking)."""
        try:
            secret_payload = cloud_request("GET", "/api/v1/settings/org-ai-config/secret")
            if not isinstance(secret_payload, dict):
                return
            provider = str(secret_payload.get("aiProvider", "")).strip()
            model = str(secret_payload.get("aiModel", "")).strip()
            api_key = str(secret_payload.get("apiKey", "")).strip()
            if not provider or provider == "mock":
                return
            state.ai.configure(provider, model, api_key, False)
        except Exception:
            pass  # 云端不可用时保留本地配置

    @app.get("/api/v1/auth/me", response_model=AuthStateResponse)
    def auth_me() -> AuthStateResponse:
        def _local_session_user() -> SessionUserRecord:
            return SessionUserRecord(
                id="local-device-user",
                organizationId="local-device",
                email="local@device.yiyu",
                fullName="本机用户",
                primaryRole="employee",
                accountStatus="approved",
            )

        def _local_auth_state(message: str | None = None) -> AuthStateResponse:
            return AuthStateResponse(
                authenticated=True,
                user=_local_session_user(),
                message=message,
                sessionMode="local",
            )

        token = get_cloud_token()
        refresh_token = get_cloud_refresh_token()
        if not token and not refresh_token:
            return _local_auth_state()
        cached_user = get_cached_session_user()
        try:
            user = require_session_user()
        except HTTPException as exc:
            if exc.status_code in {401, 403}:
                clear_cloud_session()
                return _local_auth_state(str(exc.detail))
            if exc.status_code in {502, 503, 504} and cached_user is not None:
                return AuthStateResponse(
                    authenticated=True,
                    user=cached_user,
                    message="云端暂时不可用，已保留当前设备上的登录状态。",
                    sessionMode="cloud",
                )
            raise
        import threading
        threading.Thread(target=_sync_org_ai_config_from_cloud, daemon=True).start()
        return AuthStateResponse(authenticated=True, user=user, sessionMode="cloud")

    @app.get("/api/v1/account/overview", response_model=AccountOverviewResponse)
    def account_overview() -> AccountOverviewResponse:
        token = get_cloud_token()
        refresh_token = get_cloud_refresh_token()
        if not token and not refresh_token:
            return AccountOverviewResponse(
                sessionMode="local",
                cloudConnected=False,
                cloudConfig=CloudConfigResponse(mode="disabled"),
                user=SessionUserRecord(
                    id="local-device-user",
                    organizationId="local-device",
                    email="local@device.yiyu",
                    fullName="本机用户",
                    primaryRole="employee",
                    accountStatus="approved",
                ),
            )
        cached_user = get_cached_session_user()
        return AccountOverviewResponse(
            sessionMode="cloud",
            cloudConnected=bool(token or refresh_token),
            cloudConfig=CloudConfigResponse(
                mode="official_test" if state.cloud_api_url else "disabled",
                apiBaseUrl=state.cloud_api_url or None,
            ),
            user=cached_user,
        )

    @app.get("/api/v1/local-input-memory", response_model=LocalInputMemoryResponse)
    def get_local_input_memory() -> LocalInputMemoryResponse:
        return _hydrate_local_input_memory()

    @app.post("/api/v1/local-input-memory/cloud-auth", response_model=LocalInputMemoryResponse)
    def save_cloud_auth_input_memory(payload: SaveCloudAuthInputMemoryPayload) -> LocalInputMemoryResponse:
        current = _get_local_input_memory_record()
        existing_accounts = current.cloudAuth.accounts
        for account in existing_accounts:
            if not payload.rememberInputs:
                try:
                    _remembered_cloud_auth_store(account.email).delete_api_key()
                except Exception:
                    pass
        if not payload.rememberInputs:
            record = current.model_copy(
                update={
                    "cloudAuth": LocalInputMemoryCloudAuth(
                        rememberInputs=False,
                        lastEmail=None,
                        accounts=[],
                    )
                }
            )
            _save_local_input_memory_record(record)
            return _hydrate_local_input_memory(record)

        email = payload.email.strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="请先填写邮箱，再决定是否记住账号和密码。")
        previous_account = next((account for account in existing_accounts if account.email.strip().lower() == email), None)
        full_name = (payload.fullName or "").strip() or (previous_account.fullName if previous_account else "")
        password = (payload.password or "").strip()
        if password:
            _remembered_cloud_auth_store(email).set_api_key(password)
        updated_account = RememberedCloudAuthAccount(
            email=email,
            fullName=full_name,
            updatedAt=now_iso(),
        )
        next_accounts = [updated_account]
        seen_emails = {email}
        for account in existing_accounts:
            normalized_email = account.email.strip().lower()
            if not normalized_email or normalized_email in seen_emails:
                continue
            seen_emails.add(normalized_email)
            next_accounts.append(
                account.model_copy(
                    update={
                        "email": normalized_email,
                        "fullName": full_name if normalized_email == email and full_name else account.fullName,
                    }
                )
            )
        record = current.model_copy(
            update={
                "cloudAuth": LocalInputMemoryCloudAuth(
                    rememberInputs=True,
                    lastEmail=email,
                    accounts=next_accounts[:8],
                )
            }
        )
        _save_local_input_memory_record(record)
        return _hydrate_local_input_memory(record)

    @app.post("/api/v1/local-input-memory/ai", response_model=LocalInputMemoryResponse)
    def save_ai_input_memory(payload: SaveAiInputMemoryPayload) -> LocalInputMemoryResponse:
        current = _get_local_input_memory_record()
        store = _remembered_ai_store()
        api_key = (payload.apiKey or "").strip()
        if payload.rememberApiKey and api_key:
            store.set_api_key(api_key)
            ai_record = LocalInputMemoryAiSettings(rememberApiKey=True)
        else:
            try:
                store.delete_api_key()
            except Exception:
                pass
            ai_record = LocalInputMemoryAiSettings(rememberApiKey=False)
        record = current.model_copy(update={"aiSettings": ai_record})
        _save_local_input_memory_record(record)
        return _hydrate_local_input_memory(record)

    @app.post("/api/v1/local-input-memory/feishu", response_model=LocalInputMemoryResponse)
    def save_feishu_input_memory(payload: SaveFeishuInputMemoryPayload) -> LocalInputMemoryResponse:
        current = _get_local_input_memory_record()
        store = _remembered_feishu_store()
        if payload.rememberInputs:
            next_secret = (payload.appSecret or "").strip()
            if next_secret:
                store.set_api_key(next_secret)
            feishu_record = LocalInputMemoryFeishuIntegration(
                rememberInputs=True,
                appId=(payload.appId or "").strip(),
                callbackMode=payload.callbackMode or "cloud_relay",
                customCallbackUrl=(payload.customCallbackUrl or "").strip(),
            )
        else:
            try:
                store.delete_api_key()
            except Exception:
                pass
            feishu_record = LocalInputMemoryFeishuIntegration(rememberInputs=False)
        record = current.model_copy(update={"feishuIntegration": feishu_record})
        _save_local_input_memory_record(record)
        return _hydrate_local_input_memory(record)

    @app.get("/api/v1/me/org-membership", response_model=OrgMembershipSummaryRecord)
    def me_org_membership() -> OrgMembershipSummaryRecord:
        if not get_cloud_token() and not get_cloud_refresh_token():
            return OrgMembershipSummaryRecord(hasOrganization=False)
        try:
            payload = cloud_request("GET", "/api/v1/me/org-membership")
            if isinstance(payload, dict):
                return OrgMembershipSummaryRecord(**payload)
        except Exception:
            pass
        return OrgMembershipSummaryRecord(hasOrganization=False)

    @app.get("/api/v1/org-integrations/feishu", response_model=OrgFeishuIntegrationRecord)
    def get_org_feishu_integration() -> OrgFeishuIntegrationRecord:
        _offline = OrgFeishuIntegrationRecord(
            organizationId=None, organizationName=None, updatedAt=now_iso(),
            authorizationBlockedReason="云端暂时不可用，飞书协作功能稍后自动恢复。",
        )
        if not get_cloud_token() and not get_cloud_refresh_token():
            return _offline
        try:
            payload = cloud_request("GET", "/api/v1/org-integrations/feishu")
            if isinstance(payload, dict):
                return OrgFeishuIntegrationRecord(**payload)
        except Exception:
            pass
        return _offline

    @app.post("/api/v1/org-integrations/feishu/validate-and-save", response_model=OrgFeishuIntegrationRecord)
    def validate_and_save_org_feishu_integration(payload: OrgFeishuIntegrationSavePayload) -> OrgFeishuIntegrationRecord:
        if not get_cloud_token() and not get_cloud_refresh_token():
            raise HTTPException(status_code=400, detail="连接云端并加入或创建组织后，才能启用飞书协作。")
        response = cloud_request(
            "POST",
            "/api/v1/org-integrations/feishu/validate-and-save",
            json_body=payload.model_dump(exclude_none=True),
        )
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid org feishu payload")
        return OrgFeishuIntegrationRecord(**response)

    @app.get("/api/v1/me/feishu-authorization", response_model=FeishuMemberAuthorizationRecord)
    def get_feishu_member_authorization() -> FeishuMemberAuthorizationRecord:
        if not get_cloud_token() and not get_cloud_refresh_token():
            return FeishuMemberAuthorizationRecord(
                linked=False,
                readyForAuthorization=False,
                organizationId=None,
                organizationName=None,
                appId="",
                userId="local-device-user",
                blockedReason="连接云端并加入或创建组织后，才能启用飞书协作。",
            )
        try:
            payload = cloud_request("GET", "/api/v1/me/feishu-authorization")
            if isinstance(payload, dict):
                return FeishuMemberAuthorizationRecord(**payload)
        except Exception:
            pass
        return FeishuMemberAuthorizationRecord(
            linked=False, readyForAuthorization=False, organizationId=None, organizationName=None,
            appId="", userId="local-device-user", blockedReason="云端暂时不可用，飞书协作功能稍后自动恢复。",
        )

    @app.post("/api/v1/me/feishu-authorization/start", response_model=FeishuMemberAuthorizationStartResponse)
    def start_feishu_member_authorization() -> FeishuMemberAuthorizationStartResponse:
        if not get_cloud_token() and not get_cloud_refresh_token():
            raise HTTPException(status_code=400, detail="连接云端并加入或创建组织后，才能启用飞书协作。")
        payload = cloud_request("POST", "/api/v1/me/feishu-authorization/start")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Invalid feishu authorization start payload")
        return FeishuMemberAuthorizationStartResponse(**payload)

    @app.delete("/api/v1/me/feishu-authorization", response_model=FeishuMemberAuthorizationRecord)
    def clear_feishu_member_authorization() -> FeishuMemberAuthorizationRecord:
        if not get_cloud_token() and not get_cloud_refresh_token():
            return FeishuMemberAuthorizationRecord(
                linked=False,
                readyForAuthorization=False,
                organizationId=None,
                organizationName=None,
                appId="",
                userId="local-device-user",
                blockedReason="连接云端并加入或创建组织后，才能启用飞书协作。",
            )
        payload = cloud_request("DELETE", "/api/v1/me/feishu-authorization")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Invalid feishu authorization payload")
        return FeishuMemberAuthorizationRecord(**payload)

    @app.get("/api/v1/auth/department-options", response_model=list[DepartmentOptionRecord])
    def auth_department_options() -> list[DepartmentOptionRecord]:
        return [
            DepartmentOptionRecord(id=item.id, name=item.name, color=item.color)
            for item in list_department_catalog()
        ]

    @app.post("/api/v1/auth/register", response_model=AuthStateResponse)
    def auth_register(payload: AuthRegisterPayload) -> AuthStateResponse:
        response = cloud_request(
            "POST",
            "/api/v1/auth/register",
            json_body=payload.model_dump(),
            allow_unauthenticated=True,
        )
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid auth payload")
        token = str(response.get("accessToken", ""))
        refresh_token = str(response.get("refreshToken", ""))
        user_payload = response.get("user")
        if not token or not refresh_token or not isinstance(user_payload, dict):
            message = response.get("message") if isinstance(response, dict) else "注册成功，但未拿到有效会话。"
            raise HTTPException(status_code=502, detail=str(message))
        user = SessionUserRecord(**user_payload)
        set_cloud_session(token, user, persist=True)
        set_cloud_refresh_token(refresh_token, persist=True)
        log_activity("auth.register", "session", user.id, {"email": user.email})
        return AuthStateResponse(authenticated=True, user=user, sessionMode="cloud")

    @app.post("/api/v1/auth/login", response_model=AuthStateResponse)
    def auth_login(payload: AuthLoginPayload) -> AuthStateResponse:
        response = cloud_request(
            "POST",
            "/api/v1/auth/login",
            json_body=payload.model_dump(),
            allow_unauthenticated=True,
        )
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid auth payload")
        token = str(response.get("accessToken", ""))
        refresh_token = str(response.get("refreshToken", ""))
        user_payload = response.get("user")
        if not token or not refresh_token or not isinstance(user_payload, dict):
            raise HTTPException(status_code=502, detail="Cloud auth payload missing session data")
        user = SessionUserRecord(**user_payload)
        set_cloud_session(token, user, persist=payload.rememberMe)
        set_cloud_refresh_token(refresh_token, persist=payload.rememberMe)
        log_activity("auth.login", "session", user.id, {"email": user.email})
        return AuthStateResponse(authenticated=True, user=user)

    @app.post("/api/v1/auth/change-password")
    def auth_change_password(payload: dict) -> dict:
        response = cloud_request("POST", "/api/v1/auth/change-password", json_body=payload)
        return response if isinstance(response, dict) else {"message": "密码修改成功"}

    @app.patch("/api/v1/auth/me", response_model=AuthStateResponse)
    def auth_update_profile(payload: UpdateProfilePayload) -> AuthStateResponse:
        if not get_cloud_token() and not get_cloud_refresh_token():
            raise HTTPException(status_code=400, detail="当前处于本机模式，请先连接云端账号。")
        response = cloud_request("PATCH", "/api/v1/auth/me", json_body=payload.model_dump(exclude_none=True))
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid auth payload")
        user = SessionUserRecord(**response)
        set_cloud_session(get_cloud_token(), user)
        return AuthStateResponse(authenticated=True, user=user, sessionMode="cloud")

    @app.post("/api/v1/auth/logout", response_model=AuthStateResponse)
    def auth_logout() -> AuthStateResponse:
        if get_cloud_token():
            try:
                cloud_request("POST", "/api/v1/auth/logout")
            except HTTPException:
                pass
        clear_cloud_session()
        log_activity("auth.logout", "session", "current", {})
        return AuthStateResponse(
            authenticated=True,
            user=SessionUserRecord(
                id="local-device-user",
                organizationId="local-device",
                email="local@device.yiyu",
                fullName="本机用户",
                primaryRole="employee",
                accountStatus="approved",
            ),
            sessionMode="local",
        )

    def process_pending_consultation_knowledge_requests_impl() -> ConsultationKnowledgeProcessSummaryResponse:
        all_requests = list_cloud_consultation_knowledge_requests()
        now_ts = time.time()
        eligible = [
            item
            for item in all_requests
            if _should_retry_consultation_knowledge_request(item, now_ts=now_ts)
        ]
        eligible.sort(
            key=lambda item: (
                _parse_iso_moment(item.createdAt).timestamp() if _parse_iso_moment(item.createdAt) else now_ts,
                item.id,
            )
        )
        summary = ConsultationKnowledgeProcessSummaryResponse(
            totalPending=len(eligible),
            updatedAt=now_iso(),
        )
        if not eligible:
            return summary

        processed_items: list[ConsultationKnowledgeRequestRecord] = []
        for item in eligible:
            summary.processedCount += 1
            try:
                update_cloud_consultation_knowledge_request_status(item.id, status="processing")
                generated = sink_consultation_knowledge_request(item)
                completed = update_cloud_consultation_knowledge_request_status(
                    item.id,
                    status="completed",
                    local_document_id=generated.documentId,
                    local_document_path=generated.path,
                )
                summary.completedCount += 1
                processed_items.append(completed)
            except Exception as exc:
                detail = exc.detail if isinstance(exc, HTTPException) else exc
                error_message = str(detail or "本地综合库写入失败")
                try:
                    failed = update_cloud_consultation_knowledge_request_status(
                        item.id,
                        status="failed",
                        error_message=error_message,
                    )
                except Exception:
                    failed = ConsultationKnowledgeRequestRecord(
                        **{
                            **item.model_dump(),
                            "status": "failed",
                            "errorMessage": error_message,
                            "completedAt": None,
                            "updatedAt": now_iso(),
                        }
                    )
                summary.failedCount += 1
                processed_items.append(failed)
        summary.updatedAt = now_iso()
        summary.items = processed_items
        return summary

    @app.get("/api/v1/consultation/knowledge-requests", response_model=list[ConsultationKnowledgeRequestRecord])
    def list_consultation_knowledge_requests(
        status_filter: Literal["pending", "processing", "completed", "failed"] | None = Query(default=None, alias="status"),
    ) -> list[ConsultationKnowledgeRequestRecord]:
        if not get_cloud_token() and not get_cloud_refresh_token():
            return []
        require_session_user()
        return list_cloud_consultation_knowledge_requests(status_filter)

    @app.post(
        "/api/v1/consultation/knowledge-requests/process-pending",
        response_model=ConsultationKnowledgeProcessSummaryResponse,
    )
    def process_pending_consultation_knowledge_requests() -> ConsultationKnowledgeProcessSummaryResponse:
        if not get_cloud_token() and not get_cloud_refresh_token():
            return ConsultationKnowledgeProcessSummaryResponse(updatedAt=now_iso())
        require_session_user()
        if state.consultation_knowledge_sync_running:
            return ConsultationKnowledgeProcessSummaryResponse(updatedAt=now_iso())
        state.consultation_knowledge_sync_running = True
        try:
            return process_pending_consultation_knowledge_requests_impl()
        finally:
            state.consultation_knowledge_sync_running = False

    @app.get("/api/v1/admin/employees", response_model=list[EmployeeRecord])
    def list_employee_reviews() -> list[EmployeeRecord]:
        try:
            payload = cloud_request("GET", "/api/v1/admin/employees")
            if isinstance(payload, list):
                return [EmployeeRecord(**item) for item in payload if isinstance(item, dict)]
        except Exception:
            pass
        return []

    @app.get("/api/v1/settings/org-model/profile", response_model=OrgModelProfileRecord)
    def read_org_model_profile() -> OrgModelProfileRecord:
        try:
            payload = cloud_request("GET", "/api/v1/settings/org-model/profile")
            if isinstance(payload, dict):
                return OrgModelProfileRecord(**payload)
        except Exception:
            pass
        return OrgModelProfileRecord(
            organization=OrgProfileRecord(
                organizationId="",
                name="",
                updatedAt="",
            ),
            updatedAt=now_iso(),
        )

    @app.post("/api/v1/settings/org-model/profile", response_model=OrgModelProfileRecord)
    def update_org_model_profile(payload: OrgModelProfileRecord) -> OrgModelProfileRecord:
        response = cloud_request("POST", "/api/v1/settings/org-model/profile", json_body=payload.model_dump())
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid org model payload")
        return OrgModelProfileRecord(**response)

    @app.post("/api/v1/settings/org-model/backfill-task-links", response_model=TaskOrgBackfillResultRecord)
    def backfill_org_task_links() -> TaskOrgBackfillResultRecord:
        response = cloud_request("POST", "/api/v1/settings/org-model/backfill-task-links")
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid task org backfill payload")
        return TaskOrgBackfillResultRecord(**response)

    @app.get("/api/v1/event-lines", response_model=list[EventLineRecord])
    def list_event_lines() -> list[EventLineRecord]:
        if get_cloud_token():
            try:
                response = cloud_request("GET", "/api/v1/event-lines")
                if not isinstance(response, list):
                    raise HTTPException(status_code=502, detail="Invalid event line payload")
                return [build_cloud_event_line(item) for item in response if isinstance(item, dict)]
            except HTTPException:
                pass
        rows = state.db.fetchall(
            """
            SELECT *
            FROM event_lines
            ORDER BY updated_at DESC, created_at DESC
            """
        )
        return [build_event_line(row) for row in rows]

    @app.post("/api/v1/event-lines", response_model=EventLineRecord)
    def create_event_line(payload: EventLineCreatePayload) -> EventLineRecord:
        if get_cloud_token():
            try:
                response = cloud_request("POST", "/api/v1/event-lines", json_body=payload.model_dump())
                if not isinstance(response, dict):
                    raise HTTPException(status_code=502, detail="Invalid event line payload")
                return build_cloud_event_line(response)
            except HTTPException:
                pass
        timestamp = now_iso()
        event_line_id = new_id("eline")
        client_id = str(payload.primaryClientId).strip() if payload.primaryClientId else None
        client_row = state.db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,)) if client_id else None
        state.db.execute(
            """
            INSERT INTO event_lines(
                id, name, kind, status, visibility_scope, business_category, stage, summary, intent, current_blocker,
                recent_decision, next_step, evidence_count, owner_id, owner_name, primary_client_id,
                primary_client_name, primary_department_id, primary_department_name, participant_ids_json,
                created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_line_id,
                payload.name.strip(),
                payload.kind,
                payload.status,
                payload.visibilityScope,
                payload.businessCategory,
                payload.stage,
                payload.summary,
                payload.intent,
                payload.currentBlocker,
                payload.recentDecision,
                payload.nextStep,
                _event_line_evidence_count_or_zero(payload.evidenceCount),
                payload.ownerId,
                current_operator_name(),
                client_id,
                str(client_row["name"]) if client_row else None,
                payload.primaryDepartmentId,
                None,
                to_json(payload.participantIds),
                timestamp,
                timestamp,
            ),
        )
        row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
        if not row:
            raise HTTPException(status_code=500, detail="Event line creation failed")
        return build_event_line(row)

    @app.get("/api/v1/event-lines/{event_line_id}", response_model=EventLineDetailRecord)
    def get_event_line(event_line_id: str) -> EventLineDetailRecord:
        if get_cloud_token():
            try:
                response = cloud_request("GET", f"/api/v1/event-lines/{event_line_id}")
                if not isinstance(response, dict):
                    raise HTTPException(status_code=502, detail="Invalid event line detail payload")
                return build_cloud_event_line_detail(response)
            except HTTPException:
                pass
        row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Event line not found")
        return build_event_line_detail(row)

    @app.post("/api/v1/event-lines/{event_line_id}/clarification-draft", response_model=EventLineClarificationDraftRecord)
    def generate_event_line_clarification_draft(
        event_line_id: str,
        payload: EventLineClarificationDraftPayload,
    ) -> EventLineClarificationDraftRecord:
        detail = get_event_line(event_line_id)
        conversation_text = payload.conversationText.strip()
        if len(conversation_text) < 8:
            raise HTTPException(status_code=400, detail="请先粘贴至少一小段聊天记录，再让 AI 整理。")
        activity_lines = [
            f"{item.happenedAt[:10]} {item.title}：{item.summary}"
            for item in detail.activities[:6]
            if item.title or item.summary
        ]
        task_lines = [
            f"任务《{task.title}》：{task.desc or task.ddl or task.status}"
            for task in detail.tasks[:5]
            if task.title
        ]
        draft = state.ai.generate_event_line_clarification_draft(
            event_line_name=detail.eventLine.name,
            conversation_text=conversation_text,
            current_summary=detail.eventLine.summary or "",
            current_stage=detail.eventLine.stage or "",
            current_intent=detail.eventLine.intent or "",
            current_blocker=detail.eventLine.currentBlocker or "",
            current_next_step=detail.eventLine.nextStep or "",
            current_recent_decision=detail.eventLine.recentDecision or "",
            recent_activity_lines=[*activity_lines, *task_lines],
        )
        return EventLineClarificationDraftRecord(**draft)

    @app.get("/api/v1/event-lines/{event_line_id}/memory", response_model=EventLineMemoryResponse)
    def get_event_line_memory(event_line_id: str) -> EventLineMemoryResponse:
        row = state.db.fetchone("SELECT id FROM event_lines WHERE id = ?", (event_line_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Event line not found")
        return get_event_line_memory_response(state.db, event_line_id)

    @app.get("/api/v1/event-lines/{event_line_id}/context-bundle", response_model=EventLineContextBundleRecord)
    def get_event_line_context_bundle(event_line_id: str) -> EventLineContextBundleRecord:
        bundle = _event_line_context_bundle(event_line_id)
        if bundle is None:
            raise HTTPException(status_code=404, detail="Event line context bundle not found")
        return bundle

    _context_preview_cache: dict[str, tuple[float, object]] = {}

    # ── Task Understanding (预处理+缓存架构) ──────

    def _build_task_understanding_record(task: "TaskRecord") -> UnderstandingSnapshotV1Record:
        from app.services.understanding_builder import build_understanding_basic
        snapshot = WeeklyReviewTaskSnapshotRecord(
            title=task.title, status=task.status, dueDate=task.dueDate,
            createdAt=task.createdAt, ownerId=None, ownerName=None,
            clientId=task.clientId, clientName=task.clientName,
            eventLineId=task.eventLineId, eventLineName=task.eventLineName,
            tags=task.tags, listName=task.listName or "", listColor=task.listColor or "",
            orgContext=task.orgContext, projectContext=task.projectContext,
        )
        entry = WeeklyReviewTaskEntryRecord(
            id=f"understanding_{task.id}", reviewId=None, taskId=task.id,
            weekLabel="", contentDomain="work", note=task.desc or "",
            taskSnapshot=snapshot,
        )
        return build_understanding_basic(ai=state.ai, task_entry=entry, org_dna_modules=list_organization_dna_modules())

    def _task_content_hash(task: "TaskRecord") -> str:
        content = f"{task.title}|{task.desc or ''}|{task.status}|{task.clientId or ''}|{task.eventLineId or ''}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _precompute_task_understanding(task_id: str) -> None:
        """后台线程：生成理解并写入缓存。"""
        try:
            task = next(iter(fetch_tasks("t.id = ?", (task_id,))), None)
            if not task:
                return
            content_hash = _task_content_hash(task)
            cached = state.db.fetchone("SELECT task_hash FROM task_understanding_cache WHERE task_id = ?", (task_id,))
            if cached and str(cached["task_hash"]) == content_hash:
                return
            result = _build_task_understanding_record(task)
            ts = now_iso()
            state.db.execute(
                """INSERT INTO task_understanding_cache(task_id, snapshot_json, task_hash, created_at, updated_at)
                   VALUES(?, ?, ?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET snapshot_json=excluded.snapshot_json, task_hash=excluded.task_hash, updated_at=excluded.updated_at""",
                (task_id, to_json(result.model_dump()), content_hash, ts, ts),
            )
            if state.system_logger:
                state.system_logger.info("understanding", f"预处理完成: {task.title[:40]}", task_id=task_id, confidence=result.confidence)
        except Exception as exc:
            if state.system_logger:
                state.system_logger.error("understanding", f"预处理失败: {task_id}", error=str(exc))

    @app.get("/api/v1/tasks/{task_id}/understanding")
    def get_task_understanding(task_id: str) -> dict:
        cached = state.db.fetchone("SELECT snapshot_json FROM task_understanding_cache WHERE task_id = ?", (task_id,))
        if cached and cached["snapshot_json"]:
            return from_json(cached["snapshot_json"], {})
        task = next(iter(fetch_tasks("t.id = ?", (task_id,))), None)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # 无缓存 → 后台排队，同时返回 lightweight understanding
        Thread(target=_precompute_task_understanding, args=(task_id,), daemon=True).start()
        lightweight = _build_task_understanding_record(task).model_dump(mode="json")
        lightweight["_pending"] = True
        return lightweight

    @app.get("/api/v1/tasks/{task_id}/page-context", response_model=PageContextPackRecord)
    def get_task_page_context(
        task_id: str,
        prompt: str = Query(default=""),
        page: Literal["task_detail", "task_ai"] = Query(default="task_detail"),
        includeRawEvidence: bool = Query(default=False),
    ) -> PageContextPackRecord:
        intent = infer_page_intent(prompt, page)
        try:
            return build_task_page_context_pack(
                state.db,
                data_dir=state.data_dir,
                task_id=task_id,
                prompt=prompt,
                page=page,
                intent=intent,
                include_raw_evidence=bool(includeRawEvidence),
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/v1/tasks/{task_id}/context-preview", response_model=TaskContextPreviewRecord)
    def get_task_context_preview(task_id: str) -> TaskContextPreviewRecord:
        import time as _time
        cached = _context_preview_cache.get(task_id)
        if cached and _time.time() - cached[0] < 300:
            return cached[1]  # type: ignore[return-value]
        if get_cloud_token():
            task = fetch_cloud_task_by_id(task_id)
        else:
            task = next(iter(fetch_tasks("t.id = ?", (task_id,))), None)
            if task is None:
                raise HTTPException(status_code=404, detail="Task not found")
        result = _build_task_context_preview(task)
        _context_preview_cache[task_id] = (_time.time(), result)
        return result

    def _build_smart_brief_for_task(task: TaskRecord) -> TaskSmartBriefRecord:
        attachment_titles = [item.title for item in task.attachments[:6] if item.title]
        return _build_smart_brief_from_hints(
            task_id=task.id,
            title=task.title,
            desc=task.desc or "",
            client_id=task.clientId,
            event_line_id=task.eventLineId,
            frontend_attachment_titles=attachment_titles,
        )

    # V1 角色映射：根据关键词自动建议内部责任人
    ROLE_ROUTING_RULES: list[tuple[list[str], str]] = [
        (["技术", "路径", "系统", "实现", "可行性", "成本", "接口", "模块", "产品蓝图", "架构", "开发", "试点", "数字化"], "佳维"),
        (["策略", "理事会", "对外合作", "行业引领", "价值引导", "合作边界", "市场", "品牌", "战略", "定位", "成效表达", "判断", "沉淀", "案例卡"], "顾源源"),
        (["跟进", "约时间", "沟通", "反馈", "催", "对接", "会务", "安排", "演示", "确认", "提醒", "材料", "档案", "拉群"], "乐乐"),
    ]

    def _route_internal_owner(text: str) -> str:
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for keywords, owner in ROLE_ROUTING_RULES:
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > 0:
                scores[owner] = scores.get(owner, 0) + count
        if not scores:
            return ""
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def _clean_task_brief_text(value: str, limit: int = 180) -> str:
        text = str(value or "").replace("\u3000", " ").replace("\t", " ").strip()
        text = re.sub(r"[ \xa0]+", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        text = text.strip(" ，,。；;：:\n")
        if limit > 0 and len(text) > limit:
            text = text[: max(1, limit - 1)].rstrip(" ，,。；;：:") + "…"
        return text

    def _split_task_brief_action_lines(raw: str) -> list[str]:
        if not raw:
            return []
        normalized = str(raw or "")
        normalized = re.sub(r"[•●▪◦■□◆◇★☆]", "\n", normalized)
        normalized = normalized.replace("；", "\n").replace(";", "\n")
        normalized = normalized.replace("。", "\n")
        candidates: list[str] = []
        for line in re.split(r"[\r\n]+", normalized):
            cleaned = re.sub(r"^\s*[\-\u2022]?\s*", "", line)
            cleaned = re.sub(r"^\s*(?:第?[一二三四五六七八九十0-9]+[、.)）]|[0-9]+\.)\s*", "", cleaned)
            cleaned = _clean_task_brief_text(cleaned, limit=120)
            if len(cleaned) < 4:
                continue
            candidates.append(cleaned)
        return list(dict.fromkeys(candidates))

    def _compose_task_brief_summary_point(kind: str, point: str) -> str:
        cleaned = _clean_task_brief_text(point, limit=110)
        if not cleaned:
            return ""
        if kind == "progress":
            return cleaned
        if kind == "value":
            return cleaned
        if kind == "blocker":
            return cleaned
        return cleaned

    def _convert_external_action_to_followup(text: str, client_name: str | None) -> str:
        target = _clean_task_brief_text(client_name or "客户", limit=20) or "客户"
        cleaned = _clean_task_brief_text(text, limit=100)
        if not cleaned:
            return f"跟进{target}后续事项"
        cleaned = cleaned.removeprefix("请").removeprefix("继续").strip()
        if target and cleaned.startswith(target):
            cleaned = cleaned[len(target):].strip()
        cleaned = cleaned.lstrip("，,：: ")
        if cleaned.startswith("跟进"):
            return cleaned
        return _clean_task_brief_text(f"跟进{target}{cleaned}", limit=120)

    def _infer_due_hint_from_text(text: str) -> str:
        cleaned = str(text or "")
        for pattern in (
            r"(4月中下旬)",
            r"([0-9]+天内)",
            r"(一周内)",
            r"(本周内)",
            r"(近期)",
            r"(下次沟通前)",
            r"(下轮对接前)",
            r"(下轮沟通前)",
        ):
            matched = re.search(pattern, cleaned)
            if matched:
                return matched.group(1)
        if any(keyword in cleaned for keyword in ("安排", "确认", "约", "跟进")):
            return "下次沟通前"
        if any(keyword in cleaned for keyword in ("框架", "建议", "案例卡", "判断")):
            return "一周内"
        return ""

    def _infer_deliverable_from_text(text: str) -> str:
        cleaned = str(text or "")
        if "框架" in cleaned:
            matched = re.search(r"([^，。；\n]*框架(?:\s*V[0-9]+)?)", cleaned)
            if matched:
                return _clean_task_brief_text(matched.group(1), limit=40)
            return "成效表达框架 V1"
        if "建议" in cleaned:
            return "建议单"
        if "案例卡" in cleaned:
            return "内部案例卡"
        if "判断" in cleaned:
            return "一页判断摘要"
        if "卡点" in cleaned:
            return "本轮运行问题清单"
        if "确认" in cleaned:
            return "确认结论"
        return ""

    def _extract_task_brief_sections_from_attachments(attachment_texts: list[str]) -> dict[str, str]:
        section_aliases: dict[str, list[str]] = {
            "当前进展": ["当前进展", "项目进展", "目前进展", "现阶段"],
            "项目价值": ["项目价值", "价值判断", "为什么重要", "意义"],
            "主要卡点": ["主要卡点", "当前阻碍", "核心卡点", "数字化摩擦", "主要问题"],
            "下一阶段计划": ["下一阶段计划", "下一步计划", "后续计划", "下一步"],
            "会后分工": ["会后分工", "后续分工", "行动建议", "待办", "下一步代办"],
        }
        sections: dict[str, str] = {key: "" for key in section_aliases}
        if not attachment_texts:
            return sections
        lines: list[str] = []
        for raw in attachment_texts:
            content = str(raw or "")
            if content.startswith("【"):
                content = re.sub(r"^【[^】]+】", "", content)
            lines.extend([segment.strip() for segment in re.split(r"[\r\n]+", content) if segment.strip()])
        for index, line in enumerate(lines):
            for section_name, aliases in section_aliases.items():
                if sections[section_name]:
                    continue
                matched_alias = next((alias for alias in aliases if alias in line), None)
                if not matched_alias:
                    continue
                if line.startswith(matched_alias) or f"{matched_alias}：" in line or f"{matched_alias}:" in line:
                    remainder = line.split(matched_alias, 1)[-1].lstrip("：: ")
                else:
                    remainder = ""
                if not remainder and index + 1 < len(lines):
                    remainder = lines[index + 1]
                sections[section_name] = _clean_task_brief_text(remainder, limit=220)
        return sections

    def _build_task_brief_prompt_context(bundle: dict[str, object], title: str, desc: str) -> tuple[str, dict[str, str]]:
        context_blocks = [f"任务标题：{_clean_task_brief_text(title, limit=80)}"]
        if desc.strip():
            context_blocks.append(f"任务说明：{_clean_task_brief_text(desc, limit=260)}")
        client_name = _clean_task_brief_text(str(bundle.get("clientName") or ""), limit=40)
        if client_name:
            context_blocks.append(f"客户：{client_name}")
        client_intro = _clean_task_brief_text(str(bundle.get("clientIntro") or ""), limit=180)
        if client_intro:
            context_blocks.append(f"客户画像：{client_intro}")
        collaboration_relationship = _clean_task_brief_text(str(bundle.get("collaborationRelationship") or ""), limit=180)
        if collaboration_relationship:
            context_blocks.append(f"合作关系：{collaboration_relationship}")
        event_line_name = _clean_task_brief_text(str(bundle.get("eventLine_name") or ""), limit=60)
        if event_line_name:
            context_blocks.append(f"事件线：{event_line_name}")
        event_summary = _clean_task_brief_text(
            str(bundle.get("eventLine_summary") or bundle.get("memory_current_work") or ""),
            limit=180,
        )
        if event_summary:
            context_blocks.append(f"事件线当前状态：{event_summary}")
        review_note = _clean_task_brief_text(str(bundle.get("reviewNote") or ""), limit=180)
        if review_note:
            context_blocks.append(f"任务复盘：{review_note}")
        attachment_texts = [str(item) for item in (bundle.get("attachmentContents") or []) if str(item).strip()]
        sections = _extract_task_brief_sections_from_attachments(attachment_texts)
        if attachment_texts:
            context_blocks.append("纪要/附件内容：")
            for snippet in attachment_texts[:2]:
                context_blocks.append(_clean_task_brief_text(snippet, limit=360))
        return "\n".join(context_blocks), sections

    def _current_task_brief_actor_id() -> str:
        session_user = get_cached_session_user()
        if session_user and session_user.id:
            return f"user:{session_user.id}"
        try:
            row = current_operator_row()
            if row and row["id"]:
                return f"operator:{row['id']}"
        except Exception:
            pass
        return "operator:default"

    def _build_task_brief_action_key(task_id: str, source_label: str, text: str) -> str:
        normalized = re.sub(r"\s+", "", f"{task_id}|{source_label}|{text}".strip())
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]

    def _list_adopted_task_brief_action_keys(task_id: str, actor_id: str) -> set[str]:
        rows = state.db.fetchall(
            "SELECT action_key FROM task_smart_brief_action_adoptions WHERE source_task_id = ? AND adopted_by_user_id = ?",
            (task_id, actor_id),
        )
        return {str(row["action_key"]) for row in rows if row and row["action_key"]}

    def _record_task_brief_action_adoption(source_task_id: str, action_key: str, actor_id: str, created_task_id: str, action_text: str) -> None:
        state.db.execute(
            """
            INSERT OR REPLACE INTO task_smart_brief_action_adoptions(
                source_task_id, action_key, adopted_by_user_id, created_task_id, action_text, adopted_at
            ) VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                source_task_id,
                action_key,
                actor_id,
                created_task_id,
                action_text,
                now_iso(),
            ),
        )

    def _extract_task_brief_project_hint(bundle: dict[str, object], title: str, action_text: str) -> str:
        client_name = str(bundle.get("clientName") or "").strip()
        candidates = [
            str(bundle.get("eventLine_name") or ""),
            title,
            action_text,
            str(bundle.get("eventLine_summary") or ""),
        ]
        keyword_priority = ("教师赋能", "鸿鹄计划", "数字化", "工作坊", "成效表达", "技术共创", "社群", "品牌", "录音边界")
        combined = " ".join(candidates)
        for keyword in keyword_priority:
            if keyword in combined:
                return keyword
        for raw in candidates:
            cleaned = str(raw or "").strip()
            if not cleaned:
                continue
            if client_name:
                cleaned = cleaned.replace(client_name, "")
                cleaned = cleaned.replace(client_name.replace("基金会", ""), "")
            cleaned = re.sub(r"Q[1-4]|一季度|二季度|三季度|四季度|复盘|项目复盘|讨论|跟进|任务|安排|计划|方案|会后|会议纪要", " ", cleaned)
            cleaned = re.sub(r"[（(].*?[)）]", " ", cleaned)
            cleaned = _clean_task_brief_text(cleaned, limit=14)
            if len(cleaned) >= 2:
                return cleaned
        return ""

    def _extract_task_brief_action_core(action_text: str, client_name: str | None) -> str:
        cleaned = str(action_text or "").strip()
        if client_name:
            cleaned = cleaned.replace(client_name, "")
            cleaned = cleaned.replace(client_name.replace("基金会", ""), "")
        cleaned = re.sub(r"^跟进", "", cleaned)
        cleaned = re.sub(r"^(继续推进|继续|进一步|请|安排|梳理|设计|把)", "", cleaned)
        cleaned = cleaned.strip(" ，,：:。")
        keyword_priority = ("录音边界确认", "卡点整理", "成效表达框架V1", "成效表达框架", "数字化试点建议", "阶段判断建议", "内部案例卡", "技术共创对接", "社群路径细化", "演示与对接会安排")
        for keyword in keyword_priority:
            if keyword in cleaned:
                return keyword
        return _clean_task_brief_text(cleaned, limit=14)

    def _build_task_brief_title_suggestion(bundle: dict[str, object], source_task_title: str, action_text: str) -> str:
        client_name = _clean_task_brief_text(str(bundle.get("clientName") or ""), limit=12)
        project_hint = _extract_task_brief_project_hint(bundle, source_task_title, action_text)
        action_core = _extract_task_brief_action_core(action_text, client_name)
        segments: list[str] = []
        for part in (client_name, project_hint, action_core):
            part = _clean_task_brief_text(part, limit=16)
            if not part:
                continue
            if segments and part in "".join(segments):
                continue
            segments.append(part)
        title = "".join(segments) or _clean_task_brief_text(action_text, limit=22) or _clean_task_brief_text(source_task_title, limit=22)
        return _clean_task_brief_text(title, limit=24)

    def _build_task_brief_description_suggestion(
        source_task_title: str,
        bundle: dict[str, object],
        summary_points: list[str],
        action_text: str,
        source_label: str,
        due_hint: str,
        deliverable: str,
        internal_owner: str,
    ) -> str:
        client_name = _clean_task_brief_text(str(bundle.get("clientName") or ""), limit=30) or "该客户"
        event_line_name = _clean_task_brief_text(str(bundle.get("eventLine_name") or ""), limit=40)
        source_sentence = f"这条任务来自《{_clean_task_brief_text(source_task_title, limit=40)}》里的{source_label or '下一步代办'}。"
        if event_line_name:
            source_sentence += f"当前关联事件线为“{event_line_name}”。"
        summary_sentence = " ".join([_clean_task_brief_text(point, limit=60) for point in summary_points if point])[:130]
        if summary_sentence:
            summary_sentence = f"结合现有任务说明、会议纪要和事件线信息，这条线目前的关键判断是：{summary_sentence}。"
        else:
            summary_sentence = ""
        action_sentence = f"这次需要推进的具体事项是：{_clean_task_brief_text(action_text, limit=80)}。"
        deliverable_sentence = ""
        if deliverable and due_hint:
            deliverable_sentence = f"请在{due_hint}前尽量拿到“{_clean_task_brief_text(deliverable, limit=40)}”这一结果。"
        elif deliverable:
            deliverable_sentence = f"请优先收束为“{_clean_task_brief_text(deliverable, limit=40)}”这一交付物。"
        elif due_hint:
            deliverable_sentence = f"建议时点是{due_hint}，避免只停留在沟通层面。"
        coordination_sentence = f"如果需要协作，默认先与{internal_owner}对齐。" if internal_owner else ""
        body = (
            f"{source_sentence}{client_name}当前正在推进相关工作。"
            f"{summary_sentence}{action_sentence}{deliverable_sentence}{coordination_sentence}"
            "处理时请先确认当前背景、边界和已有资料，再决定需要跟进客户、内部收束还是补充下一轮判断。"
        )
        return _clean_task_brief_text(body, limit=280)

    def _finalize_task_brief_action_items(
        task_id: str,
        source_task_title: str,
        bundle: dict[str, object],
        summary_points: list[str],
        action_items: list[TaskSmartBriefActionItem],
    ) -> list[TaskSmartBriefActionItem]:
        actor_id = _current_task_brief_actor_id()
        adopted_keys = _list_adopted_task_brief_action_keys(task_id, actor_id)
        finalized: list[TaskSmartBriefActionItem] = []
        seen: set[str] = set()
        for item in action_items:
            action_text = _clean_task_brief_text(item.text, limit=120)
            if not action_text:
                continue
            source_label = item.sourceLabel or "系统建议"
            action_key = item.actionKey or _build_task_brief_action_key(task_id, source_label, action_text)
            if action_key in adopted_keys or action_key in seen:
                continue
            seen.add(action_key)
            finalized.append(
                TaskSmartBriefActionItem(
                    text=action_text,
                    sourceLabel=source_label,
                    internalSuggestedOwner=item.internalSuggestedOwner or _route_internal_owner(action_text),
                    actionKind=item.actionKind or ("meeting_explicit" if source_label == "会议待办" else "follow_up_external" if source_label == "跟进对方" else "system_inferred"),
                    dueHint=item.dueHint or _infer_due_hint_from_text(action_text),
                    deliverable=item.deliverable or _infer_deliverable_from_text(action_text),
                    actionKey=action_key,
                    taskTitleSuggestion=item.taskTitleSuggestion or _build_task_brief_title_suggestion(bundle, source_task_title, action_text),
                    taskDescriptionSuggestion=item.taskDescriptionSuggestion or _build_task_brief_description_suggestion(
                        source_task_title=source_task_title,
                        bundle=bundle,
                        summary_points=summary_points,
                        action_text=action_text,
                        source_label=source_label,
                        due_hint=item.dueHint or _infer_due_hint_from_text(action_text),
                        deliverable=item.deliverable or _infer_deliverable_from_text(action_text),
                        internal_owner=item.internalSuggestedOwner or _route_internal_owner(action_text),
                    ),
                )
            )
        return finalized[:8]

    def _build_structured_task_brief_fallback(
        task_id: str,
        title: str,
        bundle: dict[str, object],
        source_labels: list[str],
        sections: dict[str, str],
    ) -> TaskSmartBriefRecord:
        summary_points: list[str] = []
        progress = sections.get("当前进展") or str(bundle.get("eventLine_summary") or bundle.get("memory_current_work") or bundle.get("desc") or "").strip()
        value = sections.get("项目价值") or str(bundle.get("collaborationRelationship") or bundle.get("clientIntro") or "").strip()
        blockers = sections.get("主要卡点") or str(bundle.get("eventLine_current_blocker") or bundle.get("memory_current_blocker") or bundle.get("review_reflection") or "").strip()
        for kind, point in (("progress", progress), ("value", value), ("blocker", blockers)):
            cleaned = _compose_task_brief_summary_point(kind, point)
            if cleaned:
                summary_points.append(cleaned)
        while len(summary_points) < 3:
            summary_points.append("待继续补充这条任务的关键判断。")
        final_summary = "\n".join(f"{index + 1}. {point}" for index, point in enumerate(summary_points[:3]))

        client_name = str(bundle.get("clientName") or "").strip()
        action_items: list[TaskSmartBriefActionItem] = []
        explicit_candidates = _split_task_brief_action_lines(sections.get("会后分工", "")) or _split_task_brief_action_lines(sections.get("下一阶段计划", ""))
        for item in explicit_candidates[:4]:
            normalized_text = item
            source_label = "会议待办"
            lowered = normalized_text.lower()
            internal_markers = ("益语", "我们", "梳理", "设计", "安排", "沉淀", "内部")
            if client_name and client_name in normalized_text:
                normalized_text = _convert_external_action_to_followup(normalized_text, client_name)
                source_label = "跟进对方"
            elif any(marker in lowered for marker in ("日慈", "对方", "客户")):
                normalized_text = _convert_external_action_to_followup(normalized_text, client_name or "客户")
                source_label = "跟进对方"
            elif not any(marker in normalized_text for marker in internal_markers):
                normalized_text = _convert_external_action_to_followup(normalized_text, client_name)
                source_label = "跟进对方"
            owner = "乐乐" if source_label == "跟进对方" else _route_internal_owner(normalized_text)
            due_hint = _infer_due_hint_from_text(item)
            if not due_hint:
                due_hint = "下次沟通前" if source_label == "跟进对方" else "近期"
            action_items.append(
                TaskSmartBriefActionItem(
                    text=normalized_text,
                    sourceLabel=source_label,
                    internalSuggestedOwner=owner,
                    actionKind="follow_up_external" if source_label == "跟进对方" else "meeting_explicit",
                    dueHint=due_hint,
                    deliverable=_infer_deliverable_from_text(item),
                )
            )

        inferred_candidates: list[str] = []
        blockers_text = sections.get("主要卡点", "")
        value_text = sections.get("项目价值", "")
        if blockers_text and ("数字化" in blockers_text or "飞书" in blockers_text or "表单" in blockers_text):
            inferred_candidates.append("梳理教师赋能数字化试点模块建议")
        if value_text and ("资方" in value_text or "公众" in value_text or "价值" in value_text or "成效" in blockers_text):
            inferred_candidates.append("设计教师赋能项目成效表达框架 V1")
        if value_text:
            inferred_candidates.append("梳理教师赋能项目的阶段判断与长期方向建议")
            inferred_candidates.append("把教师赋能项目沉淀为益语内部案例卡")
        for item in inferred_candidates:
            if len(action_items) >= 7:
                break
            if any(existing.text.startswith(item) for existing in action_items):
                continue
            action_items.append(
                TaskSmartBriefActionItem(
                    text=item,
                    sourceLabel="系统建议",
                    internalSuggestedOwner=_route_internal_owner(item),
                    actionKind="system_inferred",
                    dueHint=_infer_due_hint_from_text(item),
                    deliverable=_infer_deliverable_from_text(item),
                )
            )

        return TaskSmartBriefRecord(
            taskId=task_id,
            summary=final_summary[:900],
            summarySourceLabels=list(dict.fromkeys(source_labels)),
            actionItems=_finalize_task_brief_action_items(task_id, title, bundle, summary_points[:3], action_items),
        )

    def _gather_task_context_bundle(task_id: str, title: str, desc: str, client_id: str | None, event_line_id: str | None) -> dict:
        """Assemble all available context for a task into a single bundle."""
        bundle: dict[str, object] = {"taskId": task_id, "title": title, "desc": desc}
        source_labels: list[str] = []

        if desc.strip():
            source_labels.append("任务说明")

        # 客户/项目背景
        if client_id:
            notebook_row = state.db.fetchone(
                "SELECT organization_intro, collaboration_relationship FROM organization_notebook_snapshots WHERE client_id = ?",
                (client_id,),
            )
            if notebook_row:
                org_intro = str(notebook_row["organization_intro"] or "").strip()
                collab = str(notebook_row["collaboration_relationship"] or "").strip()
                if org_intro:
                    bundle["clientIntro"] = org_intro[:300]
                    source_labels.append("客户画像")
                if collab:
                    bundle["collaborationRelationship"] = collab[:300]
                    source_labels.append("合作关系")
            client_row = state.db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
            if client_row:
                bundle["clientName"] = str(client_row["name"])

        # 事件线上下文
        if event_line_id:
            el_row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
            if el_row:
                for field in ("name", "summary", "intent", "current_blocker", "recent_decision", "next_step", "stage"):
                    val = str(el_row[field] or "").strip()
                    if val:
                        bundle[f"eventLine_{field}"] = val[:200]
                source_labels.append("事件线")

            snapshot_row = state.db.fetchone(
                "SELECT current_work, current_blocker, recent_decision, next_step, clarification_needs_json FROM event_line_memory_snapshots WHERE event_line_id = ?",
                (event_line_id,),
            )
            if snapshot_row:
                for field in ("current_work", "current_blocker", "recent_decision", "next_step"):
                    val = str(snapshot_row[field] or "").strip()
                    if val:
                        bundle[f"memory_{field}"] = val[:200]
                needs = from_json(snapshot_row["clarification_needs_json"], [])
                # 过滤掉原始字段名（如 current_blocker、next_step），只保留有实际中文内容的
                raw_field_names = {"current_blocker", "recent_decision", "next_step", "current_work", "current_stage", "summary", "intent"}
                filtered_needs = [str(n).strip() for n in needs if str(n).strip() and str(n).strip().lower() not in raw_field_names and len(str(n).strip()) > 4]
                if filtered_needs:
                    bundle["clarification_needs"] = filtered_needs[:5]
                source_labels.append("事件线记忆")

        # 附件 + 附件内容提取（本任务 + 同事件线其他任务的附件）
        attachment_rows = state.db.fetchall(
            "SELECT id, title, path, kind, document_id FROM task_attachments WHERE task_id = ? UNION ALL SELECT id, title, path, kind, document_id FROM task_attachments_cloud WHERE task_id = ?",
            (task_id, task_id),
        )
        if not attachment_rows and event_line_id:
            # 如果本任务没有附件，检查同事件线下其他任务的附件
            attachment_rows = state.db.fetchall(
                "SELECT id, title, path, kind, document_id FROM task_attachments WHERE event_line_id = ? UNION ALL SELECT id, title, path, kind, document_id FROM task_attachments_cloud WHERE event_line_id = ?",
                (event_line_id, event_line_id),
            )
        if attachment_rows:
            bundle["attachments"] = [str(row["title"]) for row in attachment_rows[:5]]
            source_labels.append("附件")

            # 提取附件文本内容（优先本地缓存，然后本地文件，最后 documents 表）
            attachment_texts: list[str] = []
            for att_row in attachment_rows[:3]:
                doc_id = str(att_row["document_id"]) if att_row["document_id"] else None
                att_path = str(att_row["path"] or "")
                att_kind = str(att_row["kind"] or "")
                att_title = str(att_row["title"] or "")
                att_id = str(att_row["id"]) if "id" in att_row.keys() else ""

                # 1. Try local attachment cache first (fastest — milliseconds)
                cached_text = ""
                if att_id:
                    cached_bytes = _att_cache_read(att_id, ".text.json")
                    if cached_bytes:
                        try:
                            td = json.loads(cached_bytes)
                            t = str(td.get("text", "")).strip()
                            if t and "提取失败" not in t and "No module" not in t:
                                cached_text = t
                        except Exception:
                            pass
                if cached_text:
                    attachment_texts.append(f"【{att_title}】{cached_text}")
                    continue

                # 2. Try reading local file directly
                if att_path and att_kind in ("docx", "md", "txt"):
                    try:
                        file_path = Path(att_path)
                        if file_path.exists():
                            if att_kind in ("md", "txt"):
                                local_text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
                            elif att_kind in ("docx", "doc"):
                                from docx import Document as _DocxDoc
                                local_text = "\n".join(p.text for p in _DocxDoc(str(file_path)).paragraphs if p.text.strip())
                            else:
                                local_text = ""
                            if local_text:
                                attachment_texts.append(f"【{att_title}】{local_text}")
                                continue
                    except Exception:
                        pass

                # 3. Fall back to documents table excerpt
                if doc_id:
                    doc_row = state.db.fetchone("SELECT excerpt FROM documents WHERE id = ?", (doc_id,))
                    if doc_row and doc_row["excerpt"]:
                        excerpt = str(doc_row["excerpt"]).strip()[:900]
                        if excerpt:
                            attachment_texts.append(f"【{att_title}】{excerpt}")

            if attachment_texts:
                bundle["attachmentContents"] = attachment_texts
                source_labels.append("附件内容")

        # 周复盘
        review_row = state.db.fetchone(
            "SELECT note, structured_note_json FROM weekly_review_task_entries WHERE task_id = ? ORDER BY reviewed_at DESC LIMIT 1",
            (task_id,),
        )
        if review_row and review_row["note"]:
            bundle["reviewNote"] = str(review_row["note"]).strip()[:200]
            source_labels.append("周复盘")
            if review_row["structured_note_json"]:
                structured = from_json(review_row["structured_note_json"], {})
                for field in ("reflection", "successExperience", "nextAction", "completionStatus"):
                    val = str(structured.get(field, "")).strip()
                    if val:
                        bundle[f"review_{field}"] = val[:150]

        # 最近活动
        if event_line_id:
            activity_rows = state.db.fetchall(
                "SELECT title, summary FROM event_line_activities WHERE event_line_id = ? ORDER BY happened_at DESC LIMIT 3",
                (event_line_id,),
            )
            if activity_rows:
                bundle["recentActivities"] = [f"{str(r['title'])}: {str(r['summary'])[:80]}" for r in activity_rows]

        bundle["sourceLabels"] = list(dict.fromkeys(source_labels))
        return bundle

    def _build_smart_brief_from_hints(task_id: str, title: str, desc: str, client_id: str | None, event_line_id: str | None, frontend_attachment_titles: list[str] | None = None) -> TaskSmartBriefRecord:
        # Check cache first — smart brief is expensive (calls AI API ~10-16s)
        cache_key = f"smart_brief_cache::{task_id}"
        cached_raw = state.db.get_setting(cache_key, "")
        if cached_raw:
            try:
                cached = json.loads(cached_raw)
                if isinstance(cached, dict) and cached.get("summary"):
                    return TaskSmartBriefRecord(**cached)
            except Exception:
                pass

        result = _build_smart_brief_uncached(task_id, title, desc, client_id, event_line_id, frontend_attachment_titles)
        # Cache the result if it has meaningful content
        if result.summary:
            try:
                state.db.set_setting(cache_key, json.dumps(result.model_dump(), ensure_ascii=False, default=str))
            except Exception:
                pass
        return result

    def _build_smart_brief_uncached(task_id: str, title: str, desc: str, client_id: str | None, event_line_id: str | None, frontend_attachment_titles: list[str] | None = None) -> TaskSmartBriefRecord:
        bundle = _gather_task_context_bundle(task_id, title, desc, client_id, event_line_id)
        source_labels = bundle.get("sourceLabels", [])

        # 如果前端传来了附件标题但后端没找到，手动注入
        if frontend_attachment_titles and not bundle.get("attachments"):
            bundle["attachments"] = frontend_attachment_titles[:5]
            if "附件" not in source_labels:
                source_labels.append("附件")
            bundle["sourceLabels"] = source_labels

        # 触发规则：只有当有实质内容时才生成智能概要
        has_attachments = bool(bundle.get("attachmentContents")) or bool(bundle.get("attachments"))
        has_desc = bool(desc.strip())
        has_review = bool(bundle.get("reviewNote"))
        has_activities = bool(bundle.get("recentActivities"))
        has_event_line_content = bool(bundle.get("eventLine_summary") or bundle.get("memory_current_work"))
        if not has_attachments and not has_desc and not has_review and not (has_activities and has_event_line_content):
            return TaskSmartBriefRecord(
                taskId=task_id,
                summary="",
                summarySourceLabels=[],
                actionItems=[],
            )

        prompt_context, attachment_sections = _build_task_brief_prompt_context(bundle, title, desc)

        # 直接调用豆包 API 生成（绕过 state.ai 的 provider 设置问题）
        try:
            from app.services.secrets import MacOSKeychainSecretStore
            doubao_store = MacOSKeychainSecretStore(service_name="com.yiyu.self-workbench.doubao", account_name="default")
            api_key = doubao_store.get_api_key()
        except Exception:
            api_key = ""
        if api_key:
            try:
                prompt = (
                    f"以下是这条任务最关键的上下文资料：\n{prompt_context}\n\n"
                    f"请回答两个问题，严格返回 JSON，不要输出任何额外文字：\n\n"
                    f'{{"summaryPoints": ["第1点：当前进展","第2点：项目价值","第3点：主要卡点"],'
                    f'"nextActions": [{{"title": "任务标题", "sourceType": "meeting_explicit|follow_up_external|system_inferred", "who": "负责人", "when": "时间提示", "deliverable": "预期交付物"}}]}}\n\n'
                    f"规则：\n"
                    f"- summaryPoints 必须严格返回 3 条，顺序固定为：当前进展、项目价值、主要卡点\n"
                    f"- 每条 1-2 句，不要写空话，不要重复任务标题\n"
                    f"- 优先依据会议纪要，再用任务说明、客户背景、合作关系补足，不要被无关背景带偏\n"
                    f"- nextActions 先抽会议里明确说出的后续事项，再补系统建议补建的内部代办\n"
                    f"- 如果会议里说的是对方要做的事，不要照抄，统一改写成「跟进 + 对方事项 + 我方想拿到的结果」\n"
                    f"- sourceType 只能是：meeting_explicit、follow_up_external、system_inferred\n"
                    f"- who 参考：策略/判断/成效→顾源源，跟进/对接/安排→乐乐，技术/系统/试点→佳维\n"
                    f"- deliverable 尽量写清楚，如果资料里没有就留空字符串\n"
                )
                model = state.db.get_setting("ai_model", "doubao-seed-2-0-pro-260215")
                result: dict[str, object] | None = None
                last_error: Exception | None = None
                for timeout_seconds in (10.0, 16.0):
                    try:
                        resp = httpx.post(
                            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                            json={
                                "model": model,
                                "messages": [
                                    {"role": "system", "content": "你是益语智库的项目助手。只返回纯 JSON，不要 Markdown，不要解释过程。"},
                                    {"role": "user", "content": prompt},
                                ],
                                "max_tokens": 3000,
                                "temperature": 0.5,
                            },
                            timeout=timeout_seconds,
                        )
                        if resp.status_code != 200:
                            raise RuntimeError(f"doubao status={resp.status_code} body={resp.text[:300]}")
                        raw = resp.json()["choices"][0]["message"]["content"].strip()
                        if raw.startswith("```"):
                            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                        try:
                            result = json.loads(raw)
                        except Exception:
                            match = re.search(r"\{.*\}", raw, re.S)
                            if not match:
                                raise
                            result = json.loads(match.group(0))
                        break
                    except Exception as error:
                        last_error = error
                        continue

                if result:
                    summary_points = result.get("summaryPoints", [])
                    if not isinstance(summary_points, list):
                        summary_points = result.get("keyTopics", [])
                    normalized_points = [str(item).strip() for item in summary_points if str(item).strip()][:3]
                    ai_summary = "\n".join(
                        f"{index + 1}. {point}"
                        for index, point in enumerate(normalized_points)
                    )

                    ai_actions: list[TaskSmartBriefActionItem] = []
                    for item in result.get("nextActions", []):
                        if not isinstance(item, dict):
                            continue
                        title_text = str(item.get("title") or item.get("text") or "").strip()
                        if not title_text:
                            continue
                        source_type = str(item.get("sourceType") or "").strip()
                        who = str(item.get("who", "")).strip()
                        when = str(item.get("when", "")).strip()
                        deliverable = str(item.get("deliverable", "")).strip()
                        source_label = (
                            "会议待办" if source_type == "meeting_explicit"
                            else "跟进对方" if source_type == "follow_up_external"
                            else "系统建议"
                        )
                        action_text = title_text
                        internal_owner = who if who in ("顾源源", "乐乐", "佳维") else _route_internal_owner(action_text)
                        due_hint = when or _infer_due_hint_from_text(action_text)
                        if not due_hint:
                            due_hint = "下次沟通前" if source_label == "跟进对方" else "近期" if source_label == "会议待办" else ""
                        ai_actions.append(
                            TaskSmartBriefActionItem(
                                text=action_text,
                                sourceLabel=source_label,
                                internalSuggestedOwner=internal_owner,
                                actionKind=source_type or ("meeting_explicit" if source_label == "会议待办" else "follow_up_external" if source_label == "跟进对方" else "system_inferred"),
                                dueHint=due_hint,
                                deliverable=deliverable or _infer_deliverable_from_text(action_text),
                            )
                        )

                    if ai_summary:
                        deduped_labels = list(dict.fromkeys((list(source_labels) if isinstance(source_labels, list) else []) + ["AI"]))
                        return TaskSmartBriefRecord(
                            taskId=task_id,
                            summary=ai_summary[:900],
                            summarySourceLabels=deduped_labels,
                            actionItems=_finalize_task_brief_action_items(task_id, title, bundle, normalized_points[:3], ai_actions),
                        )
                if last_error:
                    print(f"[task-smart-brief] AI generation fallback for {task_id}: {last_error}")
            except Exception:
                pass  # AI 失败时 fallback 到规则拼接

        return _build_structured_task_brief_fallback(
            task_id=task_id,
            title=title,
            bundle=bundle,
            source_labels=list(source_labels) if isinstance(source_labels, list) else [],
            sections=attachment_sections,
        )

    @app.get("/api/v1/tasks/{task_id}/smart-brief", response_model=TaskSmartBriefRecord)
    def get_task_smart_brief(task_id: str) -> TaskSmartBriefRecord:
        try:
            if not get_cloud_token():
                task_row = state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
                if not task_row:
                    raise HTTPException(status_code=404, detail="Task not found")
                task = fetch_tasks("t.id = ?", (task_id,))[0]
            else:
                task = fetch_cloud_task_by_id(task_id)
            return _build_smart_brief_for_task(task)
        except HTTPException:
            raise
        except Exception as exc:
            # Return empty brief instead of 500
            return TaskSmartBriefRecord(taskId=task_id, summary="", summarySourceLabels=[], actionItems=[])

    @app.post("/api/v1/tasks/smart-briefs", response_model=list[TaskSmartBriefRecord])
    def get_task_smart_briefs_batch(payload: dict) -> list[TaskSmartBriefRecord]:
        items = payload.get("tasks", [])
        if not items or not isinstance(items, list):
            return []
        results: list[TaskSmartBriefRecord] = []
        for item in items[:30]:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            try:
                attachment_titles = [str(t) for t in item.get("attachmentTitles", []) if t] if isinstance(item.get("attachmentTitles"), list) else []
                results.append(_build_smart_brief_from_hints(
                    task_id=str(item["id"]),
                    title=str(item.get("title", "")),
                    desc=str(item.get("desc", "")),
                    client_id=str(item["clientId"]) if item.get("clientId") else None,
                    event_line_id=str(item["eventLineId"]) if item.get("eventLineId") else None,
                    frontend_attachment_titles=attachment_titles,
                ))
            except Exception as brief_exc:
                # Log the error and return empty brief
                import traceback
                try:
                    Path(state.data_dir).joinpath("smart_brief_error.log").write_text(
                        f"task_id={item.get('id')}\n{traceback.format_exc()}", encoding="utf-8"
                    )
                except Exception:
                    pass
                results.append(TaskSmartBriefRecord(
                    taskId=str(item.get("id", "")),
                    summary="",
                    summarySourceLabels=[],
                    actionItems=[],
                ))
        return results

    @app.post("/api/v1/tasks/{task_id}/smart-brief-actions/{action_key}/adopt")
    def adopt_task_smart_brief_action(task_id: str, action_key: str, payload: dict | None = Body(default=None)) -> dict:
        payload = payload or {}
        created_task_id = str(payload.get("createdTaskId") or "").strip()
        action_text = str(payload.get("actionText") or "").strip()
        if not created_task_id:
            raise HTTPException(status_code=400, detail="createdTaskId is required")
        actor_id = _current_task_brief_actor_id()
        _record_task_brief_action_adoption(task_id, action_key, actor_id, created_task_id, action_text)
        return {"ok": True, "taskId": task_id, "actionKey": action_key, "createdTaskId": created_task_id}

    def _proposal_row_to_record(row) -> ProposalRecordRecord:
        target_refs_data = from_json(row["target_refs_json"], [])
        target_refs = [ProposalTargetRefRecord(**item) for item in target_refs_data] if isinstance(target_refs_data, list) else []
        source_refs_data = from_json(row["source_refs_json"], [])
        boundary_notes_data = from_json(row["boundary_notes_json"], [])
        payload_data = from_json(row["payload_json"], {})
        execution_ticket = None
        if row["execution_ticket_id"]:
            ticket_row = state.db.fetchone("SELECT * FROM execution_tickets WHERE id = ?", (str(row["execution_ticket_id"]),))
            if ticket_row:
                execution_ticket = _execution_ticket_row_to_record(ticket_row)
        return ProposalRecordRecord(
            id=str(row["id"]),
            clientId=str(row["client_id"]),
            kind=str(row["kind"]),  # type: ignore[arg-type]
            status=str(row["status"]),  # type: ignore[arg-type]
            riskLevel=str(row["risk_level"] or "medium"),  # type: ignore[arg-type]
            title=str(row["title"]),
            summary=str(row["summary"] or ""),
            rationale=str(row["rationale"] or ""),
            targetRefs=target_refs,
            sourceRefs=[str(item).strip() for item in source_refs_data if str(item).strip()] if isinstance(source_refs_data, list) else [],
            boundaryNotes=[str(item).strip() for item in boundary_notes_data if str(item).strip()] if isinstance(boundary_notes_data, list) else [],
            payload=payload_data if isinstance(payload_data, dict) else {},
            createdBy=str(row["created_by"] or ""),
            decidedBy=str(row["decided_by"]) if row["decided_by"] else None,
            decidedAt=str(row["decided_at"]) if row["decided_at"] else None,
            rejectedReason=str(row["rejected_reason"]) if row["rejected_reason"] else None,
            executionTicketId=str(row["execution_ticket_id"]) if row["execution_ticket_id"] else None,
            executionTicket=execution_ticket,
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def _execution_ticket_row_to_record(row) -> ExecutionTicketRecord:
        payload_data = from_json(row["payload_json"], {})
        result_data = from_json(row["result_json"], {})
        if not isinstance(result_data, dict):
            result_data = {}
        artifact_refs_data = result_data.get("artifactRefs", [])
        artifact_refs = [
            ExecutionArtifactRefRecord(
                artifactType=str(item.get("artifactType") or ""),
                refId=str(item.get("refId") or ""),
                title=str(item.get("title") or ""),
            )
            for item in artifact_refs_data
            if isinstance(item, dict)
        ] if isinstance(artifact_refs_data, list) else []
        result_record = ExecutionTicketResultRecord(
            resultType=(
                str(result_data.get("resultType") or "")
                if str(result_data.get("resultType") or "") in {"recorded_only", "prep_artifact_ready", "followup_task_created", "failed"}
                else ("failed" if str(row["status"]) == "failed" else "recorded_only")
            ),
            summary=str(result_data.get("summary") or result_data.get("message") or ""),
            createdTaskIds=[
                str(item).strip()
                for item in result_data.get("createdTaskIds", [])
                if str(item).strip()
            ] if isinstance(result_data.get("createdTaskIds"), list) else [
                str(item.get("id")).strip()
                for item in result_data.get("createdTasks", [])
                if isinstance(item, dict) and str(item.get("id") or "").strip()
            ],
            artifactRefs=artifact_refs,
        )
        return ExecutionTicketRecord(
            id=str(row["id"]),
            proposalId=str(row["proposal_id"]),
            clientId=str(row["client_id"]),
            executionType=str(row["execution_type"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            payload=payload_data if isinstance(payload_data, dict) else {},
            result=result_record,
            errorMessage=str(row["error_message"]) if row["error_message"] else None,
            executedAt=str(row["executed_at"]) if row["executed_at"] else None,
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def _current_proposal_actor() -> tuple[str, str]:
        session_user = get_cached_session_user()
        operator = current_operator_row()
        if session_user:
            return session_user.id, session_user.fullName
        return str(operator["id"]), str(operator["name"])

    def _task_for_prep_pack(task_id: str) -> TaskRecord:
        local_tasks = fetch_tasks("t.id = ?", (task_id,))
        if local_tasks:
            return local_tasks[0]
        if get_cloud_token():
            return fetch_cloud_task_by_id(task_id)
        raise HTTPException(status_code=404, detail="Task not found")

    def _client_id_for_task_scope(task: TaskRecord) -> str | None:
        if task.clientId:
            return task.clientId
        if task.eventLineId:
            row = state.db.fetchone("SELECT primary_client_id FROM event_lines WHERE id = ?", (task.eventLineId,))
            if row and row["primary_client_id"]:
                return str(row["primary_client_id"])
        return None

    def _latest_proposal_id_for_target(target_id: str, kind: str | None = None) -> str | None:
        if kind:
            row = state.db.fetchone(
                "SELECT id FROM proposal_records WHERE kind = ? AND target_refs_json LIKE ? ORDER BY updated_at DESC LIMIT 1",
                (kind, f"%{target_id}%"),
            )
        else:
            row = state.db.fetchone(
                "SELECT id FROM proposal_records WHERE target_refs_json LIKE ? ORDER BY updated_at DESC LIMIT 1",
                (f"%{target_id}%",),
            )
        return str(row["id"]) if row and row["id"] else None

    def _build_task_prep_pack(task: TaskRecord) -> PrepPackCardRecord:
        client_id = _client_id_for_task_scope(task)
        if is_private_task(task) or (not client_id and not task.eventLineId):
            return PrepPackCardRecord(
                taskId=task.id,
                title=task.title,
                summary="",
                materials=[],
                openQuestions=[],
                judgments=[],
                risks=[],
                boundaryNotes=["只有已绑定 client 或 event line 的协作任务才生成业务准备包。"],
                sourceLabels=[],
                proposalId=_latest_proposal_id_for_target(task.id, "task_prep"),
            )

        workspace = workspace_for_client(client_id) if client_id else None
        if workspace is None:
            return PrepPackCardRecord(
                taskId=task.id,
                title=task.title,
                summary="",
                materials=[],
                openQuestions=[],
                judgments=[],
                risks=[],
                boundaryNotes=["当前找不到关联客户，无法生成任务准备包。"],
                sourceLabels=[],
                proposalId=_latest_proposal_id_for_target(task.id, "task_prep"),
            )

        state_pack = build_state_answer_context_pack(workspace, f"为任务 {task.title} 生成准备包")
        approved_judgments, candidate_judgments = _workspace_state_judgments(workspace)
        materials: list[PrepPackMaterialRecord] = []

        if workspace.latestContextPack:
            materials.append(
                PrepPackMaterialRecord(
                    sourceType="context_pack",
                    sourceId=workspace.latestContextPack.id,
                    title="最新状态包",
                    summary=_workspace_state_payload_summary(workspace.latestContextPack.payload) or "已有最新客户状态包",
                    authorityLevel=workspace.latestContextPack.authorityLevel,
                )
            )
        for item in approved_judgments[:2]:
            materials.append(
                PrepPackMaterialRecord(
                    sourceType="judgment",
                    sourceId=item.id,
                    title=item.topic,
                    summary=_workspace_state_compact(item.summary, limit=120),
                    authorityLevel="approved",
                )
            )
        for item in candidate_judgments[:1]:
            materials.append(
                PrepPackMaterialRecord(
                    sourceType="judgment",
                    sourceId=item.id,
                    title=item.topic,
                    summary=_workspace_state_compact(item.summary, limit=120),
                    authorityLevel="candidate",
                )
            )
        for meeting in workspace.meetings[:2]:
            materials.append(
                PrepPackMaterialRecord(
                    sourceType="meeting",
                    sourceId=meeting.id,
                    title=meeting.title,
                    summary=f"{_workspace_state_date_label(meeting.updatedAt or meeting.scheduledAt)} · 阶段 {meeting.stage}",
                    authorityLevel="approved" if meeting.stage in {"resolved", "published"} else "informational",
                )
            )
        for related in [item for item in workspace.relatedTasks if item.id != task.id][:2]:
            materials.append(
                PrepPackMaterialRecord(
                    sourceType="task",
                    sourceId=related.id,
                    title=related.title,
                    summary=_workspace_state_compact(related.nextAction or related.currentBlocker or related.recentDecision or related.desc or related.status, limit=120),
                    authorityLevel="informational",
                )
            )

        judgments = [
            f"正式：{item.topic} - {_workspace_state_compact(item.summary, limit=100)}"
            for item in approved_judgments[:2]
        ] + [
            f"待确认：{item.topic} - {_workspace_state_compact(item.summary, limit=100)}"
            for item in candidate_judgments[:2]
        ]
        open_questions = [
            _workspace_state_compact(item.question + (f"；{item.reason}" if item.reason else ""), limit=120)
            for item in workspace.latestOpenQuestions[:3]
        ]
        risks = [
            _workspace_state_compact(item.title + "：" + item.summary, limit=120)
            for item in workspace.latestConflicts[:3]
        ]
        source_labels = list(dict.fromkeys(item.sourceType for item in materials))
        summary_parts = [
            f"任务已关联到 {workspace.client.name} 的客户状态池。",
            f"当前准备重点：{approved_judgments[0].topic}" if approved_judgments else "",
            f"最近动作：{active.summary}" if (active := next((item for item in materials if item.sourceType == 'task'), None)) else "",
            f"近期会议：{meeting.title}" if (meeting := next((item for item in materials if item.sourceType == 'meeting'), None)) else "",
        ]
        summary = " ".join(part for part in summary_parts if part).strip() or state_pack.summary
        return PrepPackCardRecord(
            taskId=task.id,
            title=task.title,
            summary=summary[:900],
            materials=materials[:8],
            openQuestions=open_questions,
            judgments=judgments[:4],
            risks=risks[:4],
            boundaryNotes=list(dict.fromkeys([
                *state_pack.boundaryNotes,
                "准备包只提供 candidate / risk / official 的边界清晰上下文，不直接改写 official judgment。",
            ]))[:6],
            sourceLabels=source_labels,
            proposalId=_latest_proposal_id_for_target(task.id, "task_prep"),
        )

    def _proposal_payload_hash(payload: dict[str, object]) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

    def _find_existing_meeting_proposal(
        *,
        client_id: str,
        meeting_id: str,
        kind: Literal["meeting_followup"],
        payload_hash: str,
    ) -> ProposalRecordRecord | None:
        rows = state.db.fetchall(
            """
            SELECT *
            FROM proposal_records
            WHERE client_id = ? AND kind = ? AND status NOT IN ('rejected', 'failed') AND target_refs_json LIKE ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 20
            """,
            (client_id, kind, f"%{meeting_id}%"),
        )
        for row in rows:
            proposal = _proposal_row_to_record(row)
            existing_payload = proposal.payload if isinstance(proposal.payload, dict) else {}
            existing_hash = str(existing_payload.get("payloadHash") or "").strip()
            if existing_hash == payload_hash:
                return proposal
        return None

    def _insert_proposal_record(
        *,
        client_id: str,
        kind: Literal["task_prep", "meeting_prep", "meeting_followup"],
        title: str,
        summary: str,
        rationale: str,
        target_refs: list[ProposalTargetRefRecord],
        source_refs: list[str],
        boundary_notes: list[str],
        payload: dict[str, object],
        risk_level: Literal["low", "medium", "high"] = "medium",
        status: Literal["draft", "pending_review", "approved", "rejected", "execution_pending", "executed", "failed"] = "pending_review",
    ) -> ProposalRecordRecord:
        proposal_id = new_id("proposal")
        actor_id, actor_name = _current_proposal_actor()
        timestamp = now_iso()
        state.db.execute(
            """
            INSERT INTO proposal_records(
                id, client_id, kind, status, risk_level, title, summary, rationale,
                target_refs_json, source_refs_json, boundary_notes_json, payload_json,
                created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (
                proposal_id,
                client_id,
                kind,
                status,
                risk_level,
                title,
                summary,
                rationale,
                to_json([item.model_dump() for item in target_refs]),
                to_json(source_refs),
                to_json(boundary_notes),
                to_json(payload),
                actor_name or actor_id,
                timestamp,
                timestamp,
            ),
        )
        row = state.db.fetchone("SELECT * FROM proposal_records WHERE id = ?", (proposal_id,))
        assert row is not None
        log_activity("proposal.create", "proposal", proposal_id, {"kind": kind, "clientId": client_id, "status": status})
        return _proposal_row_to_record(row)

    def _append_proposal_approval_audit(
        proposal: ProposalRecordRecord,
        *,
        decision: Literal["approved", "rejected"],
        comment: str,
    ) -> None:
        actor_id, actor_name = _current_proposal_actor()
        timestamp = now_iso()
        state.db.execute(
            """
            INSERT INTO approval_records(
                id, object_type, object_id, client_id, status, note, actor_id, actor_name, created_at,
                approval_target_type, approval_target_id, policy_type, decision, comment, decided_by, decided_at, metadata_json
            )
            VALUES(?, 'proposal_record', ?, ?, ?, ?, ?, ?, ?, 'proposal_record', ?, 'proposal_review', ?, ?, ?, ?, ?)
            """,
            (
                new_id("apr"),
                proposal.id,
                proposal.clientId,
                "completed",
                comment,
                actor_id,
                actor_name,
                timestamp,
                proposal.id,
                decision,
                comment,
                actor_name or actor_id,
                timestamp,
                to_json({"proposalKind": proposal.kind, "proposalStatus": proposal.status}),
            ),
        )

    def _update_proposal_status(
        proposal_id: str,
        *,
        status: Literal["draft", "pending_review", "approved", "rejected", "execution_pending", "executed", "failed"],
        rejected_reason: str | None = None,
        execution_ticket_id: str | None = None,
        decided: bool = False,
    ) -> ProposalRecordRecord:
        actor_id, actor_name = _current_proposal_actor()
        timestamp = now_iso()
        existing_row = state.db.fetchone("SELECT decided_by, decided_at FROM proposal_records WHERE id = ?", (proposal_id,))
        if not existing_row:
            raise HTTPException(status_code=404, detail="Proposal not found")
        current_decided_by = str(existing_row["decided_by"]) if existing_row["decided_by"] else None
        current_decided_at = str(existing_row["decided_at"]) if existing_row["decided_at"] else None
        state.db.execute(
            """
            UPDATE proposal_records
            SET status = ?, decided_by = ?, decided_at = ?, rejected_reason = ?, execution_ticket_id = COALESCE(?, execution_ticket_id), updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                actor_name or actor_id if decided else current_decided_by,
                timestamp if decided else current_decided_at,
                rejected_reason,
                execution_ticket_id,
                timestamp,
                proposal_id,
            ),
        )
        row = state.db.fetchone("SELECT * FROM proposal_records WHERE id = ?", (proposal_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found")
        return _proposal_row_to_record(row)

    def _insert_execution_ticket(
        *,
        proposal: ProposalRecordRecord,
        execution_type: str,
        payload: dict[str, object],
    ) -> ExecutionTicketRecord:
        ticket_id = new_id("exec")
        timestamp = now_iso()
        state.db.execute(
            """
            INSERT INTO execution_tickets(
                id, proposal_id, client_id, execution_type, status, payload_json, result_json, error_message, executed_at, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, 'running', ?, '{}', NULL, NULL, ?, ?)
            """,
            (
                ticket_id,
                proposal.id,
                proposal.clientId,
                execution_type,
                to_json(payload),
                timestamp,
                timestamp,
            ),
        )
        row = state.db.fetchone("SELECT * FROM execution_tickets WHERE id = ?", (ticket_id,))
        assert row is not None
        return _execution_ticket_row_to_record(row)

    def _complete_execution_ticket(
        ticket_id: str,
        *,
        status: Literal["executed", "failed"],
        result: dict[str, object] | None = None,
        error_message: str | None = None,
    ) -> ExecutionTicketRecord:
        timestamp = now_iso()
        state.db.execute(
            """
            UPDATE execution_tickets
            SET status = ?, result_json = ?, error_message = ?, executed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                to_json(result or {}),
                error_message,
                timestamp if status == "executed" else None,
                timestamp,
                ticket_id,
            ),
        )
        row = state.db.fetchone("SELECT * FROM execution_tickets WHERE id = ?", (ticket_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Execution ticket not found")
        return _execution_ticket_row_to_record(row)

    @app.get("/api/v1/tasks/{task_id}/prep-pack", response_model=PrepPackCardRecord)
    def get_task_prep_pack(task_id: str) -> PrepPackCardRecord:
        task = _task_for_prep_pack(task_id)
        return _build_task_prep_pack(task)

    @app.post("/api/v1/tasks/{task_id}/prep-pack/proposals", response_model=ProposalRecordRecord)
    def create_task_prep_proposal(task_id: str) -> ProposalRecordRecord:
        task = _task_for_prep_pack(task_id)
        prep_pack = _build_task_prep_pack(task)
        client_id = _client_id_for_task_scope(task)
        if not client_id or not prep_pack.summary.strip():
            raise HTTPException(status_code=400, detail="当前任务没有足够的业务上下文，不能生成 proposal")
        target_refs = [
            ProposalTargetRefRecord(targetType="task", targetId=task.id, label=task.title),
            ProposalTargetRefRecord(targetType="client", targetId=client_id, label=task.clientName or ""),
        ]
        if task.eventLineId:
            target_refs.append(ProposalTargetRefRecord(targetType="event_line", targetId=task.eventLineId, label=task.eventLineName or ""))
        return _insert_proposal_record(
            client_id=client_id,
            kind="task_prep",
            title=f"任务准备包 · {task.title}",
            summary=prep_pack.summary,
            rationale="基于客户资料、判断、会议、任务推进和未决问题生成只读准备包，待人工批准后进入执行。",
            target_refs=target_refs,
            source_refs=prep_pack.sourceLabels,
            boundary_notes=prep_pack.boundaryNotes,
            payload={
                "taskId": task.id,
                "taskTitle": task.title,
                "prepPack": prep_pack.model_dump(),
            },
            risk_level="medium" if prep_pack.risks else "low",
        )

    @app.get("/api/v1/proposals", response_model=list[ProposalRecordRecord])
    def list_proposals(status: str | None = Query(default=None), clientId: str | None = Query(default=None)) -> list[ProposalRecordRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clientId:
            clauses.append("client_id = ?")
            params.append(clientId)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = state.db.fetchall(
            f"SELECT * FROM proposal_records {where_clause} ORDER BY updated_at DESC, created_at DESC LIMIT 200",
            tuple(params),
        )
        return [_proposal_row_to_record(row) for row in rows]

    @app.post("/api/v1/proposals/{proposal_id}/approve", response_model=ProposalRecordRecord)
    def approve_proposal(proposal_id: str, payload: ProposalDecisionPayload) -> ProposalRecordRecord:
        row = state.db.fetchone("SELECT * FROM proposal_records WHERE id = ?", (proposal_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found")
        proposal = _proposal_row_to_record(row)
        updated = _update_proposal_status(proposal_id, status="approved", decided=True)
        _append_proposal_approval_audit(updated, decision="approved", comment=payload.comment)
        log_activity("proposal.approve", "proposal", proposal_id, {"comment": payload.comment})
        return updated

    @app.post("/api/v1/proposals/{proposal_id}/reject", response_model=ProposalRecordRecord)
    def reject_proposal(proposal_id: str, payload: ProposalDecisionPayload) -> ProposalRecordRecord:
        row = state.db.fetchone("SELECT * FROM proposal_records WHERE id = ?", (proposal_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found")
        proposal = _proposal_row_to_record(row)
        updated = _update_proposal_status(
            proposal_id,
            status="rejected",
            rejected_reason=payload.comment or "人工驳回",
            decided=True,
        )
        _append_proposal_approval_audit(updated, decision="rejected", comment=payload.comment or "人工驳回")
        log_activity("proposal.reject", "proposal", proposal_id, {"comment": payload.comment})
        return updated

    @app.post("/api/v1/proposals/{proposal_id}/execute", response_model=ProposalExecutionResponse)
    def execute_proposal(proposal_id: str, payload: ProposalDecisionPayload) -> ProposalExecutionResponse:
        row = state.db.fetchone("SELECT * FROM proposal_records WHERE id = ?", (proposal_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found")
        proposal = _proposal_row_to_record(row)
        if proposal.status == "executed" and proposal.executionTicketId:
            ticket_row = state.db.fetchone("SELECT * FROM execution_tickets WHERE id = ?", (proposal.executionTicketId,))
            if ticket_row:
                return ProposalExecutionResponse(proposal=proposal, executionTicket=_execution_ticket_row_to_record(ticket_row))
        if proposal.status == "execution_pending" and proposal.executionTicketId:
            ticket_row = state.db.fetchone("SELECT * FROM execution_tickets WHERE id = ?", (proposal.executionTicketId,))
            if ticket_row:
                ticket = _execution_ticket_row_to_record(ticket_row)
                if ticket.status in {"running", "executed"}:
                    return ProposalExecutionResponse(proposal=proposal, executionTicket=ticket)
        if proposal.status not in {"approved", "execution_pending"}:
            raise HTTPException(status_code=400, detail="只有已批准 proposal 才能执行")
        execution_type = "task_creation" if proposal.kind == "meeting_followup" else "proposal_ack"
        ticket = _insert_execution_ticket(proposal=proposal, execution_type=execution_type, payload=proposal.payload)
        _update_proposal_status(proposal.id, status="execution_pending", execution_ticket_id=ticket.id)
        try:
            result: dict[str, object]
            if proposal.kind == "meeting_followup":
                created_tasks: list[dict[str, object]] = []
                action_items = proposal.payload.get("actionItems", [])
                if not isinstance(action_items, list) or not action_items:
                    raise HTTPException(status_code=400, detail="该 proposal 没有可执行的会后 action items")
                settings = get_client_workspace_settings()
                default_list_id = settings.meetingPublishDefaultListId or _get_local_task_settings().defaultListId or "list-0"
                for item in action_items[:8]:
                    if not isinstance(item, dict):
                        continue
                    title = _workspace_state_compact(str(item.get("title") or "").strip(), limit=120)
                    if not title:
                        continue
                    created = create_task(
                        TaskPayload(
                            title=title,
                            desc=str(item.get("summary") or item.get("deliverable") or "来自会议 follow-up proposal"),
                            priority=settings.meetingPublishDefaultPriority,
                            listId=default_list_id,
                            ddl=str(item.get("dueDate") or "本周"),
                            ownerName=str(item.get("ownerName") or current_operator_name()),
                            clientId=proposal.clientId,
                            sourceType="meeting_followup_proposal",
                            sourceId=proposal.id,
                            tags=["Proposal", "会议跟进"],
                        ),
                        status="inbox",
                    )
                    created_tasks.append({"id": created.id, "title": created.title})
                result = {
                    "resultType": "followup_task_created",
                    "summary": f"已从会后 follow-up proposal 创建 {len(created_tasks)} 条真实任务。",
                    "createdTaskIds": [str(item["id"]) for item in created_tasks if str(item.get("id") or "").strip()],
                    "artifactRefs": [],
                    "count": len(created_tasks),
                    "createdTasks": created_tasks,
                }
            else:
                artifact_ref = ExecutionArtifactRefRecord(
                    artifactType="prep_pack",
                    refId=str(proposal.payload.get("taskId") or proposal.payload.get("meetingId") or proposal.id),
                    title=str(proposal.payload.get("taskTitle") or proposal.payload.get("meetingTitle") or proposal.title),
                ).model_dump()
                result = {
                    "resultType": "prep_artifact_ready",
                    "summary": "已生成可消费准备包，本轮仅进入执行台账，不直接改写 official judgment。",
                    "createdTaskIds": [],
                    "artifactRefs": [artifact_ref],
                }
            completed_ticket = _complete_execution_ticket(ticket.id, status="executed", result=result)
            updated = _update_proposal_status(proposal.id, status="executed", execution_ticket_id=ticket.id)
            log_activity("proposal.execute", "proposal", proposal.id, {"executionType": execution_type, "result": result})
            return ProposalExecutionResponse(proposal=updated, executionTicket=completed_ticket)
        except HTTPException as exc:
            failed_ticket = _complete_execution_ticket(
                ticket.id,
                status="failed",
                result={
                    "resultType": "failed",
                    "summary": str(exc.detail),
                    "createdTaskIds": [],
                    "artifactRefs": [],
                },
                error_message=str(exc.detail),
            )
            updated = _update_proposal_status(proposal.id, status="failed", execution_ticket_id=ticket.id)
            return ProposalExecutionResponse(proposal=updated, executionTicket=failed_ticket)
        except Exception as exc:
            failed_ticket = _complete_execution_ticket(
                ticket.id,
                status="failed",
                result={
                    "resultType": "failed",
                    "summary": str(exc),
                    "createdTaskIds": [],
                    "artifactRefs": [],
                },
                error_message=str(exc),
            )
            updated = _update_proposal_status(proposal.id, status="failed", execution_ticket_id=ticket.id)
            return ProposalExecutionResponse(proposal=updated, executionTicket=failed_ticket)

    @app.post("/api/v1/event-lines/{event_line_id}/attachments")
    def upload_event_line_attachment(
        event_line_id: str,
        file: UploadFile = File(...),
        title: str | None = Form(default=None),
    ) -> dict:
        if not get_cloud_token():
            raise HTTPException(status_code=400, detail="需要登录云端才能上传事件线附件")
        content = file.file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传内容为空")
        try:
            result = cloud_upload_file(
                f"/api/v1/event-lines/{event_line_id}/attachments",
                file_name=file.filename or "attachment",
                file_content=content,
                content_type=file.content_type or "application/octet-stream",
                form_fields={"title": title or file.filename or "事件线附件"},
            )
            return result if isinstance(result, dict) else {}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"附件上传失败：{exc}") from exc

    @app.get("/api/v1/event-lines/{event_line_id}/report-snapshot")
    def get_event_line_report_snapshot(event_line_id: str) -> dict:
        if not get_cloud_token():
            raise HTTPException(status_code=400, detail="需要登录云端才能获取事件线汇报快照")
        payload = cloud_request("GET", f"/api/v1/event-lines/{event_line_id}/report-snapshot")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Invalid report snapshot payload")
        return payload

    @app.post("/api/v1/event-lines/{event_line_id}/export-word")
    def export_event_line_word(event_line_id: str, draft: dict = Body(...)) -> dict:
        from docx.shared import Pt, Cm, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        doc = WordDocument()

        event_line_kind_labels = {
            "project_line": "项目线",
            "issue_line": "议题线",
            "coordination_line": "协同线",
            "case_line": "案例线",
            "custom": "事件线",
        }
        event_line_status_labels = {
            "active": "推进中",
            "blocked": "存在阻点",
            "paused": "暂缓中",
            "done": "已完成",
            "archived": "已归档",
        }

        def _clean_text(value: object | None) -> str:
            return " ".join(str(value or "").split()).strip()

        def _truncate_text(value: object | None, limit: int) -> str:
            normalized = _clean_text(value)
            if not normalized:
                return ""
            if len(normalized) <= limit:
                return normalized
            return f"{normalized[: max(0, limit - 1)].rstrip()}…"

        def _format_doc_date(value: object | None) -> str:
            normalized = _clean_text(value)
            if not normalized:
                return "待补充"
            return normalized[:10].replace("-", ".")

        def _activity_title(activity: dict) -> str:
            return _clean_text(activity.get("editedTitle") or activity.get("title") or "未命名活动")

        def _activity_summary(activity: dict) -> str:
            return _clean_text(activity.get("editedSummary") or activity.get("summary") or "")

        def _is_key(activity: dict) -> bool:
            if activity.get("isKey") is not None:
                return bool(activity["isKey"])
            source_type = str(activity.get("sourceType", ""))
            if source_type in ("manual_note", "attachment"):
                return True
            metadata = activity.get("metadata") or {}
            if source_type == "task_activity" and isinstance(metadata, dict) and metadata.get("eventType") == "created":
                return True
            return False

        def _is_bootstrap_activity(activity: dict) -> bool:
            source_type = str(activity.get("sourceType", ""))
            metadata = activity.get("metadata") or {}
            event_type = str(metadata.get("eventType", "")).lower() if isinstance(metadata, dict) else ""
            if source_type == "task_activity" and event_type == "created":
                return True
            if event_type in {"event_line_created", "line_created"}:
                return True
            text = f"{_activity_title(activity)} {_activity_summary(activity)}".lower()
            return "创建事件线" in text or "created event line" in text

```
