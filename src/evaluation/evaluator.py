"""Automatic evaluation and qualitative analysis helpers."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from src.logger import get_logger
from src.utils import CandidateScore, EvaluationMetrics, RolePrediction, Segment, SummaryCandidate, dump_json, to_serializable

LOGGER = get_logger(__name__)


class Evaluator:
    """Compute automatic metrics and qualitative summaries."""

    def evaluate_summary(self, generated_summary: str, gold_summary: str) -> EvaluationMetrics:
        rouge_scores = self._rouge(generated_summary, gold_summary)
        bert_scores = self._bertscore(generated_summary, gold_summary)
        return EvaluationMetrics(
            rouge_1=rouge_scores["rouge1"],
            rouge_2=rouge_scores["rouge2"],
            rouge_l=rouge_scores["rougeL"],
            bertscore_precision=bert_scores.get("precision"),
            bertscore_recall=bert_scores.get("recall"),
            bertscore_f1=bert_scores.get("f1"),
            metadata={"rouge_backend": rouge_scores["backend"], "bertscore_backend": bert_scores.get("backend")},
        )

    def evaluate_batch(self, records: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for record in records:
            metrics = self.evaluate_summary(record["generated_summary"], record["gold_summary"])
            results.append({"document_id": record.get("document_id"), **to_serializable(metrics)})
        return results

    def export_metrics(self, metrics: List[Dict[str, Any]], output_path: str | Path) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            dump_json(path, metrics)
        elif path.suffix.lower() == ".csv":
            fieldnames = sorted({key for row in metrics for key in row.keys()})
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(metrics)
        else:
            raise ValueError("Metrics export path must end with .json or .csv")

    def qualitative_analysis(
        self,
        segments: List[Segment],
        role_predictions: List[RolePrediction],
        candidates: List[SummaryCandidate],
        scores: List[CandidateScore],
    ) -> Dict[str, Any]:
        role_distribution: Dict[str, int] = {}
        for prediction in role_predictions:
            role_distribution[prediction.label] = role_distribution.get(prediction.label, 0) + 1

        score_map = {score.candidate_id: score for score in scores}
        candidate_table = [
            {
                "candidate_id": candidate.candidate_id,
                "generation_method": candidate.generation_method,
                "length_words": len(candidate.text.split()),
                "final_score": score_map[candidate.candidate_id].final_score if candidate.candidate_id in score_map else None,
            }
            for candidate in candidates
        ]

        key_segments = scores[0].supporting_segments if scores else []
        return {
            "key_legal_segments": key_segments,
            "role_distribution": role_distribution,
            "candidate_comparison": candidate_table,
            "selection_explanation": scores[0].reasoning if scores else [],
        }

    def _rouge(self, generated_summary: str, gold_summary: str) -> Dict[str, Any]:
        try:
            from rouge_score import rouge_scorer

            scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
            scores = scorer.score(gold_summary, generated_summary)
            return {
                "rouge1": scores["rouge1"].fmeasure,
                "rouge2": scores["rouge2"].fmeasure,
                "rougeL": scores["rougeL"].fmeasure,
                "backend": "rouge_score",
            }
        except Exception as error:
            LOGGER.warning("ROUGE computation failed; using overlap fallback: %s", error)
            fallback = self._overlap_f1(generated_summary, gold_summary)
            return {"rouge1": fallback, "rouge2": fallback / 2, "rougeL": fallback, "backend": "token_overlap_fallback"}

    def _bertscore(self, generated_summary: str, gold_summary: str) -> Dict[str, Any]:
        try:
            from bert_score import score

            precision, recall, f1 = score([generated_summary], [gold_summary], lang="en", verbose=False)
            return {
                "precision": float(precision.mean().item()),
                "recall": float(recall.mean().item()),
                "f1": float(f1.mean().item()),
                "backend": "bert_score",
            }
        except Exception as error:
            LOGGER.warning("BERTScore unavailable; returning nulls: %s", error)
            return {"precision": None, "recall": None, "f1": None, "backend": "unavailable"}

    def _overlap_f1(self, generated_summary: str, gold_summary: str) -> float:
        generated_tokens = set(generated_summary.lower().split())
        gold_tokens = set(gold_summary.lower().split())
        overlap = len(generated_tokens & gold_tokens)
        if not generated_tokens or not gold_tokens:
            return 0.0
        precision = overlap / len(generated_tokens)
        recall = overlap / len(gold_tokens)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)
