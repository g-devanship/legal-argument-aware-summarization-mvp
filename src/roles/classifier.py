"""Hybrid rhetorical-role classifier with transformer and heuristic fallback."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import numpy as np

from src.config import ModelConfig
from src.logger import get_logger
from src.roles.heuristics import HeuristicRoleLabeler
from src.roles.labels import LABEL_DESCRIPTIONS, LEGAL_ROLE_LABELS
from src.utils import RolePrediction, Segment, clamp, cosine_similarity, normalize_scores, softmax

LOGGER = get_logger(__name__)


class RoleClassifier:
    """Predict rhetorical roles for legal segments.

    The classifier uses a best-effort transformer backend:
    1. Fine-tuned sequence classification checkpoint if configured.
    2. Encoder similarity against label prototypes.
    3. Heuristic cue-phrase fallback when models are unavailable.
    """

    def __init__(self, model_config: Optional[ModelConfig] = None) -> None:
        self.model_config = model_config
        self.heuristics = HeuristicRoleLabeler()
        self.tokenizer = None
        self.model = None
        self.backend: str = "heuristic"
        self.label_embeddings: Optional[Dict[str, np.ndarray]] = None
        self._loaded = False

    def predict(self, segment: str | Segment) -> RolePrediction:
        if isinstance(segment, Segment):
            segment_id, text = segment.segment_id, segment.text
        else:
            segment_id, text = "segment", segment
        synthetic = Segment(
            segment_id=segment_id,
            text=text,
            level="sentence",
            start_char=0,
            end_char=len(text),
            paragraph_index=0,
        )
        return self.predict_batch([synthetic])[0]

    def predict_batch(self, segments: Iterable[str | Segment]) -> List[RolePrediction]:
        normalized_segments: List[Segment] = []
        for index, segment in enumerate(segments):
            if isinstance(segment, Segment):
                normalized_segments.append(segment)
            else:
                normalized_segments.append(
                    Segment(
                        segment_id=f"segment-{index}",
                        text=segment,
                        level="sentence",
                        start_char=0,
                        end_char=len(segment),
                        paragraph_index=0,
                    )
                )

        self._ensure_loaded()

        if self.backend == "heuristic":
            return [self.heuristics.predict(segment.segment_id, segment.text, top_k=self._top_k) for segment in normalized_segments]
        return [self._predict_hybrid(segment) for segment in normalized_segments]

    @property
    def _top_k(self) -> int:
        if self.model_config:
            return self.model_config.roles.top_k
        return 3

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        if not self.model_config or self.model_config.runtime.use_heuristics_only or not self.model_config.runtime.load_models:
            self.backend = "heuristic"
            LOGGER.info("Role classifier running in heuristic-only mode.")
            return

        candidate_models = [
            self.model_config.roles.fine_tuned_checkpoint,
            self.model_config.roles.preferred_model,
            self.model_config.roles.alternative_model,
            self.model_config.roles.lightweight_model,
        ]

        try:
            from transformers import AutoModel, AutoTokenizer

            for model_name in [model_name for model_name in candidate_models if model_name]:
                try:
                    LOGGER.info("Loading role encoder model: %s", model_name)
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        model_name, local_files_only=self.model_config.runtime.local_files_only
                    )
                    self.model = AutoModel.from_pretrained(
                        model_name, local_files_only=self.model_config.runtime.local_files_only
                    )
                    self.model.to(self.model_config.runtime.device)
                    self.model.eval()
                    self.backend = "prototype_transformer"
                    self.label_embeddings = self._embed_texts(list(LABEL_DESCRIPTIONS.values()))
                    LOGGER.info("Role classifier using prototype-transformer backend with %s", model_name)
                    return
                except Exception as model_error:
                    LOGGER.warning("Could not load role model %s: %s", model_name, model_error)
        except Exception as import_error:
            LOGGER.warning("Transformers backend unavailable for role classifier: %s", import_error)

        self.backend = "heuristic"
        LOGGER.info("Falling back to heuristic rhetorical-role classification.")

    def _predict_hybrid(self, segment: Segment) -> RolePrediction:
        assert self.label_embeddings is not None
        heuristic_scores, heuristic_rationale = self.heuristics.score(segment.text)
        embedding_map = self._segment_label_scores(segment.text)

        heuristic_weight = self.model_config.roles.hybrid_heuristic_weight if self.model_config else 0.35
        combined_scores = {
            label: (1.0 - heuristic_weight) * embedding_map.get(label, 0.0)
            + heuristic_weight * heuristic_scores.get(label, 0.0)
            for label in LEGAL_ROLE_LABELS
        }
        probabilities = normalize_scores(combined_scores)
        sorted_items = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
        label, confidence = sorted_items[0]
        return RolePrediction(
            segment_id=segment.segment_id,
            label=label,
            confidence=clamp(confidence),
            probabilities=dict(sorted_items[: self._top_k]),
            rationale=heuristic_rationale[:2] + [f"Transformer prototype similarity favored '{label}'."],
        )

    def _segment_label_scores(self, text: str) -> Dict[str, float]:
        segment_embedding = next(iter(self._embed_texts([text]).values()))
        similarities = []
        for label in LEGAL_ROLE_LABELS:
            label_embedding = self.label_embeddings[label]
            similarities.append(cosine_similarity(segment_embedding, label_embedding))
        probabilities = softmax(similarities)
        return {label: probability for label, probability in zip(LEGAL_ROLE_LABELS, probabilities)}

    def _embed_texts(self, texts: List[str]) -> Dict[str, np.ndarray]:
        import torch

        if not self.tokenizer or not self.model:
            raise RuntimeError("Role classifier transformer backend is not loaded.")

        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.model_config.roles.max_length if self.model_config else 256,
            return_tensors="pt",
        )
        device = self.model_config.runtime.device if self.model_config else "cpu"
        encoded = {key: value.to(device) for key, value in encoded.items()}

        with torch.no_grad():
            outputs = self.model(**encoded)
        hidden = outputs.last_hidden_state
        attention = encoded["attention_mask"].unsqueeze(-1)
        summed = (hidden * attention).sum(dim=1)
        counts = attention.sum(dim=1).clamp(min=1)
        embeddings = (summed / counts).cpu().numpy()

        if len(texts) == len(LEGAL_ROLE_LABELS) and texts == list(LABEL_DESCRIPTIONS.values()):
            return {label: embeddings[index] for index, label in enumerate(LEGAL_ROLE_LABELS)}
        return {texts[index]: embeddings[index] for index in range(len(texts))}
