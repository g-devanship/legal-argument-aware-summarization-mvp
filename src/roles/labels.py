"""Canonical rhetorical role labels and prototype descriptions."""

from __future__ import annotations

LEGAL_ROLE_LABELS = [
    "facts",
    "issue",
    "arguments",
    "analysis",
    "ruling",
    "statute",
    "other",
]

LABEL_DESCRIPTIONS = {
    "facts": "factual background procedural history chronology evidence witness findings case background",
    "issue": "legal question issue before the court question presented disputed point determination needed",
    "arguments": "arguments submissions contentions parties petitioner respondent appellant appellee argued submitted",
    "analysis": "reasoning analysis discussion application interpretation why the court considered balanced",
    "ruling": "holding ruling disposition final order court held allowed dismissed affirmed reversed",
    "statute": "statute provision article section code act regulation precedent legal rule",
    "other": "administrative text neutral transition metadata judge names appearances heading",
}

LABEL_PRIORITY = {
    "facts": 0.14,
    "issue": 0.14,
    "arguments": 0.14,
    "analysis": 0.20,
    "ruling": 0.24,
    "statute": 0.10,
    "other": 0.04,
}
