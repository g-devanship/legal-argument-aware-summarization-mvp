from __future__ import annotations

from src.data.preprocessing import DataProcessor


def test_preprocessing_segments_and_chunks(test_config, sample_legal_text):
    processor = DataProcessor(test_config.model, test_config.app)
    processed = processor.process_document(sample_legal_text, document_id="demo")

    assert processed.document_id == "demo"
    assert len(processed.paragraphs) >= 1
    assert len(processed.sentences) >= 5
    assert len(processed.rhetorical_units) >= len(processed.sentences)
    assert len(processed.chunks) >= 1
    assert processed.chunks[0]["segment_ids"]
