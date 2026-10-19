"""
QuizGen AI — Professional Streamlit Dashboard.

Run with:
    streamlit run src/quiz_gen/web_ui.py
"""

import sys
import os
import io
import re
import json
import time
import html as html_lib

import streamlit as st


# ---------------------------------------------------------------------------
# Import project package
# ---------------------------------------------------------------------------

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from quiz_gen.core import (  # noqa: E402
    generate_quiz,
    score_quiz,
    export_quiz_pdf_ready,
    check_ollama_running,
    ConfigManager,
    QuestionBank,
    ScoreTracker,
    QUIZ_TYPES,
)

from rag.vector_store import build_vector_store  # noqa: E402
from rag.rag_quiz import generate_rag_quiz  # noqa: E402


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="QuizGen AI",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def html(markup: str, target=st) -> None:
    """Render HTML safely.

    Strips indentation and blank lines so Markdown never mistakes the
    HTML for a code block. `target` can be `st` or an `st.empty()` placeholder.
    """
    cleaned = "\n".join(
        line.strip() for line in markup.splitlines() if line.strip()
    )
    target.markdown(cleaned, unsafe_allow_html=True)


def esc(value) -> str:
    """Escape text coming from the PDF / AI so it can't break the HTML."""
    return html_lib.escape(str(value))


def extract_pdf_text(data: bytes) -> str:
    """Extract plain text from PDF bytes. Returns "" if no library/text is available."""
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader  # type: ignore
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        pass
    try:
        import fitz  # pymupdf

        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


def topic_in_text(topic: str, text: str) -> bool:
    """Quick guard: does at least one meaningful word of the topic appear in the PDF?

    If the PDF text is unavailable (e.g. scanned PDF), the check is skipped.
    """
    if not text.strip():
        return True
    words = [w for w in re.findall(r"[A-Za-z0-9]+", topic.lower()) if len(w) >= 3]
    if not words:
        return True
    haystack = text.lower()
    return any(
        re.search(rf"\b{re.escape(w)}(?:s|es)?\b", haystack) for w in words
    )


# ---------------------------------------------------------------------------
# Professional UI (CSS)
# ---------------------------------------------------------------------------

