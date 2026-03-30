"""Argument-aware summary candidate reranking."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Optional

import numpy as np

from src.config import ModelConfig, ScoringConfig
from src.logger import get_logger
from src.roles.classifier import RoleClassifier
from src.roles.labels import LABEL_PRIORITY
from src.utils import (
    CandidateScore,
    RolePrediction,
    Segment,
    SummaryCandidate,
    clamp,
    cosine_similarity,
    extract_legal_references,
    extract_named_chunks,
    extract_numbers,
    rolling_ngrams,
    safe_mean,
    split_sentences,
    word_count,
)

LOGGER = get_logger(__name__)


class SummaryReranker:
    """Score and rank summary candidates using structure-aware signals."""

    def __init__(self, scoring_config: Optional[ScoringConfig] = None, model_config: Optional[ModelConfig] = None) -> None:
        self.scoring_config = scoring_config
        self.model_config = model_config
        self.embedding_model = None
        self._loaded = False
        self.backend = "tfidf"

    def score_candidates(
        self,
        document_text: str,
        segments: List[Segment],
        role_predictions: List[RolePrediction],
        candidates: List[SummaryCandidate],
        role_classifier: Optional[RoleClassifier] = None,
    ) -> List[CandidateScore]:
        self._ensure_loaded()
        role_map = {prediction.segment_id: prediction for prediction in role_predictions}
        scores = [
            self._score_candidate(
                candidate=candidate,
                document_text=document_text,
                segments=segments,
                role_map=role_map,
                role_classifier=role_classifier,
            )
            for candidate in candidates
        ]
        return sorted(scores, key=lambda item: item.final_score, reverse=True)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        if not self.model_config or self.model_config.runtime.use_heuristics_only or not self.model_config.runtime.load_models:
            self.backend = "tfidf"
            return

        try:
            from sentence_transformers import SentenceTransformer

            LOGGER.info("Loading reranker embedding model: %s", self.model_config.embeddings.model_name)
            self.embedding_model = SentenceTransformer(
                self.model_config.embeddings.model_name,
                device=self.model_config.runtime.device,
                cache_folder=None,
            )
            self.backend = "sentence_transformers"
        except Exception as error:
            LOGGER.warning("Embedding model unavailable; reverting to TF-IDF reranking: %s", error)
            self.backend = "tfidf"

    def _score_candidate(
        self,
        candidate: SummaryCandidate,
        document_text: str,
        segments: List[Segment],
        role_map: Dict[str, RolePrediction],
        role_classifier: Optional[RoleClassifier],
    ) -> CandidateScore:
        semantic_similarity = self._semantic_similarity(document_text, candidate.text)
        role_coverage = self._role_coverage(candidate.text, role_map, role_classifier)
        factual_proxy = self._factual_proxy(document_text, candidate.text)
        redundancy_penalty = self._redundancy_penalty(candidate.text)
        length_penalty = self._length_penalty(candidate.text)
        readability_bonus = self._readability_bonus(candidate.text)

        weights = self.scoring_config.weights if self.scoring_config else None
        final_score = (
            (weights.semantic_similarity if weights else 0.38) * semantic_similarity
            + (weights.role_coverage if weights else 0.26) * role_coverage
            + (weights.factual_proxy if weights else 0.20) * factual_proxy
            - (weights.redundancy_penalty if weights else 1.0) * abs(redundancy_penalty)
            - (weights.length_penalty if weights else 1.0) * abs(length_penalty)
            + (weights.readability_bonus if weights else 0.08) * readability_bonus
        )
        final_score = clamp(final_score)

        reasoning = self._build_reasoning(semantic_similarity, role_coverage, factual_proxy, redundancy_penalty, length_penalty)
        supporting_segments = self._supporting_segments(candidate.text, segments)
        return CandidateScore(
            candidate_id=candidate.candidate_id,
            semantic_similarity=semantic_similarity,
            role_coverage=role_coverage,
            factual_proxy=factual_proxy,
            redundancy_penalty=redundancy_penalty,
            length_penalty=length_penalty,
            readability_bonus=readability_bonus,
            final_score=final_score,
            reasoning=reasoning,
            supporting_segments=supporting_segments,
        )

    def _semantic_similarity(self, source_text: str, summary_text: str) -> float:
        vectors = self._embed_texts([source_text, summary_text])
        return clamp(cosine_similarity(vectors[0], vectors[1]))

    def _role_coverage(
        self,
        summary_text: str,
        role_map: Dict[str, RolePrediction],
        role_classifier: Optional[RoleClassifier],
    ) -> float:
        source_distribution = Counter(role.label for role in role_map.values())
        source_total = sum(source_distribution.values()) or 1
        summary_sentences = split_sentences(summary_text)
        if not summary_sentences:
            return 0.0

        if role_classifier is not None:
            summary_roles = role_classifier.predict_batch(summary_sentences)
        else:
            summary_roles = [role for role in role_map.values()][: len(summary_sentences)]

        coverage = 0.0
        denom = 0.0
        role_importance = self.scoring_config.role_importance if self.scoring_config else LABEL_PRIORITY
        summary_role_set = {prediction.label for prediction in summary_roles}
        for label, weight in role_importance.items():
            denom += weight
            source_presence = source_distribution.get(label, 0) / source_total
            if label in summary_role_set:
                coverage += weight * min(1.0, 0.4 + source_presence)
        return clamp(coverage / max(denom, 1e-6))

    def _factual_proxy(self, source_text: str, summary_text: str) -> float:
        source_refs = set(extract_legal_references(source_text))
        summary_refs = set(extract_legal_references(summary_text))
        source_numbers = set(extract_numbers(source_text))
        summary_numbers = set(extract_numbers(summary_text))
        source_entities = set(extract_named_chunks(source_text))
        summary_entities = set(extract_named_chunks(summary_text))

        ref_score = len(source_refs & summary_refs) / max(len(summary_refs), 1) if summary_refs else 0.8
        number_score = len(source_numbers & summary_numbers) / max(len(summary_numbers), 1) if summary_numbers else 0.8
        entity_score = len(source_entities & summary_entities) / max(len(summary_entities), 1) if summary_entities else 0.7
        return clamp(0.4 * ref_score + 0.25 * number_score + 0.35 * entity_score)

    def _redundancy_penalty(self, summary_text: str) -> float:
        sentences = [sentence.strip() for sentence in split_sentences(summary_text) if sentence.strip()]
        if not sentences:
            return 1.0
        normalized_sentences = [re.sub(r"\W+", " ", sentence.lower()).strip() for sentence in sentences]
        sentence_dup_ratio = 1.0 - (len(set(normalized_sentences)) / max(len(normalized_sentences), 1))
        ngram_size = self.scoring_config.thresholds.redundancy_ngram_size if self.scoring_config else 3
        tokens = re.findall(r"\b\w+\b", summary_text.lower())
        ngrams = rolling_ngrams(tokens, ngram_size)
        if not ngrams:
            return 0.0
        repeated = sum(count - 1 for count in Counter(ngrams).values() if count > 1)
        ngram_dup_ratio = repeated / max(len(ngrams), 1)
        return clamp(0.5 * sentence_dup_ratio + 0.5 * ngram_dup_ratio)

    def _length_penalty(self, summary_text: str) -> float:
        thresholds = self.scoring_config.thresholds if self.scoring_config else None
        target = thresholds.ideal_summary_words if thresholds else 170
        minimum = thresholds.min_summary_words if thresholds else 90
        maximum = thresholds.max_summary_words if thresholds else 260
        count = word_count(summary_text)
        if minimum <= count <= maximum:
            return 0.0
        return clamp(abs(count - target) / max(target, 1))

    def _readability_bonus(self, summary_text: str) -> float:
        thresholds = self.scoring_config.thresholds if self.scoring_config else None
        sentence_lengths = [word_count(sentence) for sentence in split_sentences(summary_text)]
        if not sentence_lengths:
            return 0.0
        avg_len = safe_mean(sentence_lengths)
        lower = thresholds.readability_sentence_min if thresholds else 10
        upper = thresholds.readability_sentence_max if thresholds else 32
        if lower <= avg_len <= upper:
            return 1.0
        if avg_len < lower:
            return clamp(avg_len / max(lower, 1))
        return clamp(upper / max(avg_len, 1))

    def _supporting_segments(self, summary_text: str, segments: List[Segment], top_k: int = 3) -> List[Dict[str, object]]:
        if not segments or not summary_text.strip():
            return []
        all_texts = [summary_text] + [segment.text for segment in segments]
        embeddings = self._embed_texts(all_texts)
        summary_vector = embeddings[0]
        scored = []
        for segment, embedding in zip(segments, embeddings[1:]):
            score = cosine_similarity(summary_vector, embedding)
            scored.append(
                {
                    "segment_id": segment.segment_id,
                    "text": segment.text,
                    "score": round(score, 4),
                    "start_char": segment.start_char,
                    "end_char": segment.end_char,
                }
            )
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]

    def _build_reasoning(
        self,
        semantic_similarity: float,
        role_coverage: float,
        factual_proxy: float,
        redundancy_penalty: float,
        length_penalty: float,
    ) -> List[str]:
        reasoning: List[str] = []
        if semantic_similarity >= 0.7:
            reasoning.append("High semantic overlap with the source opinion.")
        if role_coverage >= 0.6:
            reasoning.append("Covers the main rhetorical roles expected in a legal summary.")
        if factual_proxy >= 0.7:
            reasoning.append("Preserves citations, entities, or numerical details from the source.")
        if redundancy_penalty <= 0.15:
            reasoning.append("Shows low redundancy across sentences and n-grams.")
        if length_penalty <= 0.15:
            reasoning.append("Stays close to the target summary length.")
        if not reasoning:
            reasoning.append("Selected because it achieved the best overall weighted trade-off.")
        return reasoning

    def _embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        if self.backend == "sentence_transformers" and self.embedding_model is not None:
            embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
            return [np.array(embedding) for embedding in embeddings]

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            vectorizer = TfidfVectorizer(stop_words="english")
            matrix = vectorizer.fit_transform(texts)
            return [matrix[index].toarray()[0] for index in range(matrix.shape[0])]
        except Exception:
            return self._basic_tfidf_embeddings(texts)

    def _basic_tfidf_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        tokenized = [re.findall(r"\b\w+\b", text.lower()) for text in texts]
        vocabulary = sorted({token for tokens in tokenized for token in tokens})
        if not vocabulary:
            return [np.zeros(1) for _ in texts]

        df_counts = {token: sum(1 for tokens in tokenized if token in tokens) for token in vocabulary}
        embeddings: List[np.ndarray] = []
        total_docs = len(texts)
        for tokens in tokenized:
            counts = Counter(tokens)
            vector = []
            token_total = max(len(tokens), 1)
            for token in vocabulary:
                tf = counts[token] / token_total
                idf = np.log((1 + total_docs) / (1 + df_counts[token])) + 1.0
                vector.append(tf * idf)
            embeddings.append(np.array(vector, dtype=float))
        return embeddings
