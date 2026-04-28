import { useState, useEffect } from "react";
import { AlertTriangle, ExternalLink, FileText, CheckCircle, XCircle, RefreshCw, Zap } from "lucide-react";
import { apiCall } from "../App";

const STATUS_CONFIG = {
  detected:      { color: "#f59e0b", bg: "rgba(245,158,11,0.12)",  label: "Detected" },
  confirmed:     { color: "#ef4444", bg: "rgba(239,68,68,0.12)",   label: "Confirmed" },
  disputed:      { color: "#8b5cf6", bg: "rgba(139,92,246,0.12)", label: "Disputed" },
  resolved:      { color: "#10b981", bg: "rgba(16,185,129,0.12)", label: "Resolved" },
  false_positive:{ color: "#6b7280", bg: "rgba(107,114,128,0.12)","label": "False Positive" },
};

const PLATFORM_EMOJI = { twitter: "🐦", youtube: "▶️", instagram: "📷", web: "🌐", facebook: "📘" };

function SimilarityBar({ score }) {
  const color = score >= 95 ? "#ef4444" : score >= 85 ? "#f59e0b" : "#3b82f6";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2 }}>
        <div style={{ width: `${score}%`, height: "100%", background: color, borderRadius: 2, transition: "width 0.4s" }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 36, textAlign: "right" }}>{score?.toFixed(0)}%</span>
    </div>
  );
}

