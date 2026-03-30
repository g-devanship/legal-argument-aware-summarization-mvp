"""Shared data structures and utility helpers."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def repair_text_artifacts(text: str) -> str:
    replacements = {
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€": '"',
        "â€“": "-",
        "â€”": "-",
        "Â": "",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def softmax(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    array = np.array(values, dtype=float)
    shifted = array - np.max(array)
    exps = np.exp(shifted)
    probs = exps / exps.sum()
    return probs.tolist()


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    if not a_arr.any() or not b_arr.any():
        return 0.0
    denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if denom == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / denom)


def split_sentences(text: str) -> List[str]:
    """A lightweight sentence splitter with a legal-domain friendly fallback."""

    try:
        import nltk

        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            raise LookupError("punkt tokenizer not available locally")
        return [segment.strip() for segment in nltk.sent_tokenize(text) if segment.strip()]
    except Exception:
        pattern = r"(?<=[.!?])\s+(?=(?:[A-Z(]|In |The |It |Section |Article ))"
        return [segment.strip() for segment in re.split(pattern, text) if segment.strip()]


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def rolling_ngrams(tokens: Sequence[str], size: int) -> List[tuple[str, ...]]:
    if size <= 0 or len(tokens) < size:
        return []
    return [tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)]


def extract_legal_references(text: str) -> List[str]:
    patterns = [
        r"\bSection\s+\d+[A-Za-z-]*",
        r"\bArticle\s+\d+[A-Za-z-]*",
        r"\b\d+\s+U\.S\.\s+\d+\b",
        r"\bAIR\s+\d{4}\s+[A-Z]+\s+\d+\b",
        r"\b\[\d{4}\]\s+\d+\s+[A-Z. ]+\s+\d+\b",
    ]
    references: List[str] = []
    for pattern in patterns:
        references.extend(re.findall(pattern, text))
    return sorted(set(references))


def extract_numbers(text: str) -> List[str]:
    return re.findall(r"\b\d+(?:\.\d+)?\b", text)


def extract_named_chunks(text: str) -> List[str]:
    candidates = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text)
    return [candidate for candidate in candidates if len(candidate.split()) <= 4]


def to_serializable(payload: Any) -> Any:
    if is_dataclass(payload):
        return {key: to_serializable(value) for key, value in asdict(payload).items()}
    if isinstance(payload, dict):
        return {key: to_serializable(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [to_serializable(value) for value in payload]
    if isinstance(payload, np.generic):
        return payload.item()
    return payload


def dump_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(to_serializable(payload), handle, indent=2, ensure_ascii=False)


def normalize_scores(score_map: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(value, 0.0) for value in score_map.values())
    if total == 0:
        uniform = 1.0 / max(len(score_map), 1)
        return {key: uniform for key in score_map}
    return {key: max(value, 0.0) / total for key, value in score_map.items()}


@dataclass
class DocumentRecord:
    document_id: str
    document_text: str
    gold_summary: Optional[str] = None
    segment_labels: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Segment:
    segment_id: str
    text: str
    level: str
    start_char: int
    end_char: int
    paragraph_index: int
    sentence_index: Optional[int] = None
    rhetorical_unit_index: Optional[int] = None
    original_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RolePrediction:
    segment_id: str
    label: str
    confidence: float
    probabilities: Dict[str, float]
    rationale: List[str] = field(default_factory=list)


@dataclass
class SummaryCandidate:
    candidate_id: str
    text: str
    generation_method: str
    decoding_parameters: Dict[str, Any]
    source_chunks: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateScore:
    candidate_id: str
    semantic_similarity: float
    role_coverage: float
    factual_proxy: float
    redundancy_penalty: float
    length_penalty: float
    readability_bonus: float
    final_score: float
    reasoning: List[str]
    supporting_segments: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EvaluationMetrics:
    rouge_1: float
    rouge_2: float
    rouge_l: float
    bertscore_precision: Optional[float]
    bertscore_recall: Optional[float]
    bertscore_f1: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessedDocument:
    document_id: str
    original_text: str
    normalized_text: str
    paragraphs: List[Segment]
    sentences: List[Segment]
    rhetorical_units: List[Segment]
    chunks: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


def compute_distribution(labels: Iterable[str]) -> Dict[str, float]:
    counts = Counter(labels)
    total = sum(counts.values()) or 1
    return {label: count / total for label, count in counts.items()}


def safe_mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def unique_preserve_order(values: Sequence[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def strip_role_prefix(text: str) -> str:
    cleaned = repair_text_artifacts(text).strip()
    cleaned = re.sub(
        r"(?im)^\s*(facts|background|issue|issues|arguments|analysis|discussion|holding|ruling|judgment|statute|order|conclusion)\s*:\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(r"^\[[A-Za-z_]+\]\s*", "", cleaned)
    return normalize_whitespace(cleaned)
