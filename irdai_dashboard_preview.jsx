import { useState, useEffect } from "react";

const EXAMPLE_QUERIES = [
  "What are the solvency margin requirements for life insurers?",
  "Explain IRDAI guidelines on electronic insurance accounts.",
  "What are the rules for reinsurance arrangements under IRDAI?",
  "What is the process for filing complaints under Grievance Redressal?",
];

const MOCK_CITATIONS = [
  { source: "IRDAI_Solvency_Regulations_2023.pdf", page: 4, score: 0.91 },
  { source: "Circular_Life_Insurance_Capital_2022.pdf", page: 2, score: 0.87 },
  { source: "IRDAI_Financial_Guidelines_2021.pdf", page: 11, score: 0.79 },
];

const MOCK_ANSWER = `Based on the IRDAI (Assets, Liabilities and Solvency Margin of Life Insurance Business) Regulations, 2023, the solvency margin requirements for life insurers are as follows:

**1. Required Solvency Margin (RSM)**
Every insurer shall maintain a Required Solvency Margin (RSM) which is higher of:
- ₹50 crore (minimum), or
- The sum of (a) First Factor and (b) Second Factor as specified in Schedule II

**2. Solvency Ratio**
Insurers must maintain a solvency ratio of not less than **1.5** at all times. This is the ratio of Available Solvency Margin (ASM) to Required Solvency Margin (RSM).

**3. Reporting Obligations**
- Quarterly filing with IRDAI within 45 days of quarter end
- Annual filing certified by appointed actuary

Insurers falling below the prescribed ratio must submit a remediation plan within 30 days.`;

const DB_STATS = {
  regulations: 142,
  circulars: 387,
  notifications: 94,
  guidelines: 61,
};

function TypewriterText({ text, active }) {
  const [displayed, setDisplayed] = useState("");
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (!active) { setDisplayed(""); setIdx(0); return; }
    if (idx >= text.length) return;
    const t = setTimeout(() => {
      setDisplayed(text.slice(0, idx + 1));
      setIdx(idx + 1);
    }, 8);
    return () => clearTimeout(t);
  }, [idx, active, text]);

  return <span>{displayed}{active && idx < text.length && <span className="cursor">|</span>}</span>;
}

function MetricCard({ value, label, accent }) {
  return (
    <div style={{
      background: "#111827", border: "1px solid #1F2D40", borderRadius: 10,
      padding: "18px 22px", textAlign: "center", flex: 1
    }}>
      <div style={{
        fontFamily: "'Syne', sans-serif", fontSize: "1.9rem", fontWeight: 800,
        color: accent || "#00C6A2"
      }}>{value}</div>
      <div style={{
        fontSize: ".72rem", color: "#94A3B8", textTransform: "uppercase",
        letterSpacing: "1px", marginTop: 4
      }}>{label}</div>
    </div>
  );
}

function CitationBadge({ source, page, score }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      background: "rgba(59,130,246,.12)", border: "1px solid rgba(59,130,246,.3)",
      borderRadius: 6, padding: "4px 10px", fontSize: ".76rem",
      fontFamily: "monospace", color: "#93C5FD", margin: "4px 4px 4px 0"
    }}>
      📄 {source} &nbsp;·&nbsp; pg. {page} &nbsp;·&nbsp; {score}
    </span>
  );
}

function formatAnswer(text) {
  return text.split("\n").map((line, i) => {
    if (line.startsWith("**") && line.endsWith("**")) {
      return <div key={i} style={{ fontWeight: 700, color: "#00C6A2", margin: "12px 0 4px" }}>{line.slice(2, -2)}</div>;
    }
    if (line.startsWith("- ")) {
      return <div key={i} style={{ paddingLeft: 18, marginBottom: 3 }}>• {line.slice(2)}</div>;
    }
    const bold = line.replace(/\*\*(.*?)\*\*/g, (_, m) => `<strong style="color:#E2E8F0">${m}</strong>`);
    return <div key={i} dangerouslySetInnerHTML={{ __html: bold }} style={{ marginBottom: 4 }} />;
  });
}

