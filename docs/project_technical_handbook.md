# Legal Argument-Aware Summarization MVP

## Purpose Of This Guide

This handbook explains the complete project in one place:

- what problem the system solves
- how the pipeline works from input to output
- what models and fallbacks are used
- how candidate summaries are generated
- how reranking works and what each score means
- what evaluation metrics are used and why they matter
- what technologies and libraries are used
- what each main class does
- what each file in the repository is responsible for

It is written as a technical explanation of the current codebase, not as a generic description of legal summarization.

## Project Overview

This project is a legal document summarization MVP for long court judgments and legal opinions. It accepts TXT or PDF documents, preprocesses and segments them, predicts rhetorical roles, generates multiple abstractive summary candidates, reranks them with argument-aware scoring, and returns the best summary with metrics and interpretable reasoning.

The project is inspired by the ACL 2023 paper on argument-aware abstractive summarization with summary reranking, but it is implemented as a practical local-first engineering system rather than a one-to-one reproduction of the paper's exact experimental setup.

## Core Problem Statement

Legal opinions are difficult to summarize because:

- they are long and often exceed the context length of standard models
- key information is distributed across facts, issue, arguments, analysis, statutes, and ruling
- legal usefulness depends not only on fluency but also on preserving the court's reasoning path
- citations, section headers, numbers, and procedural history can matter a lot

A plain summarizer may produce readable text but still miss the most important legal structure. This system tries to solve that by making summary selection aware of rhetorical and argumentative content.

## High-Level System Architecture

The high-level flow is:

1. Input ingestion
2. Text preprocessing and segmentation
3. Rhetorical-role prediction
4. Multi-candidate summary generation
5. Role-aware reranking
6. Evaluation and explainability
7. Delivery through API and Streamlit UI

In simple form:

`TXT/PDF -> Loader -> DataProcessor -> RoleClassifier -> SummaryGenerator -> SummaryReranker -> Evaluator -> API/UI`

## End-To-End Pipeline Steps

### Step 1: Input Loading

The system accepts:

- plain text files
- PDF files
- dataset records from JSON, JSONL, or CSV
- direct pasted text from the Streamlit UI or API

TXT files are read directly. PDF files are parsed using `pdfplumber` first and `pypdf` as a fallback.

Main file: `src/data/loader.py`

### Step 2: Text Normalization

The raw text is cleaned so later components receive a more stable input. The preprocessing includes:

- whitespace cleanup
- legal citation cleanup
- section header normalization
- quote and punctuation repair where possible
- encoding cleanup

Main file: `src/data/preprocessing.py`

### Step 3: Paragraph Segmentation

The normalized document is split into paragraph-level segments. Each segment keeps mapping information such as offsets or identifiers so the system can later show supporting source text for explainability.

Why it matters:

- preserves original discourse structure
- makes long documents easier to inspect
- helps chunking and source attribution

### Step 4: Sentence Segmentation

Each paragraph is split into sentence-level units. The code uses sentence splitting utilities from `src/utils.py` and preprocessing logic in `src/data/preprocessing.py`.

Why it matters:

- role labeling often works better on sentence-sized units
- candidate generation strategies may select role-focused sentences
- evaluation and explainability become easier

### Step 5: Rhetorical-Unit Segmentation

The system approximates rhetorical or argumentative units. In practice, this is a lightweight engineering approximation built on top of sentence structure and legal cue phrases rather than a full discourse parser.

Why it matters:

- finer-grained units provide better role labeling than whole paragraphs
- allows the reranker to reason about structure at a more useful granularity

### Step 6: Chunking For Long Documents

Long judgments are split into overlapping chunks.

Current config values from `configs/model_config.yaml`:

- `chunk_max_words: 850`
- `chunk_overlap_words: 120`

How it works:

- the system collects sentence or rhetorical-unit text into a chunk until it approaches the maximum word budget
- when a new chunk starts, part of the previous chunk is repeated as overlap

Why overlap is used:

- avoids losing context at chunk boundaries
- helps preserve reasoning continuity
- improves long-document summarization stability

Main file: `src/data/chunking.py`

### Step 7: Rhetorical-Role Prediction

Each rhetorical unit is assigned a role label.

Current label set:

- `facts`
- `issue`
- `arguments`
- `analysis`
- `ruling`
- `statute`
- `other`

