"""Top-level exports for the legal summarization MVP."""

from src.data.preprocessing import DataProcessor
from src.evaluation.evaluator import Evaluator
from src.pipeline.summarization_pipeline import LegalSummarizationPipeline
from src.reranking.reranker import SummaryReranker
from src.roles.classifier import RoleClassifier
from src.summarization.generator import SummaryGenerator

__all__ = [
    "DataProcessor",
    "RoleClassifier",
    "SummaryGenerator",
    "SummaryReranker",
    "Evaluator",
    "LegalSummarizationPipeline",
]
