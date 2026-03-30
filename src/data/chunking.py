"""Chunking helpers for long legal documents."""

from __future__ import annotations

from typing import Any, Dict, List

from src.utils import Segment, word_count


def chunk_segments(segments: List[Segment], max_words: int = 850, overlap_words: int = 120) -> List[Dict[str, Any]]:
    """Create overlapping chunks from sentence-level segments."""

    if not segments:
        return []

    chunks: List[Dict[str, Any]] = []
    current_segments: List[Segment] = []
    current_word_count = 0

    for segment in segments:
        segment_words = word_count(segment.text)
        if current_segments and current_word_count + segment_words > max_words:
            chunks.append(_finalize_chunk(chunks, current_segments))
            current_segments, current_word_count = _overlap_tail(current_segments, overlap_words)

        current_segments.append(segment)
        current_word_count += segment_words

    if current_segments:
        chunks.append(_finalize_chunk(chunks, current_segments))
    return chunks


def _finalize_chunk(existing_chunks: List[Dict[str, Any]], segments: List[Segment]) -> Dict[str, Any]:
    return {
        "chunk_id": f"chunk-{len(existing_chunks)}",
        "text": " ".join(segment.text for segment in segments).strip(),
        "segment_ids": [segment.segment_id for segment in segments],
        "start_char": segments[0].start_char,
        "end_char": segments[-1].end_char,
        "word_count": sum(word_count(segment.text) for segment in segments),
    }


def _overlap_tail(segments: List[Segment], overlap_words: int) -> tuple[List[Segment], int]:
    if overlap_words <= 0:
        return [], 0

    tail: List[Segment] = []
    total_words = 0
    for segment in reversed(segments):
        segment_words = word_count(segment.text)
        if tail and total_words + segment_words > overlap_words:
            break
        tail.insert(0, segment)
        total_words += segment_words
    return tail, total_words