The classifier returns:

- predicted label
- confidence score
- optional top-k probabilities
- optional rationale metadata

Main files:

- `src/roles/classifier.py`
- `src/roles/heuristics.py`
- `src/roles/labels.py`

### Step 8: Candidate Summary Generation

The system does not trust a single generated summary. It creates several candidates for the same source document using different strategies.

Main file: `src/summarization/generator.py`

### Step 9: Candidate Reranking

All candidate summaries are scored, compared, and ranked. The highest-scoring summary becomes the final output.

Main file: `src/reranking/reranker.py`

### Step 10: Evaluation

If a gold summary is available, the selected summary is evaluated automatically using ROUGE and BERTScore.

Main file: `src/evaluation/evaluator.py`

### Step 11: Delivery And Explainability

The selected summary, metrics, reranking scores, and supporting segments are returned through:

- the FastAPI backend
- the Streamlit frontend
- exports such as Markdown, JSON, and optional PDF

Main files:

- `app/api.py`
- `app/streamlit_app.py`

## Models Used In The Project

### Summarization Models

Configured in `configs/model_config.yaml`:

- preferred: `allenai/led-base-16384`
- fallback: `facebook/bart-large-cnn`
- lightweight fallback: `google/flan-t5-base`

Why these are used:

- LED is a long-context summarization model and is the best fit for long legal documents
- BART provides a strong general fallback
- FLAN-T5 is useful as a lighter fallback when resources are limited

### Role Classification Models

Configured in `configs/model_config.yaml`:

- preferred: `law-ai/InLegalBERT`
- alternative: `nlpaueb/legal-bert-base-uncased`
- lightweight fallback: `distilbert-base-uncased`

Why these are used:

- InLegalBERT and Legal-BERT are domain-specific legal encoders
- DistilBERT gives a lightweight emergency path

### Embedding Model For Reranking

- `sentence-transformers/all-MiniLM-L6-v2`

Why it is used:

- produces sentence/document embeddings efficiently
- supports semantic similarity scoring for source-summary comparison

### Do We Have A Custom Trained Model?

The codebase supports training a role classifier, but no custom fine-tuned checkpoint is bundled by default. The system works with pretrained open-source models plus heuristic fallbacks.

## Candidate Generation Strategies

Configured in `configs/app_config.yaml`:

- `baseline_full_document`
- `role_focus_facts_issue_ruling`
- `analysis_heavy`
- `chunk_merge_conservative`
- `chunk_merge_diverse`

### 1. baseline_full_document

Uses the whole normalized document as input to produce a broad summary.

Use case:

- balanced, general legal summary

### 2. role_focus_facts_issue_ruling

Constructs a role-aware input emphasizing:

- facts
- issue
- ruling

Use case:

- concise case brief style summary
- useful when the outcome and core question matter most

### 3. analysis_heavy

Gives more attention to analysis and reasoning-heavy segments.

Use case:

- legal reasoning summary
- useful when the court's logic matters more than background detail

### 4. chunk_merge_conservative

Summarizes chunk by chunk and merges the results with safer decoding settings.

Use case:

- more stable generation
- less diverse but usually more controlled output

### 5. chunk_merge_diverse

Uses a chunk-and-merge strategy with more varied decoding.

Use case:

- generates a more diverse alternative candidate
- useful for reranking because diversity gives the selector better options

Each candidate stores:

- candidate text
- generation method
- decoding parameters
- source chunks used

## Reranking: Scores, Formula, And Meaning

The reranker combines multiple signals into a final score.

Current weights from `configs/scoring_config.yaml`:

- `semantic_similarity: 0.38`
- `role_coverage: 0.26`
- `factual_proxy: 0.20`
- `readability_bonus: 0.08`
- `redundancy_penalty: 1.0`
- `length_penalty: 1.0`

### Practical Formula

The effective logic is:

`final_score = 0.38*semantic_similarity + 0.26*role_coverage + 0.20*factual_proxy + 0.08*readability_bonus - redundancy_penalty - length_penalty`

### Score Components

#### semantic_similarity

What it means:

- how well the candidate summary matches the meaning of the full source document

How it is computed:

- embedding-based similarity using sentence-transformer embeddings
- fallback methods may be used if the embedding backend is unavailable

Why it matters:

- prevents fluent but off-topic summaries

#### role_coverage

What it means:

