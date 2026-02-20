"""
IRDAI Compliance GPT – Streamlit Application
Uses HuggingFace Inference API + ChromaDB RAG
"""

import os
import time
import logging
import sqlite3
from pathlib import Path

import streamlit as st
from huggingface_hub import InferenceClient

from ingestion import retrieve_relevant_chunks, get_chroma_collection, CHROMA_DIR
from crawler import get_download_stats, DB_PATH, init_db, PDF_DIR, EXCEL_DIR, WORD_DIR

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("irdai.app")

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title = "IRDAI Compliance GPT",
    page_icon  = "🏛️",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Google Fonts ── */
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  /* ── Root palette ── */
  :root {
    --bg:        #0B0F1A;
    --surface:   #111827;
    --border:    #1F2D40;
    --accent:    #00C6A2;
    --accent2:   #3B82F6;
    --warn:      #F59E0B;
    --danger:    #EF4444;
    --text:      #E2E8F0;
    --muted:     #94A3B8;
  }

  /* ── App background ── */
  .stApp { background: var(--bg); color: var(--text); }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border);
  }

  /* ── Title banner ── */
  .title-banner {
    background: linear-gradient(135deg, #0F2027, #203A43, #2C5364);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 28px 36px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
  }
  .title-banner::after {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, rgba(0,198,162,.18), transparent 70%);
    border-radius: 50%;
  }
  .title-banner h1 {
    font-family: 'Syne', sans-serif;
    font-size: 2rem;
    font-weight: 800;
    color: var(--accent);
    margin: 0;
    letter-spacing: -0.5px;
  }
  .title-banner p {
    color: var(--muted);
    margin: 6px 0 0;
    font-size: .9rem;
  }

  /* ── Metric cards ── */
  .metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 22px;
    text-align: center;
  }
  .metric-card .val {
    font-family: 'Syne', sans-serif;
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--accent);
  }
  .metric-card .lbl {
    font-size: .75rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 4px;
  }

  /* ── Question input ── */
  .stTextArea textarea {
    background: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
  }
  .stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(0,198,162,.2) !important;
  }

  /* ── Buttons ── */
  .stButton>button {
    background: linear-gradient(135deg, var(--accent), #00A88A) !important;
    color: #0B0F1A !important;
    font-weight: 600 !important;
    font-family: 'Syne', sans-serif !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 28px !important;
    letter-spacing: .4px;
    transition: opacity .2s;
  }
  .stButton>button:hover { opacity: .88; }

  /* ── Answer card ── */
  .answer-card {
    background: var(--surface);
    border: 1px solid var(--accent);
    border-radius: 10px;
    padding: 24px 28px;
    margin-top: 20px;
    line-height: 1.75;
  }

  /* ── Source citation badge ── */
  .cite-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(59,130,246,.12);
    border: 1px solid rgba(59,130,246,.3);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: .78rem;
    font-family: 'IBM Plex Mono', monospace;
    color: #93C5FD;
    margin: 4px 4px 4px 0;
  }

  /* ── Disclaimer ── */
  .disclaimer {
    background: rgba(245,158,11,.07);
    border: 1px solid rgba(245,158,11,.3);
    border-radius: 8px;
    padding: 14px 18px;
    font-size: .82rem;
    color: #FCD34D;
    margin-top: 28px;
  }

  /* ── Sidebar info blocks ── */
  .sb-block {
    background: rgba(0,198,162,.06);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 10px;
    font-size: .83rem;
  }
  .sb-block .sb-title {
    font-family: 'Syne', sans-serif;
    font-size: .75rem;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
  }

  /* ── Spinner ── */
  [data-testid="stSpinner"] { color: var(--accent) !important; }

  /* Status pills ── */
  .pill-ok  { color: #34D399; font-weight: 600; }
  .pill-err { color: var(--danger); font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ───────────────────────────────────────────────────────────────────
def get_hf_token() -> str:
    """Read HF token from st.secrets or env."""
    try:
        return st.secrets["HF_TOKEN"]
    except Exception:
        token = os.getenv("HF_TOKEN", "")
        if not token:
            st.error("⚠️ HF_TOKEN not found. Add it in Streamlit Cloud → Secrets.")
        return token


MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.2"

SYSTEM_PROMPT = (
    "You are an expert IRDAI (Insurance Regulatory and Development Authority of India) compliance assistant. "
    "Answer questions based ONLY on the provided regulatory context. "
    "Be precise, cite relevant regulation sections, and keep the answer professional. "
    "If the context does not contain sufficient information, say so clearly."
)


@st.cache_resource(show_spinner=False)
def get_hf_client(token: str) -> InferenceClient:
    """Create a cached HuggingFace InferenceClient."""
    return InferenceClient(model=MODEL_ID, token=token)


def run_rag_query(query: str, token: str) -> dict:
    """
    Full RAG pipeline:
      1. Retrieve relevant chunks
      2. Build context string
      3. Call HF Inference API
      4. Return answer + citations
    """
    chunks = retrieve_relevant_chunks(query, n_results=5)

    if not chunks:
        return {
            "answer":    "⚠️ No documents found in the knowledge base. Please run the crawler and ingestion pipeline first.",
            "citations": [],
        }

    context = "\n\n---\n\n".join(
        f"[{c['source']} | Page {c['page']}]\n{c['text']}"
        for c in chunks
    )

    user_message = (
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION:\n{query}\n\n"
        f"Provide a clear, structured, compliance-focused answer."
    )

    try:
        client = get_hf_client(token)
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            max_tokens=1024,
            temperature=0.3,
        )
        answer = response.choices[0].message.content
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        error_msg = str(exc).lower()
        if "rate limit" in error_msg or "429" in error_msg:
            answer = (
                "⏳ HuggingFace API rate limit reached. "
                "Please wait ~60 seconds and try again, or upgrade your HF plan."
            )
        else:
            answer = f"❌ LLM error: {exc}"

    citations = [
        {"source": c["source"], "page": c["page"], "score": c["score"]}
        for c in chunks
    ]

    return {"answer": answer.strip(), "citations": citations}


def get_collection_stats() -> dict:
    """Get vector store doc count."""
    try:
        col = get_chroma_collection()
        return {"count": col.count(), "status": "ok"}
    except Exception:
        return {"count": 0, "status": "error"}


def get_file_counts() -> dict:
    """Count actual files on disk by type."""
    counts = {"pdf": 0, "excel": 0, "word": 0}
    if PDF_DIR.exists():
        counts["pdf"] = len(list(PDF_DIR.rglob("*.pdf")))
    if EXCEL_DIR.exists():
        counts["excel"] = len(list(EXCEL_DIR.rglob("*.xlsx"))) + len(list(EXCEL_DIR.rglob("*.xls")))
    if WORD_DIR.exists():
        counts["word"] = len(list(WORD_DIR.rglob("*.docx"))) + len(list(WORD_DIR.rglob("*.doc")))
    return counts


def get_sqlite_stats() -> dict:
    """Get download stats from SQLite."""
    try:
        init_db()
        return get_download_stats()
    except Exception:
        return {}


# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='font-family:Syne,sans-serif;font-size:1.1rem;font-weight:700;
                color:#00C6A2;padding:8px 0 18px;letter-spacing:-.3px;'>
      🏛️ IRDAI Compliance GPT
    </div>
    """, unsafe_allow_html=True)

    # System Status
    col_stats = get_collection_stats()
    db_stats  = get_sqlite_stats()
    file_counts = get_file_counts()
    total_docs = sum(file_counts.values())
    vec_count  = col_stats["count"]
    vec_status_cls = "pill-ok" if col_stats["status"] == "ok" and vec_count > 0 else "pill-err"

    st.markdown(f"""
    <div class="sb-block">
      <div class="sb-title">System Status</div>
      <div>Vector DB &nbsp;<span class="{vec_status_cls}">{'✓ ' + str(vec_count) + ' chunks' if vec_count > 0 else '✗ Empty'}</span></div>
      <div>Total Docs &nbsp;<b style="color:#E2E8F0">{total_docs}</b></div>
    </div>
    """, unsafe_allow_html=True)

    # Document inventory by type
    st.markdown('<div class="sb-block"><div class="sb-title">Document Inventory</div>', unsafe_allow_html=True)
    st.markdown(f'<div>📄 PDFs: <b style="color:#E2E8F0">{file_counts["pdf"]}</b></div>', unsafe_allow_html=True)
    st.markdown(f'<div>📊 Excel: <b style="color:#E2E8F0">{file_counts["excel"]}</b></div>', unsafe_allow_html=True)
    st.markdown(f'<div>📝 Word: <b style="color:#E2E8F0">{file_counts["word"]}</b></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Category breakdown from DB
    if db_stats:
        st.markdown('<div class="sb-block"><div class="sb-title">Download Categories</div>', unsafe_allow_html=True)
        for cat, cnt in db_stats.items():
            st.markdown(f"<div>📁 {cat}: <b style='color:#E2E8F0'>{cnt}</b></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # Admin actions
    st.markdown("### ⚙️ Admin Actions")
    if st.button("🕷️ Run Crawler"):
        from crawler import run_crawl
        with st.spinner("Crawling IRDAI website…"):
            summary = run_crawl()
        st.success(f"Crawl done — PDFs: {summary.get('pdf',0)}, Excel: {summary.get('excel',0)}, Word: {summary.get('word',0)}")

    if st.button("📥 Run Ingestion"):
        from ingestion import run_ingestion
        with st.spinner("Ingesting documents into vector store…"):
            summary = run_ingestion()
        st.success(
            f"Ingested {summary['total_files']} files → {summary['total_chunks']} chunks\n"
            f"(PDF: {summary.get('pdf',0)}, Excel: {summary.get('excel',0)}, Word: {summary.get('word',0)})"
        )

    st.divider()
    st.markdown("""
    <div class="sb-block">
      <div class="sb-title">Model Info</div>
      <div style="font-size:.78rem;color:#94A3B8;line-height:1.6">
        LLM: mistralai/Mistral-7B-Instruct-v0.2<br>
        Embedding: all-MiniLM-L6-v2<br>
        Vector DB: ChromaDB (local)<br>
        Backend: HuggingFace Inference API
      </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Main Content ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="title-banner">
  <h1>🏛️ IRDAI Compliance GPT</h1>
  <p>Regulatory Intelligence System · Powered by HuggingFace + RAG · For internal compliance use only</p>
</div>
""", unsafe_allow_html=True)

# ── Metrics row
c1, c2, c3, c4, c5 = st.columns(5)
col_stats_now = get_collection_stats()
file_counts_now = get_file_counts()
total_docs_now = sum(file_counts_now.values())

with c1:
    st.markdown(f'<div class="metric-card"><div class="val">{file_counts_now["pdf"]}</div><div class="lbl">PDFs</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="val">{file_counts_now["excel"]}</div><div class="lbl">Excel Files</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="val">{file_counts_now["word"]}</div><div class="lbl">Word Docs</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="metric-card"><div class="val">{col_stats_now["count"]}</div><div class="lbl">Vector Chunks</div></div>', unsafe_allow_html=True)
with c5:
    status_txt = "🟢 Ready" if col_stats_now["count"] > 0 else "🔴 Not Ready"
    st.markdown(f'<div class="metric-card"><div class="val" style="font-size:1.2rem">{status_txt}</div><div class="lbl">System Status</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Query section
st.markdown("### 💬 Ask a Compliance Question")
st.caption("Query IRDAI regulations, circulars, notifications and guidelines using natural language.")

example_queries = [
    "What are the solvency margin requirements for life insurers?",
    "Explain IRDAI guidelines on electronic insurance accounts.",
    "What are the rules for reinsurance arrangements under IRDAI?",
    "What is the process for filing complaints under the Grievance Redressal mechanism?",
]

col_q, col_eg = st.columns([3, 1])
with col_q:
    user_query = st.text_area(
        "Your question",
        height=110,
        placeholder="e.g. What are the minimum capital requirements for a general insurer?",
        label_visibility="collapsed",
    )

with col_eg:
    st.markdown("**💡 Examples**")
    for eq in example_queries[:3]:
        if st.button(eq[:48] + "…", key=eq, use_container_width=True):
            user_query = eq

col_btn, col_pad = st.columns([1, 4])
with col_btn:
    submit = st.button("🔍  Ask IRDAI GPT", use_container_width=True)

# ── RAG execution
if submit and user_query.strip():
    token = get_hf_token()
    if token:
        with st.spinner("🔍 Retrieving relevant regulations & generating answer…"):
            t0     = time.time()
            result = run_rag_query(user_query, token)
            elapsed = round(time.time() - t0, 2)

        answer    = result["answer"]
        citations = result["citations"]

        # Answer card
        st.markdown(f'<div class="answer-card">{answer}</div>', unsafe_allow_html=True)

        # Citations
        if citations:
            st.markdown("#### 📎 Source Citations")
            badges_html = ""
            seen = set()
            for c in citations:
                key = f"{c['source']}_p{c['page']}"
                if key not in seen:
                    seen.add(key)
                    badges_html += (
                        f'<span class="cite-badge">'
                        f'📄 {c["source"]} &nbsp;·&nbsp; Page {c["page"]} '
                        f'&nbsp;·&nbsp; Score {c["score"]:.2f}'
                        f'</span>'
                    )
            st.markdown(badges_html, unsafe_allow_html=True)

        st.caption(f"⏱ Response generated in {elapsed}s")

elif submit and not user_query.strip():
    st.warning("Please enter a question before submitting.")

# ── Disclaimer
st.markdown("""
<div class="disclaimer">
  ⚠️ <strong>Disclaimer:</strong> This tool is for internal compliance use only by authorised personnel (underwriting, claims, compliance teams).
  It processes only publicly available IRDAI documents and does <strong>not</strong> store or process any policyholder data.
  Responses are AI-generated and should be verified against official IRDAI publications before making compliance decisions.
</div>
""", unsafe_allow_html=True)
