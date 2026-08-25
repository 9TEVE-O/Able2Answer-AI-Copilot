"""Tests for the evidence layer: what Abel observed, what it knows, and the
boundary between them.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from abel.evidence.observe import observe
from abel.evidence.provenance import EvidenceBundle, KnowledgeExcerpt, Observation
from abel.evidence.verifier import verify
from abel.live.bridge import parse_snapshot
from abel.live.store import SnapshotStore

FIXTURE = Path(__file__).parent / "fixtures" / "bridge_payload.json"
NOW = datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc)


@pytest.fixture
def snapshot():
    return parse_snapshot(json.loads(FIXTURE.read_text()))


def _observation(key="audio.sample_rate_hz", label="Sample rate", value=48000, unit="Hz"):
    return Observation(key=key, label=label, value=value, unit=unit, captured_at=NOW)


class TestObservationRendering:
    def test_renders_value_with_unit(self):
        assert _observation().render() == "Sample rate: 48000 Hz"

    def test_unread_value_is_reported_as_unknown_not_omitted(self):
        # The producer must be able to see that Abel could not read this.
        assert _observation(value=None).render() == "Sample rate: not reported by Live"


class TestObservationSelection:
    """Selection picks from the snapshot; it never invents."""

    def test_audio_question_selects_audio_observations(self, snapshot):
        keys = {o.key for o in observe(snapshot, "What sample rate am I working at?")}
        assert "audio.sample_rate_hz" in keys

    def test_cpu_question_selects_device_and_track_load(self, snapshot):
        keys = {o.key for o in observe(snapshot, "Why is my CPU so high?")}
        assert "set.active_device_count" in keys
        assert "set.track_count" in keys

    def test_cpu_question_names_the_heaviest_tracks(self, snapshot):
        labels = [o.label for o in observe(snapshot, "Why is my CPU spiking?")]
        assert any("Bass" in label for label in labels)

    def test_unmatched_question_still_gets_orienting_facts(self, snapshot):
        keys = {o.key for o in observe(snapshot, "Any thoughts on this one?")}
        assert "audio.sample_rate_hz" in keys
        assert "set.tempo_bpm" in keys

    def test_every_observed_value_comes_from_the_snapshot(self, snapshot):
        for obs in observe(snapshot, "sample rate tempo tracks devices selected"):
            if obs.key == "audio.sample_rate_hz":
                assert obs.value == snapshot.audio.sample_rate_hz
            if obs.key == "set.tempo_bpm":
                assert obs.value == snapshot.live_set.tempo_bpm
            if obs.key == "set.active_device_count":
                assert obs.value == snapshot.active_device_count

    def test_unread_sample_rate_is_still_selected_as_unknown(self, snapshot):
        payload = json.loads(FIXTURE.read_text())
        payload["audio"]["sample_rate"] = None
        blind = parse_snapshot(payload)
        observations = observe(blind, "What sample rate am I working at?")
        sample_rate = next(o for o in observations if o.key == "audio.sample_rate_hz")
        # Reported as unknown rather than dropped: silence would read as "fine".
        assert sample_rate.value is None


class TestEvidenceBundle:
    def test_bundle_id_is_content_addressed(self):
        first = EvidenceBundle(question="q", observations=[_observation()])
        second = EvidenceBundle(question="q", observations=[_observation()])
        assert first.bundle_id == second.bundle_id

    def test_different_evidence_gives_a_different_id(self):
        first = EvidenceBundle(question="q", observations=[_observation()])
        second = EvidenceBundle(question="q", observations=[_observation(value=44100)])
        assert first.bundle_id != second.bundle_id

    def test_knowledge_alone_is_not_session_evidence(self):
        bundle = EvidenceBundle(
            question="What is a sample rate?",
            knowledge=[KnowledgeExcerpt(document_id="sr", title="Sample rate", excerpt="...")],
        )
        # Abel knows something, but it has observed nothing about *this* session.
        assert bundle.has_session_evidence is False

    def test_unread_observations_are_not_session_evidence(self):
        bundle = EvidenceBundle(question="q", observations=[_observation(value=None)])
        assert bundle.has_session_evidence is False

    def test_a_real_reading_is_session_evidence(self):
        bundle = EvidenceBundle(question="q", observations=[_observation()])
        assert bundle.has_session_evidence is True

    def test_serialised_evidence_keeps_its_kind(self):
        bundle = EvidenceBundle(
            question="q",
            observations=[_observation()],
            knowledge=[KnowledgeExcerpt(document_id="d", title="T", excerpt="E")],
        )
        data = bundle.to_dict()
        # The UI must be able to label the two apart without guessing.
        assert data["observations"][0]["kind"] == "observation"
        assert data["knowledge"][0]["kind"] == "knowledge"


class TestVerifier:
    """The guard against invented session values."""

    @pytest.fixture
    def bundle(self):
        return EvidenceBundle(
            question="What sample rate am I working at?",
            observations=[_observation(), _observation("set.track_count", "Tracks", 24, None)],
        )

    def test_answer_quoting_evidence_passes(self, bundle):
        result = verify("You are working at 48000 Hz across 24 tracks.", bundle)
        assert result.ok

    def test_conventional_khz_form_is_still_the_observed_value(self, bundle):
        # 48000 Hz written as "48 kHz" is quoting evidence, not inventing.
        assert verify("Your session runs at 48 kHz.", bundle).ok

    def test_thousands_separator_is_the_same_number(self, bundle):
        assert verify("Your session runs at 48,000 Hz.", bundle).ok

    def test_invented_session_value_is_caught(self, bundle):
        result = verify("Your session is running at 96000 Hz.", bundle)
        assert not result.ok
        assert result.unsupported[0].value == "96000"

    def test_unsupported_claim_carries_its_context(self, bundle):
        result = verify("You have 512 samples of buffer.", bundle)
        assert "512" in result.summary
        assert "buffer" in result.unsupported[0].context

    def test_small_numbers_in_prose_are_not_flagged(self, bundle):
        assert verify("There are 2 ways to reduce this.", bundle).ok

    def test_numbers_from_the_question_are_allowed(self):
        bundle = EvidenceBundle(question="Should I switch to 96000 Hz?")
        assert verify("Moving to 96000 Hz would double the load.", bundle).ok

    def test_numbers_from_knowledge_are_allowed(self):
        bundle = EvidenceBundle(
            question="What is CD quality?",
            knowledge=[
                KnowledgeExcerpt(
                    document_id="cd", title="CD audio", excerpt="CD audio is 44100 Hz, 16-bit."
                )
            ],
        )
        assert verify("CD audio is 44100 Hz.", bundle).ok

    def test_each_unsupported_value_is_reported_once(self, bundle):
        result = verify("It is 96000 Hz. Really, 96000 Hz.", bundle)
        assert len(result.unsupported) == 1


class TestSnapshotStore:
    """A stale observation must never be presented as the current session."""

    def test_fresh_snapshot_is_returned(self, snapshot):
        store = SnapshotStore()
        store.put(snapshot)
        assert store.get() is snapshot

    def test_stale_snapshot_is_withheld(self, snapshot):
        store = SnapshotStore(max_age=timedelta(seconds=30))
        old = parse_snapshot(
            {**json.loads(FIXTURE.read_text()), "captured_at": "2020-01-01T00:00:00Z"}
        )
        store.put(old)
        assert store.get() is None

    def test_stale_snapshot_is_still_visible_for_connection_state(self, snapshot):
        # The UI needs to say "last seen 4 minutes ago", which needs the stale one.
        store = SnapshotStore(max_age=timedelta(seconds=0))
        store.put(snapshot)
        assert store.get() is None
        assert store.get_even_if_stale() is snapshot

    def test_empty_store_reports_nothing(self):
        assert SnapshotStore().get() is None

    def test_clear_forgets_the_session(self, snapshot):
        store = SnapshotStore()
        store.put(snapshot)
        store.clear()
        assert store.get() is None