- how well the candidate covers important rhetorical roles in the legal opinion

How it is computed:

- compares source-role distribution and summary-role coverage heuristics
- uses role importance weights

Current role importance values:

- facts: `0.14`
- issue: `0.14`
- arguments: `0.14`
- analysis: `0.20`
- ruling: `0.24`
- statute: `0.10`
- other: `0.04`

Why it matters:

- makes the system argument-aware instead of fluency-only
- especially rewards analysis and ruling coverage

#### factual_proxy

What it means:

- a practical proxy for factual consistency

How it is computed:

- overlap of numbers, legal references, citations, and other support signals

Why it matters:

- helps reduce factual drift without requiring a full factuality verifier

#### redundancy_penalty

What it means:

- penalty for repeated sentences or repeated n-grams

Current threshold:

- `redundancy_ngram_size: 3`

Why it matters:

- stops the model from padding with repetitive text

#### length_penalty

What it means:

- penalty for summaries that are too short or too long

Current thresholds:

- minimum words: `90`
- maximum words: `260`
- ideal words: `170`

Why it matters:

- keeps the summary useful and proportionate

#### readability_bonus

What it means:

- reward for sentence-length patterns that stay in a readable range

Current thresholds:

- minimum readable sentence length: `10`
- maximum readable sentence length: `32`

Why it matters:

- discourages dense, unreadable output

## Evaluation Metrics

The evaluator computes both lexical and semantic metrics.

### ROUGE-1

Definition:

- unigram overlap between generated summary and reference summary

Why it matters:

- checks whether important content words are covered

### ROUGE-2

Definition:

- bigram overlap between generated summary and reference summary

Why it matters:

- stronger than unigram overlap because it cares about short phrase structure

### ROUGE-L

Definition:

- based on longest common subsequence overlap

Why it matters:

- rewards sequence-level similarity without requiring exact word-by-word identity

### BERTScore

Definition:

- semantic similarity using contextual embeddings

Key outputs:

- Precision
- Recall
- F1

Why it matters:

- legal summaries often paraphrase rather than copy
- BERTScore is better than pure lexical metrics in those cases

## Main Classes And What They Do

### DataProcessor

Main file:

- `src/data/preprocessing.py`

Responsibilities:

- normalize legal text
- segment paragraphs
- segment sentences
- approximate rhetorical units
- build long-document chunks
- preserve mapping information for explainability

### RoleClassifier

Main file:

- `src/roles/classifier.py`

Responsibilities:

- predict rhetorical roles for one segment or many segments
- use transformer-backed inference when possible
- fall back to heuristics if needed

### SummaryGenerator

Main file:

- `src/summarization/generator.py`

Responsibilities:

- create multiple abstractive summary candidates
- choose between LED, BART, FLAN-T5, or fallback logic
- support chunk-aware and role-aware generation strategies

### SummaryReranker

Main file:

- `src/reranking/reranker.py`

Responsibilities:

- score candidates
- compute semantic similarity, role coverage, factual proxy, redundancy, length, and readability values
- return ranked candidates and reasoning metadata

### Evaluator

Main file:

- `src/evaluation/evaluator.py`

Responsibilities:

- compute ROUGE
- compute BERTScore
- generate qualitative analysis and exportable metrics

### LegalSummarizationPipeline

Main file:

- `src/pipeline/summarization_pipeline.py`

Responsibilities:

- orchestrate the full process from input text to final result
- manage progress callbacks for the UI
- coordinate preprocessing, role prediction, generation, reranking, and evaluation

## Technologies And Libraries Used

### Python

Used as the main language for:

- pipeline implementation
- APIs
- UI
- training scripts
- evaluation scripts

### PyTorch

Used for:

- loading and running transformer models
- CPU or device-aware inference

### Hugging Face Transformers

Used for:

- summarization model loading
- role classification model loading
- tokenizer/model abstractions

### sentence-transformers

Used for:

- embedding-based semantic similarity
- reranking support

### datasets

Used for:

- training data preparation and model fine-tuning workflows

### scikit-learn

Used for:

- utility functions in training/evaluation and lightweight fallbacks

### FastAPI

Used for:

- backend API endpoints
- request/response serving

### Streamlit

Used for:

- local interactive UI
- file upload, text entry, progress display, exports, and auth-driven workspace

### pdfplumber and pypdf

