import { useState, useEffect, useRef } from "react";
import { Upload, FileImage, Video, Trash2, Clock, RefreshCw } from "lucide-react";
import { apiCall } from "../App";

function UploadModal({ onClose, onSuccess }) {
  const [file, setFile] = useState(null);
  const [form, setForm] = useState({ title: "", description: "", rights_owner: "", tags: "" });
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef();

  const handleUpload = async () => {
    if (!file || !form.title) {
      setError("Title and file are required");
      return;
    }
    setUploading(true);
    setError("");

    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", form.title);
    fd.append("description", form.description);
    fd.append("rights_owner", form.rights_owner);
    fd.append("tags", form.tags);

    try {
      const r = await fetch(
        `${import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"}/assets/upload`,
        { method: "POST", body: fd }
      );
      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || "Upload failed");
      }
      const asset = await r.json();
      onSuccess(asset);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
    }}>
      <div style={{
        background: "linear-gradient(135deg, #0d1525, #0a1020)",
        border: "1px solid rgba(59,130,246,0.2)",
        borderRadius: 16, padding: 32, width: 480, maxHeight: "90vh", overflowY: "auto",
        boxShadow: "0 25px 60px rgba(0,0,0,0.6)",
      }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0", margin: "0 0 24px", fontFamily: "'Space Grotesk', sans-serif" }}>
          Register New Asset
        </h2>

        {/* File Drop */}
        <div
          onClick={() => inputRef.current?.click()}
          style={{
            border: "2px dashed rgba(59,130,246,0.3)", borderRadius: 12,
            padding: "28px 20px", textAlign: "center", cursor: "pointer",
            marginBottom: 20, background: file ? "rgba(59,130,246,0.05)" : "transparent",
            transition: "all 0.2s",
          }}
        >
          <Upload size={24} color="#3b82f6" style={{ margin: "0 auto 8px", display: "block" }} />
          {file ? (
            <div>
              <div style={{ fontSize: 13, color: "#63b3ed", fontWeight: 600 }}>{file.name}</div>
              <div style={{ fontSize: 11, color: "#4a6080", marginTop: 4 }}>{(file.size / 1024 / 1024).toFixed(2)} MB</div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 13, color: "#718096" }}>Drop file or click to browse</div>
              <div style={{ fontSize: 11, color: "#4a6080", marginTop: 4 }}>JPEG, PNG, MP4, MOV — up to 500MB</div>
            </div>
          )}
          <input ref={inputRef} type="file" accept="image/*,video/*" style={{ display: "none" }}
            onChange={(e) => setFile(e.target.files[0])} />
        </div>

        {/* Form Fields */}
        {[
          { key: "title",       label: "Title *",      placeholder: "Match Highlights — Apr 22, 2026" },
          { key: "rights_owner",label: "Rights Owner", placeholder: "Your Organization Name" },
          { key: "description", label: "Description",  placeholder: "Optional description..." },
          { key: "tags",        label: "Tags",         placeholder: "match, highlights, IPL (comma-separated)" },
        ].map(({ key, label, placeholder }) => (
          <div key={key} style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 11, color: "#4a6080", textTransform: "uppercase", letterSpacing: 1, display: "block", marginBottom: 6 }}>
              {label}
            </label>
            <input
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              placeholder={placeholder}
              style={{
                width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(99,179,237,0.15)",
                borderRadius: 8, padding: "10px 12px", color: "#e2e8f0", fontSize: 13,
                outline: "none", boxSizing: "border-box",
              }}
            />
          </div>
        ))}

        {error && (
          <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 16, padding: "8px 12px", background: "rgba(239,68,68,0.1)", borderRadius: 8 }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
          <button onClick={onClose} style={{
            flex: 1, padding: "11px 0", borderRadius: 9, border: "1px solid rgba(99,179,237,0.15)",
            background: "transparent", color: "#718096", cursor: "pointer", fontSize: 13,
          }}>
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={uploading || !file || !form.title}
            style={{
              flex: 2, padding: "11px 0", borderRadius: 9, border: "none",
              background: uploading ? "rgba(59,130,246,0.4)" : "linear-gradient(135deg, #3b82f6, #2563eb)",
              color: "white", cursor: uploading ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 600,
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            }}
          >
            {uploading
              ? <><RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> Processing...</>
              : "Register Asset"
            }
          </button>
        </div>
      </div>
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function AssetCard({ asset, onDelete }) {
  const isVideo = asset.asset_type === "video";
  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(15,25,50,0.9), rgba(10,18,35,0.9))",
      border: "1px solid rgba(59,130,246,0.1)", borderRadius: 12, padding: "18px",
      transition: "border-color 0.2s",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 9,
          background: isVideo ? "rgba(139,92,246,0.15)" : "rgba(59,130,246,0.15)",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          {isVideo
            ? <Video size={18} color="#8b5cf6" />
            : <FileImage size={18} color="#3b82f6" />
          }
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {asset.title}
          </div>
          <div style={{ fontSize: 11, color: "#4a6080", marginTop: 3 }}>
            {asset.mime_type} · {asset.file_size ? `${(asset.file_size / 1024 / 1024).toFixed(1)}MB` : "—"}
          </div>
        </div>
        <button onClick={() => onDelete(asset.id)} style={{
          background: "none", border: "none", color: "#4a6080", cursor: "pointer", padding: 4,
        }}>
          <Trash2 size={14} />
        </button>
      </div>

      {asset.phash && (
        <div style={{
          background: "rgba(0,0,0,0.3)", borderRadius: 7, padding: "7px 10px", marginBottom: 10,
          fontFamily: "monospace", fontSize: 10, color: "#4a90d9",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          pHash: {asset.phash}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, padding: "3px 7px", borderRadius: 5, background: "rgba(16,185,129,0.12)", color: "#10b981", fontWeight: 600 }}>
          ✓ Indexed
        </span>
        <div style={{ fontSize: 10, color: "#4a6080", display: "flex", alignItems: "center", gap: 4 }}>
          <Clock size={10} />
          {new Date(asset.registered_at).toLocaleDateString()}
        </div>
      </div>
    </div>
  );
}

export default function Assets() {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [total, setTotal] = useState(0);

  const loadAssets = () => {
    setLoading(true);
    apiCall("/assets/")
      .then((r) => r.json())
      .then((data) => {
        setAssets(data.items || []);
        setTotal(data.total || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(loadAssets, []);

  const handleDelete = async (id) => {
    if (!confirm("Remove this asset from protection?")) return;
    await apiCall(`/assets/${id}`, { method: "DELETE" });
    loadAssets();
  };

  return (
    <div style={{ padding: "32px 36px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "#e2e8f0", fontFamily: "'Space Grotesk', sans-serif", margin: 0 }}>
            Registered Assets
          </h1>
          <div style={{ fontSize: 13, color: "#4a6080", marginTop: 4 }}>{total} assets protected</div>
        </div>
        <button
          onClick={() => setShowUpload(true)}
          style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "10px 20px", borderRadius: 10, border: "none",
            background: "linear-gradient(135deg, #3b82f6, #2563eb)",
            color: "white", cursor: "pointer", fontSize: 13, fontWeight: 600,
            boxShadow: "0 4px 15px rgba(59,130,246,0.3)",
          }}
        >
          <Upload size={15} /> Register Asset
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", color: "#4a6080", padding: 60 }}>Loading assets...</div>
      ) : assets.length === 0 ? (
        <div style={{
          textAlign: "center", padding: 80,
          border: "2px dashed rgba(59,130,246,0.15)", borderRadius: 16,
        }}>
          <FileImage size={40} color="#3b82f6" style={{ margin: "0 auto 16px", display: "block", opacity: 0.4 }} />
          <div style={{ color: "#4a6080", fontSize: 15 }}>No assets registered yet</div>
          <div style={{ color: "#2d4060", fontSize: 13, marginTop: 6 }}>Upload your first media file to start protection</div>
          <button onClick={() => setShowUpload(true)} style={{
            marginTop: 20, padding: "10px 24px", borderRadius: 9,
            background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.3)",
            color: "#63b3ed", cursor: "pointer", fontSize: 13,
          }}>
            Upload First Asset
          </button>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
          {assets.map((a) => <AssetCard key={a.id} asset={a} onDelete={handleDelete} />)}
        </div>
      )}

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onSuccess={loadAssets} />}
    </div>
  );
}
