import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import RiskMeter from "../components/RiskMeter";
import StatusCard from "../components/StatusCard";
import { getAnalytics, getEvents, getStatus } from "../services/api";

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

function Dashboard() {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [riskData, setRiskData] = useState([]);
  const [connected, setConnected] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [statusResponse, eventsResponse, analyticsResponse] =
        await Promise.all([
          getStatus(),
          getEvents(8),
          getAnalytics(60),
        ]);

      setStatus(statusResponse.data);
      setEvents(eventsResponse.data?.events || []);
      setRiskData(analyticsResponse.data?.charts?.risk || []);
      setConnected(true);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Dashboard API error:", error);
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 1000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const riskScore = Number(status?.risk_score ?? 0);
  const riskLevel = status?.risk_level ?? "UNKNOWN";

  const riskTone =
    riskScore >= 70 ? "danger" : riskScore >= 35 ? "warning" : "safe";

  const driverState = useMemo(() => {
    if (status?.drowsy) return ["Drowsy", "danger"];
    if (status?.distracted) return ["Distracted", "warning"];
    if (status?.yawning) return ["Yawning", "warning"];
    return ["Safe", "safe"];
  }, [status]);

  return (
    <div>
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">LIVE MONITORING</p>
          <h1>Driver Safety Dashboard</h1>
          <p>Real-time AI monitoring and accident-prevention intelligence.</p>
        </div>

        <div className="connection-box">
          <span
            className={`connection-dot ${connected ? "online" : "offline"}`}
          />
          <div>
            <strong>{connected ? "API Connected" : "API Offline"}</strong>
            <span>
              {lastUpdated
                ? `Updated ${lastUpdated.toLocaleTimeString()}`
                : "Waiting for data"}
            </span>
          </div>
        </div>
      </header>

      {!connected && (
        <div className="error-banner">
          FastAPI is unavailable. Make sure the backend is running on port 8000.
        </div>
      )}

      <section className="dashboard-grid">
        <div className="card risk-card">
          <div>
            <div className="card-label">Current Risk</div>
            <h3>Driver Risk Score</h3>
          </div>
          <RiskMeter score={riskScore} level={riskLevel} />
        </div>

        <StatusCard
          label="Driver Status"
          value={driverState[0]}
          subtitle={`Head: ${status?.head_direction ?? "Unknown"}`}
          tone={driverState[1]}
        />

        <StatusCard
          label="Phone Detection"
          value={status?.phone_detected ? "Detected" : "Clear"}
          subtitle={
            status?.phone_detected
              ? "Unsafe phone activity"
              : "No phone detected"
          }
          tone={status?.phone_detected ? "danger" : "safe"}
        />

        <StatusCard
          label="Seatbelt"
          value={status?.seatbelt_detected ? "Detected" : "Not Detected"}
          subtitle={
            status?.seatbelt_detected
              ? "Seatbelt appears secured"
              : "Safety violation"
          }
          tone={status?.seatbelt_detected ? "safe" : "danger"}
        />
      </section>

      <section className="content-grid">
        <div className="card chart-card">
          <div className="section-heading">
            <div>
              <div className="card-label">RISK TREND</div>
              <h3>Live Risk Timeline</h3>
            </div>
            <span className="live-pill">LIVE</span>
          </div>

          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={riskData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#263247" />
                <XAxis
                  dataKey="timestamp"
                  tick={{ fill: "#8491a8", fontSize: 10 }}
                  axisLine={{ stroke: "#344056" }}
                  tickLine={false}
                  minTickGap={24}
                  tickFormatter={formatTime}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: "#8491a8", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  labelFormatter={(value) => formatTime(value)}
                  contentStyle={{
                    background: "#121b2b",
                    border: "1px solid #2a374d",
                    borderRadius: "10px",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="risk_score"
                  name="Risk"
                  stroke="#5b8cff"
                  strokeWidth={3}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card alerts-card">
          <div className="section-heading">
            <div>
              <div className="card-label">EVENT STREAM</div>
              <h3>Recent Alerts</h3>
            </div>
            <span className="count-badge">{events.length}</span>
          </div>

          <div className="alerts-list">
            {events.length === 0 ? (
              <div className="empty-state">No safety events recorded yet.</div>
            ) : (
              events.map((event) => (
                <div className="alert-row" key={event.id}>
                  <div className="alert-marker" />
                  <div className="alert-copy">
                    <strong>{event.event_type}</strong>
                    <span>{formatTime(event.timestamp)}</span>
                  </div>
                  <div className="event-risk">{event.risk_score}/100</div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="metrics-grid">
        <StatusCard
          label="Eye Aspect Ratio"
          value={Number(status?.ear ?? 0).toFixed(3)}
          subtitle="EAR"
          tone={status?.drowsy ? "danger" : "neutral"}
          compact
        />
        <StatusCard
          label="Mouth Aspect Ratio"
          value={Number(status?.mar ?? 0).toFixed(3)}
          subtitle="MAR"
          tone={status?.yawning ? "warning" : "neutral"}
          compact
        />
        <StatusCard
          label="Head Pitch"
          value={`${Number(status?.pitch ?? 0).toFixed(1)}°`}
          subtitle="Vertical head angle"
          compact
        />
        <StatusCard
          label="Head Yaw"
          value={`${Number(status?.yaw ?? 0).toFixed(1)}°`}
          subtitle="Horizontal head angle"
          compact
        />
      </section>
    </div>
  );
}

export default Dashboard;
