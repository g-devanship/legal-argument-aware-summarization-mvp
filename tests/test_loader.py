from __future__ import annotations

import json

from src.data.loader import LegalDocumentLoader


def test_load_text_file(tmp_path):
    sample_path = tmp_path / "opinion.txt"
    sample_path.write_text("Facts: Sample text.", encoding="utf-8")

    loader = LegalDocumentLoader()
    record = loader.load_text_file(sample_path)

    assert record.document_id == "opinion"
    assert "Facts" in record.document_text


def test_load_dataset_json_and_csv(tmp_path):
    payload = [
        {
            "document_id": "doc-1",
            "document_text": "Facts: Example legal text.",
            "gold_summary": "Example summary.",
        }
    ]
    json_path = tmp_path / "dataset.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    csv_path = tmp_path / "dataset.csv"
    csv_path.write_text(
        "document_id,document_text,gold_summary\n"
        '"doc-1","Facts: Example legal text.","Example summary."\n',
        encoding="utf-8",
    )

    loader = LegalDocumentLoader()
    json_records = loader.load_dataset(json_path)
    csv_records = loader.load_dataset(csv_path)

    assert len(json_records) == 1
    assert len(csv_records) == 1
    assert json_records[0].gold_summary == "Example summary."
    assert csv_records[0].document_id == "doc-1"