html(
    """
<style>
/* -------------------- Global -------------------- */

.stApp {
    background:
        radial-gradient(circle at 10% 0%, rgba(99,102,241,.10), transparent 28%),
        radial-gradient(circle at 90% 10%, rgba(139,92,246,.08), transparent 28%),
        #080b14;
    color: #f8fafc;
}

header[data-testid="stHeader"] {
    background: transparent !important;
    box-shadow: none !important;
}

div[data-testid="stDecoration"] {
    display: none !important;
}

.block-container {
    max-width: 1380px;
    padding-top: 1rem !important;
    padding-bottom: 4rem;
}

footer {
    visibility: hidden;
}

/* -------------------- Sidebar -------------------- */

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #101526 0%, #0b1020 100%) !important;
    border-right: 1px solid rgba(148,163,184,.12);
}

section[data-testid="stSidebar"] > div {
    padding-top: 1.8rem;
}

section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #e5e7eb !important;
}

.brand {
    padding: 4px 2px 24px 2px;
}

.brand-title {
    color: #ffffff;
    font-size: 1.45rem;
    font-weight: 800;
    letter-spacing: -.4px;
}

.brand-subtitle {
    color: #94a3b8;
    font-size: .80rem;
    margin-top: 5px;
}

/* -------------------- Inputs -------------------- */

input,
textarea {
    color: #f8fafc !important;
    background: #111827 !important;
}

input::placeholder,
textarea::placeholder {
    color: #64748b !important;
}

div[data-baseweb="select"] > div {
    background: #111827 !important;
    border-color: #334155 !important;
    color: #f8fafc !important;
}

div[data-baseweb="select"] span {
    color: #f8fafc !important;
}

div[data-baseweb="select"] svg {
    fill: #cbd5e1 !important;
}

/* -------------------- Typography -------------------- */

h1, h2, h3 {
    color: #f8fafc !important;
}

/* -------------------- Header -------------------- */

.hero {
    padding: 30px 34px;
    border-radius: 20px;
    margin-bottom: 24px;
    background:
        linear-gradient(135deg,
            rgba(79,70,229,.18),
            rgba(124,58,237,.08));
    border: 1px solid rgba(129,140,248,.18);
    box-shadow: 0 18px 45px rgba(0,0,0,.20);
}

.hero-title {
    font-size: 2.35rem;
    line-height: 1.1;
    font-weight: 850;
    color: #ffffff;
    letter-spacing: -1px;
}

.hero-title .accent {
    color: #a78bfa;
}

.hero-subtitle {
    color: #94a3b8;
    font-size: .98rem;
    margin-top: 10px;
    line-height: 1.6;
}

.hero-badge {
    display: inline-block;
    margin-top: 17px;
    padding: 6px 11px;
    border-radius: 999px;
    background: rgba(34,197,94,.08);
    border: 1px solid rgba(34,197,94,.20);
    color: #86efac;
    font-size: .76rem;
    font-weight: 650;
}

/* -------------------- Sections -------------------- */

.section-title {
    color: #f8fafc;
    font-size: 1.30rem;
    font-weight: 760;
    margin-top: 8px;
    margin-bottom: 4px;
}

.section-subtitle {
    color: #64748b;
    font-size: .86rem;
    margin-bottom: 18px;
}

/* -------------------- Cards -------------------- */

.card {
    background: linear-gradient(145deg, #111827, #0f172a);
    border: 1px solid rgba(148,163,184,.11);
    border-radius: 15px;
    padding: 19px;
    margin-bottom: 13px;
    box-shadow: 0 9px 28px rgba(0,0,0,.16);
}

.metric-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 17px;
    text-align: center;
}

.metric-value {
    color: #f8fafc;
    font-size: 1.30rem;
    font-weight: 800;
}

.metric-label {
    color: #64748b;
    font-size: .76rem;
    margin-top: 4px;
}

/* -------------------- Questions -------------------- */

.question-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 15px;
    padding: 21px;
    margin: 13px 0;
}

.question-number {
    color: #818cf8;
    font-size: .72rem;
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}

.question-text {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 600;
    line-height: 1.6;
}

.option {
    color: #cbd5e1;
    padding: 6px 0;
    font-size: .93rem;
}

/* -------------------- Buttons -------------------- */

.stButton > button {
    width: 100%;
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    min-height: 45px;
    font-weight: 700 !important;
}

.stButton > button p {
    color: #ffffff !important;
}

.stButton > button span {
    color: #ffffff !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    color: #ffffff !important;
    transform: translateY(-1px);
    box-shadow: 0 9px 22px rgba(99,102,241,.28);
}

.stDownloadButton > button {
    width: 100%;
    background: #111827 !important;
    color: #e2e8f0 !important;
    border: 1px solid #334155 !important;
    border-radius: 10px !important;
    min-height: 43px;
    font-weight: 600 !important;
}

.stDownloadButton > button:hover {
    border-color: #6366f1 !important;
    color: #ffffff !important;
}

/* -------------------- Tabs -------------------- */

button[data-baseweb="tab"] {
    color: #64748b !important;
    font-weight: 650 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #a5b4fc !important;
}

div[data-baseweb="tab-highlight"] {
    background-color: #6366f1 !important;
}

/* -------------------- Expander -------------------- */

div[data-testid="stExpander"] {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 13px;
    margin-bottom: 9px;
}

div[data-testid="stExpander"] summary {
    color: #e2e8f0 !important;
}

/* -------------------- Radio / checkbox -------------------- */

div[data-testid="stCheckbox"] label,
div[data-testid="stRadio"] label {
    color: #cbd5e1 !important;
}

/* -------------------- Ollama status -------------------- */

.status-online,
.status-offline {
    padding: 13px;
    border-radius: 12px;
    margin-top: 10px;
}

.status-online {
    background: rgba(34,197,94,.07);
    border: 1px solid rgba(34,197,94,.20);
}

.status-offline {
    background: rgba(239,68,68,.07);
    border: 1px solid rgba(239,68,68,.20);
}

.status-title {
    color: #e2e8f0;
    font-weight: 700;
}

.status-text {
    color: #94a3b8;
    font-size: .76rem;
    margin-top: 3px;
}

/* -------------------- Score -------------------- */

.score-card {
    padding: 28px;
    border-radius: 17px;
    background: linear-gradient(135deg,
        rgba(79,70,229,.16),
        rgba(124,58,237,.08));
    border: 1px solid rgba(129,140,248,.18);
    text-align: center;
}

.score-number {
    font-size: 3rem;
    font-weight: 850;
    color: #ffffff;
}

.score-label {
    color: #94a3b8;
}

/* -------------------- Misc -------------------- */

hr {
    border-color: #1e293b !important;
}
</style>
"""
)


# ---------------------------------------------------------------------------
# Configuration and session state
# ---------------------------------------------------------------------------

cfg = ConfigManager()

if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}

if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False

if "quiz_start_time" not in st.session_state:
    st.session_state.quiz_start_time = None

if "rag_ready" not in st.session_state:
    st.session_state.rag_ready = False

