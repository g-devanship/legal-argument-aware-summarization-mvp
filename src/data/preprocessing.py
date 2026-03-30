"""Preprocessing pipeline for legal text inputs."""

from __future__ import annotations

import re
from typing import Any, Callable, List, Optional

from src.config import AppConfig, ModelConfig
from src.data.chunking import chunk_segments
from src.logger import get_logger
from src.utils import ProcessedDocument, Segment, normalize_whitespace, repair_text_artifacts, split_sentences

LOGGER = get_logger(__name__)


class DataProcessor:
    """Normalize legal documents and build reusable segmentation artifacts."""

    SECTION_HEADER_PATTERN = re.compile(
        r"(?im)^(facts|background|issue|issues|arguments|analysis|discussion|holding|ruling|judgment|statute|order|conclusion)\s*[:.-]?\s*$"
    )

    def __init__(self, model_config: Optional[ModelConfig] = None, app_config: Optional[AppConfig] = None) -> None:
        self.model_config = model_config
        self.app_config = app_config

    def process_document(
        self,
        document_text: str,
        document_id: str = "document",
        progress_callback: Optional[Callable[[str, str, dict[str, Any]], None]] = None,
    ) -> ProcessedDocument:
        LOGGER.info("Processing document %s", document_id)
        original_text = document_text or ""

        self._emit_progress(
            progress_callback,
            "normalize",
            "running",
            "Normalizing citations, whitespace, and legal section headers.",
        )
        normalized_text = self.normalize_text(original_text)
        self._emit_progress(
            progress_callback,
            "normalize",
            "completed",
            "Source normalization complete.",
            character_count=len(normalized_text),
        )

        self._emit_progress(
            progress_callback,
            "paragraphs",
            "running",
            "Segmenting paragraphs and preserving source offsets.",
        )
        paragraph_segments = self.segment_paragraphs(original_text)
        self._emit_progress(
            progress_callback,
            "paragraphs",
            "completed",
            f"Identified {len(paragraph_segments)} normalized paragraphs.",
            paragraph_count=len(paragraph_segments),
        )

        self._emit_progress(
            progress_callback,
            "sentences",
            "running",
            "Splitting normalized paragraphs into legal-domain friendly sentences.",
        )
        sentence_segments = self.segment_sentences(paragraph_segments)
        self._emit_progress(
            progress_callback,
            "sentences",
            "completed",
            f"Built {len(sentence_segments)} sentence-level segments.",
            sentence_count=len(sentence_segments),
        )

        self._emit_progress(
            progress_callback,
            "rhetorical_units",
            "running",
            "Approximating argumentative units for downstream role-aware summarization.",
        )
        rhetorical_units = (
            self.segment_rhetorical_units(sentence_segments)
            if not self.app_config or self.app_config.data.rhetorical_unit_segmentation
            else sentence_segments
        )
        self._emit_progress(
            progress_callback,
            "rhetorical_units",
            "completed",
            f"Prepared {len(rhetorical_units)} rhetorical units.",
            rhetorical_unit_count=len(rhetorical_units),
        )

        summarization_cfg = self.model_config.summarization if self.model_config else None
        self._emit_progress(
            progress_callback,
            "chunking",
            "running",
            "Chunking the document into long-context windows for summarization.",
        )
        chunks = chunk_segments(
            sentence_segments,
            max_words=summarization_cfg.chunk_max_words if summarization_cfg else 850,
            overlap_words=summarization_cfg.chunk_overlap_words if summarization_cfg else 120,
        )
        self._emit_progress(
            progress_callback,
            "chunking",
            "completed",
            f"Constructed {len(chunks)} overlapping source chunks.",
            chunk_count=len(chunks),
        )

        return ProcessedDocument(
            document_id=document_id,
            original_text=original_text,
            normalized_text=normalized_text,
            paragraphs=paragraph_segments,
            sentences=sentence_segments,
            rhetorical_units=rhetorical_units,
            chunks=chunks,
            metadata={
                "paragraph_count": len(paragraph_segments),
                "sentence_count": len(sentence_segments),
                "chunk_count": len(chunks),
            },
        )

    def _emit_progress(
        self,
        progress_callback: Optional[Callable[[str, str, dict[str, Any]], None]],
        stage: str,
        state: str,
        message: str,
        **payload: Any,
    ) -> None:
        if progress_callback is None:
            return
        progress_callback(stage, state, {"message": message, **payload})

    def normalize_text(self, text: str) -> str:
        text = repair_text_artifacts(text)
        text = normalize_whitespace(text)
        text = self.cleanup_legal_citations(text)
        text = self.normalize_section_headers(text)
        text = re.sub(
            r"(?im)\b(Facts|Background|Issue|Issues|Arguments|Analysis|Discussion|Holding|Ruling|Judgment|Statute|Order|Conclusion):\s*\n+",
            r"\1: ",
            text,
        )
        return text

    def cleanup_legal_citations(self, text: str) -> str:
        text = re.sub(r"\[(\d{4})\]\s+", r"[\1] ", text)
        text = re.sub(r"\((\d{4})\)\s+", r"(\1) ", text)
        text = re.sub(r"\s+v\.\s+", " v. ", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text

    def normalize_section_headers(self, text: str) -> str:
        def _normalize(match: re.Match[str]) -> str:
            header = match.group(1).strip().title()
            return f"{header}:"

        return self.SECTION_HEADER_PATTERN.sub(_normalize, text)

    def segment_paragraphs(self, text: str) -> List[Segment]:
        paragraphs: List[Segment] = []
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        matches = list(re.finditer(r".+?(?:\n\s*\n|$)", normalized, flags=re.S))
        paragraph_index = 0

        for match in matches:
            raw_paragraph = match.group(0).strip()
            if not raw_paragraph:
                continue
            cleaned = self.normalize_text(raw_paragraph)
            if self.app_config and len(cleaned) < self.app_config.data.paragraph_min_chars:
                continue
            paragraphs.append(
                Segment(
                    segment_id=f"p-{paragraph_index}",
                    text=cleaned,
                    level="paragraph",
                    start_char=match.start(),
                    end_char=match.end(),
                    paragraph_index=paragraph_index,
                    original_text=raw_paragraph,
                )
            )
            paragraph_index += 1
        return paragraphs

    def segment_sentences(self, paragraphs: List[Segment]) -> List[Segment]:
        sentences: List[Segment] = []
        sentence_index = 0
        min_chars = self.app_config.data.sentence_min_chars if self.app_config else 10

        for paragraph in paragraphs:
            local_cursor = 0
            for sentence in split_sentences(paragraph.text):
                if len(sentence) < min_chars:
                    continue
                relative_position = paragraph.text.find(sentence, local_cursor)
                if relative_position < 0:
                    relative_position = max(local_cursor, 0)
                start = paragraph.start_char + relative_position
                end = start + len(sentence)
                sentences.append(
                    Segment(
                        segment_id=f"s-{sentence_index}",
                        text=sentence,
                        level="sentence",
                        start_char=start,
                        end_char=end,
                        paragraph_index=paragraph.paragraph_index,
                        sentence_index=sentence_index,
                        original_text=sentence,
                    )
                )
                local_cursor = relative_position + len(sentence)
                sentence_index += 1
        return sentences

    def segment_rhetorical_units(self, sentences: List[Segment]) -> List[Segment]:
        """Approximate argumentative units by splitting on cue phrases and semicolons."""

        units: List[Segment] = []
        unit_index = 0
        cue_pattern = re.compile(
            r"(?i)\b(however|therefore|because|it was argued|the court held|the issue is|in view of|accordingly)\b"
        )

        for sentence in sentences:
            parts = [
                part.strip(" ;")
                for part in re.split(r";|\s+(?=(?:however|therefore|accordingly)\b)", sentence.text, flags=re.I)
            ]
            if len(parts) == 1 and not cue_pattern.search(sentence.text):
                parts = [sentence.text]

            cursor = 0
            for part in parts:
                if not part:
                    continue
                relative_position = sentence.text.find(part, cursor)
                start = sentence.start_char + max(relative_position, 0)
                end = start + len(part)
                units.append(
                    Segment(
                        segment_id=f"u-{unit_index}",
                        text=part,
                        level="rhetorical_unit",
                        start_char=start,
                        end_char=end,
                        paragraph_index=sentence.paragraph_index,
                        sentence_index=sentence.sentence_index,
                        rhetorical_unit_index=unit_index,
                        original_text=part,
                    )
                )
                cursor = max(relative_position, 0) + len(part)
                unit_index += 1
        return units
