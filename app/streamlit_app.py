"""Streamlit UI for the legal summarization MVP."""

from __future__ import annotations

import html
import io
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
import streamlit.components.v1 as components

from src.auth import AuthService, AuthValidationError
from src.pipeline.summarization_pipeline import LegalSummarizationPipeline

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_FILES = {
    "Indian judgment sample": PROJECT_ROOT / "data" / "demo" / "indian_judgment_sample.txt",
    "U.S. opinion sample": PROJECT_ROOT / "data" / "demo" / "us_opinion_sample.txt",
}
ROLE_COLORS = {
    "facts": "#6F95B6",
    "issue": "#C88778",
    "arguments": "#C9AD7A",
    "analysis": "#D9B36C",
    "ruling": "#5FB39F",
    "statute": "#87A8C8",
    "other": "#8B96A6",
}
PROCESS_STAGES = [
    ("normalize", "Normalize Source", "Repair whitespace, citations, and headers."),
    ("paragraphs", "Segment Paragraphs", "Preserve paragraph boundaries and offsets."),
    ("sentences", "Split Sentences", "Build legal-domain sentence units."),
    ("rhetorical_units", "Map Rhetorical Units", "Approximate argument-aware segments."),
    ("chunking", "Build Chunks", "Assemble long-context summarization windows."),
    ("role_prediction", "Predict Roles", "Assign rhetorical labels and confidence."),
    ("candidate_generation", "Generate Candidates", "Create multiple abstractive summaries."),
    ("reranking", "Rerank Candidates", "Score coverage, similarity, and redundancy."),
    ("evaluation", "Evaluate Output", "Compute metrics when gold text is available."),
]
PROCESS_STAGE_LABELS = {stage_id: label for stage_id, label, _ in PROCESS_STAGES}


@st.cache_resource
def get_services() -> tuple[LegalSummarizationPipeline, AuthService]:
    pipeline = LegalSummarizationPipeline()
    auth_path = PROJECT_ROOT / pipeline.config.app.auth.users_db_path
    auth_service = AuthService(auth_path, min_password_length=pipeline.config.app.auth.min_password_length)
    return pipeline, auth_service


