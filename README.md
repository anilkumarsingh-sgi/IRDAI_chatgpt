# 🏛️ IRDAI Compliance GPT — Deployment Guide

## Architecture Overview

```
┌───────────────────────────────────────────────────────┐
│                    Streamlit Cloud                     │
│                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │ Crawler  │  │Ingestion │  │   Streamlit UI (app) │ │
│  │(crawler) │  │(ingest)  │  │   + RAG Pipeline     │ │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘ │
│       │              │                   │              │
│  ┌────▼─────┐   ┌────▼──────┐  ┌────────▼───────────┐ │
│  │  SQLite  │   │  ChromaDB │  │  HuggingFace API   │ │
│  │(tracker) │   │  (vectors)│  │  Mistral-7B-Instruct│ │
│  └──────────┘   └───────────┘  └────────────────────┘ │
└───────────────────────────────────────────────────────┘
```

## Folder Structure

```
irdai_compliance_gpt/
├── app.py                  ← Streamlit UI + RAG pipeline
├── crawler.py              ← IRDAI website crawler
├── ingestion.py            ← PDF → embed → ChromaDB
├── requirements.txt
├── .env.example
├── .streamlit/
│   └── secrets.toml        ← HF_TOKEN (don't commit!)
└── data/                   ← Auto-created at runtime
    ├── pdfs/               ← Downloaded PDFs
    ├── chroma_db/          ← Vector store
    └── irdai_tracker.db    ← SQLite dedup tracker
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
git add app.py crawler.py ingestion.py requirements.txt .streamlit/ .env.example
# DO NOT add data/ or .env (add them to .gitignore)
echo "data/" >> .gitignore
echo ".env" >> .gitignore
git commit -m "Initial IRDAI Compliance GPT"
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
7. Click **Deploy**

> ⏳ First deployment takes ~5 minutes (installs packages)

---

## ⚡ C) Running the Pipeline on Streamlit Cloud

The app includes **Admin Actions** in the sidebar:

1. **🕷️ Run Crawler** — Crawls IRDAI website, downloads PDFs into `data/pdfs/`
2. **📥 Run Ingestion** — Processes PDFs, generates embeddings, stores in ChromaDB

> **Note:** On Streamlit Cloud, `data/` is ephemeral (resets on redeploy). For persistence, use a mounted volume or S3 + pre-built ChromaDB.

---

## 📉 D) Handling HuggingFace API Limits

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

## 💰 E) Cost Optimization Tips

1. **Use smaller models first**: `google/flan-t5-large` is free and fast for simple queries
2. **Cache aggressively**: Use `@st.cache_resource` for models, `@st.cache_data` for static data
3. **Limit n_results**: Keep retrieval to 3-5 chunks (reduces context size → cheaper API calls)
4. **Batch ingestion**: Run crawler + ingestion once a week, not on every visit
5. **Use quantized models**: `TheBloke/Mistral-7B-Instruct-v0.2-GPTQ` is faster on shared infra

---

## 🏢 F) Enterprise Upgrade Plan

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
