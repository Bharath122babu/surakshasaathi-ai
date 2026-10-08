import { useState, useEffect, useCallback } from "react";

// ── API BASE — change to your server if not localhost ────────────────────────
const API = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

// ── All 5 sample messages from app.py ────────────────────────────────────────
const SAMPLES = [
  { label: "Electricity Disconnection", msg: "Your electricity will be cut off at 9:30 PM tonight. Call 9876543210 immediately." },
  { label: "KYC Phishing Link",         msg: "Dear SBI Customer, your KYC expired. Click http://sbi-kyc-update.xyz now or account blocked in 24h." },
  { label: "KBC Lottery Advance Fee",   msg: "Congratulations! You won Rs 25 Lakhs in KBC. Pay Rs 4999 processing fee to claim." },
  { label: "Digital Arrest (CBI)",      msg: "This is CBI Officer Sharma. You are under Digital Arrest for money laundering. Pay Rs 2 lakh bail now." },
  { label: "UPI PIN Reverse Trick",     msg: "Enter your UPI PIN to receive Rs 500 cashback into your account immediately." },
];

const SEV_COLOR = { CRITICAL:"#ff3b30", HIGH:"#ff9f0a", MEDIUM:"#ffd60a", LOW:"#30d158" };
const SEV_BG    = { CRITICAL:"rgba(255,59,48,.13)", HIGH:"rgba(255,159,10,.12)", MEDIUM:"rgba(255,214,10,.1)", LOW:"rgba(48,209,88,.1)" };
const LANG_OPTS = [{ k:"en", label:"English", flag:"🇬🇧" }, { k:"hi", label:"हिंदी", flag:"🇮🇳" }, { k:"hng", label:"Hinglish", flag:"🤝" }];

// ── tiny helpers ──────────────────────────────────────────────────────────────
const Pill = ({ children, color, bg }) => (
  <span style={{ display:"inline-block", padding:"3px 11px", borderRadius:20, fontSize:12, fontWeight:600, color, background:bg, margin:3, border:`1px solid ${color}33` }}>{children}</span>
);

const MetricCard = ({ icon, value, label, color }) => (
  <div style={{ background:"rgba(255,255,255,.04)", borderRadius:14, padding:"16px 18px", border:"1px solid rgba(255,255,255,.07)", borderTop:`2px solid ${color}` }}>
    <div style={{ fontSize:20, marginBottom:6 }}>{icon}</div>
    <div style={{ fontSize:22, fontWeight:800, color, fontFamily:"monospace" }}>{value}</div>
    <div style={{ fontSize:11, color:"rgba(255,255,255,.4)", textTransform:"uppercase", letterSpacing:"0.08em", marginTop:3 }}>{label}</div>
  </div>
);

const SevBadge = ({ sev }) => (
  <span style={{ fontSize:12, fontWeight:700, padding:"2px 10px", borderRadius:6, color:SEV_COLOR[sev]||"#888", background:SEV_BG[sev]||"rgba(128,128,128,.1)" }}>{sev}</span>
);

