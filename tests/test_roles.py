from __future__ import annotations

from src.roles.classifier import RoleClassifier


def test_role_classifier_heuristic_predictions(test_config):
    classifier = RoleClassifier(test_config.model)
    predictions = classifier.predict_batch(
        [
            "The issue before the court was whether the allotment could be cancelled without notice.",
            "The court held that the cancellation order was invalid and remanded the matter.",
            "Section 21 of the General Clauses Act was considered by the bench.",
        ]
    )

    labels = [prediction.label for prediction in predictions]
    assert labels[0] in {"issue", "analysis"}
    assert labels[1] == "ruling"
    assert labels[2] == "statute"