if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    html(
        """
<div class="brand">
    <div class="brand-title">QuizGen AI</div>
    <div class="brand-subtitle">Local AI-powered quiz generator</div>
</div>
"""
    )

    st.markdown("### RAG Knowledge Base")

    uploaded_pdf = st.file_uploader(
        "Upload Study PDF",
        type=["pdf"],
        help="Upload a PDF to generate quizzes from its content.",
    )

    build_rag = st.button(
        "Build Knowledge Base",
        use_container_width=True,
    )

    if build_rag:
        if uploaded_pdf is None:
            st.warning("Please upload a PDF first.")
        else:
            try:
                data_dir = os.path.join(PROJECT_ROOT, "rag", "data")
                os.makedirs(data_dir, exist_ok=True)

                pdf_path = os.path.join(data_dir, uploaded_pdf.name)

                with open(pdf_path, "wb") as file:
                    file.write(uploaded_pdf.getbuffer())

                with st.spinner("Building RAG knowledge base..."):
                    build_vector_store(pdf_path)

                st.session_state.pdf_text = extract_pdf_text(bytes(uploaded_pdf.getbuffer()))
                st.session_state.rag_ready = True
                st.success(f"Knowledge base created from {uploaded_pdf.name}")
                if not st.session_state.pdf_text.strip():
                    st.warning(
                        "Topic check is OFF: could not read text from this PDF. "
                        "Install it with: pip install pypdf"
                    )

            except Exception as exc:
                st.session_state.rag_ready = False
                st.error(f"RAG build failed: {exc}")

    st.divider()

    st.markdown("### Quiz Settings")

    topic = st.text_input(
        "Topic",
        placeholder="e.g. Python, Java, Networking",
    )

    num_questions = st.slider(
        "Number of questions",
        min_value=1,
        max_value=cfg.get("quiz", "max_questions", default=50),
        value=cfg.get("quiz", "default_num_questions", default=5),
    )

    # Only multiple-choice questions are supported
    quiz_type = "multiple-choice"

    difficulty = st.select_slider(
        "Difficulty",
        options=["easy", "medium", "hard"],
        value="medium",
    )

    enable_timer = st.checkbox(
        "Enable timer",
        value=False,
    )

    st.divider()

    ollama_ok = check_ollama_running()

    if ollama_ok:
        html(
            """
<div class="status-online">
    <div class="status-title">Ollama Online</div>
    <div class="status-text">Local AI engine is ready</div>
</div>
"""
        )
    else:
        html(
            """
<div class="status-offline">
    <div class="status-title">Ollama Offline</div>
    <div class="status-text">Start Ollama to generate quizzes</div>
</div>
"""
        )

    st.caption("Powered by Ollama and Gemma")


# ---------------------------------------------------------------------------
# Main header
# ---------------------------------------------------------------------------

html(
    """
<div class="hero">
    <div class="hero-title">Quiz<span class="accent">Gen AI</span></div>
    <div class="hero-subtitle">
        Create intelligent quizzes locally using AI.<br>
        Generate, practice, analyze and store your quizzes.
    </div>
    <div class="hero-badge">Local AI • Private • Powered by Ollama</div>
</div>
"""
)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

tab_gen, tab_take, tab_bank, tab_history = st.tabs(
    ["Generate", "Take Quiz", "Question Bank", "Analytics"]
)


# ===========================================================================
# GENERATE
# ===========================================================================

