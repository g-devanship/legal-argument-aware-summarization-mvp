from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.api import create_app


def _make_pdf_bytes(text: str) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(f'BT /F1 12 Tf 72 72 Td ({text}) Tj ET'.encode('latin-1'))} >>\nstream\nBT /F1 12 Tf 72 72 Td ({text}) Tj ET\nendstream".encode(
            "latin-1"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("ascii"))
        buffer.write(obj)
        buffer.write(b"\nendobj\n")
    xref_start = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    buffer.write(f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref_start}\n%%EOF".encode("ascii"))
    return buffer.getvalue()


def test_summarize_and_evaluate_endpoints(pipeline, sample_legal_text):
    client = TestClient(create_app(pipeline))

    summarize_response = client.post(
        "/summarize",
        json={"document_text": sample_legal_text, "document_id": "api-demo"},
    )
    assert summarize_response.status_code == 200
    summarize_payload = summarize_response.json()
    assert summarize_payload["best_summary"]
    assert summarize_payload["reranking_scores"]

    evaluate_response = client.post(
        "/evaluate",
        json={
            "generated_summary": "The court remanded the matter after finding notice was missing.",
            "gold_summary": "The court set aside the cancellation for lack of notice and remanded the case.",
        },
    )
    assert evaluate_response.status_code == 200
    assert "evaluation" in evaluate_response.json()


def test_upload_pdf_endpoint(pipeline):
    client = TestClient(create_app(pipeline))
    pdf_bytes = _make_pdf_bytes("Facts: Sample legal PDF text.")
    response = client.post(
        "/upload-pdf",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "metadata" in payload
