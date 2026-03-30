"""Configuration loading helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field


class RuntimeConfig(BaseModel):
    device: str = "cpu"
    local_files_only: bool = False
    load_models: bool = True
    use_heuristics_only: bool = False
    random_seed: int = 42


class SummarizationConfig(BaseModel):
    preferred_model: str = "allenai/led-base-16384"
    fallback_model: str = "facebook/bart-large-cnn"
    lightweight_model: str = "google/flan-t5-base"
    encoder_max_input_tokens: int = 4096
    chunk_max_words: int = 850
    chunk_overlap_words: int = 120
    min_summary_tokens: int = 80
    max_summary_tokens: int = 220
    candidate_count: int = 5


class RoleModelConfig(BaseModel):
    preferred_model: str = "law-ai/InLegalBERT"
    alternative_model: str = "nlpaueb/legal-bert-base-uncased"
    lightweight_model: str = "distilbert-base-uncased"
    fine_tuned_checkpoint: Optional[str] = None
    max_length: int = 256
    top_k: int = 3
    hybrid_heuristic_weight: float = 0.35


class EmbeddingConfig(BaseModel):
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"


class TrainingConfig(BaseModel):
    output_dir: str = "data/processed/role_classifier"
    batch_size: int = 4
    learning_rate: float = 2e-5
    num_train_epochs: int = 2
    warmup_ratio: float = 0.1


class ModelConfig(BaseModel):
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    summarization: SummarizationConfig = Field(default_factory=SummarizationConfig)
    roles: RoleModelConfig = Field(default_factory=RoleModelConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)


class DataConfig(BaseModel):
    paragraph_min_chars: int = 30
    sentence_min_chars: int = 10
    rhetorical_unit_segmentation: bool = True
    normalize_headers: bool = True


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    title: str = "Legal Argument-Aware Summarization MVP"
    version: str = "0.1.0"


class UiConfig(BaseModel):
    page_title: str = "Legal Summarization MVP"
    layout: str = "wide"


class AuthConfig(BaseModel):
    enabled: bool = True
    users_db_path: str = "data/processed/app_users.db"
    min_password_length: int = 8


class GenerationConfig(BaseModel):
    strategies: list[str] = Field(
        default_factory=lambda: [
            "baseline_full_document",
            "role_focus_facts_issue_ruling",
            "analysis_heavy",
            "chunk_merge_conservative",
            "chunk_merge_diverse",
        ]
    )


class ExplainabilityConfig(BaseModel):
    supporting_segment_count: int = 5


class AppConfig(BaseModel):
    data: DataConfig = Field(default_factory=DataConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    explainability: ExplainabilityConfig = Field(default_factory=ExplainabilityConfig)


class ScoreWeights(BaseModel):
    semantic_similarity: float = 0.38
    role_coverage: float = 0.26
    factual_proxy: float = 0.20
    redundancy_penalty: float = 1.0
    length_penalty: float = 1.0
    readability_bonus: float = 0.08


class ScoreThresholds(BaseModel):
    min_summary_words: int = 90
    max_summary_words: int = 260
    ideal_summary_words: int = 170
    redundancy_ngram_size: int = 3
    readability_sentence_min: int = 10
    readability_sentence_max: int = 32


class ScoringConfig(BaseModel):
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    role_importance: Dict[str, float] = Field(default_factory=dict)
    thresholds: ScoreThresholds = Field(default_factory=ScoreThresholds)


class ProjectConfig(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a mapping in config file: {path}")
    return payload


def load_project_config(
    model_path: Optional[str] = None,
    app_path: Optional[str] = None,
    scoring_path: Optional[str] = None,
) -> ProjectConfig:
    """Load the project configuration from YAML files."""

    base = Path.cwd()
    model_cfg_path = Path(model_path or os.getenv("MODEL_CONFIG_PATH", str(base / "configs" / "model_config.yaml")))
    app_cfg_path = Path(app_path or os.getenv("APP_CONFIG_PATH", str(base / "configs" / "app_config.yaml")))
    scoring_cfg_path = Path(
        scoring_path or os.getenv("SCORING_CONFIG_PATH", str(base / "configs" / "scoring_config.yaml"))
    )

    model_cfg = ModelConfig.model_validate(_load_yaml(model_cfg_path))
    app_cfg = AppConfig.model_validate(_load_yaml(app_cfg_path))
    scoring_cfg = ScoringConfig.model_validate(_load_yaml(scoring_cfg_path))

    device_override = os.getenv("DEVICE")
    if device_override:
        model_cfg.runtime.device = device_override

    local_files_override = os.getenv("LOCAL_FILES_ONLY")
    if local_files_override:
        model_cfg.runtime.local_files_only = local_files_override.lower() == "true"

    heuristics_only_override = os.getenv("USE_HEURISTICS_ONLY")
    if heuristics_only_override:
        model_cfg.runtime.use_heuristics_only = heuristics_only_override.lower() == "true"

    return ProjectConfig(model=model_cfg, app=app_cfg, scoring=scoring_cfg)
