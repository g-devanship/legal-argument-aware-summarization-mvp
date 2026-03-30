from __future__ import annotations

from src.data.preprocessing import DataProcessor
from src.reranking.reranker import SummaryReranker
from src.roles.classifier import RoleClassifier
from src.summarization.candidates import build_candidate


def test_reranker_orders_candidates(test_config, sample_legal_text):
    processor = DataProcessor(test_config.model, test_config.app)
    classifier = RoleClassifier(test_config.model)
    reranker = SummaryReranker(test_config.scoring, test_config.model)

    processed = processor.process_document(sample_legal_text, document_id="demo")
    role_predictions = classifier.predict_batch(processed.rhetorical_units)
    candidates = [
        build_candidate(
            "cand-good",
            "The court held that cancellation without notice violated Article 14 and remanded the matter.",
            "manual",
            {},
            [],
        ),
        build_candidate(
            "cand-bad",
            "This is repetitive. This is repetitive. This is repetitive.",
            "manual",
            {},
            [],
        ),
    ]

    scores = reranker.score_candidates(
        document_text=processed.normalized_text,
        segments=processed.rhetorical_units,
        role_predictions=role_predictions,
        candidates=candidates,
        role_classifier=classifier,
    )

    assert scores[0].candidate_id == "cand-good"
    assert scores[0].final_score >= scores[1].final_score
