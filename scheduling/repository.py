"""Optional PostgreSQL persistence for scheduling feedback and habit history."""

import os
from datetime import datetime, timezone

from .models import UserProfile


class PostgresRepository:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.getenv("DATABASE_URL")

    @property
    def configured(self) -> bool:
        return bool(self.dsn)

    def _connect(self):
        if not self.dsn:
            return None
        try:
            import psycopg2
        except ImportError as exc:
            raise RuntimeError("Thiếu psycopg2-binary để lưu feedback scheduling.") from exc
        return psycopg2.connect(self.dsn)

    def ensure_schema(self) -> None:
        connection = self._connect()
        if connection is None:
            return
        try:
            with connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scheduling_feedback (
                        id BIGSERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        slot_start TIMESTAMPTZ NOT NULL,
                        action TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
        finally:
            connection.close()

    def record_feedback(
        self,
        user_id: str,
        event_type: str,
        slot_start: datetime,
        action: str,
    ) -> None:
        if action not in {"accepted", "rejected", "rescheduled", "cancelled"}:
            raise ValueError(f"Feedback action không hợp lệ: {action}")
        connection = self._connect()
        if connection is None:
            return
        try:
            with connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO scheduling_feedback
                        (user_id, event_type, slot_start, action, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, event_type, slot_start, action, datetime.now(timezone.utc)),
                )
        finally:
            connection.close()

    def load_profile(self, user_id: str) -> UserProfile:
        connection = self._connect()
        if connection is None:
            return UserProfile()
        try:
            with connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_type, EXTRACT(HOUR FROM slot_start),
                           COUNT(*) FILTER (WHERE action = 'accepted') AS accepted,
                           COUNT(*) FILTER (WHERE action IN ('rescheduled', 'cancelled')) AS unstable
                    FROM scheduling_feedback
                    WHERE user_id = %s
                    GROUP BY event_type, EXTRACT(HOUR FROM slot_start)
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
        finally:
            connection.close()
        hours: dict[str, list[float]] = {}
        instability: dict[str, list[int]] = {}
        for event_type, hour, accepted, unstable in rows:
            hours.setdefault(event_type, []).extend([float(hour)] * max(1, accepted))
            instability.setdefault(event_type, []).extend([0] * accepted + [1] * unstable)
        return UserProfile(
            habit_hours={key: tuple(values) for key, values in hours.items()},
            reschedule_rate={
                key: sum(values) / len(values) for key, values in instability.items() if values
            },
        )
