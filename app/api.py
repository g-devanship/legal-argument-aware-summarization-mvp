"""FastAPI entrypoint for the legal summarization MVP."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import EvaluateRequest, EvaluateResponse, SummarizeRequest, SummarizeResponse, UploadPdfResponse
from src.pipeline.summarization_pipeline import LegalSummarizationPipeline


def create_app(pipeline: Optional[LegalSummarizationPipeline] = None) -> FastAPI:
    active_pipeline = pipeline or LegalSummarizationPipeline()
    app = FastAPI(
        title=active_pipeline.config.app.api.title,
        version=active_pipeline.config.app.api.version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/upload-pdf", response_model=UploadPdfResponse)
    async def upload_pdf(file: UploadFile = File(...)) -> UploadPdfResponse:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF uploads are supported for this endpoint.")
        try:
            payload = await file.read()
            parsed = active_pipeline.loader.extract_text_from_pdf_bytes(payload, filename=file.filename)
            return UploadPdfResponse(text=parsed["text"], metadata=parsed["metadata"])
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/summarize", response_model=SummarizeResponse)
    async def summarize(request: SummarizeRequest) -> SummarizeResponse:
        try:
            result = active_pipeline.summarize_text(
                text=request.document_text,
                document_id=request.document_id,
                gold_summary=request.gold_summary,
            )
            return SummarizeResponse.model_validate(result)
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Summarization failed: {error}") from error

    @app.post("/evaluate", response_model=EvaluateResponse)
    async def evaluate(request: EvaluateRequest) -> EvaluateResponse:
        try:
            if request.generated_summary and request.gold_summary:
                evaluation = active_pipeline.evaluator.evaluate_summary(request.generated_summary, request.gold_summary)
                return EvaluateResponse(evaluation=evaluation.__dict__)

            result = active_pipeline.summarize_text(
                text=request.document_text or "",
                document_id=request.document_id,
                gold_summary=request.gold_summary,
            )
            return EvaluateResponse(
                evaluation=result["evaluation"] or {},
                best_summary=result["best_summary"],
            )
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Evaluation failed: {error}") from error

    return app


app = create_app()
