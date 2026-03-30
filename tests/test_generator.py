from __future__ import annotations

from src.data.preprocessing import DataProcessor
from src.roles.classifier import RoleClassifier
from src.summarization.generator import SummaryGenerator


def test_generate_multiple_candidates(test_config, sample_legal_text):
    processor = DataProcessor(test_config.model, test_config.app)
    classifier = RoleClassifier(test_config.model)
    generator = SummaryGenerator(test_config.model, test_config.app)

    processed = processor.process_document(sample_legal_text, document_id="demo")
    roles = classifier.predict_batch(processed.rhetorical_units)
    candidates = generator.generate_candidates(
        document_text=processed.normalized_text,
        segments=processed.rhetorical_units,
        role_predictions=roles,
        chunks=processed.chunks,
    )

    assert len(candidates) >= 4
    assert all(candidate.text for candidate in candidates)
    assert {candidate.generation_method for candidate in candidates}