function ViolationDetail({ v, onUpdate, onClose }) {
  const [updating, setUpdating] = useState(false);
  const [dmcaText, setDmcaText] = useState(null);
  const sc = STATUS_CONFIG[v.status] || STATUS_CONFIG.detected;

  const updateStatus = async (newStatus) => {
    setUpdating(true);
    try {
      const r = await apiCall(`/violations/${v.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      const updated = await r.json();
      onUpdate(updated);
    } finally {
      setUpdating(false);
    }
  };

  const generateDMCA = async () => {
    const r = await apiCall(`/violations/${v.id}/dmca`, { method: "POST" });
    const data = await r.json();
    setDmcaText(data.dmca_notice);
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
    }}>
      <div style={{
        background: "linear-gradient(135deg, #0d1525, #0a1020)",
        border: "1px solid rgba(59,130,246,0.2)", borderRadius: 16,
        padding: 32, width: 560, maxHeight: "85vh", overflowY: "auto",
        boxShadow: "0 25px 60px rgba(0,0,0,0.6)",
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 24 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <span style={{ fontSize: 22 }}>{PLATFORM_EMOJI[v.platform] || "🌐"}</span>
              <span style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0", fontFamily: "'Space Grotesk',sans-serif" }}>
                {v.platform?.charAt(0).toUpperCase() + v.platform?.slice(1)} Violation
              </span>
            </div>
            <span style={{
              fontSize: 11, padding: "3px 9px", borderRadius: 6,
              background: sc.bg, color: sc.color, fontWeight: 600,
            }}>{sc.label}</span>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#718096", cursor: "pointer", fontSize: 20 }}>✕</button>
        </div>

        {/* URL */}
        <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: 9, padding: "12px 14px", marginBottom: 16 }}>
          <div style={{ fontSize: 10, color: "#4a6080", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>Infringing URL</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <a href={v.infringing_url} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 12, color: "#63b3ed", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
              {v.infringing_url}
            </a>
            <ExternalLink size={13} color="#3b82f6" />
          </div>
        </div>

        {/* Similarity */}
        <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: 9, padding: "12px 14px", marginBottom: 16 }}>
          <div style={{ fontSize: 10, color: "#4a6080", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>Match Confidence</div>
          <SimilarityBar score={v.similarity_score || 0} />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "#4a6080" }}>
            <span>Hamming Distance: <span style={{ color: "#a0aec0" }}>{v.hamming_distance}</span></span>
            <span>Method: <span style={{ color: "#a0aec0" }}>{v.match_type}</span></span>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#4a6080", marginBottom: 20 }}>
          <span>Detected: <span style={{ color: "#a0aec0" }}>{new Date(v.detected_at).toLocaleString()}</span></span>
          {v.is_dmca_sent && <span style={{ color: "#10b981" }}>✓ DMCA sent</span>}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: dmcaText ? 20 : 0 }}>
          {v.status !== "resolved" && (
            <button onClick={() => updateStatus("resolved")} disabled={updating} style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "9px 14px", borderRadius: 8, border: "none",
              background: "rgba(16,185,129,0.15)", color: "#10b981", cursor: "pointer", fontSize: 12, fontWeight: 600,
            }}>
              <CheckCircle size={13} /> Mark Resolved
            </button>
          )}
          {v.status !== "false_positive" && (
            <button onClick={() => updateStatus("false_positive")} style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "9px 14px", borderRadius: 8, border: "none",
              background: "rgba(107,114,128,0.12)", color: "#9ca3af", cursor: "pointer", fontSize: 12,
            }}>
              <XCircle size={13} /> False Positive
            </button>
          )}
          <button onClick={generateDMCA} style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "9px 14px", borderRadius: 8, border: "1px solid rgba(59,130,246,0.3)",
            background: "rgba(59,130,246,0.1)", color: "#63b3ed", cursor: "pointer", fontSize: 12, fontWeight: 600,
          }}>
            <FileText size={13} /> Generate DMCA
          </button>
        </div>

        {/* DMCA Text */}
        {dmcaText && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 11, color: "#4a6080", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>DMCA Notice</div>
            <textarea
              readOnly value={dmcaText}
              style={{
                width: "100%", height: 200, background: "rgba(0,0,0,0.4)",
                border: "1px solid rgba(59,130,246,0.15)", borderRadius: 8,
                color: "#a0aec0", fontSize: 11, fontFamily: "monospace", padding: 12,
                resize: "vertical", boxSizing: "border-box",
              }}
            />
            <button onClick={() => navigator.clipboard.writeText(dmcaText)} style={{
              marginTop: 8, padding: "7px 14px", borderRadius: 7, border: "none",
              background: "rgba(59,130,246,0.15)", color: "#63b3ed", cursor: "pointer", fontSize: 12,
            }}>
              Copy to Clipboard
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

const DEMO_VIOLATIONS = [
  { id: "1", platform: "twitter", infringing_url: "https://twitter.com/user/status/1234567890", similarity_score: 97.6, hamming_distance: 2, match_type: "phash", status: "detected", is_dmca_sent: false, detected_at: new Date(Date.now()-3600000).toISOString(), asset_id: "a1" },
  { id: "2", platform: "youtube", infringing_url: "https://youtube.com/watch?v=dQw4w9WgXcQ", similarity_score: 94.1, hamming_distance: 4, match_type: "phash", status: "confirmed", is_dmca_sent: true, detected_at: new Date(Date.now()-7200000).toISOString(), asset_id: "a2" },
  { id: "3", platform: "instagram", infringing_url: "https://instagram.com/p/ABC123xyz789", similarity_score: 91.3, hamming_distance: 6, match_type: "dhash", status: "detected", is_dmca_sent: false, detected_at: new Date(Date.now()-14400000).toISOString(), asset_id: "a1" },
  { id: "4", platform: "web", infringing_url: "https://randomnews.com/sports/stolen-highlight-photo", similarity_score: 88.0, hamming_distance: 8, match_type: "phash", status: "resolved", is_dmca_sent: true, detected_at: new Date(Date.now()-86400000).toISOString(), asset_id: "a3" },
  { id: "5", platform: "twitter", infringing_url: "https://twitter.com/anotheruser/status/9876543210", similarity_score: 95.2, hamming_distance: 3, match_type: "phash", status: "detected", is_dmca_sent: false, detected_at: new Date(Date.now()-1800000).toISOString(), asset_id: "a2" },
];

export default function Violations() {
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState("all");
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    apiCall("/violations/")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.items?.length) setViolations(data.items);
        else setViolations(DEMO_VIOLATIONS);
      })
      .catch(() => setViolations(DEMO_VIOLATIONS))
      .finally(() => setLoading(false));
  }, []);

  const handleUpdate = (updated) => {
    setViolations((prev) => prev.map((v) => (v.id === updated.id ? updated : v)));
    setSelected(updated);
  };

  const triggerScan = async () => {
    setScanning(true);
    await apiCall("/violations/scan/trigger", { method: "POST" }).catch(() => {});
    setTimeout(() => setScanning(false), 3000);
  };

  const filtered = filter === "all" ? violations : violations.filter((v) => v.status === filter);
  const counts = violations.reduce((acc, v) => { acc[v.status] = (acc[v.status] || 0) + 1; return acc; }, {});

  return (
    <div style={{ padding: "32px 36px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "#e2e8f0", fontFamily: "'Space Grotesk',sans-serif", margin: 0 }}>
            Violations
          </h1>
          <div style={{ fontSize: 13, color: "#4a6080", marginTop: 4 }}>
            {violations.length} detected · {counts.detected || 0} needs action
          </div>
        </div>
        <button onClick={triggerScan} disabled={scanning} style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "10px 20px", borderRadius: 10, border: "1px solid rgba(59,130,246,0.3)",
          background: scanning ? "rgba(59,130,246,0.08)" : "rgba(59,130,246,0.12)",
          color: "#63b3ed", cursor: scanning ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 600,
        }}>
          {scanning
            ? <><RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> Scanning...</>
            : <><Zap size={14} /> Run Scan</>
          }
        </button>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 24 }}>
        {["all", "detected", "confirmed", "resolved", "false_positive"].map((f) => {
          const active = filter === f;
          const sc = STATUS_CONFIG[f] || { color: "#a0aec0", bg: "rgba(160,174,192,0.1)", label: "All" };
          return (
            <button key={f} onClick={() => setFilter(f)} style={{
              padding: "6px 14px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 12, fontWeight: active ? 600 : 400,
              background: active ? sc.bg : "transparent",
              color: active ? sc.color : "#4a6080",
              transition: "all 0.15s",
            }}>
              {f === "all" ? `All (${violations.length})` : `${sc.label} (${counts[f] || 0})`}
            </button>
          );
        })}
      </div>

      {/* Table */}
      <div style={{
        background: "linear-gradient(135deg, rgba(15,25,50,0.9), rgba(10,18,35,0.9))",
        border: "1px solid rgba(59,130,246,0.1)", borderRadius: 14, overflow: "hidden",
      }}>
        <div style={{
          display: "grid", gridTemplateColumns: "36px 1fr 140px 160px 100px 90px",
          padding: "12px 20px", borderBottom: "1px solid rgba(99,179,237,0.06)",
          fontSize: 10, color: "#4a6080", textTransform: "uppercase", letterSpacing: 1, gap: 12,
        }}>
          <div></div>
          <div>Infringing URL</div>
          <div>Platform</div>
          <div>Similarity</div>
          <div>Status</div>
          <div>Detected</div>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: 40, color: "#4a6080" }}>Loading violations...</div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: "center", padding: 60, color: "#4a6080" }}>
            <AlertTriangle size={32} style={{ margin: "0 auto 12px", display: "block", opacity: 0.3 }} color="#f59e0b" />
            No violations found
          </div>
        ) : filtered.map((v) => {
          const sc = STATUS_CONFIG[v.status] || STATUS_CONFIG.detected;
          return (
            <div
              key={v.id}
              onClick={() => setSelected(v)}
              style={{
                display: "grid", gridTemplateColumns: "36px 1fr 140px 160px 100px 90px",
                padding: "14px 20px", gap: 12,
                borderBottom: "1px solid rgba(99,179,237,0.04)",
                cursor: "pointer", transition: "background 0.15s", alignItems: "center",
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = "rgba(59,130,246,0.04)"}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
            >
              <div style={{ fontSize: 18, textAlign: "center" }}>{PLATFORM_EMOJI[v.platform] || "🌐"}</div>
              <div style={{ fontSize: 12, color: "#a0aec0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {v.infringing_url}
              </div>
              <div style={{ fontSize: 12, color: "#718096", textTransform: "capitalize" }}>{v.platform}</div>
              <div style={{ paddingRight: 8 }}><SimilarityBar score={v.similarity_score || 0} /></div>
              <div>
                <span style={{
                  fontSize: 11, padding: "3px 8px", borderRadius: 6,
                  background: sc.bg, color: sc.color, fontWeight: 600,
                }}>{sc.label}</span>
              </div>
              <div style={{ fontSize: 11, color: "#4a6080" }}>
                {new Date(v.detected_at).toLocaleDateString()}
              </div>
            </div>
          );
        })}
      </div>

      {selected && (
        <ViolationDetail v={selected} onUpdate={handleUpdate} onClose={() => setSelected(null)} />
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
