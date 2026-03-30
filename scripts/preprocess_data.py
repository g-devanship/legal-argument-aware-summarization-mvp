"""Preprocess a legal summarization dataset into segmented JSONL records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.loader import LegalDocumentLoader
from src.pipeline.summarization_pipeline import LegalSummarizationPipeline
from src.utils import to_serializable


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess legal documents into segmented JSONL records.")
    parser.add_argument("--input-path", required=True, help="Path to a CSV, JSON, or JSONL dataset.")
    parser.add_argument("--output-path", default="data/processed/preprocessed_dataset.jsonl")
    args = parser.parse_args()

    loader = LegalDocumentLoader()
    pipeline = LegalSummarizationPipeline()
    records = loader.load_dataset(args.input_path)

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            processed = pipeline.data_processor.process_document(record.document_text, document_id=record.document_id)
            payload = {
                "document_id": record.document_id,
                "gold_summary": record.gold_summary,
                "paragraphs": to_serializable(processed.paragraphs),
                "sentences": to_serializable(processed.sentences),
                "rhetorical_units": to_serializable(processed.rhetorical_units),
                "chunks": processed.chunks,
                "metadata": processed.metadata,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    print(f"Saved {len(records)} preprocessed records to {output_path}")


if __name__ == "__main__":
    main()
