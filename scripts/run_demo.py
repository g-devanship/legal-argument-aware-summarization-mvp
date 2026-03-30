"""Run the legal summarization pipeline on bundled demo documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.summarization_pipeline import LegalSummarizationPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the demo summarization pipeline.")
    parser.add_argument(
        "--input-path",
        default="data/demo/indian_judgment_sample.txt",
        help="Path to a TXT or PDF legal document.",
    )
    parser.add_argument("--gold-summary", default=None, help="Optional gold summary for evaluation.")
    parser.add_argument("--output-path", default="data/processed/demo_result.json")
    args = parser.parse_args()

    pipeline = LegalSummarizationPipeline()
    result = pipeline.summarize_file(args.input_path, gold_summary=args.gold_summary)

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nBest Summary:\n")
    print(result["best_summary"])
    print(f"\nSaved full result to {output_path}")


if __name__ == "__main__":
    main()
