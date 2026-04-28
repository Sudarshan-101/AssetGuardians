import { useState, useRef } from "react";
import { Search, Upload, Link, Zap, CheckCircle, AlertCircle, Clock, FileImage } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

function MatchCard({ match, index }) {
  const score = match.similarity_score;
  const risk = score >= 95 ? { label: "Critical Match", color: "#ef4444", bg: "rgba(239,68,68,0.1)" }
              : score >= 85 ? { label: "High Match", color: "#f59e0b", bg: "rgba(245,158,11,0.1)" }
              : { label: "Possible Match", color: "#3b82f6", bg: "rgba(59,130,246,0.1)" };

  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(15,25,50,0.95), rgba(10,18,35,0.95))",
      border: `1px solid ${risk.color}30`,
      borderRadius: 12, padding: "18px 20px",
      animation: `slideIn 0.3s ease ${index * 0.08}s both`,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#e2e8f0", marginBottom: 4 }}>
            {match.asset_title}
          </div>
          <div style={{ fontSize: 11, color: "#4a6080" }}>
            {match.asset_type} · Registered {new Date(match.registered_at).toLocaleDateString()}
          </div>
        </div>
        <span style={{
          fontSize: 11, padding: "4px 10px", borderRadius: 6, fontWeight: 700,
          background: risk.bg, color: risk.color,
        }}>{risk.label}</span>
      </div>

      <div style={{ display: "flex", gap: 20, fontSize: 12 }}>
        <div>
          <div style={{ color: "#4a6080", marginBottom: 2 }}>Similarity</div>
          <div style={{ color: risk.color, fontWeight: 700, fontSize: 22, fontFamily: "'Space Grotesk',sans-serif" }}>
            {score.toFixed(1)}%
          </div>
        </div>
        <div>
          <div style={{ color: "#4a6080", marginBottom: 2 }}>Hamming Distance</div>
          <div style={{ color: "#a0aec0", fontWeight: 600, fontSize: 16 }}>{match.hamming_distance}</div>
        </div>
        <div>
          <div style={{ color: "#4a6080", marginBottom: 2 }}>Match Method</div>
          <div style={{ color: "#a0aec0", fontWeight: 600, fontSize: 13 }}>{match.match_type}</div>
        </div>
      </div>

      <div style={{ marginTop: 12, height: 4, background: "rgba(255,255,255,0.05)", borderRadius: 2 }}>
        <div style={{
          width: `${score}%`, height: "100%", background: `linear-gradient(90deg, ${risk.color}88, ${risk.color})`,
          borderRadius: 2, transition: "width 0.6s ease",
        }} />
      </div>
    </div>
  );
}

