"""Heuristic fallback role prediction for legal segments."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Tuple

from src.roles.labels import LEGAL_ROLE_LABELS
from src.utils import RolePrediction, clamp, normalize_scores


ROLE_PATTERNS: Dict[str, List[str]] = {
    "facts": [
        r"\bfacts?\b",
        r"\bbackground\b",
        r"\bthe plaintiff alleged\b",
        r"\bon\s+\d{1,2}\s+\w+\s+\d{4}\b",
        r"\bprocedural history\b",
    ],
    "issue": [
        r"\bissue[s]?\b",
        r"\bquestion before (?:the )?court\b",
        r"\bwhether\b",
        r"\bpoint for determination\b",
    ],
    "arguments": [
        r"\bargued\b",
        r"\bcontended\b",
        r"\bsubmitted\b",
        r"\baccording to the (?:petitioner|respondent|appellant|appellee)\b",
        r"\bcounsel\b",
    ],
    "analysis": [
        r"\bwe find\b",
        r"\bthe court considers\b",
        r"\bthe court observed\b",
        r"\bthe court reasoned\b",
        r"\breasoned that\b",
        r"\bbecause\b",
        r"\btherefore\b",
        r"\bin view of\b",
        r"\breasoning\b",
    ],
    "ruling": [
        r"\bheld\b",
        r"\bordered\b",
        r"\bset aside\b",
        r"\bremanded\b",
        r"\bthe appeal is\b",
        r"\bpetition is\b",
        r"\baffirmed\b",
        r"\breversed\b",
        r"\bdismissed\b",
        r"\ballowed\b",
    ],
    "statute": [
        r"\bsection\s+\d+\b",
        r"\barticle\s+\d+\b",
        r"\bact\b",
        r"\bcode\b",
        r"\brule\b",
        r"\bconstitution\b",
    ],
}


class HeuristicRoleLabeler:
    """Assign legal rhetorical roles using cue phrases and regex rules."""

    def score(self, text: str) -> Tuple[Dict[str, float], List[str]]:
        lowered = text.lower()
        scores = defaultdict(float)
        rationale: List[str] = []

        leading_header = re.match(
            r"(?is)^\s*(facts|background|issue|issues|arguments|analysis|discussion|holding|ruling|judgment|statute|order|conclusion)\s*:",
            text,
        )
        if leading_header:
            header_label = leading_header.group(1).lower()
            if header_label == "background":
                header_label = "facts"
            elif header_label in {"discussion", "holding", "judgment", "order", "conclusion"}:
                header_label = "analysis" if header_label == "discussion" else "ruling"
            elif header_label == "issues":
                header_label = "issue"
            scores[header_label] += 2.5
            rationale.append(f"Detected leading section header: {leading_header.group(1)}")

        for label, patterns in ROLE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lowered, flags=re.I):
                    scores[label] += 1.0
                    rationale.append(f"Matched {label} cue: {pattern}")

        if text.strip().endswith(":") and lowered.rstrip(":") in {"facts", "issue", "analysis", "ruling"}:
            label = lowered.rstrip(":")
            scores[label] += 1.5
            rationale.append(f"Detected section header: {text.strip()}")

        if not scores:
            scores["other"] = 1.0
            rationale.append("No strong legal cue phrases matched; defaulted to 'other'.")
        else:
            scores["other"] += 0.1

        normalized = normalize_scores({label: scores.get(label, 0.0) for label in LEGAL_ROLE_LABELS})
        return normalized, rationale

    def predict(self, segment_id: str, text: str, top_k: int = 3) -> RolePrediction:
        scores, rationale = self.score(text)
        sorted_items = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        label, confidence = sorted_items[0]
        probabilities = dict(sorted_items[:top_k])
        return RolePrediction(
            segment_id=segment_id,
            label=label,
            confidence=clamp(confidence),
            probabilities=probabilities,
            rationale=rationale[:3],
        )
