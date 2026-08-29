import { useCallback, useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import StatusCard from "../components/StatusCard";
import { getAnalytics } from "../services/api";

function formatTime(value) {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function Analytics() {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const response = await getAnalytics(300);
      setData(response.data);
      setConnected(true);
    } catch (error) {
      console.error("Analytics error:", error);
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 2000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const risk = data?.risk_summary || {};
  const counts = data?.event_counts || {};
  const session = data?.session_summary || {};
  const charts = data?.charts || {};

  return (
    <div>
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">DRIVER INTELLIGENCE</p>
          <h1>Analytics</h1>
          <p>Fatigue, distraction, head movement and risk trends.</p>
        </div>
        <span className={`api-badge ${connected ? "ok" : "bad"}`}>
          {connected ? "Live data" : "Disconnected"}
        </span>
      </header>

      <section className="analytics-summary-grid">
        <StatusCard
          label="Telemetry Samples"
          value={risk.samples ?? 0}
          subtitle="Recorded samples"
          compact
        />
        <StatusCard
          label="Average Risk"
          value={`${risk.average_risk ?? 0}/100`}
          subtitle="Session average"
          tone={
            Number(risk.average_risk) >= 70
              ? "danger"
              : Number(risk.average_risk) >= 35
              ? "warning"
              : "safe"
          }
          compact
        />
        <StatusCard
          label="Peak Risk"
          value={`${risk.max_risk ?? 0}/100`}
          subtitle={risk.peak_risk_level ?? "LOW"}
          tone={
            Number(risk.max_risk) >= 70
              ? "danger"
              : Number(risk.max_risk) >= 35
              ? "warning"
              : "safe"
          }
          compact
        />
        <StatusCard
          label="Phone Events"
          value={counts.PHONE ?? 0}
          subtitle="Detected alerts"
          compact
        />
        <StatusCard
          label="Drowsiness Events"
          value={counts.DROWSINESS ?? 0}
          subtitle="Detected alerts"
          compact
        />
        <StatusCard
          label="Seatbelt Violations"
          value={counts.NO_SEATBELT ?? 0}
          subtitle="Detected alerts"
          compact
        />
      </section>

      <section className="analytics-chart-grid">
        <div className="card chart-card">
          <div className="section-heading">
            <div>
              <div className="card-label">FATIGUE ANALYSIS</div>
              <h3>EAR & MAR Timeline</h3>
            </div>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={charts.fatigue || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#263247" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={formatTime}
                  tick={{ fill: "#8491a8", fontSize: 10 }}
                  tickLine={false}
                  minTickGap={28}
                />
                <YAxis
                  tick={{ fill: "#8491a8", fontSize: 11 }}
                  tickLine={false}
                />
                <Tooltip
                  labelFormatter={formatTime}
                  contentStyle={{
                    background: "#121b2b",
                    border: "1px solid #2a374d",
                    borderRadius: "10px",
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="ear"
                  name="EAR"
                  stroke="#55d6be"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="mar"
                  name="MAR"
                  stroke="#f5b971"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card chart-card">
          <div className="section-heading">
            <div>
              <div className="card-label">HEAD POSE</div>
              <h3>Pitch & Yaw Timeline</h3>
            </div>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={charts.head_pose || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#263247" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={formatTime}
                  tick={{ fill: "#8491a8", fontSize: 10 }}
                  tickLine={false}
                  minTickGap={28}
                />
                <YAxis
                  tick={{ fill: "#8491a8", fontSize: 11 }}
                  tickLine={false}
                />
                <Tooltip
                  labelFormatter={formatTime}
                  contentStyle={{
                    background: "#121b2b",
                    border: "1px solid #2a374d",
                    borderRadius: "10px",
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="pitch"
                  name="Pitch"
                  stroke="#9b8cff"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="yaw"
                  name="Yaw"
                  stroke="#5b8cff"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="card session-card">
        <div className="section-heading">
          <div>
            <div className="card-label">SESSION SUMMARY</div>
            <h3>Current Monitoring Session</h3>
          </div>
        </div>

        <div className="session-grid">
          <div>
            <span>Start</span>
            <strong>{session.start_time || "--"}</strong>
          </div>
          <div>
            <span>End / Latest</span>
            <strong>{session.end_time || "--"}</strong>
          </div>
          <div>
            <span>Drowsy Samples</span>
            <strong>{session.drowsy_samples ?? 0}</strong>
          </div>
          <div>
            <span>Yawn Samples</span>
            <strong>{session.yawn_samples ?? 0}</strong>
          </div>
          <div>
            <span>Distracted Samples</span>
            <strong>{session.distracted_samples ?? 0}</strong>
          </div>
          <div>
            <span>Phone Samples</span>
            <strong>{session.phone_samples ?? 0}</strong>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Analytics;