export default function IRDAIDashboard() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [elapsed, setElapsed] = useState(null);
  const [activeTab, setActiveTab] = useState("query");
  const [crawlStatus, setCrawlStatus] = useState(null);
  const [crawlLoading, setCrawlLoading] = useState(false);

  const totalPdfs = Object.values(DB_STATS).reduce((a, b) => a + b, 0);
  const vecChunks = 24381;

  const handleQuery = async (q) => {
    const question = q || query;
    if (!question.trim()) return;
    setQuery(question);
    setLoading(true);
    setResult(null);
    const t = Date.now();
    await new Promise(r => setTimeout(r, 2200));
    setResult({ answer: MOCK_ANSWER, citations: MOCK_CITATIONS });
    setElapsed(((Date.now() - t) / 1000).toFixed(2));
    setLoading(false);
  };

  const handleCrawl = async () => {
    setCrawlLoading(true);
    setCrawlStatus(null);
    await new Promise(r => setTimeout(r, 2500));
    setCrawlStatus({ regulations: 3, circulars: 7, notifications: 2, guidelines: 1 });
    setCrawlLoading(false);
  };

  return (
    <div style={{
      background: "#0B0F1A", minHeight: "100vh", color: "#E2E8F0",
      fontFamily: "'Inter', system-ui, sans-serif", display: "flex"
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: #0B0F1A; }
        ::-webkit-scrollbar-thumb { background: #1F2D40; border-radius: 3px; }
        textarea { resize: none; outline: none; }
        button { cursor: pointer; }
        .cursor { animation: blink 1s infinite; } @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        .tab-btn { background:none; border:none; padding:8px 16px; font-size:.84rem; border-radius:6px; transition:all .2s; }
        .tab-btn.active { background:rgba(0,198,162,.15); color:#00C6A2; font-weight:600; }
        .tab-btn:not(.active) { color:#64748B; }
        .tab-btn:not(.active):hover { color:#94A3B8; background:rgba(255,255,255,.04); }
        .action-btn { background:none; border:1px solid #1F2D40; color:#94A3B8; padding:8px 14px; border-radius:7px; font-size:.8rem; transition:all .2s; }
        .action-btn:hover { border-color:#00C6A2; color:#00C6A2; }
        .action-btn.danger:hover { border-color:#3B82F6; color:#3B82F6; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .spinner { width:18px; height:18px; border:2px solid #1F2D40; border-top-color:#00C6A2; border-radius:50%; animation:spin .8s linear infinite; display:inline-block; }
        @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        .fade-in { animation: fadeIn .4s ease forwards; }
        .pulse-dot { width:8px;height:8px;border-radius:50%;background:#34D399;display:inline-block;animation:pulse 2s infinite; }
        @keyframes pulse { 0%,100%{opacity:1}50%{opacity:.4} }
        input[type="text"] { outline:none; }
      `}</style>

      {/* Sidebar */}
      <div style={{
        width: 260, background: "#111827", borderRight: "1px solid #1F2D40",
        padding: "24px 16px", display: "flex", flexDirection: "column", gap: 16,
        flexShrink: 0
      }}>
        <div>
          <div style={{ fontFamily: "'Syne',sans-serif", fontSize: "1rem", fontWeight: 800, color: "#00C6A2", letterSpacing: "-.3px" }}>
            🏛️ IRDAI Compliance GPT
          </div>
          <div style={{ fontSize: ".72rem", color: "#475569", marginTop: 2 }}>Regulatory Intelligence System</div>
        </div>

        {/* Status block */}
        <div style={{ background: "rgba(0,198,162,.06)", border: "1px solid #1F2D40", borderRadius: 8, padding: "12px 14px" }}>
          <div style={{ fontSize: ".7rem", color: "#00C6A2", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 8, fontWeight: 600 }}>System Status</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <div className="pulse-dot" />
            <span style={{ fontSize: ".8rem", color: "#34D399", fontWeight: 600 }}>Online & Ready</span>
          </div>
          <div style={{ fontSize: ".78rem", color: "#94A3B8" }}>Vector DB: <span style={{ color: "#E2E8F0" }}>{vecChunks.toLocaleString()} chunks</span></div>
          <div style={{ fontSize: ".78rem", color: "#94A3B8", marginTop: 2 }}>PDFs: <span style={{ color: "#E2E8F0" }}>{totalPdfs}</span></div>
        </div>

        {/* Document inventory */}
        <div style={{ background: "rgba(0,198,162,.04)", border: "1px solid #1F2D40", borderRadius: 8, padding: "12px 14px" }}>
          <div style={{ fontSize: ".7rem", color: "#00C6A2", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 8, fontWeight: 600 }}>Document Inventory</div>
          {Object.entries(DB_STATS).map(([cat, cnt]) => (
            <div key={cat} style={{ display: "flex", justifyContent: "space-between", fontSize: ".78rem", marginBottom: 4 }}>
              <span style={{ color: "#94A3B8" }}>📄 {cat.charAt(0).toUpperCase() + cat.slice(1)}</span>
              <span style={{ color: "#E2E8F0", fontWeight: 600 }}>{cnt}</span>
            </div>
          ))}
        </div>

        <div style={{ borderTop: "1px solid #1F2D40", paddingTop: 14 }}>
          <div style={{ fontSize: ".75rem", color: "#475569", marginBottom: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".5px" }}>Admin Actions</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <button className="action-btn" onClick={handleCrawl} disabled={crawlLoading} style={{ textAlign: "left" }}>
              {crawlLoading ? <><span className="spinner" style={{ width: 12, height: 12, marginRight: 6 }} />Crawling…</> : "🕷️  Run Crawler"}
            </button>
            {crawlStatus && (
              <div className="fade-in" style={{ fontSize: ".73rem", color: "#34D399", background: "rgba(52,211,153,.08)", border: "1px solid rgba(52,211,153,.2)", borderRadius: 6, padding: "6px 10px" }}>
                ✓ {Object.values(crawlStatus).reduce((a,b)=>a+b,0)} new PDFs downloaded
              </div>
            )}
            <button className="action-btn danger" style={{ textAlign: "left" }}>
              📥  Run Ingestion
            </button>
          </div>
        </div>

        <div style={{ marginTop: "auto", background: "rgba(0,0,0,.3)", borderRadius: 8, padding: "10px 14px" }}>
          <div style={{ fontSize: ".68rem", color: "#475569", lineHeight: 1.6 }}>
            LLM: Mistral-7B-Instruct<br />
            Embed: all-MiniLM-L6-v2<br />
            VectorDB: ChromaDB<br />
            API: HuggingFace Inference
          </div>
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {/* Title banner */}
        <div style={{
          background: "linear-gradient(135deg,#0F2027,#203A43,#2C5364)",
          borderBottom: "1px solid #1F2D40",
          padding: "24px 36px", position: "relative", overflow: "hidden"
        }}>
          <div style={{
            position: "absolute", top: -40, right: -40, width: 220, height: 220,
            background: "radial-gradient(circle, rgba(0,198,162,.15), transparent 70%)",
            borderRadius: "50%"
          }} />
          <h1 style={{ fontFamily: "'Syne',sans-serif", fontSize: "1.7rem", fontWeight: 800, color: "#00C6A2", margin: 0 }}>
            🏛️ IRDAI Compliance GPT
          </h1>
          <p style={{ color: "#94A3B8", margin: "6px 0 0", fontSize: ".85rem" }}>
            Regulatory Intelligence System · HuggingFace + RAG · Internal Compliance Use Only
          </p>
        </div>

        <div style={{ padding: "28px 36px" }}>
          {/* Metrics */}
          <div style={{ display: "flex", gap: 16, marginBottom: 28 }}>
            <MetricCard value={totalPdfs} label="PDFs Indexed" />
            <MetricCard value={vecChunks.toLocaleString()} label="Vector Chunks" />
            <MetricCard value="4" label="Categories" />
            <MetricCard value="🟢 Ready" label="System Status" accent="#34D399" />
          </div>

          {/* Tabs */}
          <div style={{ display: "flex", gap: 4, marginBottom: 24, borderBottom: "1px solid #1F2D40", paddingBottom: 12 }}>
            {["query", "documents", "audit"].map(tab => (
              <button key={tab} className={`tab-btn ${activeTab === tab ? "active" : ""}`}
                onClick={() => setActiveTab(tab)}>
                {{ query: "💬 Ask a Question", documents: "📂 Documents", audit: "📊 Audit Log" }[tab]}
              </button>
            ))}
          </div>

          {activeTab === "query" && (
            <div>
              <div style={{ marginBottom: 8 }}>
                <span style={{ fontWeight: 600, fontSize: ".95rem" }}>Ask a Compliance Question</span>
                <span style={{ color: "#64748B", fontSize: ".8rem", marginLeft: 10 }}>
                  Query IRDAI regulations, circulars, notifications and guidelines
                </span>
              </div>

              {/* Example chips */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
                {EXAMPLE_QUERIES.map(q => (
                  <button key={q} onClick={() => handleQuery(q)} style={{
                    background: "rgba(0,198,162,.06)", border: "1px solid rgba(0,198,162,.2)",
                    color: "#00C6A2", borderRadius: 20, padding: "5px 12px",
                    fontSize: ".75rem", cursor: "pointer", transition: "all .2s",
                    fontFamily: "'Inter',sans-serif"
                  }} onMouseEnter={e => e.target.style.background="rgba(0,198,162,.14)"}
                     onMouseLeave={e => e.target.style.background="rgba(0,198,162,.06)"}>
                    {q.length > 52 ? q.slice(0, 52) + "…" : q}
                  </button>
                ))}
              </div>

              {/* Input */}
              <div style={{ position: "relative" }}>
                <textarea
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="e.g. What are the minimum capital requirements for a general insurer?"
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleQuery(); } }}
                  style={{
                    width: "100%", height: 100, background: "#111827",
                    border: "1px solid #1F2D40", borderRadius: 10, padding: "14px 16px",
                    color: "#E2E8F0", fontSize: ".9rem", fontFamily: "'Inter',sans-serif",
                    lineHeight: 1.6,
                    borderColor: query ? "#00C6A2" : "#1F2D40",
                    transition: "border-color .2s"
                  }}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
                <button
                  onClick={() => handleQuery()}
                  disabled={loading || !query.trim()}
                  style={{
                    background: loading ? "#1F2D40" : "linear-gradient(135deg,#00C6A2,#00A88A)",
                    color: loading ? "#64748B" : "#0B0F1A",
                    border: "none", borderRadius: 8, padding: "10px 28px",
                    fontWeight: 700, fontSize: ".9rem",
                    fontFamily: "'Syne',sans-serif", letterSpacing: ".3px",
                    transition: "all .2s", display: "flex", alignItems: "center", gap: 8
                  }}>
                  {loading ? <><span className="spinner" />Searching regulations…</> : "🔍  Ask IRDAI GPT"}
                </button>
                {elapsed && !loading && (
                  <span style={{ fontSize: ".78rem", color: "#64748B" }}>⏱ {elapsed}s</span>
                )}
              </div>

              {/* Answer */}
              {result && (
                <div className="fade-in" style={{ marginTop: 24 }}>
                  <div style={{
                    background: "#111827", border: "1px solid #00C6A2", borderRadius: 10,
                    padding: "24px 28px", lineHeight: 1.75, fontSize: ".88rem"
                  }}>
                    <TypewriterText text={result.answer} active={true} />
                  </div>

                  {/* Citations */}
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: ".8rem", color: "#64748B", marginBottom: 8, fontWeight: 600 }}>
                      📎 Source Citations
                    </div>
                    <div>
                      {result.citations.map((c, i) => (
                        <CitationBadge key={i} source={c.source} page={c.page} score={c.score} />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Disclaimer */}
              <div style={{
                background: "rgba(245,158,11,.07)", border: "1px solid rgba(245,158,11,.25)",
                borderRadius: 8, padding: "12px 16px", marginTop: 28,
                fontSize: ".78rem", color: "#FCD34D", lineHeight: 1.6
              }}>
                ⚠️ <strong>Disclaimer:</strong> For internal compliance use only. Processes only public IRDAI documents.
                No policyholder data is stored. AI responses should be verified against official IRDAI publications.
              </div>
            </div>
          )}

          {activeTab === "documents" && (
            <div className="fade-in">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                {Object.entries(DB_STATS).map(([cat, cnt]) => (
                  <div key={cat} style={{
                    background: "#111827", border: "1px solid #1F2D40", borderRadius: 10, padding: "20px 22px"
                  }}>
                    <div style={{ fontSize: "1.6rem", marginBottom: 6 }}>
                      {{ regulations: "📜", circulars: "📋", notifications: "🔔", guidelines: "📌" }[cat]}
                    </div>
                    <div style={{ fontFamily: "'Syne',sans-serif", fontSize: "1.5rem", fontWeight: 700, color: "#00C6A2" }}>{cnt}</div>
                    <div style={{ fontSize: ".8rem", color: "#94A3B8", marginTop: 2 }}>{cat.charAt(0).toUpperCase()+cat.slice(1)}</div>
                    <div style={{ marginTop: 12, height: 3, background: "#1F2D40", borderRadius: 2 }}>
                      <div style={{ height: "100%", background: "#00C6A2", borderRadius: 2, width: `${(cnt/400)*100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "audit" && (
            <div className="fade-in">
              <div style={{ background: "#111827", border: "1px solid #1F2D40", borderRadius: 10, padding: "20px 22px" }}>
                <div style={{ fontSize: ".8rem", color: "#64748B", marginBottom: 16 }}>Recent Query Log (demo)</div>
                {[
                  { q: "Solvency margin requirements for life insurers?", t: "2 min ago", status: "✓" },
                  { q: "IRDAI guidelines on motor insurance pricing", t: "15 min ago", status: "✓" },
                  { q: "Third party administrator regulations", t: "1 hr ago", status: "✓" },
                ].map((row, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: i < 2 ? "1px solid #1F2D40" : "none" }}>
                    <div>
                      <div style={{ fontSize: ".83rem" }}>{row.q}</div>
                      <div style={{ fontSize: ".72rem", color: "#475569", marginTop: 2 }}>{row.t}</div>
                    </div>
                    <span style={{ color: "#34D399", fontSize: ".85rem" }}>{row.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
