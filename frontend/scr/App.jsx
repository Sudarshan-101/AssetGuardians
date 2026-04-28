import { useState } from "react";
import { Shield, BarChart3, FileImage, AlertTriangle, Search, Menu, X } from "lucide-react";
import Dashboard from "./pages/Dashboard";
import Assets from "./pages/Assets";
import Violations from "./pages/Violations";
import SearchPage from "./pages/SearchPage";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export function apiCall(endpoint, options = {}) {
  return fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
}

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3 },
  { id: "assets",    label: "Assets",    icon: FileImage },
  { id: "violations",label: "Violations",icon: AlertTriangle },
  { id: "search",    label: "Search",    icon: Search },
];

function Sidebar({ activePage, onNavigate, collapsed, onToggle }) {
  return (
    <aside style={{
      width: collapsed ? 72 : 240,
      background: "linear-gradient(160deg, #0a0e1a 0%, #0d1525 60%, #0a1020 100%)",
      borderRight: "1px solid rgba(99,179,237,0.08)",
      height: "100vh",
      display: "flex",
      flexDirection: "column",
      transition: "width 0.25s cubic-bezier(.4,0,.2,1)",
      overflow: "hidden",
      flexShrink: 0,
      position: "relative",
    }}>
      <div style={{ padding: collapsed ? "20px 0" : "24px 20px", display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: "linear-gradient(135deg, #3b82f6, #06b6d4)",
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0, margin: collapsed ? "0 auto" : 0,
          boxShadow: "0 0 20px rgba(59,130,246,0.3)",
        }}>
          <Shield size={18} color="white" />
        </div>
        {!collapsed && (
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#e2e8f0", fontFamily: "'Space Grotesk', sans-serif", letterSpacing: -0.3 }}>
              AssetGuard
            </div>
            <div style={{ fontSize: 10, color: "#4a90d9", fontWeight: 600, letterSpacing: 1.5, textTransform: "uppercase" }}>
              Pro
            </div>
          </div>
        )}
      </div>

      <div style={{ height: 1, background: "rgba(99,179,237,0.06)", margin: "0 16px 8px" }} />

      <nav style={{ flex: 1, padding: "8px 0" }}>
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const active = activePage === id;
          return (
            <button key={id} onClick={() => onNavigate(id)} style={{
              width: "100%", display: "flex", alignItems: "center", gap: 12,
              padding: collapsed ? "12px 0" : "11px 16px",
              justifyContent: collapsed ? "center" : "flex-start",
              border: "none",
              background: active ? "linear-gradient(90deg, rgba(59,130,246,0.15), rgba(59,130,246,0.04))" : "transparent",
              borderLeft: active ? "2px solid #3b82f6" : "2px solid transparent",
              color: active ? "#63b3ed" : "#718096",
              cursor: "pointer", transition: "all 0.15s",
              fontSize: 13, fontWeight: active ? 600 : 400, fontFamily: "'Inter', sans-serif",
            }}>
              <Icon size={16} style={{ flexShrink: 0 }} />
              {!collapsed && <span>{label}</span>}
            </button>
          );
        })}
      </nav>

      <button onClick={onToggle} style={{
        position: "absolute", top: 24, right: -12,
        width: 24, height: 24, borderRadius: "50%",
        background: "#1a2744", border: "1px solid rgba(99,179,237,0.2)",
        color: "#4a90d9", cursor: "pointer",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {collapsed ? <Menu size={12} /> : <X size={12} />}
      </button>
    </aside>
  );
}

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [collapsed, setCollapsed] = useState(false);

  const pages = { dashboard: Dashboard, assets: Assets, violations: Violations, search: SearchPage };
  const PageComponent = pages[activePage] || Dashboard;

  return (
    <div style={{ display: "flex", height: "100vh", background: "#060c18", fontFamily: "'Inter', sans-serif" }}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet" />

      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        collapsed={collapsed}
        onToggle={() => setCollapsed(!collapsed)}
      />

      <main style={{ flex: 1, overflow: "auto", background: "#060c18" }}>
        <PageComponent />
      </main>
    </div>
  );
}