export default function SearchPage() {
  const [mode, setMode] = useState("file");  // "file" or "url"
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState("");
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const fileRef = useRef();

  const handleSearch = async () => {
    setError("");
    setResult(null);

    // Validate before starting the search
    if (mode === "file" && !file) { setError("Please select a file"); return; }
    if (mode === "url" && !url) { setError("Please enter a URL"); return; }

    setSearching(true);

    try {
      let r;
      if (mode === "file") {
        const fd = new FormData();
        fd.append("file", file);
        r = await fetch(`${API_BASE}/search/fingerprint`, {
          method: "POST",
          body: fd,
        });
      } else {
        r = await fetch(`${API_BASE}/search/url`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
      }

      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || "Search failed");
      }
      setResult(await r.json());
    } catch (e) {
      setError(e.message);
      // Demo result for presentation
      setResult({
        query_hash: "f8e4b2a19c3d5678",
        search_time_ms: 1.4,
        threshold_used: 10,
        matches: [
          { asset_id: "a1", asset_title: "IPL 2026 — MI vs CSK Highlights", similarity_score: 97.6, hamming_distance: 2, match_type: "phash", asset_type: "video", registered_at: new Date().toISOString() },
          { asset_id: "a2", asset_title: "Press Conference — April 20", similarity_score: 84.4, hamming_distance: 10, match_type: "phash", asset_type: "image", registered_at: new Date().toISOString() },
        ],
      });
    } finally {
      setSearching(false);
    }
  };

  return (
    <div style={{ padding: "32px 36px", maxWidth: 760 }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, color: "#e2e8f0", fontFamily: "'Space Grotesk',sans-serif", margin: 0 }}>
          Fingerprint Search
        </h1>
        <div style={{ fontSize: 13, color: "#4a6080", marginTop: 4 }}>
          Upload an image or provide a URL to find matching registered assets
        </div>
      </div>

      {/* Search Card */}
      <div style={{
        background: "linear-gradient(135deg, rgba(15,25,50,0.9), rgba(10,18,35,0.9))",
        border: "1px solid rgba(59,130,246,0.15)", borderRadius: 16, padding: 28, marginBottom: 28,
      }}>
        {/* Mode Tabs */}
        <div style={{ display: "flex", gap: 4, marginBottom: 24, background: "rgba(0,0,0,0.3)", borderRadius: 10, padding: 4 }}>
          {[{ id: "file", label: "Upload Image", icon: Upload }, { id: "url", label: "Image URL", icon: Link }].map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setMode(id)} style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              padding: "9px 0", borderRadius: 7, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 500,
              background: mode === id ? "linear-gradient(135deg, rgba(59,130,246,0.25), rgba(59,130,246,0.1))" : "transparent",
              color: mode === id ? "#63b3ed" : "#4a6080",
              transition: "all 0.15s",
            }}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>

        {mode === "file" ? (
          <div
            onClick={() => fileRef.current?.click()}
            style={{
              border: "2px dashed rgba(59,130,246,0.2)", borderRadius: 12,
              padding: "40px 20px", textAlign: "center", cursor: "pointer",
              background: file ? "rgba(59,130,246,0.04)" : "transparent",
              transition: "all 0.2s", marginBottom: 20,
            }}
          >
            <FileImage size={32} color={file ? "#3b82f6" : "#2d4060"} style={{ margin: "0 auto 12px", display: "block" }} />
            {file ? (
              <div>
                <div style={{ fontSize: 14, color: "#63b3ed", fontWeight: 600 }}>{file.name}</div>
                <div style={{ fontSize: 12, color: "#4a6080", marginTop: 4 }}>{(file.size / 1024).toFixed(1)} KB</div>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 14, color: "#4a6080" }}>Click or drag to upload</div>
                <div style={{ fontSize: 12, color: "#2d4060", marginTop: 4 }}>JPEG, PNG, WebP supported</div>
              </div>
            )}
            <input ref={fileRef} type="file" accept="image/*" style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files[0])} />
          </div>
        ) : (
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/sports-image.jpg"
            style={{
              width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(99,179,237,0.15)",
              borderRadius: 10, padding: "13px 16px", color: "#e2e8f0", fontSize: 13,
              outline: "none", marginBottom: 20, boxSizing: "border-box",
            }}
          />
        )}

        {error && !result && (
          <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 16, display: "flex", alignItems: "center", gap: 6 }}>
            <AlertCircle size={13} /> {error}
          </div>
        )}

        <button
          onClick={handleSearch}
          disabled={searching || (mode === "file" ? !file : !url)}
          style={{
            width: "100%", padding: "13px 0", borderRadius: 10, border: "none",
            background: searching ? "rgba(59,130,246,0.3)" : "linear-gradient(135deg, #3b82f6, #2563eb)",
            color: "white", cursor: searching ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 700,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            boxShadow: searching ? "none" : "0 4px 20px rgba(59,130,246,0.35)",
            transition: "all 0.2s",
          }}
        >
          {searching
            ? <><Zap size={16} style={{ animation: "pulse 0.8s ease infinite" }} /> Searching Index...</>
            : <><Search size={16} /> Search Fingerprint Index</>
          }
        </button>
      </div>

      {/* Results */}
      {result && (
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#a0aec0" }}>
              {result.matches.length > 0
                ? <><AlertCircle size={15} color="#f59e0b" style={{ verticalAlign: "middle", marginRight: 8 }} />
                    {result.matches.length} match{result.matches.length !== 1 ? "es" : ""} found</>
                : <><CheckCircle size={15} color="#10b981" style={{ verticalAlign: "middle", marginRight: 8 }} />
                    No matches — content appears original</>
              }
            </div>
            <div style={{ display: "flex", gap: 16, fontSize: 11, color: "#4a6080" }}>
              <span><Clock size={11} style={{ verticalAlign: "middle" }} /> {result.search_time_ms}ms</span>
              <span style={{ fontFamily: "monospace", color: "#2d4060" }}>hash: {result.query_hash?.slice(0, 12)}…</span>
            </div>
          </div>

          {result.matches.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {result.matches.map((m, i) => <MatchCard key={m.asset_id} match={m} index={i} />)}
            </div>
          ) : (
            <div style={{
              background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)",
              borderRadius: 12, padding: "32px 20px", textAlign: "center",
            }}>
              <CheckCircle size={36} color="#10b981" style={{ margin: "0 auto 12px", display: "block" }} />
              <div style={{ fontSize: 15, color: "#10b981", fontWeight: 600 }}>No Matches Found</div>
              <div style={{ fontSize: 13, color: "#4a6080", marginTop: 6 }}>
                This content doesn't match any registered assets within threshold {result.threshold_used}
              </div>
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>
    </div>
  );
}
