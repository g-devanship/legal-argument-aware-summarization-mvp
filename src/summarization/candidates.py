"""Candidate-building helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from src.utils import SummaryCandidate


def build_candidate(
    candidate_id: str,
    text: str,
    generation_method: str,
    decoding_parameters: Dict[str, Any],
    source_chunks: List[str],
    metadata: Dict[str, Any] | None = None,
) -> SummaryCandidate:
    return SummaryCandidate(
        candidate_id=candidate_id,
        text=text.strip(),
        generation_method=generation_method,
        decoding_parameters=decoding_parameters,
        source_chunks=source_chunks,
        metadata=metadata or {},
    )