with tab_gen:
    html(
        """
<div class="section-title">Create Your Quiz</div>
<div class="section-subtitle">
    Configure your topic and let your local AI generate the questions.
</div>
"""
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        html(
            f"""
<div class="metric-card">
    <div class="metric-value">{num_questions}</div>
    <div class="metric-label">Questions</div>
</div>
"""
        )

    with c2:
        html(
            f"""
<div class="metric-card">
    <div class="metric-value">{esc(difficulty.title())}</div>
    <div class="metric-label">Difficulty</div>
</div>
"""
        )

    with c3:
        html(
            f"""
<div class="metric-card">
    <div class="metric-value">{esc(quiz_type.replace("-", " ").title())}</div>
    <div class="metric-label">Question Type</div>
</div>
"""
        )

    st.markdown("")

    generate_clicked = st.button(
        "Generate Quiz",
        disabled=not topic.strip(),
        use_container_width=True,
    )

    if generate_clicked:
        if not ollama_ok:
            st.error("Ollama is not running. Please start Ollama and try again.")
        elif not st.session_state.rag_ready:
            st.error("Please upload a PDF and click Build Knowledge Base first.")
        elif not topic_in_text(
            topic,
            st.session_state.pdf_text
            or (extract_pdf_text(bytes(uploaded_pdf.getbuffer())) if uploaded_pdf else ""),
        ):
            st.session_state.quiz_data = None
            st.error(
                f'The topic "{topic}" does not appear to be covered in the uploaded PDF. '
                "Please enter a topic from the document."
            )
        else:
            progress = st.empty()
            html(
                """
<div class="card">
    <b>Generating your quiz...</b><br>
    <span style="color:#94a3b8;">Your local AI is creating the questions. This may take a few seconds.</span>
</div>
""",
                progress,
            )

            # Clear the previous quiz so an old one is not shown next to an error
            st.session_state.quiz_data = None

            try:
                quiz = generate_rag_quiz(topic, num_questions)

                st.session_state.quiz_data = quiz
                st.session_state.user_answers = {}
                st.session_state.quiz_submitted = False
                st.session_state.quiz_start_time = time.time()

                progress.empty()
                st.success("Quiz generated successfully.")

            except Exception as exc:
                progress.empty()
                st.error(f"Quiz generation failed: {exc}")

    quiz = st.session_state.quiz_data

    if quiz:
        st.markdown("")

        html(
            f"""
<div class="hero">
    <div class="hero-title">{esc(quiz.get("title", "Generated Quiz"))}</div>
    <div class="hero-subtitle">Topic: {esc(quiz.get("topic", topic))}</div>
</div>
"""
        )

        questions = quiz.get("questions", [])

        html(
            f"""
<div class="section-title">{len(questions)} Questions</div>
<div class="section-subtitle">Review your generated questions below.</div>
"""
        )

        for index, q in enumerate(questions, 1):
            number = q.get("number", index)
            question = q.get("question", "")
            q_type = q.get("type", quiz_type)

            options_html = ""
            for option in q.get("options", []) or []:
                options_html += f'<div class="option">• {esc(option)}</div>'

            html(
                f"""
<div class="question-card">
    <div class="question-number">Question {number} • {esc(q_type.replace("-", " ").title())}</div>
    <div class="question-text">{esc(question)}</div>
    <div style="margin-top:14px;">{options_html}</div>
</div>
"""
            )

            with st.expander(f"Show answer and explanation — Q{number}"):
                st.markdown(f"**Correct answer:** `{q.get('answer', 'N/A')}`")

                if q.get("explanation"):
                    st.info(q["explanation"])

        st.markdown("### Export Quiz")

        col1, col2 = st.columns(2)

        with col1:
            json_str = json.dumps(quiz, indent=2, ensure_ascii=False)

            st.download_button(
                "Download JSON",
                json_str,
                "quiz.json",
                "application/json",
                use_container_width=True,
            )

        with col2:
            md_str = export_quiz_pdf_ready(quiz)

            st.download_button(
                "Download Markdown",
                md_str,
                "quiz.md",
                "text/markdown",
                use_container_width=True,
            )


# ===========================================================================
# TAKE QUIZ
# ===========================================================================

with tab_take:
    html(
        """
<div class="section-title">Take Your Quiz</div>
<div class="section-subtitle">Test yourself and track your performance.</div>
"""
    )

    quiz = st.session_state.quiz_data

    if quiz is None:
        st.info("Generate a quiz first from the Generate tab.")
    else:
        questions = quiz.get("questions", [])

        if enable_timer and st.session_state.quiz_start_time:
            elapsed = time.time() - st.session_state.quiz_start_time

            html(
                f"""
<div class="metric-card">
    <div class="metric-value">{elapsed:.0f}s</div>
    <div class="metric-label">Elapsed time</div>
</div>
"""
            )

        st.markdown("")

        with st.form("quiz_form"):
            for q in questions:
                number = q.get("number", 0)
                key = f"q_{number}"

                html(
                    f"""
<div class="question-card">
    <div class="question-number">Question {number}</div>
    <div class="question-text">{esc(q.get("question", ""))}</div>
</div>
"""
                )

                if (
                    q.get("type") in ("multiple-choice", "true-false")
                    and q.get("options")
                ):
                    st.session_state.user_answers[key] = st.radio(
                        "Select your answer",
                        q["options"],
                        key=f"radio_{key}",
                    )
                else:
                    st.session_state.user_answers[key] = st.text_input(
                        "Your answer",
                        key=f"text_{key}",
                    )

            submitted = st.form_submit_button(
                "Submit Quiz",
                use_container_width=True,
            )

        if submitted:
            st.session_state.quiz_submitted = True
            user_ans_list = []

            for q in questions:
                key = f"q_{q.get('number', 0)}"
                raw = st.session_state.user_answers.get(key, "")

                if (
                    q.get("type") == "multiple-choice"
                    and raw
                    and ")" in raw
                ):
                    raw = raw.split(")")[0].strip()

                user_ans_list.append(raw)

            result = score_quiz(questions, user_ans_list)
            result.topic = quiz.get("topic", "")

            percentage = result.percentage

            html(
                f"""
<div class="score-card">
    <div class="score-number">{percentage:.0f}%</div>
    <div class="score-label">{result.score} correct out of {result.total}</div>
</div>
"""
            )

            st.markdown("### Answer Review")

            for q, ua in zip(questions, user_ans_list):
                correct = ua.strip().lower() == q.get("answer", "").strip().lower()
                status = "Correct" if correct else "Incorrect"

                with st.expander(f"{status} — Question {q.get('number')}"):
                    st.write(q.get("question", ""))
                    st.markdown(f"**Your answer:** {ua or 'Not answered'}")
                    st.markdown(f"**Correct answer:** {q.get('answer', 'N/A')}")

                    if q.get("explanation"):
                        st.info(q["explanation"])

            tracker = ScoreTracker(
                cfg.get("scoring", "history_file", default="quiz_scores.json")
            )
            tracker.record(result)


# ===========================================================================
# QUESTION BANK
# ===========================================================================

with tab_bank:
    html(
        """
<div class="section-title">Question Bank</div>
<div class="section-subtitle">Save and manage questions generated by your local AI.</div>
"""
    )

    bank_path = cfg.get(
        "question_bank",
        "storage_file",
        default="question_bank.json",
    )

    qb = QuestionBank(bank_path)

    col1, col2 = st.columns([3, 1])

    with col1:
        filter_topic = st.text_input(
            "Search questions",
            placeholder="Filter by topic...",
            key="bank_filter",
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("Clear Bank", use_container_width=True):
            qb.clear()
            st.rerun()

    quiz = st.session_state.quiz_data

    if quiz:
        if st.button("Add Current Quiz to Bank", use_container_width=True):
            added = qb.add_from_quiz(quiz)
            st.success(f"Added {added} questions to the question bank.")
            st.rerun()

    questions = qb.filter(topic=filter_topic) if filter_topic else qb.all()

    if questions:
        for i, q in enumerate(questions, 1):
            html(
                f"""
<div class="question-card">
    <div class="question-number">Question {i} • {esc(q.q_type)}</div>
    <div class="question-text">{esc(q.question)}</div>
</div>
"""
            )
    else:
        st.info("Your question bank is empty. Generate a quiz and add it here.")


# ===========================================================================
# ANALYTICS
# ===========================================================================

with tab_history:
    html(
        """
<div class="section-title">Performance Analytics</div>
<div class="section-subtitle">Track your quiz performance over time.</div>
"""
    )

    tracker = ScoreTracker(
        cfg.get("scoring", "history_file", default="quiz_scores.json")
    )

    history = tracker.history()

    if history:
        average = tracker.average_score()
        best = tracker.best_score()
        total_attempts = len(history)

        col1, col2, col3 = st.columns(3)

        with col1:
            html(
                f"""
<div class="metric-card">
    <div class="metric-value">{average:.1f}%</div>
    <div class="metric-label">Average Score</div>
</div>
"""
            )

        with col2:
            best_score = best.get("percentage", 0) if best else 0

            html(
                f"""
<div class="metric-card">
    <div class="metric-value">{best_score:.0f}%</div>
    <div class="metric-label">Best Score</div>
</div>
"""
            )

        with col3:
            html(
                f"""
<div class="metric-card">
    <div class="metric-value">{total_attempts}</div>
    <div class="metric-label">Quiz Attempts</div>
</div>
"""
            )

        st.markdown("### Score Progress")

        chart_data = [
            {"attempt": i + 1, "percentage": h.get("percentage", 0)}
            for i, h in enumerate(history)
        ]

        st.line_chart(chart_data, x="attempt", y="percentage")

        st.markdown("### Recent Attempts")

        for item in reversed(history[-5:]):
            html(
                f"""
<div class="card">
    <b>{esc(item.get("topic", "Quiz"))}</b>
    <span style="float:right;color:#818cf8;">{item.get("percentage", 0):.0f}%</span>
</div>
"""
            )

        if st.button("Clear Score History", use_container_width=True):
            tracker.clear()
            st.rerun()

    else:
        st.info("No quiz attempts yet. Take a quiz to start building your analytics.")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

html(
    """
<div style="text-align:center;color:#475569;font-size:.76rem;padding:35px 0 10px 0;">
    QuizGen AI • Local AI Quiz Platform • Ollama
</div>
"""
)