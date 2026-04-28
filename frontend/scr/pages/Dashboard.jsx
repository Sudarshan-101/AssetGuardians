import { useState, useEffect } from "react";
import { AlertTriangle, FileImage, Eye, CheckCircle } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { apiCall } from "../App";

const COLORS = ["#3b82f6", "#06b6d4", "#8b5cf6", "#ec4899", "#f59e0b"];

function StatCard({ icon: Icon, label, value, sub, color = "#3b82f6", glow }) {
  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(15,25,50,0.9), rgba(10,18,35,0.9))",
      border: `1px solid rgba(${glow || "59,130,246"},0.15)`,
      borderRadius: 14,
      padding: "20px 24px",
      display: "flex",
      alignItems: "flex-start",
      gap: 16,
      boxShadow: `0 0 30px rgba(${glow || "59,130,246"},0.05)`,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 12,
        background: `rgba(${glow || "59,130,246"},0.12)`,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}>
        <Icon size={20} color={color} />
      </div>
      <div>
        <div style={{ fontSize: 28, fontWeight: 700, color: "#e2e8f0", fontFamily: "'Space Grotesk', sans-serif", lineHeight: 1.1 }}>
          {value}
        </div>
        <div style={{ fontSize: 13, color: "#718096", marginTop: 4 }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: color, marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  );
}

function ViolationRow({ v }) {
  const statusColors = {
    detected: "#f59e0b",
    confirmed: "#ef4444",
    resolved: "#10b981",
    false_positive: "#6b7280",
  };
  const platformIcons = { twitter: "🐦", youtube: "▶️", instagram: "📷", web: "🌐" };

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "12px 0",
      borderBottom: "1px solid rgba(99,179,237,0.05)",
    }}>
      <span style={{ fontSize: 18 }}>{platformIcons[v.platform] || "🌐"}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: "#a0aec0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {v.infringing_url}
        </div>
        <div style={{ fontSize: 11, color: "#4a6080", marginTop: 2 }}>
          {v.platform} · {new Date(v.detected_at).toLocaleDateString()}
        </div>
      </div>
      <div style={{
        fontSize: 11, fontWeight: 600, padding: "3px 8px", borderRadius: 6,
        background: `${statusColors[v.status]}22`,
        color: statusColors[v.status],
      }}>
        {v.status}
      </div>
      <div style={{ fontSize: 12, color: "#63b3ed", fontWeight: 600, minWidth: 40, textAlign: "right" }}>
        {v.similarity_score?.toFixed(0)}%
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiCall("/violations/dashboard")
      .then((r) => r.json())
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // Demo data if API not connected
  const demo = {
    total_assets: 1247,
    total_violations: 89,
    active_violations: 34,
    resolved_violations: 55,
    violations_trend: [
      { date: "Apr 16", count: 3 }, { date: "Apr 17", count: 7 },
      { date: "Apr 18", count: 5 }, { date: "Apr 19", count: 12 },
      { date: "Apr 20", count: 8 }, { date: "Apr 21", count: 15 },
      { date: "Apr 22", count: 6 },
    ],
    violations_by_platform: { twitter: 38, youtube: 22, instagram: 18, web: 11 },
    recent_violations: [
      { id: "1", platform: "twitter", infringing_url: "https://twitter.com/user/status/123456789", similarity_score: 97, status: "detected", detected_at: new Date().toISOString() },
      { id: "2", platform: "youtube", infringing_url: "https://youtube.com/watch?v=abc123def", similarity_score: 94, status: "confirmed", detected_at: new Date().toISOString() },
      { id: "3", platform: "instagram", infringing_url: "https://instagram.com/p/XYZ123abc", similarity_score: 91, status: "detected", detected_at: new Date().toISOString() },
      { id: "4", platform: "web", infringing_url: "https://somenewssite.com/article/stolen-photo", similarity_score: 88, status: "resolved", detected_at: new Date().toISOString() },
    ],
  };

  const data = stats || demo;

  const pieData = Object.entries(data.violations_by_platform || {}).map(([name, value]) => ({ name, value }));

  return (
    <div style={{ padding: "32px 36px", maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, color: "#e2e8f0", fontFamily: "'Space Grotesk', sans-serif", margin: 0 }}>
          Overview
        </h1>
        <div style={{ fontSize: 13, color: "#4a6080", marginTop: 4 }}>
          {new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
        </div>
      </div>

      {/* Stat Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 32 }}>
        <StatCard icon={FileImage} label="Registered Assets" value={data.total_assets?.toLocaleString()} sub="↑ 12 this week" color="#3b82f6" glow="59,130,246" />
        <StatCard icon={AlertTriangle} label="Total Violations" value={data.total_violations} sub="All-time detected" color="#f59e0b" glow="245,158,11" />
        <StatCard icon={Eye} label="Active Violations" value={data.active_violations} sub="Needs attention" color="#ef4444" glow="239,68,68" />
        <StatCard icon={CheckCircle} label="Resolved" value={data.resolved_violations} sub="Successfully handled" color="#10b981" glow="16,185,129" />
      </div>

      {/* Charts Row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20, marginBottom: 28 }}>
        {/* Trend Chart */}
        <div style={{
          background: "linear-gradient(135deg, rgba(15,25,50,0.9), rgba(10,18,35,0.9))",
          border: "1px solid rgba(59,130,246,0.1)",
          borderRadius: 14, padding: "24px",
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#a0aec0", marginBottom: 20 }}>
            Violations — 7-Day Trend
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data.violations_trend}>
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#4a6080" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#4a6080" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: "#0d1525", border: "1px solid rgba(59,130,246,0.2)", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "#a0aec0" }}
              />
              <Line
                type="monotone" dataKey="count" stroke="#3b82f6"
                strokeWidth={2} dot={{ fill: "#3b82f6", r: 3 }}
                activeDot={{ r: 5, fill: "#63b3ed" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Platform Distribution */}
        <div style={{
          background: "linear-gradient(135deg, rgba(15,25,50,0.9), rgba(10,18,35,0.9))",
          border: "1px solid rgba(59,130,246,0.1)",
          borderRadius: 14, padding: "24px",
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#a0aec0", marginBottom: 20 }}>
            By Platform
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={35} outerRadius={55} paddingAngle={3} dataKey="value">
                {pieData.map((_, index) => (
                  <Cell key={index} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#0d1525", border: "1px solid rgba(59,130,246,0.2)", borderRadius: 8, fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 12px", marginTop: 12 }}>
            {pieData.map((item, i) => (
              <div key={item.name} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: COLORS[i % COLORS.length] }} />
                <span style={{ color: "#718096" }}>{item.name}</span>
                <span style={{ color: "#a0aec0", fontWeight: 600 }}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Violations */}
      <div style={{
        background: "linear-gradient(135deg, rgba(15,25,50,0.9), rgba(10,18,35,0.9))",
        border: "1px solid rgba(59,130,246,0.1)",
        borderRadius: 14, padding: "24px",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#a0aec0" }}>Recent Violations</div>
          <div style={{ fontSize: 11, color: "#3b82f6", cursor: "pointer" }}>View all →</div>
        </div>
        {(data.recent_violations || []).map((v) => <ViolationRow key={v.id} v={v} />)}
      </div>
    </div>
  );
}
