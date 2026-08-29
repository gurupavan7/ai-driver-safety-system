import { useEffect, useState } from "react";
import { getStatus, getEvents } from "../services/api";

function Dashboard() {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(false);

  const loadLiveData = async () => {
    try {
      const [statusResponse, eventsResponse] = await Promise.all([
        getStatus(),
        getEvents(8),
      ]);

      setStatus(statusResponse.data);
      setEvents(eventsResponse.data.events || []);
      setError(false);
    } catch (err) {
      console.error("Dashboard API error:", err);
      setError(true);
    }
  };

  useEffect(() => {
    loadLiveData();

    const interval = setInterval(loadLiveData, 1000);

    return () => clearInterval(interval);
  }, []);

  const riskScore = status?.risk_score ?? 0;
  const riskLevel = status?.risk_level ?? "UNKNOWN";

  const riskClass =
    riskScore >= 70
      ? "status-danger"
      : riskScore >= 35
      ? "status-warning"
      : "status-safe";

  return (
    <div>
      <div className="page-header">
        <h1>Driver Safety Dashboard</h1>
        <p>Real-time AI monitoring and accident prevention</p>
      </div>

      {error && (
        <div className="card status-danger">
          FastAPI connection unavailable
        </div>
      )}

      <div className="dashboard-grid">

        <div className="card">
          <div className="card-label">Risk Score</div>
          <div className={`card-value ${riskClass}`}>
            {riskScore} / 100
          </div>
          <p>{riskLevel}</p>
        </div>

        <div className="card">
          <div className="card-label">Driver Status</div>

          <div className={`card-value ${riskClass}`}>
            {status?.drowsy
              ? "Drowsy"
              : status?.distracted
              ? "Distracted"
              : status?.yawning
              ? "Yawning"
              : "Safe"}
          </div>
        </div>

        <div className="card">
          <div className="card-label">Phone Detection</div>

          <div
            className={`card-value ${
              status?.phone_detected
                ? "status-danger"
                : "status-safe"
            }`}
          >
            {status?.phone_detected ? "Detected" : "Clear"}
          </div>
        </div>

        <div className="card">
          <div className="card-label">Seatbelt</div>

          <div
            className={`card-value ${
              status?.seatbelt_detected
                ? "status-safe"
                : "status-danger"
            }`}
          >
            {status?.seatbelt_detected
              ? "Detected"
              : "Not Detected"}
          </div>
        </div>

      </div>

      <div className="content-grid">

        <div className="card large-card">
          <div className="card-title">
            Live Driver Metrics
          </div>

          <p>EAR: {Number(status?.ear ?? 0).toFixed(3)}</p>
          <p>MAR: {Number(status?.mar ?? 0).toFixed(3)}</p>
          <p>Pitch: {Number(status?.pitch ?? 0).toFixed(2)}</p>
          <p>Yaw: {Number(status?.yaw ?? 0).toFixed(2)}</p>

          <p>
            Head Direction:{" "}
            <strong>
              {status?.head_direction ?? "Unknown"}
            </strong>
          </p>
        </div>

        <div className="card large-card">
          <div className="card-title">Recent Alerts</div>

          {events.length === 0 ? (
            <p>No safety events recorded.</p>
          ) : (
            events.map((event) => (
              <div
                key={event.id}
                style={{
                  padding: "12px 0",
                  borderBottom: "1px solid #1f2937",
                }}
              >
                <strong>{event.event_type}</strong>

                <p>
                  Risk: {event.risk_score}/100
                </p>

                <small>{event.timestamp}</small>
              </div>
            ))
          )}
        </div>

      </div>
    </div>
  );
}

export default Dashboard;