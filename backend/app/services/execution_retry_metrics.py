from __future__ import annotations

from datetime import datetime, timedelta

from app.db import Database
from app.models import (
    ExecutionRetryMetricAlertRecord,
    ExecutionRetryMetricTopItemRecord,
    ExecutionRetryMetricsRecord,
)


def _window_start_iso(days: int) -> str:
    return (datetime.now() - timedelta(days=max(int(days), 1))).replace(microsecond=0).isoformat()


def _metric_top_items(rows, *, key_column: str) -> list[ExecutionRetryMetricTopItemRecord]:
    items: list[ExecutionRetryMetricTopItemRecord] = []
    for row in rows:
        key = str(row[key_column] or "").strip()
        if not key:
            continue
        items.append(
            ExecutionRetryMetricTopItemRecord(
                key=key,
                count=int(row["count"] or 0),
            )
        )
    return items


def get_execution_retry_metrics(
    db: Database,
    *,
    client_id: str | None = None,
    days: int = 7,
) -> ExecutionRetryMetricsRecord:
    window_days = max(int(days), 1)
    since = _window_start_iso(window_days)

    clauses = ["created_at >= ?"]
    params: list[object] = [since]
    if client_id:
        clauses.append("client_id = ?")
        params.append(client_id)
    where_clause = f"WHERE {' AND '.join(clauses)}"

    total_tickets = int(
        db.scalar(
            f"SELECT COUNT(1) AS count FROM execution_tickets {where_clause}",
            tuple(params),
        )
        or 0
    )
    failed_tickets = int(
        db.scalar(
            f"SELECT COUNT(1) AS count FROM execution_tickets {where_clause} AND status = 'failed'",
            tuple(params),
        )
        or 0
    )
    retried_tickets = int(
        db.scalar(
            f"SELECT COUNT(1) AS count FROM execution_tickets {where_clause} AND retry_count > 0",
            tuple(params),
        )
        or 0
    )
    retry_exhausted_tickets = int(
        db.scalar(
            f"SELECT COUNT(1) AS count FROM execution_tickets {where_clause} AND status = 'failed' AND retry_count >= max_retries",
            tuple(params),
        )
        or 0
    )
    retried_success_tickets = int(
        db.scalar(
            f"SELECT COUNT(1) AS count FROM execution_tickets {where_clause} AND status = 'executed' AND retry_count > 0",
            tuple(params),
        )
        or 0
    )
    avg_retry_count = float(
        db.scalar(
            f"SELECT AVG(retry_count) AS avg_count FROM execution_tickets {where_clause} AND retry_count > 0",
            tuple(params),
        )
        or 0.0
    )
    oldest_failed_row = db.fetchone(
        f"""
        SELECT MIN(created_at) AS oldest_created_at
        FROM execution_tickets
        {where_clause}
        AND status = 'failed'
        """,
        tuple(params),
    )
    oldest_failed_ticket_age_hours = 0.0
    oldest_failed_value = ""
    if oldest_failed_row:
        oldest_failed_value = str(oldest_failed_row["oldest_created_at"] or "").strip()
    if oldest_failed_value:
        try:
            oldest_dt = datetime.fromisoformat(oldest_failed_value)
            oldest_failed_ticket_age_hours = max(
                0.0,
                round((datetime.now() - oldest_dt).total_seconds() / 3600.0, 2),
            )
        except Exception:
            oldest_failed_ticket_age_hours = 0.0

    failure_reason_rows = db.fetchall(
        f"""
        SELECT COALESCE(last_error, 'unknown') AS reason, COUNT(1) AS count
        FROM execution_tickets
        {where_clause}
        AND status = 'failed'
        GROUP BY COALESCE(last_error, 'unknown')
        ORDER BY count DESC, reason ASC
        LIMIT 5
        """,
        tuple(params),
    )
    failure_reason_topn = _metric_top_items(failure_reason_rows, key_column="reason")

    log_clauses = ["l.created_at >= ?"]
    log_params: list[object] = [since]
    if client_id:
        log_clauses.append("t.client_id = ?")
        log_params.append(client_id)
    log_where_clause = f"WHERE {' AND '.join(log_clauses)}"
    failed_stage_rows = db.fetchall(
        f"""
        SELECT l.stage AS stage, COUNT(1) AS count
        FROM execution_ticket_logs l
        JOIN execution_tickets t ON t.id = l.ticket_id
        {log_where_clause}
        AND l.status = 'failed'
        GROUP BY l.stage
        ORDER BY count DESC, stage ASC
        LIMIT 5
        """,
        tuple(log_params),
    )
    failed_stage_topn = _metric_top_items(failed_stage_rows, key_column="stage")

    alerts: list[ExecutionRetryMetricAlertRecord] = []
    if retry_exhausted_tickets > 0:
        alerts.append(
            ExecutionRetryMetricAlertRecord(
                level="warning",
                message=f"存在 {retry_exhausted_tickets} 个 execution ticket 重试次数耗尽",
            )
        )
    if failed_tickets > 0 and total_tickets > 0 and (failed_tickets / total_tickets) >= 0.2:
        alerts.append(
            ExecutionRetryMetricAlertRecord(
                level="warning",
                message="execution ticket 失败率超过 20%，建议先排查失败阶段与原因 TopN",
            )
        )
    if oldest_failed_ticket_age_hours >= 24:
        alerts.append(
            ExecutionRetryMetricAlertRecord(
                level="warning",
                message=f"存在失败 ticket 超过 {oldest_failed_ticket_age_hours} 小时未处理",
            )
        )

    return ExecutionRetryMetricsRecord(
        windowDays=window_days,
        totalTickets=total_tickets,
        failedTickets=failed_tickets,
        retriedTickets=retried_tickets,
        retryExhaustedTickets=retry_exhausted_tickets,
        retrySuccessRate=round(float(retried_success_tickets) / float(retried_tickets), 4) if retried_tickets > 0 else 0.0,
        avgRetryCount=round(avg_retry_count, 2),
        oldestFailedTicketAgeHours=oldest_failed_ticket_age_hours,
        failureReasonTopN=failure_reason_topn,
        failedStageTopN=failed_stage_topn,
        alerts=alerts,
    )
