"""Dataset and file loading helpers."""

from __future__ import annotations

import io
import json
import csv
from pathlib import Path
from typing import Any, Dict, List

from src.logger import get_logger
from src.utils import DocumentRecord, normalize_whitespace

LOGGER = get_logger(__name__)


class LegalDocumentLoader:
    """Load legal text records from local files and datasets."""

    REQUIRED_COLUMNS = {"document_id", "document_text"}

    def load_text_file(self, path: str | Path) -> DocumentRecord:
        path = Path(path)
        LOGGER.info("Loading text file from %s", path)
        text = path.read_text(encoding="utf-8")
        return DocumentRecord(document_id=path.stem, document_text=normalize_whitespace(text), metadata={"path": str(path)})

    def load_pdf_file(self, path: str | Path) -> DocumentRecord:
        path = Path(path)
        LOGGER.info("Loading PDF file from %s", path)
        with path.open("rb") as handle:
            parsed = self.extract_text_from_pdf_bytes(handle.read(), filename=path.name)
        return DocumentRecord(
            document_id=path.stem,
            document_text=parsed["text"],
            metadata={"path": str(path), **parsed["metadata"]},
        )

    def extract_text_from_pdf_bytes(self, payload: bytes, filename: str = "uploaded.pdf") -> Dict[str, Any]:
        pages: List[str] = []
        metadata: Dict[str, Any] = {"filename": filename}

        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(payload)) as pdf:
                metadata["page_count"] = len(pdf.pages)
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
        except Exception as pdfplumber_error:
            LOGGER.warning("pdfplumber extraction failed: %s", pdfplumber_error)
            try:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(payload))
                metadata["page_count"] = len(reader.pages)
                for page in reader.pages:
                    pages.append(page.extract_text() or "")
            except Exception as pypdf_error:
                LOGGER.exception("Unable to parse PDF with pdfplumber or pypdf")
                raise ValueError(
                    f"Unable to parse PDF '{filename}'. pdfplumber error: {pdfplumber_error}; pypdf error: {pypdf_error}"
                ) from pypdf_error

        text = normalize_whitespace("\n\n".join(page for page in pages if page.strip()))
        metadata["char_length"] = len(text)
        return {"text": text, "metadata": metadata}

    def load_dataset(self, path: str | Path) -> List[DocumentRecord]:
        path = Path(path)
        LOGGER.info("Loading dataset from %s", path)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                records = list(csv.DictReader(handle))
        elif suffix in {".json", ".jsonl"}:
            if suffix == ".jsonl":
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
                records = payload if isinstance(payload, list) else payload.get("records", [])
        else:
            raise ValueError(f"Unsupported dataset format: {path.suffix}")

        return [self._coerce_record(record, fallback_id=f"record-{index}") for index, record in enumerate(records)]

    def _coerce_record(self, record: Dict[str, Any], fallback_id: str) -> DocumentRecord:
        missing = self.REQUIRED_COLUMNS - record.keys()
        if missing:
            raise ValueError(f"Record missing required columns: {sorted(missing)}")

        return DocumentRecord(
            document_id=str(record.get("document_id", fallback_id)),
            document_text=normalize_whitespace(str(record["document_text"])),
            gold_summary=str(record["gold_summary"]) if record.get("gold_summary") is not None else None,
            segment_labels=record.get("segment_labels"),
            metadata={
                key: value
                for key, value in record.items()
                if key not in {"document_id", "document_text", "gold_summary", "segment_labels"}
            },
        )