// ── API status indicator ──────────────────────────────────────────────────────
function APIStatus({ status }) {
  const map = { ok:["#30d158","LIVE"], error:["#ff3b30","OFFLINE"], checking:["#ff9f0a","..."] };
  const [c, t] = map[status] || map.checking;
  return (
    <div style={{ display:"flex", alignItems:"center", gap:6, padding:"5px 12px", borderRadius:20, background:`${c}18`, border:`1px solid ${c}44` }}>
      <span style={{ width:7, height:7, borderRadius:"50%", background:c, display:"inline-block", animation: status==="ok" ? "pulse 2s infinite" : "none" }} />
      <span style={{ fontSize:11, fontWeight:700, color:c }}>API {t}</span>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// TAB 1 — ANALYSE  (mirrors app.py tab_analyse)
// ════════════════════════════════════════════════════════════════════════════
function TabAnalyse({ lang, threshold }) {
  const [msg, setMsg]         = useState("");
  const [result, setResult]   = useState(null);
  const [busy, setBusy]       = useState(false);
  const [err, setErr]         = useState("");

  const runAnalysis = async () => {
    if (!msg.trim()) return;
    setBusy(true); setErr(""); setResult(null);
    try {
      const r = await fetch(`${API}/analyze`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ message: msg, language: lang, risk_threshold: threshold }),
      });
      if (!r.ok) throw new Error(`API ${r.status}`);
      setResult(await r.json());
    } catch(e) {
      setErr(`${e.message} — is api.py running on port 8000?`);
    }
    setBusy(false);
  };

  const score = result?.gemini_risk_score ?? 0;

  return (
    <div>
      <p style={{ fontSize:14, color:"rgba(255,255,255,.5)", marginBottom:16 }}>
        Paste a suspicious email, SMS or WhatsApp message
      </p>

      {/* Sample picker */}
      <div style={{ display:"flex", flexWrap:"wrap", gap:8, marginBottom:14 }}>
        {SAMPLES.map((s,i) => (
          <button key={i} onClick={() => { setMsg(s.msg); setResult(null); setErr(""); }}
            style={{ padding:"5px 13px", borderRadius:8, fontSize:12, fontWeight:600, cursor:"pointer",
              background:"rgba(255,159,10,.1)", border:"1px solid rgba(255,159,10,.3)", color:"#ff9f0a" }}>
            {s.label}
          </button>
        ))}
      </div>

      <textarea aria-label="Suspicious message" value={msg} onChange={e => { setMsg(e.target.value); setResult(null); setErr(""); }}
        placeholder="Paste suspicious message here…"
        style={{ width:"100%", minHeight:130, background:"rgba(255,255,255,.04)", border:"1px solid rgba(255,255,255,.1)",
          borderRadius:12, padding:14, color:"#fff", fontSize:15, lineHeight:1.6, outline:"none",
          fontFamily:"inherit", boxSizing:"border-box" }} />

      <button onClick={runAnalysis} disabled={busy || !msg.trim()}
        style={{ marginTop:12, width:"100%", padding:"13px 0", borderRadius:12, fontSize:15, fontWeight:700,
          background: busy ? "rgba(99,54,255,.3)" : "linear-gradient(135deg,#6336ff,#8b5cf6)",
          border:"none", color:"#fff", cursor: busy ? "default" : "pointer",
          boxShadow: busy ? "none" : "0 6px 20px rgba(99,54,255,.4)", opacity: !msg.trim() ? .5 : 1 }}>
        {busy ? "Reviewing message…" : "Review message"}
      </button>

      {err && <div style={{ marginTop:12, padding:"10px 14px", borderRadius:8, background:"rgba(255,59,48,.12)", border:"1px solid rgba(255,59,48,.3)", color:"#ff6b6b", fontSize:13 }}>❌ {err}</div>}

      {result && (
        <div style={{ marginTop:20 }}>

          {/* Stage 1: Similarity */}
          <div style={{ marginBottom:18 }}>
            <div style={{ fontSize:13, fontWeight:700, color:"rgba(255,255,255,.5)", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:10 }}>
              Stage 1 — Closest library pattern
            </div>
            <div style={{ display:"flex", alignItems:"center", gap:12 }}>
              <div style={{ flex:1, background:"rgba(255,255,255,.06)", borderRadius:6, height:10, overflow:"hidden" }}>
                <div style={{ height:"100%", borderRadius:6, width:`${(result.similarity_score*100).toFixed(0)}%`,
                  background: result.similarity_score > .8 ? "#ff3b30" : result.similarity_score > .6 ? "#ff9f0a" : "#30d158",
                  transition:"width .8s ease" }} />
              </div>
              <span style={{ fontSize:13, fontWeight:700, color:"#fff", minWidth:50 }}>{(result.similarity_score*100).toFixed(0)}%</span>
              <SevBadge sev={result.matched_severity} />
            </div>
            <div style={{ marginTop:8, fontSize:13, color:"rgba(255,255,255,.5)" }}>
              Matched: <em style={{ color:"rgba(255,255,255,.8)" }}>{result.matched_pattern}</em> · {result.matched_category}
            </div>
          </div>

          {/* Stage 2: Gemini */}
          <div style={{ fontSize:13, fontWeight:700, color:"rgba(255,255,255,.5)", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:14 }}>
            {result.analysis_source === "knowledge_base" ? "Curated library response · no model call" : "Stage 2 — Model-assisted analysis"}
          </div>

          {result.error ? (
            <div style={{ padding:"10px 14px", background:"rgba(255,59,48,.1)", border:"1px solid rgba(255,59,48,.3)", borderRadius:8, color:"#ff6b6b", fontSize:13 }}>
              Analysis error: {result.error}
            </div>
          ) : (
            <>
              {/* 4 metric mini-cards */}
              <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:16 }}>
                {[
                  { label:"Danger Level", value: result.danger_level, color: SEV_COLOR[result.danger_level]||"#888" },
                  { label:"Risk Score",   value: `${score}/10`,        color: score>=7?"#ff3b30":score>=5?"#ff9f0a":"#ffd60a" },
                  { label:"Response source", value: result.analysis_source === "knowledge_base" ? "Library" : "Gemini", color:"#65d6c0" },
                  { label:"Flagged",      value: result.flagged?"YES 🚨":"NO ✅", color: result.flagged?"#ff3b30":"#30d158" },
                ].map((m,i) => (
                  <div key={i} style={{ background:"rgba(255,255,255,.04)", borderRadius:10, padding:"12px 14px", border:"1px solid rgba(255,255,255,.07)" }}>
                    <div style={{ fontSize:10, color:"rgba(255,255,255,.4)", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:4 }}>{m.label}</div>
                    <div style={{ fontSize:16, fontWeight:800, color:m.color }}>{m.value}</div>
                  </div>
                ))}
              </div>

              {/* Scam type */}
              {result.scam_type && (
                <div style={{ marginBottom:12, fontSize:13 }}>
                  <span style={{ color:"rgba(255,255,255,.4)" }}>Scam Type: </span>
                  <span style={{ color:"#a78bff", fontWeight:700 }}>{result.scam_type}</span>
                </div>
              )}

              {/* Psychological tactics */}
              {result.psychological_tactics?.length > 0 && (
                <div style={{ marginBottom:14 }}>
                  <div style={{ fontSize:12, color:"rgba(255,255,255,.4)", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:8 }}>Psychological Tactics Detected</div>
                  <div>{result.psychological_tactics.map((t,i) => <Pill key={i} color="#ff9f0a" bg="rgba(255,159,10,.1)">{t}</Pill>)}</div>
                </div>
              )}

              {/* Deep Reasoning */}
              {result.reasoning && (
                <div style={{ marginBottom:14, background:"rgba(48,209,88,.05)", borderLeft:"3px solid #30d158", borderRadius:"0 8px 8px 0", padding:"12px 16px" }}>
                  <div style={{ fontSize:11, color:"rgba(255,255,255,.4)", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:6 }}>Deep Reasoning</div>
                  <div style={{ fontSize:13, lineHeight:1.7, color:"rgba(255,255,255,.75)", fontFamily:"monospace" }}>{result.reasoning}</div>
                </div>
              )}

              {/* Advice (language-aware from KB) */}
              {(result.hinglish_advice || result.advice) && (
                <div style={{ marginBottom:14, background:"rgba(255,159,10,.07)", border:"1px solid rgba(255,159,10,.2)", borderRadius:10, padding:"14px 16px" }}>
                  <div style={{ fontSize:11, color:"#ff9f0a", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:6 }}>Safety guidance</div>
                  <div style={{ fontSize:14, lineHeight:1.8, color:"rgba(255,255,255,.85)", fontStyle:"italic" }}>
                    {result.hinglish_advice || result.advice}
                  </div>
                </div>
              )}

              {/* Safe action */}
              {result.safe_action && (
                <div style={{ background:"rgba(48,209,88,.08)", border:"1px solid rgba(48,209,88,.25)", borderRadius:10, padding:"12px 16px", fontSize:14, color:"rgba(255,255,255,.9)" }}>
                  ✅ <strong>Safe Action:</strong> {result.safe_action}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// TAB 2 — LIVE FEED  (mirrors app.py tab_feed)
// ════════════════════════════════════════════════════════════════════════════
function TabFeed() {
  const [logs, setLogs]     = useState([]);
  const [total, setTotal]   = useState(0);
  const [busy, setBusy]     = useState(true);
  const [autoRef, setAutoRef] = useState(false);

  const loadLogs = useCallback(() => {
    return fetch(`${API}/logs?limit=50`)
      .then(r => { if (!r.ok) throw new Error(`API ${r.status}`); return r.json(); })
      .then(d => {
      setLogs(d.logs || []);
      setTotal(d.total || 0);
      })
      .catch(() => setLogs([]))
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  useEffect(() => {
    if (!autoRef) return;
    const t = setInterval(loadLogs, 10000);
    return () => clearInterval(t);
  }, [autoRef, loadLogs]);

  const COLS = ["timestamp","sender","subject","matched_pattern","similarity_score","danger_level","scam_type","flagged"];

  return (
    <div>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
        <span style={{ fontSize:14, color:"rgba(255,255,255,.5)" }}>
          {total} total entries in guardian_logs.csv
        </span>
        <div style={{ display:"flex", gap:10, alignItems:"center" }}>
          <label style={{ display:"flex", alignItems:"center", gap:7, fontSize:12, color:"rgba(255,255,255,.5)", cursor:"pointer" }}>
            <input type="checkbox" checked={autoRef} onChange={e => setAutoRef(e.target.checked)} />
            Auto-refresh (10s)
          </label>
          <button onClick={() => { setBusy(true); void loadLogs(); }}
            style={{ padding:"6px 14px", borderRadius:8, fontSize:12, fontWeight:600, cursor:"pointer",
              background:"rgba(99,54,255,.15)", border:"1px solid rgba(99,54,255,.35)", color:"#a78bff" }}>
            {busy ? "Loading…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      {logs.length === 0 ? (
        <div style={{ padding:"32px 0", textAlign:"center", color:"rgba(255,255,255,.3)", fontSize:14 }}>
          No detections logged yet.<br/>
          <span style={{ fontFamily:"monospace", fontSize:12, marginTop:8, display:"block" }}>Run python main_monitor.py to start the Watchman</span>
        </div>
      ) : (
        <div style={{ overflowX:"auto" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
            <thead>
              <tr>
                {COLS.map(c => (
                  <th key={c} style={{ textAlign:"left", padding:"8px 12px", borderBottom:"1px solid rgba(255,255,255,.1)",
                    color:"rgba(255,255,255,.4)", fontWeight:600, textTransform:"uppercase", letterSpacing:"0.07em", fontSize:11, whiteSpace:"nowrap" }}>
                    {c.replace(/_/g," ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((row, i) => {
                const dl = row.danger_level;
                return (
                  <tr key={i} style={{ borderBottom:"1px solid rgba(255,255,255,.05)", background: i%2===0?"transparent":"rgba(255,255,255,.015)" }}>
                    {COLS.map(c => (
                      <td key={c} style={{ padding:"8px 12px", color: c==="danger_level" ? (SEV_COLOR[row[c]]||"#888") : "rgba(255,255,255,.75)",
                        fontWeight: c==="danger_level" ? 700 : 400, whiteSpace: c==="timestamp"||c==="danger_level"?"nowrap":"normal",
                        background: c==="danger_level" ? (SEV_BG[dl]||"transparent") : "transparent",
                        maxWidth: c==="subject"||c==="matched_pattern" ? 200 : "none", overflow:"hidden", textOverflow:"ellipsis" }}>
                        {c==="flagged" ? (row[c]==="True"||row[c]===true ? "🚨 YES" : "✅ NO") : (row[c]||"—")}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// TAB 3 — KNOWLEDGE BASE  (mirrors app.py tab_kb)
// ════════════════════════════════════════════════════════════════════════════
function TabKB({ lang }) {
  const [patterns, setPatterns] = useState([]);
  const [search, setSearch]     = useState("");
  const [total, setTotal]       = useState(0);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch(`${API}/knowledge-base?search=${encodeURIComponent(search)}`);
        const d = await r.json();
        setPatterns(d.patterns || []);
        setTotal(d.total || 0);
      } catch { setPatterns([]); }
    };
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [search]);

  const adviceKey = { en:"advice_en", hi:"advice_hi", hng:"advice_hng" }[lang] || "advice_en";

  const sevIcon = { CRITICAL:"🔴", HIGH:"🟠", MEDIUM:"🟡", LOW:"🟢" };

  return (
    <div>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
        <span style={{ fontSize:14, color:"rgba(255,255,255,.5)" }}>{total} patterns loaded</span>
        <span style={{ fontSize:11, color:"rgba(255,255,255,.3)", fontFamily:"monospace" }}>Add more → context/data.py</span>
      </div>
      <input aria-label="Filter reference patterns" value={search} onChange={e => setSearch(e.target.value)}
        placeholder="🔍 Filter patterns…"
        style={{ width:"100%", marginBottom:16, padding:"10px 14px", background:"rgba(255,255,255,.05)",
          border:"1px solid rgba(255,255,255,.1)", borderRadius:10, color:"#fff", fontSize:14, outline:"none", boxSizing:"border-box" }} />

      <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
        {patterns.map(p => (
          <div key={p.id}>
            <button onClick={() => setExpanded(expanded===p.id ? null : p.id)}
              style={{ width:"100%", textAlign:"left", background:"rgba(255,255,255,.03)", border:"1px solid rgba(255,255,255,.08)",
                borderRadius:10, padding:"12px 16px", cursor:"pointer", display:"flex", alignItems:"center", gap:10 }}>
              <span>{sevIcon[p.severity]||"⚪"}</span>
              <span style={{ flex:1, fontWeight:600, color:"#fff", fontSize:14 }}>{p.pattern}</span>
              <span style={{ fontFamily:"monospace", fontSize:11, color:"rgba(255,255,255,.3)", marginRight:8 }}>{p.id}</span>
              <SevBadge sev={p.severity} />
              <span style={{ color:"rgba(255,255,255,.3)", fontSize:12 }}>{expanded===p.id ? "▲" : "▼"}</span>
            </button>
            {expanded === p.id && (
              <div style={{ background:"rgba(255,255,255,.02)", border:"1px solid rgba(255,255,255,.06)", borderTop:"none",
                borderRadius:"0 0 10px 10px", padding:"16px 18px" }}>
                <div style={{ display:"grid", gridTemplateColumns:"2fr 1fr", gap:20 }}>
                  <div>
                    <div style={{ fontSize:12, color:"rgba(255,255,255,.4)", marginBottom:4 }}>Category</div>
                    <div style={{ fontSize:13, color:"rgba(255,255,255,.8)", marginBottom:12 }}>{p.category}</div>
                    <div style={{ fontSize:12, color:"rgba(255,255,255,.4)", marginBottom:4 }}>Sample Message</div>
                    <div style={{ fontSize:13, color:"rgba(255,255,255,.65)", fontStyle:"italic", lineHeight:1.6, marginBottom:12 }}>"{p.content}"</div>
                    <div style={{ fontSize:12, color:"rgba(255,255,255,.4)", marginBottom:4 }}>Why it works</div>
                    <div style={{ fontSize:13, color:"rgba(255,255,255,.7)", lineHeight:1.6, marginBottom:12 }}>{p.logic}</div>
                    <div style={{ fontSize:12, color:"rgba(255,255,255,.4)", marginBottom:4 }}>
                      Advice ({lang === "en" ? "English" : lang === "hi" ? "Hindi" : "Hinglish"})
                    </div>
                    <div style={{ fontSize:13, color:"#ffd60a", lineHeight:1.6, fontStyle:"italic" }}>{p[adviceKey]}</div>
                  </div>
                  <div>
                    <div style={{ fontSize:12, color:"rgba(255,255,255,.4)", marginBottom:6 }}>Severity</div>
                    <div style={{ fontSize:22, fontWeight:800, color:SEV_COLOR[p.severity]||"#888", marginBottom:16 }}>{p.severity}</div>
                    <div style={{ fontSize:12, color:"rgba(255,255,255,.4)", marginBottom:6 }}>Hinglish Hook</div>
                    <div style={{ fontSize:13, color:"rgba(255,255,255,.6)", fontStyle:"italic", lineHeight:1.6 }}>{p.hinglish_hook}</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// ROOT APP
// ════════════════════════════════════════════════════════════════════════════
export default function App() {
  const [tab, setTab]           = useState(0);
  const [lang, setLang]         = useState("hng");
  const [threshold, setThreshold] = useState(5);
  const [apiStatus, setApiStatus] = useState("checking");
  const [stats, setStats]         = useState(null);

  // Check API health on mount
  useEffect(() => {
    fetch(`${API}/health`)
      .then(r => r.json())
      .then(d => { setApiStatus(d.status === "ok" ? "ok" : "error"); })
      .catch(() => setApiStatus("error"));
    fetch(`${API}/stats`)
      .then(r => r.json())
      .then(setStats)
      .catch(() => {});
  }, []);

  const TABS = ["⚡ Analyse Email", "📋 Live Detection Feed", "🗄️ Knowledge Base"];

  return (
    <div style={{
      minHeight:"100vh", background:"#070711", color:"#fff",
      fontFamily:"'Space Grotesk', system-ui, sans-serif",
      backgroundImage:"radial-gradient(ellipse at 10% 0%,rgba(99,54,255,.09) 0%,transparent 50%),radial-gradient(ellipse at 90% 100%,rgba(255,45,85,.06) 0%,transparent 50%)",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;700&display=swap');
        * { box-sizing:border-box; margin:0; padding:0; }
        textarea, input { font-family:inherit; }
        @keyframes pulse { 0%,100%{opacity:1}50%{opacity:.4} }
        ::-webkit-scrollbar{width:5px;height:5px}
        ::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:3px}
      `}</style>

      {/* ── SIDEBAR ── */}
      <div className="dashboard-sidebar" style={{
        position:"fixed", top:0, left:0, width:220, height:"100vh",
        background:"rgba(7,7,17,.95)", borderRight:"1px solid rgba(255,255,255,.06)",
        backdropFilter:"blur(20px)", display:"flex", flexDirection:"column", zIndex:100,
      }}>
        {/* Logo */}
        <div style={{ padding:"22px 18px 16px", borderBottom:"1px solid rgba(255,255,255,.06)" }}>
          <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:6 }}>
            <div style={{ width:36, height:36, borderRadius:10, background:"linear-gradient(135deg,#6336ff,#ff3b5c)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:18 }}>🛡️</div>
            <div>
              <div style={{ fontSize:15, fontWeight:800 }}>Suraksha Saathi</div>
              <div style={{ fontSize:9, color:"rgba(255,255,255,.35)", letterSpacing:"0.12em", textTransform:"uppercase" }}>v2.0 · Multi-Agent</div>
            </div>
          </div>
          <div style={{ marginTop:10 }}>
            <APIStatus status={apiStatus} />
          </div>
        </div>

        {/* Nav */}
        <nav style={{ padding:"14px 12px", flex:1 }}>
          <div style={{ fontSize:10, color:"rgba(255,255,255,.3)", letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 6px 8px" }}>Navigation</div>
          {TABS.map((t, i) => (
            <button key={i} onClick={() => setTab(i)}
              style={{ width:"100%", textAlign:"left", padding:"9px 12px", borderRadius:8, fontSize:13,
                fontWeight: tab===i ? 700 : 500, cursor:"pointer", border:"none", marginBottom:2,
                background: tab===i ? "rgba(99,54,255,.2)" : "transparent",
                color: tab===i ? "#a78bff" : "rgba(255,255,255,.6)",
                borderLeft: tab===i ? "2px solid #6336ff" : "2px solid transparent" }}>
              {t}
            </button>
          ))}
        </nav>

        {/* Settings */}
        <div style={{ padding:"14px 18px", borderTop:"1px solid rgba(255,255,255,.06)" }}>
          <div style={{ fontSize:11, color:"rgba(255,255,255,.4)", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:10 }}>⚙️ Settings</div>
          <div style={{ marginBottom:12 }}>
            <div style={{ fontSize:11, color:"rgba(255,255,255,.4)", marginBottom:6 }}>Alert Language</div>
            <div style={{ display:"flex", gap:4 }}>
              {LANG_OPTS.map(l => (
                <button key={l.k} aria-label={l.label} aria-pressed={lang === l.k} onClick={() => setLang(l.k)}
                  style={{ flex:1, padding:"5px 0", borderRadius:6, fontSize:11, fontWeight:600, cursor:"pointer", border:"none",
                    background: lang===l.k ? "rgba(99,54,255,.3)" : "rgba(255,255,255,.06)",
                    color: lang===l.k ? "#a78bff" : "rgba(255,255,255,.5)" }}>
                  {l.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div style={{ display:"flex", justifyContent:"space-between", fontSize:11, color:"rgba(255,255,255,.4)", marginBottom:6 }}>
              <span>Risk Threshold</span><span style={{ color:"#ff9f0a", fontWeight:700 }}>{threshold}</span>
            </div>
            <input aria-label="Risk threshold" type="range" min={0} max={10} value={threshold} onChange={e => setThreshold(+e.target.value)}
              style={{ width:"100%", accentColor:"#6336ff" }} />
          </div>
          <div style={{ marginTop:12 }}>
            <div style={{ fontSize:10, color:"rgba(255,255,255,.25)", lineHeight:1.5 }}>
              Backend {apiStatus === "ok" ? "connected" : "unavailable"}<br/>
              API on <span style={{ fontFamily:"monospace" }}>:8000</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── MAIN CONTENT ── */}
      <div className="dashboard-main" style={{ marginLeft:220, padding:"28px 28px" }}>

        {/* Header */}
        <div style={{ marginBottom:24 }}>
          <h1 style={{ fontSize:22, fontWeight:800, marginBottom:4 }}>
            {TABS[tab]}
          </h1>
          <div style={{ fontSize:12, color:"rgba(255,255,255,.35)", letterSpacing:"0.1em", textTransform:"uppercase" }}>
            Hackathon prototype · Context retrieval & model-assisted explanations
          </div>
        </div>

        {/* Metric row */}
        <div className="dashboard-metrics" style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:14, marginBottom:26 }}>
          <MetricCard icon="◉" value={apiStatus === "ok" ? "ONLINE" : "OFFLINE"} label="API connection" color="#65d6c0" />
          <MetricCard icon="!" value={stats ? stats.total_flagged : "—"} label="Flagged email logs" color="#ff9f0a" />
          <MetricCard icon="↗" value={stats?.accuracy || "—"} label="Library self-check · not detection accuracy" color="#65d6c0" />
          <MetricCard icon="▤" value={stats?.kb_patterns ?? "—"} label="Curated patterns" color="#ff9f0a" />
        </div>

        {/* Tab content */}
        <div style={{ background:"rgba(255,255,255,.025)", borderRadius:16, border:"1px solid rgba(255,255,255,.07)", padding:24, minHeight:400 }}>
          {tab === 0 && <TabAnalyse lang={lang} threshold={threshold} />}
          {tab === 1 && <TabFeed />}
          {tab === 2 && <TabKB lang={lang} />}
        </div>

        {/* Footer */}
        <div style={{ marginTop:20, textAlign:"center", fontSize:11, color:"rgba(255,255,255,.15)", fontFamily:"monospace" }}>
          SURAKSHASAATHI-AI · HACKATHON PROTOTYPE · AI SYNERGY HACKATHON 2026
        </div>
      </div>
    </div>
  );
}
