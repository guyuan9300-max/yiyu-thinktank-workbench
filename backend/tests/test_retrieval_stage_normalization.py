"""Regression tests for retrieval-stage normalization.

The bug this guards against: the user asks a question, evidence is collected
into EvidenceItems where ``retrievalStage`` is legally Optional (None allowed),
but the downstream KnowledgeSearchHitRecord declares ``stage`` as a strict
Literal of four values. Passing ``stage=item.retrievalStage`` straight through
used to blow up at runtime with::

    1 validation error for KnowledgeSearchHitRecord
    stage
      Input should be 'master_index', 'surrogate', 'raw_chunk' or 'state_pool'
      [type=literal_error, input_value=None, input_type=NoneType]

These tests lock in two layers of defence:

1. ``normalize_retrieval_stage`` — centralised white-list helper used by every
   call site that builds ``EvidenceItem.retrievalStage`` / ``KnowledgeSearch
   HitRecord.stage`` from upstream data.
2. ``KnowledgeSearchHitRecord`` field validator — coerces any
   None/legacy/unknown stage to ``"raw_chunk"`` so future call sites that
   forget to call the helper still produce a valid record.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import (
    EvidenceItem,
    KnowledgeSearchHitRecord,
    RETRIEVAL_STAGE_VALUES,
    normalize_retrieval_stage,
)


class TestNormalizeRetrievalStage:
    def test_valid_values_pass_through(self) -> None:
        for stage in RETRIEVAL_STAGE_VALUES:
            assert normalize_retrieval_stage(stage) == stage

    def test_none_defaults_to_raw_chunk(self) -> None:
        assert normalize_retrieval_stage(None) == "raw_chunk"

    def test_empty_string_defaults_to_raw_chunk(self) -> None:
        assert normalize_retrieval_stage("") == "raw_chunk"

    def test_unknown_value_defaults_to_raw_chunk(self) -> None:
        # "doc_index" / "section_index" are display aliases used elsewhere but
        # not part of the underlying Literal — they must fall back, not leak.
        assert normalize_retrieval_stage("doc_index") == "raw_chunk"
        assert normalize_retrieval_stage("unknown_stage") == "raw_chunk"

    def test_state_pool_is_not_downgraded(self) -> None:
        # Regression: the old dict.get pattern only listed master_index and
        # surrogate, so state_pool silently became raw_chunk. The helper must
        # preserve it.
        assert normalize_retrieval_stage("state_pool") == "state_pool"

    def test_custom_default(self) -> None:
        assert normalize_retrieval_stage(None, default="master_index") == "master_index"


class TestKnowledgeSearchHitRecordStageValidator:
    def _hit(self, **overrides: object) -> KnowledgeSearchHitRecord:
        kwargs: dict[str, object] = {
            "title": "t",
            "excerpt": "x",
            "score": 0.5,
            "stage": "raw_chunk",
        }
        kwargs.update(overrides)
        return KnowledgeSearchHitRecord(**kwargs)  # type: ignore[arg-type]

    def test_accepts_each_valid_stage(self) -> None:
        for stage in RETRIEVAL_STAGE_VALUES:
            assert self._hit(stage=stage).stage == stage

    def test_coerces_none_to_raw_chunk(self) -> None:
        # Before fix this raised: literal_error for stage=None.
        assert self._hit(stage=None).stage == "raw_chunk"

    def test_coerces_unknown_string_to_raw_chunk(self) -> None:
        assert self._hit(stage="something_else").stage == "raw_chunk"

    def test_coerces_empty_string_to_raw_chunk(self) -> None:
        assert self._hit(stage="").stage == "raw_chunk"


class TestEvidenceItemRetrievalStageRemainsOptional:
    """EvidenceItem.retrievalStage stays Optional; only the downstream
    KnowledgeSearchHitRecord coerces. EvidenceItem is the source-of-truth
    record so we keep its semantics permissive."""

    def _evidence(self, **overrides: object) -> EvidenceItem:
        kwargs: dict[str, object] = {
            "id": "ev_1",
            "title": "t",
            "excerpt": "x",
            "sourceType": "knowledge_chunk",
        }
        kwargs.update(overrides)
        return EvidenceItem(**kwargs)  # type: ignore[arg-type]

    def test_none_retrieval_stage_is_kept(self) -> None:
        item = self._evidence(retrievalStage=None)
        assert item.retrievalStage is None

    def test_valid_state_pool_is_preserved(self) -> None:
        item = self._evidence(retrievalStage="state_pool")
        assert item.retrievalStage == "state_pool"

    def test_hit_constructed_from_evidence_with_none_stage_does_not_raise(self) -> None:
        # End-to-end regression for the original incident — building a hit
        # straight from an EvidenceItem whose retrievalStage is None must now
        # succeed (validator coerces to raw_chunk) instead of raising.
        evidence = self._evidence(retrievalStage=None)
        hit = KnowledgeSearchHitRecord(
            title=evidence.title,
            excerpt=evidence.excerpt,
            score=0.0,
            stage=evidence.retrievalStage,  # type: ignore[arg-type]
        )
        assert hit.stage == "raw_chunk"
