"""Pydantic schemas for the FastAPI application."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class UploadPdfResponse(BaseModel):
    text: str
    metadata: Dict[str, Any]


class SummarizeRequest(BaseModel):
    document_text: str = Field(..., min_length=20)
    document_id: str = "document"
    gold_summary: Optional[str] = None


class EvaluateRequest(BaseModel):
    generated_summary: Optional[str] = None
    gold_summary: Optional[str] = None
    document_text: Optional[str] = None
    document_id: str = "document"

    @model_validator(mode="after")
    def validate_payload(self) -> "EvaluateRequest":
        if self.generated_summary and self.gold_summary:
            return self
        if self.document_text and self.gold_summary:
            return self
        raise ValueError("Provide either generated_summary + gold_summary, or document_text + gold_summary.")


class CandidateScoreResponse(BaseModel):
    candidate_id: str
    semantic_similarity: float
    role_coverage: float
    factual_proxy: float
    redundancy_penalty: float
    length_penalty: float
    readability_bonus: float
    final_score: float
    reasoning: List[str]
    supporting_segments: List[Dict[str, Any]]


class SummarizeResponse(BaseModel):
    document_id: str
    document_metadata: Dict[str, Any]
    runtime_info: Dict[str, Any]
    segmented_text: Dict[str, Any]
    predicted_roles: List[Dict[str, Any]]
    generated_summary_candidates: List[Dict[str, Any]]
    reranking_scores: List[CandidateScoreResponse]
    best_summary: str
    best_candidate_id: Optional[str]
    evaluation: Optional[Dict[str, Any]]
    qualitative_analysis: Dict[str, Any]


class EvaluateResponse(BaseModel):
    evaluation: Dict[str, Any]
    best_summary: Optional[str] = None
