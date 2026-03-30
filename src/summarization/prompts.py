"""Input construction helpers for role-aware summarization."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from src.utils import RolePrediction, Segment, unique_preserve_order


def build_role_grouped_context(segments: Iterable[Segment], role_predictions: Dict[str, RolePrediction]) -> Dict[str, List[Segment]]:
    grouped: Dict[str, List[Segment]] = defaultdict(list)
    for segment in segments:
        role = role_predictions.get(segment.segment_id)
        grouped[role.label if role else "other"].append(segment)
    return grouped


def compose_role_aware_source(
    segments: List[Segment],
    role_predictions: Dict[str, RolePrediction],
    priority_roles: List[str],
    max_segments: int = 18,
) -> tuple[str, List[str]]:
    grouped = build_role_grouped_context(segments, role_predictions)
    selected_segments: List[Segment] = []

    for role in priority_roles:
        quota = max(2, max_segments // max(len(priority_roles), 1))
        selected_segments.extend(grouped.get(role, [])[:quota])

    if len(selected_segments) < max_segments:
        selected_ids = {item.segment_id for item in selected_segments}
        remaining = [segment for segment in segments if segment.segment_id not in selected_ids]
        selected_segments.extend(remaining[: max_segments - len(selected_segments)])

    selected_segments = selected_segments[:max_segments]
    used_ids = unique_preserve_order([segment.segment_id for segment in selected_segments])
    text = "\n".join(
        f"[{role_predictions.get(segment.segment_id).label if role_predictions.get(segment.segment_id) else 'other'}] {segment.text}"
        for segment in selected_segments
    )
    return text, used_ids
