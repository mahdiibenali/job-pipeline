import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from db.connection import get_connection

log = logging.getLogger(__name__)

PENDING = "PENDING"
PROCESSING = "PROCESSING"
EXTRACTED = "EXTRACTED"
FAILED = "FAILED"
QUALIFIED = "QUALIFIED"
DISQUALIFIED = "DISQUALIFIED"
CV_DONE = "CV_DONE"
CL_DONE = "CL_DONE"
PENDING_REVIEW = "PENDING_REVIEW"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
ARCHIVED = "ARCHIVED"
DEAD_LETTER = "DEAD_LETTER"

ALL_STATES = {
    PENDING, PROCESSING, EXTRACTED, FAILED, QUALIFIED,
    DISQUALIFIED, CV_DONE, CL_DONE, PENDING_REVIEW,
    APPROVED, REJECTED, ARCHIVED, DEAD_LETTER,
}

VALID_TRANSITIONS: dict[str, set[str]] = {
    PENDING: {PROCESSING},
    PROCESSING: {EXTRACTED, FAILED, PENDING},
    EXTRACTED: {QUALIFIED, DISQUALIFIED, FAILED},
    FAILED: {PENDING, DEAD_LETTER, ARCHIVED},
    QUALIFIED: {CV_DONE, DISQUALIFIED, FAILED, REJECTED},
    DISQUALIFIED: {ARCHIVED, REJECTED},
    CV_DONE: {CL_DONE, FAILED, REJECTED},
    CL_DONE: {PENDING_REVIEW, FAILED, REJECTED},
    PENDING_REVIEW: {APPROVED, REJECTED},
    APPROVED: {ARCHIVED, REJECTED},
    REJECTED: {ARCHIVED},
    DEAD_LETTER: {ARCHIVED},
}

RETRY_DELAYS = [1, 5, 15]
LEASE_DURATION_MINUTES = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(entity_id: str, action: str, actor: str, payload: dict | None = None) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log (entity_type, entity_id, action, actor, payload, created_at) "
        "VALUES ('job', ?, ?, ?, ?, ?)",
        (entity_id, action, actor, json.dumps(payload) if payload else None, _now_iso()),
    )


def transition(job_id: str, to_state: str, actor: str = "system", error: str | None = None) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT state, retry_count FROM jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if not row:
        log.warning("[SM] Job %s not found.", job_id)
        return False

    from_state = row["state"]
    retry_count = row["retry_count"]

    allowed = VALID_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        log.warning("[SM] Invalid transition: %s -> %s for job %s", from_state, to_state, job_id)
        return False

    updates: dict[str, str | int | None] = {"state": to_state, "updated_at": _now_iso()}

    if to_state == PROCESSING:
        expires = datetime.now(timezone.utc) + timedelta(minutes=LEASE_DURATION_MINUTES)
        updates["lease_expires_at"] = expires.isoformat()

    if to_state == FAILED:
        new_retry = retry_count + 1
        updates["retry_count"] = new_retry
        if new_retry >= 3:
            dlq_category = error or "unknown"
            conn.execute(
                "INSERT INTO dead_letter_queue (job_id, category, error_trace, agent, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, dlq_category, error, actor, _now_iso()),
            )

    if to_state == PENDING and from_state == FAILED:
        delay = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)]
        jitter = __import__("random").uniform(0.8, 1.2)
        expires = datetime.now(timezone.utc) + timedelta(minutes=delay * jitter)
        updates["lease_expires_at"] = expires.isoformat()

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [job_id]
    conn.execute(f"UPDATE jobs SET {set_clause} WHERE job_id=?", values)

    _audit(job_id, f"{from_state}->{to_state}", actor, {"error": error} if error else None)
    conn.commit()
    return True


def enqueue_job(
    title: str,
    company: str,
    domain: str,
    url: str,
    source: str,
    fingerprint: str,
    region: str | None = None,
    country: str | None = None,
    discovery_score: float = 0.0,
    visa_signal: str | None = None,
) -> str | None:
    conn = get_connection()
    job_id = str(uuid.uuid4())
    now = _now_iso()

    try:
        conn.execute(
            "INSERT INTO jobs "
            "(job_id, fingerprint, title, company, domain, url, source, "
            " region, country, state, discovery_score, visa_signal, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)",
            (job_id, fingerprint, title, company, domain, url, source,
             region, country, discovery_score, visa_signal, now, now),
        )
        conn.commit()
        _audit(job_id, "CREATED", "discovery_agent", {"score": discovery_score, "source": source})
        log.info("[Queue] Enqueued: %s at %s", title, company)
        return job_id
    except conn.IntegrityError:
        log.debug("[Queue] Duplicate fingerprint skipped: %s", fingerprint)
        return None


def pop_pending(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT job_id, title, company, domain, url, source, region, country, "
        "       discovery_score, visa_signal, retry_count "
        "FROM jobs "
        "WHERE state='PENDING' "
        "ORDER BY discovery_score DESC, created_at ASC "
        "LIMIT ?",
        (limit,),
    ).fetchall()

    result = []
    for row in rows:
        result.append(dict(row))
        transition(row["job_id"], PROCESSING, actor="scheduler")

    return result


def reclaim_stale_leases() -> int:
    conn = get_connection()
    now = _now_iso()
    stale = conn.execute(
        "SELECT job_id, retry_count FROM jobs "
        "WHERE state='PROCESSING' "
        "  AND lease_expires_at IS NOT NULL "
        "  AND lease_expires_at < ?",
        (now,),
    ).fetchall()

    reclaimed = 0
    for row in stale:
        if row["retry_count"] >= 3:
            transition(row["job_id"], DEAD_LETTER, actor="sweeper", error="lease expired 3x")
        else:
            transition(row["job_id"], PENDING, actor="sweeper")
        reclaimed += 1

    if reclaimed:
        log.info("[Sweeper] Reclaimed %d stale jobs.", reclaimed)
    return reclaimed


def get_queue_stats() -> dict[str, int]:
    conn = get_connection()
    rows = conn.execute("SELECT state, COUNT(*) as cnt FROM jobs GROUP BY state").fetchall()
    return {row["state"]: row["cnt"] for row in rows}