Used for:

- text extraction from PDF judgments and opinions

### Pydantic

Used for:

- config models
- API schemas

### PyYAML

Used for:

- YAML config loading

### rouge-score and bert-score

Used for:

- evaluation metrics

### reportlab

Used for:

- PDF report generation in the app
- PDF generation utilities such as this handbook builder

### pytest

Used for:

- automated tests across the pipeline and app

## API And UI Summary

### FastAPI Endpoints

Implemented in `app/api.py`:

- `GET /health`
- `POST /upload-pdf`
- `POST /summarize`
- `POST /evaluate`

### Streamlit UI

Implemented in `app/streamlit_app.py`:

- local login and registration
- persistent session support across refresh
- TXT/PDF input
- live pipeline status board
- final summary display
- metrics
- exports

## File-By-File Guide

This section explains the responsibility of the important files in the repository.

### Root Files

#### `.env.example`

Template for environment variables and runtime toggles.

#### `.gitignore`

Prevents virtual environments, caches, logs, and generated artifacts from being committed.

#### `Dockerfile`

Container definition for packaging and running the application.

#### `README.md`

Primary project documentation covering overview, setup, architecture, usage, limitations, and paper alignment.

#### `requirements.txt`

Dependency list for the project.

### Streamlit Runtime Config

#### `.streamlit/config.toml`

Local Streamlit runtime configuration file.

### App Layer

#### `app/__init__.py`

Marks `app` as a Python package.

#### `app/api.py`

FastAPI application entrypoint with the health, upload, summarize, and evaluate endpoints.

#### `app/schemas.py`

Pydantic request and response schemas for the API.

#### `app/streamlit_app.py`

Main Streamlit UI:

- sign-in flow
- persistent sessions
- file intake
- pipeline progress board
- summary display
- export actions

### Config Files

#### `configs/app_config.yaml`

Application-level config:

- API title and port
- UI layout
- auth settings
- generation strategies
- explainability settings

#### `configs/model_config.yaml`

Model/runtime config:

- device
- heuristics-only flags
- summarization models
- role models
- embeddings model
- training hyperparameters

#### `configs/scoring_config.yaml`

Reranking and length/readability config:

- metric weights
- role importance
- thresholds

### Demo And Sample Data

#### `data/demo/indian_judgment_sample.txt`

Sample Indian judgment text used for demos.

#### `data/demo/us_opinion_sample.txt`

Sample U.S. legal opinion text used for demos.

#### `data/demo/README.md`

Notes about demo data usage.

#### `data/samples/legal_samples.csv`

Small sample dataset for experiments, preprocessing, or evaluation.

#### `data/samples/legal_samples.json`

JSON version of the small sample dataset.

### Processed Runtime Artifacts

#### `data/processed/.gitkeep`

Keeps the processed folder in version control.

#### `data/processed/app_users.db`

Local SQLite auth database used by the Streamlit app.

#### `data/processed/demo_result_india.json`

Saved demo pipeline output for an Indian sample.

#### `data/processed/demo_result_model_stack.json`

Saved demo output from a model-backed run.

#### `data/processed/streamlit_*.log`

Runtime log files produced during local Streamlit runs. These are operational artifacts, not core source files.

### Notebook

#### `notebooks/exploratory_experiments.ipynb`

Notebook for quick experimentation with loading, preprocessing, generation, reranking, and evaluation.

### Scripts

#### `scripts/build_presentation.py`

Builds the project presentation deck.

#### `scripts/evaluate_model.py`

Runs batch evaluation and exports metrics.

#### `scripts/preprocess_data.py`

Preprocesses input datasets into segmented output.

#### `scripts/run_demo.py`

Runs the end-to-end pipeline on a sample input file.

#### `scripts/train_role_classifier.py`

Fine-tunes a rhetorical-role classifier when labeled or weak-labeled data is available.

### Core Source Package

#### `src/__init__.py`

Marks `src` as a Python package.

#### `src/config.py`

Loads YAML configuration and defines typed config models with Pydantic.

#### `src/logger.py`

Shared logging setup.

#### `src/utils.py`

Shared data structures and helpers such as:

- document record containers
- segment containers
- candidate score containers
- evaluation metric containers
- text and similarity helpers

### Auth Package

#### `src/auth/__init__.py`

Exports auth classes.

#### `src/auth/service.py`

