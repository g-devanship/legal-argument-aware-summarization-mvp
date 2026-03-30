from __future__ import annotations

import pytest

from src.config import load_project_config
from src.pipeline.summarization_pipeline import LegalSummarizationPipeline


@pytest.fixture
def test_config():
    config = load_project_config()
    config.model.runtime.load_models = False
    config.model.runtime.use_heuristics_only = True
    config.model.runtime.local_files_only = True
    return config


@pytest.fixture
def pipeline(test_config):
    return LegalSummarizationPipeline(config=test_config)


@pytest.fixture
def sample_legal_text() -> str:
    return (
        "Facts: The petitioner challenged cancellation of a housing allotment after heavy flooding delayed construction. "
        "Issue: Whether the authority could cancel the allotment without notice. "
        "Arguments: Counsel for the petitioner argued that natural justice required a hearing, while the authority argued that the allotment was conditional. "
        "Statute: The court considered Article 14 and Section 21 of the General Clauses Act. "
        "Analysis: The court reasoned that a vested benefit could not be withdrawn without fair procedure. "
        "Ruling: The cancellation was set aside and the matter was remanded."
    )
