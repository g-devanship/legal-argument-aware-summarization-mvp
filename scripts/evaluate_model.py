"""Evaluate generated summaries against gold summaries."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.loader import LegalDocumentLoader
from src.pipeline.summarization_pipeline import LegalSummarizationPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate summaries on a legal dataset.")
    parser.add_argument("--dataset-path", required=True, help="Path to CSV/JSON/JSONL dataset.")
    parser.add_argument("--output-path", default="data/processed/evaluation_metrics.json")
    args = parser.parse_args()

    loader = LegalDocumentLoader()
    pipeline = LegalSummarizationPipeline()
    records = loader.load_dataset(args.dataset_path)

    batch_results = []
    for record in records:
        result = pipeline.summarize_record(record)
        if result["evaluation"] is not None:
            batch_results.append(
                {
                    "document_id": record.document_id,
                    "generated_summary": result["best_summary"],
                    "gold_summary": record.gold_summary,
                    **result["evaluation"],
                }
            )

    pipeline.evaluator.export_metrics(batch_results, Path(args.output_path))
    print(f"Saved {len(batch_results)} evaluation rows to {args.output_path}")


if __name__ == "__main__":
    main()