Local authentication and session service:

- user registration
- password hashing
- login verification
- persistent session creation and revocation
- SQLite-backed account store

### Data Package

#### `src/data/__init__.py`

Package marker for data utilities.

#### `src/data/chunking.py`

Chunk-building logic for long documents.

#### `src/data/loader.py`

File and dataset loading:

- TXT
- PDF
- CSV
- JSON
- JSONL

#### `src/data/preprocessing.py`

Main data processing logic:

- normalization
- segmentation
- rhetorical-unit approximation
- progress callbacks

### Evaluation Package

#### `src/evaluation/__init__.py`

Package marker for evaluation utilities.

#### `src/evaluation/evaluator.py`

Implements:

- ROUGE
- BERTScore
- qualitative analysis
- export-friendly evaluation structures

### Pipeline Package

#### `src/pipeline/__init__.py`

Package marker for pipeline utilities.

#### `src/pipeline/summarization_pipeline.py`

Main orchestrator that binds together loader, preprocessing, classifier, generator, reranker, and evaluator.

### Reranking Package

#### `src/reranking/__init__.py`

Package marker for reranking utilities.

#### `src/reranking/reranker.py`

Candidate scoring and ranking logic.

### Roles Package

#### `src/roles/__init__.py`

Package marker for role classification utilities.

#### `src/roles/classifier.py`

Role prediction using transformer-backed or heuristic-supported logic.

#### `src/roles/heuristics.py`

Weak-labeling and fallback rule system using legal cue phrases, headers, regex, and keyword dictionaries.

#### `src/roles/labels.py`

Role labels, role descriptions, and role-priority metadata.

### Summarization Package

#### `src/summarization/__init__.py`

Package marker for summarization utilities.

#### `src/summarization/candidates.py`

Candidate summary construction helpers.

#### `src/summarization/generator.py`

Main summary generation engine:

- model loading
- fallback logic
- role-aware input variants
- chunk-and-merge strategies

#### `src/summarization/prompts.py`

Role-aware prompt and input-construction helpers used during candidate generation.

### Tests

#### `tests/conftest.py`

Pytest fixtures and test pipeline config.

#### `tests/test_api.py`

Tests API endpoint behavior.

#### `tests/test_auth.py`

Tests registration, authentication, and persistent-session behavior.

#### `tests/test_generator.py`

Tests candidate generation behavior.

#### `tests/test_loader.py`

Tests TXT/PDF/dataset loading behavior.

#### `tests/test_preprocessing.py`

Tests normalization and segmentation behavior.

#### `tests/test_reranker.py`

Tests reranking and score logic.

#### `tests/test_roles.py`

Tests rhetorical-role prediction behavior.

### Docs

#### `docs/legal_argument_aware_summarization_mvp_presentation.pptx`

Project presentation deck.

#### `docs/legal_argument_aware_summarization_mvp_presentation_notes.md`

Speaker notes for the presentation deck.

## What Is Faithful To The Research Idea

The code is faithful to the following high-level ideas from the source paper:

- long legal opinions need structure-aware handling
- multiple candidate summaries are better than blindly trusting a single decode
- reranking should use argument or rhetorical information
- long-document chunking is important

## What Is A Pragmatic Engineering Adaptation

The following are MVP-oriented engineering decisions:

- hybrid role classification rather than an exact paper-specific supervised pipeline
- practical faithfulness proxies instead of a research-only scoring function
- local-first UI, API, exports, auth, scripts, tests, and Docker support
- CPU-safe fallback behavior

## Current Strengths

- realistic runnable architecture
- open-source-only model stack
- fallback path when large models are unavailable
- modular codebase
- explainability support
- API plus UI
- testing and configuration support

## Current Limitations

- not an exact paper replication
- LED and other large models can be slow on CPU
- role quality improves when a dedicated fine-tuned checkpoint is available
- PDF quality depends on source formatting

## Best Next Improvements

- train a stronger rhetorical-role classifier on richer legal annotations
- add stronger legal factuality and citation-grounding checks
- benchmark on larger legal summarization datasets
- improve PDF layout understanding
- add richer jurisdiction-specific rules

## One-Sentence Summary

This project reads a long legal document, understands its rhetorical structure, generates several abstractive summaries, reranks them with argument-aware scoring, and returns the best summary with evidence and metrics.
