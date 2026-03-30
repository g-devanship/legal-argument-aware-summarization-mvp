"""End-to-end legal summarization pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.config import ProjectConfig, load_project_config
from src.data.loader import LegalDocumentLoader
from src.data.preprocessing import DataProcessor
from src.evaluation.evaluator import Evaluator
from src.logger import get_logger
from src.reranking.reranker import SummaryReranker
from src.roles.classifier import RoleClassifier
from src.summarization.generator import SummaryGenerator
from src.utils import DocumentRecord, to_serializable

LOGGER = get_logger(__name__)


class LegalSummarizationPipeline:
    """Orchestrates preprocessing, role prediction, generation, reranking, and evaluation."""

    def __init__(self, config: Optional[ProjectConfig] = None) -> None:
        self.config = config or load_project_config()
        self.loader = LegalDocumentLoader()
        self.data_processor = DataProcessor(self.config.model, self.config.app)
        self.role_classifier = RoleClassifier(self.config.model)
        self.summary_generator = SummaryGenerator(self.config.model, self.config.app)
        self.reranker = SummaryReranker(self.config.scoring, self.config.model)
        self.evaluator = Evaluator()

    def summarize_text(
        self,
        text: str,
        document_id: str = "document",
        gold_summary: Optional[str] = None,
        progress_callback: Optional[Callable[[str, str, dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        processed = self.data_processor.process_document(
            text,
            document_id=document_id,
            progress_callback=progress_callback,
        )
        self._emit_progress(
            progress_callback,
            "role_prediction",
            "running",
            "Loading the role classifier backend if needed and predicting rhetorical roles.",
        )
        role_predictions = self.role_classifier.predict_batch(processed.rhetorical_units)
        self._emit_progress(
            progress_callback,
            "role_prediction",
            "completed",
            f"Assigned rhetorical roles to {len(role_predictions)} units.",
            prediction_count=len(role_predictions),
            backend=self.role_classifier.backend,
        )

        self._emit_progress(
            progress_callback,
            "candidate_generation",
            "running",
            "Loading the summarization backend if needed and generating summary candidates.",
        )
        candidates = self.summary_generator.generate_candidates(
            document_text=processed.normalized_text,
            segments=processed.rhetorical_units,
            role_predictions=role_predictions,
            chunks=processed.chunks,
        )
        self._emit_progress(
            progress_callback,
            "candidate_generation",
            "completed",
            f"Generated {len(candidates)} candidate summaries.",
            candidate_count=len(candidates),
            backend=self.summary_generator.backend,
        )

        self._emit_progress(
            progress_callback,
            "reranking",
            "running",
            "Loading the reranker backend if needed and scoring summary candidates.",
        )
        scores = self.reranker.score_candidates(
            document_text=processed.normalized_text,
            segments=processed.rhetorical_units,
            role_predictions=role_predictions,
            candidates=candidates,
            role_classifier=self.role_classifier,
        )
        self._emit_progress(
            progress_callback,
            "reranking",
            "completed",
            f"Reranked {len(scores)} candidate summaries.",
            scored_candidate_count=len(scores),
            backend=self.reranker.backend,
        )

        best_candidate = (
            next((candidate for candidate in candidates if candidate.candidate_id == scores[0].candidate_id), None)
            if scores
            else None
        )
        if best_candidate and gold_summary:
            self._emit_progress(
                progress_callback,
                "evaluation",
                "running",
                "Evaluating the selected summary against the supplied gold summary.",
            )
            evaluation = self.evaluator.evaluate_summary(best_candidate.text, gold_summary)
            self._emit_progress(
                progress_callback,
                "evaluation",
                "completed",
                "Computed automatic evaluation metrics.",
            )
        else:
            evaluation = None
            self._emit_progress(
                progress_callback,
                "evaluation",
                "skipped",
                "Evaluation skipped because no gold summary was provided.",
            )
        qualitative = self.evaluator.qualitative_analysis(processed.rhetorical_units, role_predictions, candidates, scores)

        return {
            "document_id": document_id,
            "document_metadata": processed.metadata,
            "runtime_info": {
                "role_backend": self.role_classifier.backend,
                "summarization_backend": self.summary_generator.backend,
                "reranker_backend": self.reranker.backend,
                "device": self.config.model.runtime.device,
                "heuristics_only": self.config.model.runtime.use_heuristics_only,
            },
            "segmented_text": {
                "paragraphs": to_serializable(processed.paragraphs),
                "sentences": to_serializable(processed.sentences),
                "rhetorical_units": to_serializable(processed.rhetorical_units),
                "chunks": processed.chunks,
            },
            "predicted_roles": to_serializable(role_predictions),
            "generated_summary_candidates": to_serializable(candidates),
            "reranking_scores": to_serializable(scores),
            "best_summary": best_candidate.text if best_candidate else "",
            "best_candidate_id": best_candidate.candidate_id if best_candidate else None,
            "evaluation": to_serializable(evaluation) if evaluation else None,
            "qualitative_analysis": qualitative,
        }

    def summarize_record(self, record: DocumentRecord) -> Dict[str, Any]:
        return self.summarize_text(record.document_text, document_id=record.document_id, gold_summary=record.gold_summary)

    def summarize_file(self, path: str | Path, gold_summary: Optional[str] = None) -> Dict[str, Any]:
        path = Path(path)
        if path.suffix.lower() == ".pdf":
            record = self.loader.load_pdf_file(path)
        else:
            record = self.loader.load_text_file(path)
        if gold_summary:
            record.gold_summary = gold_summary
        return self.summarize_record(record)

    def _emit_progress(
        self,
        progress_callback: Optional[Callable[[str, str, dict[str, Any]], None]],
        stage: str,
        state: str,
        message: str,
        **payload: Any,
    ) -> None:
        if progress_callback is None:
            return
        progress_callback(stage, state, {"message": message, **payload})
