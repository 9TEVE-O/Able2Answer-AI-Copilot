"""Holds the most recent observation of the open Live Set.

Deliberately in memory and deliberately single-valued. A snapshot is only
meaningful while Live is still in that state, so persisting it would invite
Abel to answer questions about a session that has since moved on. When no
fresh snapshot is held, the correct answer to a session question is that Abel
cannot currently see the Live Set — never a stale one presented as current.
"""
from __future__ import annotations

import threading
from datetime import timedelta

from abel.live.models import SessionSnapshot

# How long an observation is treated as describing the current session.
# Producers change things constantly; an old reading is a guess in a fact's clothes.
DEFAULT_MAX_AGE = timedelta(seconds=30)


class SnapshotStore:
    """Thread-safe holder for the current session snapshot."""

    def __init__(self, max_age: timedelta = DEFAULT_MAX_AGE) -> None:
        self._max_age = max_age
        self._lock = threading.Lock()
        self._snapshot: SessionSnapshot | None = None

    def put(self, snapshot: SessionSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot

    def get(self) -> SessionSnapshot | None:
        """The current snapshot, or ``None`` if there is none or it has gone stale."""
        snapshot = self.get_even_if_stale()
        if snapshot is None or snapshot.age() > self._max_age:
            return None
        return snapshot

    def get_even_if_stale(self) -> SessionSnapshot | None:
        """The held snapshot regardless of age, for reporting connection state."""
        with self._lock:
            return self._snapshot

    def clear(self) -> None:
        with self._lock:
            self._snapshot = None

    @property
    def max_age(self) -> timedelta:
        return self._max_age
