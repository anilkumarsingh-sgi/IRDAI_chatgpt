# 🏛️ IRDAI Compliance GPT — Deployment Guide

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                    Streamlit Cloud                          │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────────┐ │
│  │ Crawler  │  │Ingestion │  │   Streamlit UI (app.py)   │ │
│  │(crawler) │→ │(ingest)  │→ │   + RAG Pipeline          │ │
│  └────┬─────┘  └────┬─────┘  └──────────┬────────────────┘ │
│       │              │                   │                   │
│  ┌────▼─────┐   ┌────▼──────┐  ┌────────▼────────────────┐ │
│  │  SQLite  │   │  ChromaDB │  │  HuggingFace API        │ │
│  │(tracker) │   │  (vectors)│  │  Mistral-7B-Instruct    │ │
│  └──────────┘   └───────────┘  └─────────────────────────┘ │
│       ▲                                                      │
│  ┌────┴─────────────────────────────────────────────────┐   │
│  │  scheduler.py – Background thread (every 12 hours)   │   │
│  │  Auto-crawls IRDAI → downloads new docs → ingests    │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

## Folder Structure

```
irdai_compliance_gpt/
├── app.py                  ← Streamlit UI + RAG pipeline
├── crawler.py              ← IRDAI website crawler
├── ingestion.py            ← PDF/Excel/Word → embed → ChromaDB
├── scheduler.py            ← Background auto-update scheduler
├── requirements.txt
├── packages.txt            ← System packages for Streamlit Cloud
├── .gitignore
├── .streamlit/
│   ├── config.toml         ← Streamlit theme/server config
│   └── secrets.toml        ← HF_TOKEN (NEVER commit!)
└── data/                   ← Auto-created at runtime
    ├── pdfs/               ← Downloaded PDFs by category
    ├── excel/              ← Downloaded Excel files
    ├── word/               ← Downloaded Word docs
    ├── chroma_db/          ← Vector store
    └── scheduler_state.json← Auto-update state tracker
```

---

## 🚀 A) Step-by-Step Deployment Guide

### Step 1: Get HuggingFace Token
1. Go to https://huggingface.co/settings/tokens
2. Create a new token with **Read** permission
3. Copy the token (starts with `hf_`)

### Step 2: Clone & Set Up Locally (optional test)
```bash
git clone https://github.com/YOUR_USERNAME/irdai-compliance-gpt.git
cd irdai-compliance-gpt
pip install -r requirements.txt
cp .env.example .env          # fill in HF_TOKEN
streamlit run app.py
```

### Step 3: Push to GitHub
```bash
git init
git add app.py crawler.py ingestion.py scheduler.py requirements.txt packages.txt .streamlit/config.toml .gitignore README.md
# DO NOT add data/ or secrets.toml
git commit -m "IRDAI Compliance GPT with auto-update"
git remote add origin https://github.com/YOUR_USERNAME/irdai-compliance-gpt.git
git push -u origin main
```

---

## 🌐 B) Streamlit Cloud Deployment

1. Go to https://share.streamlit.io
2. Click **"New app"**
3. Select your GitHub repo and branch
4. Set **Main file path** to `app.py`
5. Click **"Advanced settings"**
6. Add secrets:
   ```toml
   HF_TOKEN = "hf_your_actual_token_here"
   ```
7. (Optional) Set environment variable for update interval:
   ```toml
   # In secrets or as env var — interval in seconds (default: 43200 = 12 hours)
   IRDAI_UPDATE_INTERVAL = "43200"
   ```
8. Click **Deploy**

> ⏳ First deployment takes ~5 minutes (installs packages)

---

## 🔄 C) Automatic Document Updates

The app includes a **background scheduler** that automatically:

1. **Crawls IRDAI website** every 12 hours (configurable via `IRDAI_UPDATE_INTERVAL`)
2. **Downloads new PDFs, Excel & Word** documents with deduplication
3. **Ingests new documents** into ChromaDB vector store
4. **Tracks update state** — shows last update time in the sidebar

### How it works on Streamlit Cloud:
- A daemon thread starts when the app boots
- It checks every 5 minutes if an update is due
- When due, it runs the full crawl → ingest pipeline in the background
- The UI shows real-time status: Running / Last updated X hours ago / Pending
- **Manual override**: Click "🔄 Force Update Now" in the sidebar

### Important: Ephemeral Storage
- On Streamlit Cloud, `/tmp/irdai_data/` is used (ephemeral — resets on reboot)
- **On first start**, the scheduler will automatically crawl and build the vector database
- Subsequent restarts will re-crawl (data is fresh but takes a few minutes to rebuild)
- For persistent storage, consider upgrading to a cloud database (see Enterprise section)

---

## ⚡ D) Running the Pipeline Manually

The sidebar includes **Admin Actions**:

1. **🔄 Force Update Now** — Triggers immediate crawl + ingestion in background
2. **🕷️ Run Crawler** — Crawls IRDAI website only (downloads new documents)
3. **📥 Run Ingestion** — Processes downloaded docs into ChromaDB only

---

## 📉 E) Handling HuggingFace API Limits

| Plan | Rate Limit | Notes |
|------|-----------|-------|
| Free | ~30 req/min | Good for demos |
| PRO ($9/mo) | ~300 req/min | 10-20 users |
| Enterprise | Custom | Production |

The app automatically:
- Detects 429 rate limit errors
- Displays a user-friendly retry message
- Caches the LLM client with `@st.cache_resource`

---

## 💰 F) Cost Optimization Tips

1. **Use smaller models first**: `google/flan-t5-large` is free and fast for simple queries
2. **Cache aggressively**: Use `@st.cache_resource` for models, `@st.cache_data` for static data
3. **Limit n_results**: Keep retrieval to 3-5 chunks (reduces context size → cheaper API calls)
4. **Auto-scraping eliminates manual work**: The scheduler handles updates automatically
5. **Use quantized models**: `TheBloke/Mistral-7B-Instruct-v0.2-GPTQ` is faster on shared infra
6. **Tune update interval**: Set `IRDAI_UPDATE_INTERVAL` to `86400` (24h) if 12h is too frequent

---

## 🏢 G) Enterprise Upgrade Plan

| Feature | Free/Cloud | Enterprise |
|---------|-----------|------------|
| Hosting | Streamlit Cloud | AWS/GCP/Azure |
| LLM | HF Inference API | Dedicated HF Endpoint / Azure OpenAI |
| Vector DB | Local ChromaDB | Pinecone / Weaviate / pgvector |
| Storage | Ephemeral | S3 + persistent EFS |
| Auth | None | SSO / LDAP |
| Audit Logs | None | Full audit trail |
| Multi-tenant | No | Yes |
| SLA | None | 99.9% |

---

## 🔐 Security Hardening Checklist

- [x] HF_TOKEN stored in Streamlit secrets (never in code)
- [x] No policyholder data in the system
- [x] Only public IRDAI documents processed
- [x] Disclaimer displayed prominently in UI
- [ ] Add IP allowlisting (enterprise)
- [ ] Enable Streamlit authentication (enterprise)
- [ ] Run ChromaDB on separate persistence layer
- [ ] Add query logging + audit trail for compliance
- [ ] Rotate HF tokens quarterly
- [ ] Network-level isolation (VPC) for enterprise deploy

---

## 📞 Support

For issues, open a GitHub issue or contact your AI platform team.
