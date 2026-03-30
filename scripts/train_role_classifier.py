"""Train a rhetorical-role classifier on sentence-level legal labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datasets import Dataset, DatasetDict
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

from src.config import load_project_config
from src.data.loader import LegalDocumentLoader
from src.pipeline.summarization_pipeline import LegalSummarizationPipeline
from src.roles.labels import LEGAL_ROLE_LABELS


def build_examples(dataset_path: str, allow_weak_labels: bool) -> List[Dict[str, str]]:
    loader = LegalDocumentLoader()
    pipeline = LegalSummarizationPipeline()
    records = loader.load_dataset(dataset_path)

    examples: List[Dict[str, str]] = []
    for record in records:
        processed = pipeline.data_processor.process_document(record.document_text, document_id=record.document_id)
        if record.segment_labels and len(record.segment_labels) == len(processed.sentences):
            labels = record.segment_labels
        elif allow_weak_labels:
            weak_predictions = pipeline.role_classifier.predict_batch(processed.sentences)
            labels = [prediction.label for prediction in weak_predictions]
        else:
            continue

        for sentence, label in zip(processed.sentences, labels):
            examples.append({"text": sentence.text, "label": label})
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a sentence-level rhetorical role classifier.")
    parser.add_argument("--dataset-path", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--allow-weak-labels", action="store_true")
    args = parser.parse_args()

    config = load_project_config()
    model_name = args.model_name or config.model.roles.alternative_model
    output_dir = args.output_dir or config.model.training.output_dir

    examples = build_examples(args.dataset_path, allow_weak_labels=args.allow_weak_labels)
    if not examples:
        raise ValueError("No training examples were found. Provide segment labels or enable --allow-weak-labels.")

    label2id = {label: index for index, label in enumerate(LEGAL_ROLE_LABELS)}
    id2label = {index: label for label, index in label2id.items()}

    train_examples, eval_examples = train_test_split(examples, test_size=0.2, random_state=config.model.runtime.random_seed)
    dataset = DatasetDict(
        {
            "train": Dataset.from_list(train_examples),
            "validation": Dataset.from_list(eval_examples),
        }
    )

    tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=config.model.runtime.local_files_only)

    def tokenize(batch: Dict[str, List[str]]) -> Dict[str, List[int]]:
        tokens = tokenizer(batch["text"], truncation=True, padding=False, max_length=config.model.roles.max_length)
        tokens["labels"] = [label2id[label] for label in batch["label"]]
        return tokens

    tokenized = dataset.map(tokenize, batched=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(LEGAL_ROLE_LABELS),
        id2label=id2label,
        label2id=label2id,
        local_files_only=config.model.runtime.local_files_only,
    )

    training_args = TrainingArguments(
        output_dir=output_dir,
        learning_rate=config.model.training.learning_rate,
        per_device_train_batch_size=config.model.training.batch_size,
        per_device_eval_batch_size=config.model.training.batch_size,
        num_train_epochs=config.model.training.num_train_epochs,
        warmup_ratio=config.model.training.warmup_ratio,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to=[],
        save_total_limit=2,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
    )
    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    label_map_path = Path(output_dir) / "label_mapping.json"
    label_map_path.write_text(json.dumps({"label2id": label2id, "id2label": id2label}, indent=2), encoding="utf-8")
    print(f"Saved trained classifier to {output_dir}")


if __name__ == "__main__":
    main()
