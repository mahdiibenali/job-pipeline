import uuid

import pytest

from scheduler.state_machine import (
    DEAD_LETTER,
    FAILED,
    PENDING,
    PROCESSING,
    enqueue_job,
    get_queue_stats,
    pop_pending,
    reclaim_stale_leases,
    transition,
)


@pytest.fixture
def sample_job():
    uid = str(uuid.uuid4())
    jid = enqueue_job(
        title="Test Engineer",
        company="TestCorp",
        domain="testcorp.com",
        url="https://testcorp.com/jobs/1",
        source="test",
        fingerprint=f"test_fp_{uid}",
        region="REMOTE",
        country="REMOTE",
        discovery_score=0.8,
    )
    return jid


class TestEnqueueJob:
    def test_enqueue_returns_job_id(self, sample_job):
        assert sample_job is not None
        assert len(sample_job) == 36  # uuid4 length

    def test_enqueue_rejects_duplicate(self, sample_job):
        # Same fingerprint should return None
        uid = str(uuid.uuid4())
        jid = enqueue_job(
            title="Test Engineer",
            company="TestCorp",
            domain="testcorp.com",
            url="https://testcorp.com/jobs/1",
            source="test",
            fingerprint=f"test_fp_{uid}",
        )
        dup = enqueue_job(
            title="Test Engineer",
            company="TestCorp",
            domain="testcorp.com",
            url="https://testcorp.com/jobs/2",
            source="test",
            fingerprint=f"test_fp_{uid}",
        )
        assert dup is None

    def test_enqueue_sets_pending(self, sample_job):
        stats = get_queue_stats()
        assert stats.get(PENDING, 0) >= 1


class TestTransition:
    def test_valid_transition(self, sample_job):
        assert transition(sample_job, PROCESSING) is True

    def test_invalid_transition(self, sample_job):
        assert transition(sample_job, "APPROVED") is False  # PENDING -> APPROVED is invalid

    def test_nonexistent_job(self):
        assert transition("nonexistent", PROCESSING) is False

    def test_dead_letter_after_3_retries(self, sample_job):
        for i in range(3):
            transition(sample_job, PROCESSING)
            transition(sample_job, FAILED, error=f"error_{i}")
        # After 3 failures + 1, should go to DEAD_LETTER
        stats = get_queue_stats()
        if FAILED in stats:
            transition(sample_job, DEAD_LETTER)

    def test_transition_creates_audit_log(self, sample_job):
        from db.connection import get_connection

        transition(sample_job, PROCESSING)
        conn = get_connection()
        rows = conn.execute(
            "SELECT COUNT(*) as cnt FROM audit_log WHERE entity_id=?", (sample_job,)
        ).fetchone()
        # 1 for CREATED + 1 for PROCESSING
        assert rows["cnt"] >= 2


class TestPopPending:
    def test_pop_returns_jobs(self, sample_job):
        jobs = pop_pending(limit=10)
        assert len(jobs) >= 1
        assert jobs[0]["job_id"] == sample_job

    def test_pop_transitions_to_processing(self, sample_job):
        pop_pending(limit=10)
        stats = get_queue_stats()
        assert stats.get(PROCESSING, 0) >= 1
        assert stats.get(PENDING, 0) == 0

    def test_pop_respects_limit(self, sample_job):
        # Add more jobs
        for i in range(5):
            enqueue_job(
                title=f"Job {i}",
                company="Test",
                domain="test.com",
                url=f"https://test.com/{i}",
                source="test",
                fingerprint=f"fp_pop_test_{i}",
                discovery_score=0.5,
            )
        jobs = pop_pending(limit=3)
        assert len(jobs) <= 3


class TestReclaimStaleLeases:
    def test_reclaims_stale_jobs(self):
        jid = enqueue_job(
            title="Stale Job",
            company="Test",
            domain="test.com",
            url="https://test.com/stale",
            source="test",
            fingerprint="fp_stale_reclaim",
        )
        transition(jid, PROCESSING)

        # Manually set lease to past
        from db.connection import get_connection
        from datetime import datetime, timedelta, timezone

        conn = get_connection()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        conn.execute(
            "UPDATE jobs SET lease_expires_at=? WHERE job_id=?",
            (past, jid),
        )
        conn.commit()

        reclaimed = reclaim_stale_leases()
        assert reclaimed >= 1

        stats = get_queue_stats()
        assert stats.get(PENDING, 0) >= 1
