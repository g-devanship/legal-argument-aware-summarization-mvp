"""Multiple-candidate abstractive summary generation."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional

from src.config import AppConfig, ModelConfig
from src.logger import get_logger
from src.roles.labels import LABEL_PRIORITY
from src.summarization.candidates import build_candidate
from src.summarization.prompts import compose_role_aware_source
from src.utils import RolePrediction, Segment, SummaryCandidate, split_sentences, strip_role_prefix, word_count

LOGGER = get_logger(__name__)


class SummaryGenerator:
    """Generate multiple summary candidates with model and heuristic fallbacks."""

    def __init__(self, model_config: Optional[ModelConfig] = None, app_config: Optional[AppConfig] = None) -> None:
        self.model_config = model_config
        self.app_config = app_config
        self.tokenizer = None
        self.model = None
        self.backend = "heuristic"
        self._loaded = False

    def generate_candidates(
        self,
        document_text: str,
        segments: List[Segment],
        role_predictions: List[RolePrediction],
        chunks: Optional[List[Dict[str, object]]] = None,
    ) -> List[SummaryCandidate]:
        role_map = {prediction.segment_id: prediction for prediction in role_predictions}
        chunks = chunks or []
        self._ensure_loaded()

        strategies = (
            self.app_config.generation.strategies
            if self.app_config and self.app_config.generation.strategies
            else [
                "baseline_full_document",
                "role_focus_facts_issue_ruling",
                "analysis_heavy",
                "chunk_merge_conservative",
                "chunk_merge_diverse",
            ]
        )

        candidates: List[SummaryCandidate] = []
        for index, strategy in enumerate(strategies):
            candidate = self._generate_for_strategy(
                strategy=strategy,
                candidate_id=f"cand-{index}",
                document_text=document_text,
                segments=segments,
                role_map=role_map,
                chunks=chunks,
            )
            if candidate.text:
                candidates.append(candidate)
        return candidates

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        if not self.model_config or self.model_config.runtime.use_heuristics_only or not self.model_config.runtime.load_models:
            self.backend = "heuristic"
            LOGGER.info("Summary generator running in heuristic-only mode.")
            return

        candidate_models = [
            self.model_config.summarization.preferred_model,
            self.model_config.summarization.fallback_model,
            self.model_config.summarization.lightweight_model,
        ]

        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, LEDForConditionalGeneration, LEDTokenizer

            for model_name in candidate_models:
                try:
                    LOGGER.info("Loading summarization model: %s", model_name)
                    if "led" in model_name.lower():
                        self.tokenizer = LEDTokenizer.from_pretrained(
                            model_name, local_files_only=self.model_config.runtime.local_files_only
                        )
                        self.model = LEDForConditionalGeneration.from_pretrained(
                            model_name, local_files_only=self.model_config.runtime.local_files_only
                        )
                    else:
                        self.tokenizer = AutoTokenizer.from_pretrained(
                            model_name, local_files_only=self.model_config.runtime.local_files_only
                        )
                        self.model = AutoModelForSeq2SeqLM.from_pretrained(
                            model_name, local_files_only=self.model_config.runtime.local_files_only
                        )
                    self.model.to(self.model_config.runtime.device)
                    self.model.eval()
                    self.backend = model_name
                    LOGGER.info("Summary generator using backend %s", model_name)
                    return
                except Exception as model_error:
                    LOGGER.warning("Could not load summarization model %s: %s", model_name, model_error)
        except Exception as import_error:
            LOGGER.warning("Transformers backend unavailable for summary generation: %s", import_error)

        self.backend = "heuristic"
        LOGGER.info("Falling back to heuristic summarization.")

    def _generate_for_strategy(
        self,
        strategy: str,
        candidate_id: str,
        document_text: str,
        segments: List[Segment],
        role_map: Dict[str, RolePrediction],
        chunks: List[Dict[str, object]],
    ) -> SummaryCandidate:
        if strategy == "baseline_full_document":
            source_text = document_text
            source_ids = [segment.segment_id for segment in segments[:20]]
            params = {
                "num_beams": 4,
                "length_mode": "balanced",
                "summary_style": "balanced",
                "target_roles": ["facts", "issue", "arguments", "analysis", "ruling"],
                "max_sentences": 5,
            }
        elif strategy == "role_focus_facts_issue_ruling":
            source_text, source_ids = compose_role_aware_source(segments, role_map, ["facts", "issue", "ruling", "statute"])
            params = {
                "num_beams": 5,
                "length_mode": "legal_core",
                "summary_style": "legal_core",
                "target_roles": ["facts", "issue", "statute", "ruling"],
                "max_sentences": 4,
            }
        elif strategy == "analysis_heavy":
            source_text, source_ids = compose_role_aware_source(segments, role_map, ["analysis", "arguments", "ruling"])
            params = {
                "num_beams": 6,
                "length_mode": "analysis",
                "summary_style": "analysis_heavy",
                "target_roles": ["facts", "issue", "arguments", "analysis", "statute", "ruling"],
                "max_sentences": 6,
            }
        elif strategy == "chunk_merge_conservative":
            source_text, source_ids = self._chunk_merge(chunks, diverse=False)
            params = {
                "num_beams": 4,
                "do_sample": False,
                "summary_style": "chunk_conservative",
                "target_roles": ["facts", "issue", "ruling"],
                "max_sentences": 3,
            }
        elif strategy == "chunk_merge_diverse":
            source_text, source_ids = self._chunk_merge(chunks, diverse=True)
            params = {
                "num_beams": 3,
                "do_sample": True,
                "temperature": 0.9,
                "top_p": 0.92,
                "summary_style": "chunk_diverse",
                "target_roles": ["facts", "arguments", "analysis", "ruling"],
                "max_sentences": 4,
            }
        else:
            source_text = document_text
            source_ids = [segment.segment_id for segment in segments[:20]]
            params = {"num_beams": 4, "summary_style": "balanced", "target_roles": ["facts", "issue", "analysis", "ruling"]}

        summary_text = self._generate_text(source_text, segments=segments, role_map=role_map, decoding_parameters=params)
        return build_candidate(
            candidate_id=candidate_id,
            text=summary_text,
            generation_method=strategy,
            decoding_parameters=params,
            source_chunks=source_ids,
        )

    def _generate_text(
        self,
        source_text: str,
        segments: List[Segment],
        role_map: Dict[str, RolePrediction],
        decoding_parameters: Dict[str, object],
    ) -> str:
        if self.backend == "heuristic":
            return self._heuristic_summary(
                source_text=source_text,
                segments=segments,
                role_map=role_map,
                decoding_parameters=decoding_parameters,
            )
        try:
            return self._model_generate(source_text, decoding_parameters)
        except Exception as generation_error:
            LOGGER.warning("Model generation failed, reverting to heuristic summary: %s", generation_error)
            return self._heuristic_summary(
                source_text=source_text,
                segments=segments,
                role_map=role_map,
                decoding_parameters=decoding_parameters,
            )

    def _model_generate(self, source_text: str, decoding_parameters: Dict[str, object]) -> str:
        import torch

        if not self.model or not self.tokenizer or not self.model_config:
            raise RuntimeError("Model backend is not initialized.")

        max_input_tokens = self.model_config.summarization.encoder_max_input_tokens
        encoded = self.tokenizer(
            source_text,
            truncation=True,
            padding="longest",
            max_length=max_input_tokens,
            return_tensors="pt",
        )
        device = self.model_config.runtime.device
        encoded = {key: value.to(device) for key, value in encoded.items()}

        generate_kwargs = {
            "min_new_tokens": self.model_config.summarization.min_summary_tokens,
            "max_new_tokens": self.model_config.summarization.max_summary_tokens,
            "num_beams": int(decoding_parameters.get("num_beams", 4)),
            "do_sample": bool(decoding_parameters.get("do_sample", False)),
        }
        if generate_kwargs["do_sample"]:
            generate_kwargs["temperature"] = float(decoding_parameters.get("temperature", 0.9))
            generate_kwargs["top_p"] = float(decoding_parameters.get("top_p", 0.92))

        if "led" in self.backend.lower():
            global_attention_mask = torch.zeros_like(encoded["input_ids"])
            global_attention_mask[:, 0] = 1
            generate_kwargs["global_attention_mask"] = global_attention_mask

        with torch.no_grad():
            outputs = self.model.generate(**encoded, **generate_kwargs)
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return text.strip()

    def _heuristic_summary(
        self,
        source_text: str,
        segments: List[Segment],
        role_map: Dict[str, RolePrediction],
        decoding_parameters: Dict[str, object],
    ) -> str:
        role_to_segments: Dict[str, List[Segment]] = defaultdict(list)
        for segment in segments:
            role = role_map.get(segment.segment_id).label if role_map.get(segment.segment_id) else "other"
            role_to_segments[role].append(segment)

        preferred_roles = [str(role) for role in decoding_parameters.get("target_roles", [])]
        if not preferred_roles:
            preferred_roles = ["facts", "issue", "arguments", "analysis", "ruling"]

        sentences: List[str] = []
        style = str(decoding_parameters.get("summary_style", "balanced"))
        for role in preferred_roles:
            sentence = self._render_role_sentence(role, role_to_segments.get(role, []), style=style)
            if sentence:
                sentences.append(sentence)

        if not sentences:
            fallback_sentences = split_sentences(source_text)[: int(decoding_parameters.get("max_sentences", 4))]
            sentences = [self._clean_sentence(sentence) for sentence in fallback_sentences if sentence.strip()]

        max_sentences = int(decoding_parameters.get("max_sentences", len(sentences) or 4))
        summary = " ".join(self._deduplicate_sentences(sentences[:max_sentences]))
        return re.sub(r"\s+", " ", summary).strip()

    def _select_salient_segments(
        self,
        segments: List[Segment],
        role_map: Dict[str, RolePrediction],
        decoding_parameters: Dict[str, object],
    ) -> List[Segment]:
        scored = []
        for segment in segments:
            role = role_map.get(segment.segment_id).label if role_map.get(segment.segment_id) else "other"
            role_weight = LABEL_PRIORITY.get(role, 0.04)
            length_bonus = min(word_count(segment.text) / 40.0, 1.0)
            keyword_bonus = 0.0
            cleaned = strip_role_prefix(segment.text).lower()
            if role == "ruling" and re.search(r"\b(set aside|affirmed|reversed|dismissed|allowed|remanded|held)\b", cleaned):
                keyword_bonus += 0.25
            if role == "analysis" and re.search(r"\b(reasoned|observed|because|therefore|must act fairly)\b", cleaned):
                keyword_bonus += 0.2
            if role == "statute" and re.search(r"\b(article|section|clause|act|constitution)\b", cleaned):
                keyword_bonus += 0.15
            score = role_weight + 0.15 * length_bonus + keyword_bonus
            scored.append((score, segment))
        scored.sort(key=lambda item: item[0], reverse=True)
        limit = 9 if decoding_parameters.get("length_mode") == "analysis" else 7
        return [segment for _, segment in scored[:limit]]

    def _compress_text(self, text: str, max_words: int = 28) -> str:
        text = strip_role_prefix(text)
        tokens = text.split()
        compressed = " ".join(tokens[:max_words])
        compressed = compressed.rstrip(" ,;:.")
        compressed = re.sub(r"\b(and|or|that|because)$", "", compressed, flags=re.I).rstrip(" ,;:.")
        return compressed

    def _clean_sentence(self, text: str) -> str:
        cleaned = self._compress_text(text, max_words=32)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = cleaned.rstrip(" ,;:")
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        return cleaned

    def _render_role_sentence(self, role: str, segments: List[Segment], style: str) -> str:
        if not segments:
            return ""

        if role == "facts":
            primary = self._pick_best_segment(segments, preferred_patterns=[r"\bchallenged\b", r"\bcancelled\b", r"\bdispute\b"])
            normalized = self._normalize_role_content(role, primary.text)
            if normalized.lower().startswith(("the petitioner", "the plaintiff", "the appellant")):
                return self._clean_sentence(normalized)
            return self._prefix_sentence("The dispute concerns", normalized, 28)

        if role == "issue":
            primary = self._pick_best_segment(segments, preferred_patterns=[r"\bwhether\b", r"\bquestion\b", r"\bissue\b"])
            return self._prefix_sentence("The core legal issue was", self._normalize_role_content(role, primary.text), 30)

        if role == "arguments":
            primary, secondary = self._pick_argument_pair(segments)
            if primary is not None and secondary is not None:
                first_label, first = self._describe_argument_side(primary)
                second_label, second = self._describe_argument_side(secondary)
                return self._clean_sentence(
                    f"{first_label.capitalize()} argued that {first}, while {second_label} argued that {second}"
                )
            primary = self._pick_best_segment(segments, preferred_patterns=[r"\bargued\b", r"\bcontended\b", r"\bsubmitted\b"])
            return self._prefix_sentence("The parties argued that", self._normalize_role_content(role, primary.text), 28)

        if role == "analysis":
            primary = self._pick_best_segment(segments, preferred_patterns=[r"\breasoned\b", r"\bobserved\b", r"\bbecause\b", r"\btherefore\b"])
            return self._prefix_sentence("The court reasoned that", self._normalize_role_content(role, primary.text), 30)

        if role == "statute":
            primary = self._pick_best_segment(segments, preferred_patterns=[r"\barticle\b", r"\bsection\b", r"\bclause\b", r"\bact\b"])
            return self._prefix_sentence("The court relied on", self._normalize_role_content(role, primary.text), 26)

        if role == "ruling":
            primary = self._pick_best_segment(
                segments,
                preferred_patterns=[r"\bset aside\b", r"\bremanded\b", r"\baffirmed\b", r"\breversed\b", r"\bdismissed\b", r"\ballowed\b", r"\bheld\b"],
            )
            return self._prefix_sentence(
                "Ultimately, the court",
                self._normalize_role_content(role, primary.text),
                36,
                verb_fallback="held that",
            )

        primary = segments[0]
        return self._clean_sentence(primary.text)

    def _pick_best_segment(self, segments: List[Segment], preferred_patterns: List[str]) -> Segment:
        best_segment = segments[0]
        best_score = float("-inf")
        for segment in segments:
            cleaned = strip_role_prefix(segment.text).lower()
            score = min(word_count(cleaned) / 24.0, 1.5)
            for pattern in preferred_patterns:
                if re.search(pattern, cleaned):
                    score += 1.0
            if score > best_score:
                best_segment = segment
                best_score = score
        return best_segment

    def _pick_argument_pair(self, segments: List[Segment]) -> tuple[Segment | None, Segment | None]:
        petitioner_side = None
        respondent_side = None
        petitioner_patterns = [r"\bpetitioner\b", r"\bappellant\b", r"\bplaintiff\b"]
        respondent_patterns = [r"\brespondent\b", r"\bauthority\b", r"\bdefendant\b", r"\bappellee\b"]

        sorted_segments = sorted(segments, key=lambda item: len(strip_role_prefix(item.text)), reverse=True)
        for segment in sorted_segments:
            cleaned = strip_role_prefix(segment.text).lower()
            if petitioner_side is None and any(re.search(pattern, cleaned) for pattern in petitioner_patterns):
                petitioner_side = segment
            if respondent_side is None and any(re.search(pattern, cleaned) for pattern in respondent_patterns):
                respondent_side = segment

        if petitioner_side is not None and respondent_side is not None and petitioner_side.segment_id != respondent_side.segment_id:
            return petitioner_side, respondent_side

        if len(sorted_segments) >= 2:
            return sorted_segments[0], sorted_segments[1]
        if len(sorted_segments) == 1:
            return sorted_segments[0], None
        return None, None

    def _describe_argument_side(self, segment: Segment) -> tuple[str, str]:
        cleaned = strip_role_prefix(segment.text).lower()
        if any(token in cleaned for token in ["respondent", "authority", "defendant", "appellee"]):
            return "the respondent", self._compress_text(self._normalize_role_content("arguments", segment.text), 16)
        if any(token in cleaned for token in ["petitioner", "appellant", "plaintiff"]):
            return "the petitioner", self._compress_text(self._normalize_role_content("arguments", segment.text), 16)
        return "one side", self._compress_text(self._normalize_role_content("arguments", segment.text), 16)

    def _prefix_sentence(self, prefix: str, text: str, max_words: int, verb_fallback: str | None = None) -> str:
        cleaned = self._compress_text(text, max_words=max_words)
        lowered = cleaned.lower()
        duplicated_starters = [
            "the court reasoned that",
            "the court observed that",
            "the court considered",
            "the court relied on",
            "the core legal issue was",
            "the principal legal issue was",
        ]
        if any(lowered.startswith(starter) for starter in duplicated_starters):
            return self._clean_sentence(cleaned)
        if prefix.endswith("court") and lowered.startswith(("the cancellation order", "the writ petition", "the appeal", "the petition", "the denial")):
            cleaned = cleaned[0].lower() + cleaned[1:] if cleaned.startswith("The ") else cleaned
            return self._clean_sentence(f"Ultimately, {cleaned}")
        if verb_fallback and re.match(r"^(held|ordered|affirmed|reversed|dismissed|allowed|set aside|remanded)\b", lowered):
            return self._clean_sentence(f"{prefix} {cleaned}")
        if prefix.endswith("court") and not re.match(r"^(held|ordered|affirmed|reversed|dismissed|allowed|set aside|remanded)\b", lowered):
            prefix = f"{prefix} {verb_fallback or 'held that'}"
        return self._clean_sentence(f"{prefix} {cleaned}")

    def _normalize_role_content(self, role: str, text: str) -> str:
        cleaned = strip_role_prefix(text)
        patterns = {
            "issue": [
                r"(?i)^the principal question before the .*? was\s+",
                r"(?i)^the issue before the .*? was\s+",
                r"(?i)^the issue was\s+",
            ],
            "arguments": [
                r"(?i)^counsel for the .*? argued that\s+",
                r"(?i)^counsel for the .*? contended that\s+",
                r"(?i)^it was further submitted that\s+",
                r"(?i)^it was argued that\s+",
            ],
            "analysis": [
                r"(?i)^the court reasoned that\s+",
                r"(?i)^the court observed that\s+",
                r"(?i)^because\s+",
            ],
            "statute": [
                r"(?i)^the court considered\s+",
                r"(?i)^the court relied on\s+",
            ],
        }
        for pattern in patterns.get(role, []):
            cleaned = re.sub(pattern, "", cleaned)
        return cleaned.strip()

    def _deduplicate_sentences(self, sentences: List[str]) -> List[str]:
        seen = set()
        result = []
        for sentence in sentences:
            normalized = re.sub(r"\W+", " ", sentence.lower()).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(sentence)
        return result

    def _chunk_merge(self, chunks: List[Dict[str, object]], diverse: bool) -> tuple[str, List[str]]:
        if not chunks:
            return "", []
        partial_summaries: List[str] = []
        used_chunks: List[str] = []

        for chunk in chunks[:4]:
            chunk_text = str(chunk["text"])
            used_chunks.append(str(chunk["chunk_id"]))
            sentences = split_sentences(chunk_text)
            if diverse:
                selected = sentences[:1] + sentences[-1:] if len(sentences) > 1 else sentences[:1]
            else:
                selected = sentences[:2]
            partial_summaries.append(" ".join(selected))

        merged = " ".join(partial_summaries)
        return merged, used_chunks
