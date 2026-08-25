"""A guard against the model stating session facts that were never observed.

This is a heuristic, not a proof, and it is worth being exact about what it
does. It cannot tell whether an explanation is *correct*. It checks the
narrower and far more tractable property that every concrete quantity the
answer asserts also appears in the evidence the model was given.

That catches the specific failure Abel cares most about — a confident,
plausible, invented session value — while leaving genuine reasoning alone.
Numbers the answer merely repeats from the producer's own question are
permitted, as is ordinary prose counting ("one of the two ways").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from abel.evidence.provenance import EvidenceBundle

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")

# Small integers are pervasive in ordinary prose, and flagging them would
# produce noise rather than signal.
_PROSE_NUMBER_CEILING = 10


@dataclass(frozen=True)
class UnsupportedClaim:
    """A quantity asserted by the answer that no evidence supports."""

    value: str
    context: str

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value, "context": self.context}


@dataclass
class VerificationResult:
    """The outcome of checking one answer against one evidence bundle."""

    ok: bool
    unsupported: list[UnsupportedClaim] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.ok:
            return "Every quantity in this answer appears in its evidence."
        listed = ", ".join(claim.value for claim in self.unsupported)
        return f"Unverified quantities: {listed}"

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "unsupported": [c.to_dict() for c in self.unsupported],
        }


def _normalize(raw: str) -> str:
    """Reduce a number to a comparable form, ignoring separators and trailing zeros.

    ``48,000``, ``48000`` and ``48000.0`` are one observed value written three
    ways; the producer should not see a warning because the model picked a
    different one.
    """
    cleaned = raw.replace(",", "")
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".")
    return cleaned or "0"


def _numbers_in(text: str) -> set[str]:
    return {_normalize(m.group()) for m in _NUMBER.finditer(text)}


def _derived_forms(value: object) -> set[str]:
    """Conventional rewritings of an observed value that remain the same fact.

    48000 Hz is universally written "48 kHz" in the context this product
    operates in, so an answer that does so is quoting evidence, not inventing
    a figure.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return set()
    forms = {_normalize(str(value)), _normalize(f"{round(float(value), 2)}")}
    if value >= 1000:
        forms.add(_normalize(f"{value / 1000:.3f}"))
    return forms


def _supported_numbers(bundle: EvidenceBundle) -> set[str]:
    """Every number the model was legitimately shown."""
    supported: set[str] = set()
    for observation in bundle.observations:
        supported |= _numbers_in(observation.render())
        supported |= _derived_forms(observation.value)
    for excerpt in bundle.knowledge:
        supported |= _numbers_in(f"{excerpt.title} {excerpt.excerpt}")
    supported |= _numbers_in(bundle.question)
    return supported


def verify(answer: str, bundle: EvidenceBundle) -> VerificationResult:
    """Check that ``answer`` asserts no quantity absent from ``bundle``."""
    supported = _supported_numbers(bundle)
    unsupported: list[UnsupportedClaim] = []
    seen: set[str] = set()

    for match in _NUMBER.finditer(answer):
        value = _normalize(match.group())
        if value in supported or value in seen:
            continue
        try:
            if float(value) <= _PROSE_NUMBER_CEILING:
                continue
        except ValueError:
            continue
        seen.add(value)
        start = max(0, match.start() - 40)
        end = min(len(answer), match.end() + 40)
        unsupported.append(
            UnsupportedClaim(value=match.group(), context=answer[start:end].strip())
        )

    return VerificationResult(ok=not unsupported, unsupported=unsupported)
