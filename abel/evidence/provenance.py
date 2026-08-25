"""Where every fact Abel states actually came from.

Abel's central claim is that it explains evidence rather than inventing it.
That is only meaningful if each fact carries its origin, so this module keeps
two kinds of evidence permanently distinguishable:

``Observation``
    Something read out of the producer's own Live Set. Authoritative about
    *this* session, and about nothing else.

``KnowledgeExcerpt``
    Something retrieved from Abel's local knowledge base. Authoritative about
    Ableton and audio in general, and about no particular session.

Conflating the two is the failure this design exists to prevent: general
knowledge stated as if it had been measured, or a session value stated as if
it were a rule.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Observation:
    """A single fact read from the Live Set."""

    key: str                        # stable id, e.g. "audio.sample_rate_hz"
    label: str                      # how it is shown to the producer, e.g. "Sample rate"
    value: Any                      # exactly as read; None means Live did not report it
    captured_at: datetime
    unit: str | None = None
    lom_path: str | None = None     # the Live Object Model path, for auditability

    @property
    def kind(self) -> str:
        return "observation"

    def render(self) -> str:
        """One line of evidence, as shown to the producer and given to the model."""
        if self.value is None:
            return f"{self.label}: not reported by Live"
        value = f"{self.value} {self.unit}" if self.unit else str(self.value)
        return f"{self.label}: {value}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "lom_path": self.lom_path,
            "captured_at": self.captured_at.isoformat(),
            "rendered": self.render(),
        }


@dataclass(frozen=True)
class KnowledgeExcerpt:
    """A passage retrieved from Abel's local knowledge base."""

    document_id: str
    title: str
    excerpt: str
    source: str | None = None       # which local table or file it came from
    score: float | None = None

    @property
    def kind(self) -> str:
        return "knowledge"

    def render(self) -> str:
        return f"[{self.title}] {self.excerpt}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "document_id": self.document_id,
            "title": self.title,
            "excerpt": self.excerpt,
            "source": self.source,
            "score": self.score,
        }


@dataclass
class EvidenceBundle:
    """Everything given to the model for one question, and nothing else.

    The bundle is built before the model runs and is not modified afterwards,
    so an answer can always be audited against exactly what was available to it.
    """

    question: str
    observations: list[Observation] = field(default_factory=list)
    knowledge: list[KnowledgeExcerpt] = field(default_factory=list)
    snapshot_captured_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def bundle_id(self) -> str:
        """Content-addressed id, so identical evidence is identifiable as such."""
        payload = json.dumps(
            {
                "question": self.question,
                "observations": [o.to_dict() for o in self.observations],
                "knowledge": [k.to_dict() for k in self.knowledge],
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def has_session_evidence(self) -> bool:
        """True when at least one fact was actually read from the Live Set."""
        return any(o.value is not None for o in self.observations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "question": self.question,
            "observations": [o.to_dict() for o in self.observations],
            "knowledge": [k.to_dict() for k in self.knowledge],
            "snapshot_captured_at": (
                self.snapshot_captured_at.isoformat() if self.snapshot_captured_at else None
            ),
            "created_at": self.created_at.isoformat(),
            "has_session_evidence": self.has_session_evidence,
        }