def initialize_state() -> None:
    defaults = {
        "auth_user": None,
        "auth_session_token": None,
        "pending_auth_cookie": None,
        "clear_auth_cookie": False,
        "latest_result": None,
        "latest_markdown_report": "",
        "document_editor": "",
        "document_id_input": "streamlit-document",
        "active_demo_choice": None,
        "active_uploaded_name": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root{--bg0:#071019;--bg1:#0b1522;--surface:rgba(13,22,34,.92);--surface2:rgba(18,30,45,.96);--border:rgba(130,150,178,.18);--border2:rgba(130,150,178,.28);--text:#edf2f8;--soft:#a4b0bf;--muted:#7e8b9c;--accent:#d4b067;--accent2:#f2cb84;--shadow:0 22px 54px rgba(0,0,0,.28);}
        .stApp{background:radial-gradient(circle at top left,rgba(212,176,103,.10),transparent 20%),radial-gradient(circle at 85% 15%,rgba(111,149,182,.13),transparent 22%),radial-gradient(circle at bottom right,rgba(95,179,159,.10),transparent 20%),linear-gradient(180deg,var(--bg0) 0%,var(--bg1) 100%);color:var(--text);}
        .block-container{max-width:1280px;padding-top:1.6rem;padding-bottom:3rem;}
        [data-testid="stHeader"]{background:transparent;}
        [data-testid="stSidebar"]{background:linear-gradient(180deg,rgba(8,14,22,.98) 0%,rgba(10,18,28,.98) 100%);border-right:1px solid rgba(130,150,178,.16);}
        [data-testid="stSidebar"] *,.stMarkdown,.stMarkdown p,.stMarkdown li,h1,h2,h3,h4,h5,h6,p,li,label,span,div{color:var(--text);}
        .stButton>button,.stDownloadButton>button{border-radius:14px;border:1px solid rgba(212,176,103,.24);background:linear-gradient(180deg,#d8b56e 0%,#b99656 100%);color:#08111a;font-weight:700;box-shadow:0 14px 32px rgba(0,0,0,.20);}
        .stButton>button:hover,.stDownloadButton>button:hover{border-color:rgba(242,203,132,.42);background:linear-gradient(180deg,#e3c17c 0%,#c9a465 100%);}
        .stButton>button[kind="secondary"]{background:linear-gradient(180deg,rgba(21,32,46,.96),rgba(14,24,36,.96));color:var(--text);border-color:var(--border);box-shadow:none;}
        .stTextInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"]>div,.stMultiSelect div[data-baseweb="select"]>div,.stFileUploader>section{background:rgba(15,24,37,.94);border:1px solid rgba(130,150,178,.18);border-radius:14px;color:var(--text);}
        .stTabs [data-baseweb="tab-list"]{gap:.45rem;}.stTabs [data-baseweb="tab"]{background:rgba(18,29,42,.92);border-radius:12px 12px 0 0;color:var(--soft);padding:.62rem .92rem;border:1px solid transparent;}.stTabs [aria-selected="true"]{background:rgba(23,36,52,.98);color:var(--text);border-color:var(--border2);}
        [data-testid="stMetric"],[data-testid="stAlert"],.glass-panel,.auth-card,.metric-card,.candidate-box,.summary-box,.process-shell,.process-header,.process-log-shell{background:var(--surface);border:1px solid var(--border);box-shadow:var(--shadow);}
        [data-testid="stMetric"]{border-radius:18px;padding:.8rem .9rem;}
        [data-testid="stProgressBar"] > div > div{background:linear-gradient(90deg,#d4b067 0%,#6f95b6 52%,#5fb39f 100%) !important;}
        .hero-shell{background:radial-gradient(circle at top right,rgba(212,176,103,.16),transparent 28%),linear-gradient(145deg,rgba(13,22,34,.96),rgba(18,31,47,.98));border:1px solid rgba(212,176,103,.18);border-radius:28px;padding:1.8rem 1.75rem 1.3rem;box-shadow:0 28px 70px rgba(0,0,0,.34);margin-bottom:1.15rem;}
        .hero-shell h1{margin:0;font-size:2.2rem;line-height:1.08;font-family:"Palatino Linotype","Book Antiqua",Palatino,serif;}
        .hero-shell p{margin:.8rem 0 0 0;color:var(--soft);line-height:1.68;max-width:56rem;}
        .glass-panel{border-radius:22px;padding:1.1rem 1.2rem;margin-bottom:1rem;}.auth-card{border-radius:24px;padding:1.2rem 1.25rem 1rem;}
        .auth-note,.workspace-note{background:linear-gradient(180deg,rgba(19,31,45,.98),rgba(14,24,37,.98));border:1px solid rgba(212,176,103,.16);border-left:4px solid var(--accent);border-radius:18px;padding:.95rem 1rem;color:var(--soft);}
        .auth-note strong,.workspace-note strong{color:var(--text);}
        .metric-card{border-radius:20px;padding:1rem;min-height:118px;}.metric-label{color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-size:.77rem;margin-bottom:.4rem;}.metric-value{font-weight:700;font-size:1.95rem;line-height:1.05;}.metric-sub{margin-top:.35rem;color:var(--soft);font-size:.9rem;}
        .summary-box{background:linear-gradient(180deg,rgba(14,23,35,.98),rgba(18,31,45,.96));border-left:6px solid var(--accent);border-radius:22px;padding:1.25rem 1.3rem 1.05rem;margin-bottom:1rem;}
        .summary-box h3{margin:0 0 .65rem 0;font-family:"Palatino Linotype","Book Antiqua",Palatino,serif;}
        .chip{display:inline-block;padding:.36rem .72rem;border-radius:999px;margin:.15rem .35rem .15rem 0;background:rgba(20,33,48,.96);border:1px solid rgba(212,176,103,.18);font-size:.82rem;}
        .candidate-box{background:var(--surface2);border-radius:18px;padding:1rem;margin-bottom:.9rem;}
        .role-pill{display:inline-block;padding:.24rem .62rem;border-radius:999px;color:white;font-size:.75rem;letter-spacing:.04em;margin-right:.35rem;margin-bottom:.3rem;box-shadow:inset 0 0 0 1px rgba(255,255,255,.12);}
        .small-heading{color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-size:.78rem;margin-bottom:.4rem;}
        .profile-card{background:radial-gradient(circle at top right,rgba(212,176,103,.14),transparent 35%),linear-gradient(165deg,rgba(11,18,29,.98),rgba(16,27,40,.98));border-radius:22px;padding:1rem 1rem .95rem;color:var(--text);border:1px solid rgba(212,176,103,.16);box-shadow:0 18px 44px rgba(0,0,0,.24);}
        .profile-card p{margin:.35rem 0 0 0;color:var(--soft);}
        .status-strip{display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-bottom:.8rem;}.status-pill{display:inline-flex;align-items:center;gap:.55rem;padding:.48rem .82rem;border-radius:999px;background:rgba(18,30,45,.96);border:1px solid rgba(212,176,103,.18);font-size:.84rem;}
        .pulse-dot{width:.62rem;height:.62rem;border-radius:50%;background:var(--accent2);box-shadow:0 0 0 rgba(242,203,132,.45);animation:pulse 1.7s infinite;}
        .process-shell,.process-header,.process-log-shell{border-radius:24px;padding:1.05rem 1.1rem;margin-bottom:.9rem;overflow:hidden;}.process-kicker,.log-heading{color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-size:.74rem;}.process-title{margin:.15rem 0 0 0;font-size:1.12rem;font-weight:700;}.process-subtitle{margin:.35rem 0 0 0;color:var(--soft);line-height:1.6;}
        .stage-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;margin-top:1rem;}.stage-card{border-radius:18px;padding:.9rem .9rem .85rem;background:rgba(14,24,37,.88);border:1px solid rgba(130,150,178,.14);}
        .stage-card.running{border-color:rgba(111,149,182,.42);box-shadow:0 0 0 1px rgba(111,149,182,.10),0 18px 32px rgba(4,9,15,.24);transform:translateY(-1px);}.stage-card.completed{border-color:rgba(95,179,159,.34);}.stage-card.skipped{border-color:rgba(212,176,103,.24);}.stage-card.failed{border-color:rgba(200,135,120,.34);background:rgba(40,23,25,.86);}.stage-card.pending{opacity:.72;}
        .stage-row{display:flex;align-items:start;justify-content:space-between;gap:.75rem;}.stage-name{font-size:.94rem;font-weight:700;}.stage-badge{font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;padding:.28rem .52rem;border-radius:999px;border:1px solid rgba(130,150,178,.16);color:var(--soft);}
        .stage-badge.running{background:rgba(111,149,182,.18);color:#bed7ef;}.stage-badge.completed{background:rgba(95,179,159,.18);color:#bce9df;}.stage-badge.skipped{background:rgba(201,173,122,.18);color:#e7ce9d;}.stage-badge.failed{background:rgba(200,135,120,.18);color:#efb4aa;}
        .stage-desc{margin-top:.42rem;color:var(--soft);font-size:.88rem;line-height:1.52;}.stage-meta{margin-top:.42rem;color:var(--muted);font-size:.78rem;}
        .log-shell{margin-top:1rem;}.log-item{padding:.75rem .85rem;border-radius:16px;border:1px solid rgba(130,150,178,.14);background:rgba(14,24,37,.84);margin-bottom:.5rem;}.log-title{display:flex;align-items:center;justify-content:space-between;gap:.7rem;font-size:.84rem;font-weight:700;}.log-message{margin-top:.3rem;color:var(--soft);font-size:.84rem;line-height:1.55;}
        @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(242,203,132,.42);}70%{box-shadow:0 0 0 12px rgba(242,203,132,0);}100%{box-shadow:0 0 0 0 rgba(242,203,132,0);}}
        @keyframes shimmer{0%{background-position:0% 50%;}100%{background-position:200% 50%;}}
        @media (max-width:980px){.stage-grid{grid-template-columns:1fr;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, subtext: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{html.escape(label)}</div>
            <div class="metric-value">{html.escape(value)}</div>
            <div class="metric-sub">{html.escape(subtext)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_markdown_report(result: Dict[str, Any]) -> str:
    lines = [f"# Legal Summary: {result['document_id']}", "", "## Best Summary", result["best_summary"], "", "## Runtime Info"]
    for key, value in result.get("runtime_info", {}).items():
        lines.append(f"- **{key}**: {value}")
    lines.extend(["", "## Selection Reasoning"])
    for reason in result["qualitative_analysis"].get("selection_explanation", []):
        lines.append(f"- {reason}")
    lines.extend(["", "## Top Supporting Segments"])
    for segment in result["qualitative_analysis"].get("key_legal_segments", []):
        lines.append(f"- ({segment['score']}) {segment['text']}")
    return "\n".join(lines)


def build_pdf_report(markdown_text: str) -> Optional[bytes]:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError:
        return None

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    _, height = letter
    y = height - 50
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip() or " "
        for chunk in [line[index : index + 95] for index in range(0, len(line), 95)] or [" "]:
            pdf.drawString(40, y, chunk)
            y -= 14
            if y < 50:
                pdf.showPage()
                y = height - 50
    pdf.save()
    buffer.seek(0)
    return buffer.read()


def set_demo_document(choice: str) -> None:
    path = DEMO_FILES[choice]
    st.session_state["document_editor"] = path.read_text(encoding="utf-8")
    st.session_state["document_id_input"] = path.stem
    st.session_state["active_demo_choice"] = choice


def set_uploaded_document(pipeline: LegalSummarizationPipeline, uploaded_file: Any) -> None:
    if uploaded_file.name.lower().endswith(".pdf"):
        parsed = pipeline.loader.extract_text_from_pdf_bytes(uploaded_file.getvalue(), filename=uploaded_file.name)
        st.session_state["document_editor"] = parsed["text"]
    else:
        st.session_state["document_editor"] = uploaded_file.getvalue().decode("utf-8")
    st.session_state["document_id_input"] = uploaded_file.name.rsplit(".", 1)[0]
    st.session_state["active_uploaded_name"] = uploaded_file.name


def reset_workspace() -> None:
    st.session_state["latest_result"] = None
    st.session_state["latest_markdown_report"] = ""


def _cookie_script(cookie_name: str, token: Optional[str], max_age_seconds: int) -> str:
    if token:
        cookie_assignment = (
            f"{cookie_name}={token}; path=/; max-age={max_age_seconds}; SameSite=Lax"
        )
    else:
        cookie_assignment = f"{cookie_name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; max-age=0; SameSite=Lax"
    return f"""
    <script>
    document.cookie = {json.dumps(cookie_assignment)};
    </script>
    """


def render_auth_cookie_bridge(cookie_name: str, duration_days: int) -> None:
    pending_token = st.session_state.get("pending_auth_cookie")
    should_clear = st.session_state.get("clear_auth_cookie", False)
    if pending_token is None and not should_clear:
        return

    max_age_seconds = max(duration_days, 1) * 24 * 60 * 60
    components.html(
        _cookie_script(cookie_name, None if should_clear else pending_token, max_age_seconds),
        height=0,
        width=0,
    )
    st.session_state["pending_auth_cookie"] = None
    st.session_state["clear_auth_cookie"] = False


def hydrate_auth_from_cookie(auth_service: AuthService, cookie_name: str) -> None:
    if st.session_state.get("auth_user"):
        if not st.session_state.get("auth_session_token"):
            st.session_state["auth_session_token"] = st.context.cookies.get(cookie_name)
        return

    cookie_token = st.context.cookies.get(cookie_name)
    if not cookie_token:
        return

    user = auth_service.get_user_by_session_token(cookie_token)
    if user is None:
        st.session_state["clear_auth_cookie"] = True
        st.session_state["auth_session_token"] = None
        return

    st.session_state["auth_user"] = asdict(user)
    st.session_state["auth_session_token"] = cookie_token


def sign_out(auth_service: AuthService) -> None:
    session_token = st.session_state.get("auth_session_token")
    if session_token:
        auth_service.revoke_session(session_token)
    st.session_state["auth_user"] = None
    st.session_state["auth_session_token"] = None
    st.session_state["pending_auth_cookie"] = None
    st.session_state["clear_auth_cookie"] = True
    reset_workspace()
    st.rerun()


def render_backend_chips(runtime_info: Dict[str, Any]) -> None:
    chips = []
    for label, value in runtime_info.items():
        chips.append(f'<span class="chip"><strong>{html.escape(str(label))}</strong>: {html.escape(str(value))}</span>')
    if chips:
        st.markdown("".join(chips), unsafe_allow_html=True)


def _stage_badge(state: str) -> str:
    return {
        "running": "Live",
        "completed": "Done",
        "skipped": "Skipped",
        "failed": "Failed",
        "pending": "Queued",
    }.get(state, "Queued")


def _stage_meta(stage_id: str, payload: Dict[str, Any]) -> str:
    if stage_id == "normalize" and payload.get("character_count") is not None:
        return f"{payload['character_count']} normalized characters"
    if stage_id == "paragraphs" and payload.get("paragraph_count") is not None:
        return f"{payload['paragraph_count']} paragraphs indexed"
    if stage_id == "sentences" and payload.get("sentence_count") is not None:
        return f"{payload['sentence_count']} sentences prepared"
    if stage_id == "rhetorical_units" and payload.get("rhetorical_unit_count") is not None:
        return f"{payload['rhetorical_unit_count']} rhetorical units mapped"
    if stage_id == "chunking" and payload.get("chunk_count") is not None:
        return f"{payload['chunk_count']} long-context chunks built"
    if stage_id == "role_prediction" and payload.get("prediction_count") is not None:
        return f"{payload['prediction_count']} labels scored"
    if stage_id == "candidate_generation" and payload.get("candidate_count") is not None:
        return f"{payload['candidate_count']} candidates available"
    if stage_id == "reranking" and payload.get("scored_candidate_count") is not None:
        return f"{payload['scored_candidate_count']} candidates reranked"
    if payload.get("backend"):
        return f"Backend: {payload['backend']}"
    return ""


def render_processing_board(
    placeholder: Any,
    stage_states: Dict[str, str],
    stage_payloads: Dict[str, Dict[str, Any]],
    activity_log: list[Dict[str, str]],
    headline: str,
    status_text: str,
) -> None:
    completed_count = sum(1 for stage_id, _, _ in PROCESS_STAGES if stage_states.get(stage_id) == "completed")
    running_stage = next((stage_id for stage_id, _, _ in PROCESS_STAGES if stage_states.get(stage_id) == "running"), None)
    total_stages = len(PROCESS_STAGES)
    if running_stage:
        progress_ratio = min(0.98, (completed_count + 0.55) / total_stages)
    elif all(stage_states.get(stage_id) in {"completed", "skipped"} for stage_id, _, _ in PROCESS_STAGES):
        progress_ratio = 1.0
    else:
        progress_ratio = completed_count / total_stages

    active_label = PROCESS_STAGE_LABELS.get(running_stage, "Awaiting run")
    pill_label = "Pipeline live" if running_stage else "Workspace ready"
    with placeholder.container():
        st.markdown(
            f"""
            <div class="process-header">
                <div class="status-strip">
                    <div>
                        <div class="process-kicker">Live Pipeline Activity</div>
                        <div class="process-title">{html.escape(headline)}</div>
                    </div>
                    <div class="status-pill"><span class="pulse-dot"></span><span>{html.escape(pill_label)} | {html.escape(active_label)}</span></div>
                </div>
                <div class="process-subtitle">{html.escape(status_text)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(progress_ratio)

        for row_start in range(0, len(PROCESS_STAGES), 2):
            columns = st.columns(2, gap="small")
            for column, (stage_id, label, description) in zip(columns, PROCESS_STAGES[row_start : row_start + 2]):
                state = stage_states.get(stage_id, "pending")
                payload = stage_payloads.get(stage_id, {})
                meta = _stage_meta(stage_id, payload) or description
                with column:
                    st.markdown(
                        f"""
                        <div class="stage-card {html.escape(state)}">
                            <div class="stage-row">
                                <div class="stage-name">{html.escape(label)}</div>
                                <div class="stage-badge {html.escape(state)}">{html.escape(_stage_badge(state))}</div>
                            </div>
                            <div class="stage-desc">{html.escape(payload.get("message", description))}</div>
                            <div class="stage-meta">{html.escape(meta)}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        st.markdown(
            """
            <div class="process-log-shell">
                <div class="log-heading">Recent Events</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        recent_items = activity_log[-4:] or [
            {
                "stage": "Workspace",
                "state": "ready",
                "message": "Load a document to watch chunking, role prediction, and generation update live.",
            }
        ]
        for item in recent_items:
            st.markdown(
                f"""
                <div class="log-item">
                    <div class="log-title">
                        <span>{html.escape(item['stage'])}</span>
                        <span>{html.escape(item['state'].title())}</span>
                    </div>
                    <div class="log-message">{html.escape(item['message'])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _snapshot_processing_state_from_result(
    result: Dict[str, Any],
) -> tuple[Dict[str, str], Dict[str, Dict[str, Any]], list[Dict[str, str]]]:
    segmented = result.get("segmented_text", {})
    runtime_info = result.get("runtime_info", {})
    candidates = result.get("generated_summary_candidates", [])

    stage_states = {stage_id: "completed" for stage_id, _, _ in PROCESS_STAGES}
    stage_payloads = {
        "normalize": {"message": "Source normalization complete."},
        "paragraphs": {"message": "Paragraph boundaries preserved for explainability.", "paragraph_count": len(segmented.get("paragraphs", []))},
        "sentences": {"message": "Sentence-level segments are ready for inspection.", "sentence_count": len(segmented.get("sentences", []))},
        "rhetorical_units": {"message": "Argument-aware units are available.", "rhetorical_unit_count": len(segmented.get("rhetorical_units", []))},
        "chunking": {"message": "Long-context chunks are prepared.", "chunk_count": len(segmented.get("chunks", []))},
        "role_prediction": {
            "message": "Rhetorical role inference completed.",
            "prediction_count": len(result.get("predicted_roles", [])),
            "backend": runtime_info.get("role_backend", "unknown"),
        },
        "candidate_generation": {
            "message": "Candidate summaries were generated successfully.",
            "candidate_count": len(candidates),
            "backend": runtime_info.get("summarization_backend", "unknown"),
        },
        "reranking": {
            "message": "Candidates were reranked with argument-aware scoring.",
            "scored_candidate_count": len(result.get("reranking_scores", [])),
            "backend": runtime_info.get("reranker_backend", "unknown"),
        },
        "evaluation": {"message": "Evaluation metrics are available." if result.get("evaluation") else "Evaluation skipped because no gold summary was supplied."},
    }
    if not result.get("evaluation"):
        stage_states["evaluation"] = "skipped"

    activity_log = [
        {"stage": "Role Prediction", "state": "completed", "message": stage_payloads["role_prediction"]["message"]},
        {"stage": "Candidate Generation", "state": "completed", "message": stage_payloads["candidate_generation"]["message"]},
        {"stage": "Reranking", "state": "completed", "message": stage_payloads["reranking"]["message"]},
        {"stage": "Evaluation", "state": stage_states["evaluation"], "message": stage_payloads["evaluation"]["message"]},
    ]
    return stage_states, stage_payloads, activity_log


def run_pipeline_with_feedback(
    pipeline: LegalSummarizationPipeline,
    document_text: str,
    document_id: str,
    gold_summary: Optional[str],
    placeholder: Any,
) -> Dict[str, Any]:
    stage_states = {stage_id: "pending" for stage_id, _, _ in PROCESS_STAGES}
    stage_payloads: Dict[str, Dict[str, Any]] = {}
    activity_log: list[Dict[str, str]] = [{"stage": "Workspace", "state": "running", "message": "Preparing the legal analysis pipeline."}]
    render_processing_board(
        placeholder,
        stage_states,
        stage_payloads,
        activity_log,
        headline="Preparing Analysis",
        status_text="Initializing the document workflow and waiting for the first active stage.",
    )

    def on_progress(stage: str, state: str, payload: Dict[str, Any]) -> None:
        stage_states[stage] = state
        stage_payloads[stage] = payload
        activity_log.append(
            {
                "stage": PROCESS_STAGE_LABELS.get(stage, stage.replace("_", " ").title()),
                "state": state,
                "message": payload.get("message", ""),
            }
        )
        current_label = PROCESS_STAGE_LABELS.get(stage, stage.replace("_", " ").title())
        render_processing_board(
            placeholder,
            stage_states,
            stage_payloads,
            activity_log,
            headline=f"{current_label} In Motion",
            status_text=payload.get("message", "Processing the latest legal submission."),
        )

    try:
        result = pipeline.summarize_text(
            document_text,
            document_id=document_id,
            gold_summary=gold_summary,
            progress_callback=on_progress,
        )
    except Exception as error:
        running_stage = next((stage for stage, state in stage_states.items() if state == "running"), None)
        if running_stage:
            stage_states[running_stage] = "failed"
            stage_payloads[running_stage] = {"message": str(error)}
        activity_log.append({"stage": "Pipeline", "state": "failed", "message": str(error)})
        render_processing_board(
            placeholder,
            stage_states,
            stage_payloads,
            activity_log,
            headline="Pipeline Interrupted",
            status_text="An error occurred while processing the document.",
        )
        raise

    render_processing_board(
        placeholder,
        stage_states,
        stage_payloads,
        activity_log,
        headline="Analysis Complete",
        status_text="Chunking, role prediction, generation, and reranking are ready for review.",
    )
    return result


def render_auth_screen(auth_service: AuthService, session_duration_days: int) -> None:
    st.title("Legal Document Summarization")
    st.caption("Sign in to upload a legal document, run the pipeline, and view the final summary.")

    left_spacer, auth_col, right_spacer = st.columns([0.7, 1.1, 0.7], gap="large")
    with auth_col:
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        auth_tabs = st.tabs(["Sign In", "Create Account"])

        with auth_tabs[0]:
            with st.form("sign_in_form", clear_on_submit=False):
                email = st.text_input("Email", placeholder="name@example.com", key="sign_in_email")
                password = st.text_input("Password", type="password", placeholder="Enter your password", key="sign_in_password")
                submitted = st.form_submit_button("Secure Sign In", use_container_width=True, type="primary")
            if submitted:
                try:
                    user = auth_service.authenticate(email, password)
                    if user is None:
                        st.error("Email or password is incorrect.")
                    else:
                        session_token = auth_service.create_session(user.user_id, duration_days=session_duration_days)
                        st.session_state["auth_user"] = asdict(user)
                        st.session_state["auth_session_token"] = session_token
                        st.session_state["pending_auth_cookie"] = session_token
                        st.rerun()
                except AuthValidationError as error:
                    st.error(str(error))

        with auth_tabs[1]:
            with st.form("register_form", clear_on_submit=False):
                full_name = st.text_input("Full name", placeholder="Your name", key="register_full_name")
                email = st.text_input("Work email", placeholder="name@example.com", key="register_email")
                password = st.text_input("Password", type="password", placeholder="Create a password", key="register_password")
                confirm_password = st.text_input("Confirm password", type="password", placeholder="Repeat your password", key="register_confirm_password")
                submitted = st.form_submit_button("Create Secure Account", use_container_width=True)
            if submitted:
                if password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    try:
                        user = auth_service.register_user(email=email, password=password, full_name=full_name)
                        session_token = auth_service.create_session(user.user_id, duration_days=session_duration_days)
                        st.session_state["auth_user"] = asdict(user)
                        st.session_state["auth_session_token"] = session_token
                        st.session_state["pending_auth_cookie"] = session_token
                        st.rerun()
                    except AuthValidationError as error:
                        st.error(str(error))

        st.markdown("</div>", unsafe_allow_html=True)


def render_summary_panel(result: Dict[str, Any]) -> None:
    st.markdown(
        f"""
        <div class="summary-box">
            <h3>Selected Summary</h3>
            <div>{html.escape(result['best_summary'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_primary_result_view(result: Dict[str, Any]) -> None:
    evaluation = result.get("evaluation")
    scores = result.get("reranking_scores", [])
    best_score = next((score for score in scores if score["candidate_id"] == result.get("best_candidate_id")), {})

    summary_metrics = [
        ("Summary Words", str(len(result.get("best_summary", "").split())), "Length of the selected summary"),
        ("Reranker Score", f"{best_score.get('final_score', 0.0):.3f}", "Final selection score"),
        ("Best Candidate", result.get("best_candidate_id") or "-", "Selected candidate"),
    ]
    summary_metric_columns = st.columns(3)
    for column, (label, value, subtext) in zip(summary_metric_columns, summary_metrics):
        with column:
            render_metric_card(label, value, subtext)

    render_summary_panel(result)

    if evaluation:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown('<div class="small-heading">Evaluation</div>', unsafe_allow_html=True)
        eval_cols = st.columns(3)
        with eval_cols[0]:
            st.metric("ROUGE-1", f"{evaluation['rouge_1']:.3f}")
        with eval_cols[1]:
            st.metric("ROUGE-2", f"{evaluation['rouge_2']:.3f}")
        with eval_cols[2]:
            st.metric("ROUGE-L", f"{evaluation['rouge_l']:.3f}")
        if evaluation.get("bertscore_f1") is not None:
            st.metric("BERTScore F1", f"{evaluation['bertscore_f1']:.3f}")
        st.markdown("</div>", unsafe_allow_html=True)


def render_authenticated_workspace(
    pipeline: LegalSummarizationPipeline, auth_service: AuthService, auth_user: Dict[str, Any]
) -> None:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="profile-card">
                <h3>{html.escape(auth_user.get('full_name', 'User'))}</h3>
                <p>{html.escape(auth_user.get('email', ''))}</p>
                <p>Signed in to a locally protected legal research workspace.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        if st.button("Sign Out", use_container_width=True):
            sign_out(auth_service)

        st.subheader("Document Input")
        input_mode = st.radio("Input mode", ["Bundled demo", "Upload file", "Paste text"], index=0, key="input_mode")
        gold_summary = st.text_area("Optional gold summary", height=130, key="gold_summary_input")
        run_clicked = st.button("Generate Summary", type="primary", use_container_width=True)
        clear_clicked = st.button("Clear Current Result", use_container_width=True)

    if clear_clicked:
        reset_workspace()
        st.rerun()

    st.title("Legal Document Summarization")

    input_col, status_col = st.columns([1.18, 0.82], gap="large")
    with input_col:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown("### Document Input")
        if input_mode == "Bundled demo":
            demo_choice = st.selectbox("Choose a demo document", list(DEMO_FILES.keys()), key="demo_choice")
            if st.session_state["active_demo_choice"] != demo_choice:
                set_demo_document(demo_choice)
        elif input_mode == "Upload file":
            uploaded = st.file_uploader("Upload TXT or PDF", type=["txt", "pdf"], key="uploaded_doc")
            if uploaded is not None and st.session_state["active_uploaded_name"] != uploaded.name:
                try:
                    set_uploaded_document(pipeline, uploaded)
                except Exception as error:
                    st.error(f"Could not read the uploaded file: {error}")
        st.text_input("Document ID", key="document_id_input")
        st.text_area("Document text", key="document_editor", height=320, placeholder="Paste or load a legal opinion here...")
        st.markdown("</div>", unsafe_allow_html=True)

    with status_col:
        st.markdown("### Workspace Status")
        processing_placeholder = st.empty()
        runtime_result = st.session_state.get("latest_result")
        if runtime_result:
            stage_states, stage_payloads, activity_log = _snapshot_processing_state_from_result(runtime_result)
            render_processing_board(
                processing_placeholder,
                stage_states,
                stage_payloads,
                activity_log,
                headline="Latest Run Ready",
                status_text="The most recent document has already completed chunking, generation, and reranking.",
            )
            render_backend_chips(runtime_result.get("runtime_info", {}))
        else:
            render_processing_board(
                processing_placeholder,
                {stage_id: "pending" for stage_id, _, _ in PROCESS_STAGES},
                {},
                [],
                headline="Pipeline Ready",
                status_text="Load a document and run the analysis to watch each stage advance.",
            )

    if run_clicked:
        document_text = st.session_state.get("document_editor", "")
        document_id = st.session_state.get("document_id_input", "streamlit-document")
        if not document_text.strip():
            st.warning("Please provide a legal document before running the pipeline.")
        else:
            try:
                result = run_pipeline_with_feedback(
                    pipeline,
                    document_text=document_text,
                    document_id=document_id,
                    gold_summary=gold_summary or None,
                    placeholder=processing_placeholder,
                )
            except Exception as error:
                st.error(f"The pipeline could not finish: {error}")
                return
            st.session_state["latest_result"] = result
            st.session_state["latest_markdown_report"] = build_markdown_report(result)

    result = st.session_state.get("latest_result")
    if not result:
        st.info("Load a document on the left and run the pipeline to begin.")
        return

    render_primary_result_view(result)

    export_columns = st.columns(3)
    with export_columns[0]:
        st.download_button(
            "Export Markdown",
            data=st.session_state["latest_markdown_report"],
            file_name=f"{result['document_id']}_summary.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with export_columns[1]:
        st.download_button(
            "Export JSON",
            data=json.dumps(result, indent=2),
            file_name=f"{result['document_id']}_result.json",
            mime="application/json",
            use_container_width=True,
        )
    with export_columns[2]:
        pdf_report = build_pdf_report(st.session_state["latest_markdown_report"])
        if pdf_report is not None:
            st.download_button(
                "Export PDF",
                data=pdf_report,
                file_name=f"{result['document_id']}_summary.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.caption("PDF export unavailable without `reportlab`.")


def main() -> None:
    st.set_page_config(page_title="Counsel Desk", layout="wide")
    pipeline, auth_service = get_services()
    initialize_state()
    inject_styles()
    cookie_name = pipeline.config.app.auth.session_cookie_name
    session_duration_days = pipeline.config.app.auth.session_duration_days
    render_auth_cookie_bridge(cookie_name, session_duration_days)
    hydrate_auth_from_cookie(auth_service, cookie_name)

    if pipeline.config.app.auth.enabled and not st.session_state.get("auth_user"):
        render_auth_screen(auth_service, session_duration_days)
        return

    render_authenticated_workspace(pipeline, auth_service, st.session_state.get("auth_user") or {})


if __name__ == "__main__":
    main()
