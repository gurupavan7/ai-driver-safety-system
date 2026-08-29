import { useCallback, useEffect, useState } from "react";

import { getEvents, getHistory } from "../services/api";

function displayTimestamp(value) {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
}

function History() {
  const [history, setHistory] = useState([]);
  const [events, setEvents] = useState([]);
  const [tab, setTab] = useState("events");
  const [connected, setConnected] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [historyResponse, eventsResponse] = await Promise.all([
        getHistory(200),
        getEvents(100),
      ]);

      setHistory(historyResponse.data?.history || []);
      setEvents(eventsResponse.data?.events || []);
      setConnected(true);
    } catch (error) {
      console.error("History API error:", error);
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div>
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">SAFETY RECORDS</p>
          <h1>History</h1>
          <p>Review driver events and continuous telemetry records.</p>
        </div>
        <span className={`api-badge ${connected ? "ok" : "bad"}`}>
          {connected ? "Loaded" : "API Offline"}
        </span>
      </header>

      <div className="tab-row">
        <button
          className={tab === "events" ? "tab-button active" : "tab-button"}
          onClick={() => setTab("events")}
        >
          Safety Events
        </button>
        <button
          className={tab === "telemetry" ? "tab-button active" : "tab-button"}
          onClick={() => setTab("telemetry")}
        >
          Telemetry
        </button>
        <button className="secondary-button" onClick={refresh}>
          Refresh
        </button>
      </div>

      {tab === "events" ? (
        <div className="card table-card">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Timestamp</th>
                  <th>Event</th>
                  <th>Risk</th>
                  <th>EAR</th>
                  <th>MAR</th>
                  <th>Head</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="empty-table">
                      No events available.
                    </td>
                  </tr>
                ) : (
                  events.map((event) => (
                    <tr key={event.id}>
                      <td>{event.id}</td>
                      <td>{displayTimestamp(event.timestamp)}</td>
                      <td>
                        <span className="event-tag">{event.event_type}</span>
                      </td>
                      <td>{event.risk_score}/100</td>
                      <td>{Number(event.details?.ear ?? 0).toFixed(3)}</td>
                      <td>{Number(event.details?.mar ?? 0).toFixed(3)}</td>
                      <td>{event.details?.head_direction ?? "--"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card table-card">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Risk</th>
                  <th>EAR</th>
                  <th>MAR</th>
                  <th>Pitch</th>
                  <th>Yaw</th>
                  <th>Phone</th>
                  <th>Seatbelt</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="empty-table">
                      No telemetry available.
                    </td>
                  </tr>
                ) : (
                  history
                    .slice()
                    .reverse()
                    .map((row) => (
                      <tr key={row.id}>
                        <td>{displayTimestamp(row.timestamp)}</td>
                        <td>
                          <span className={`risk-tag ${String(row.risk_level).toLowerCase()}`}>
                            {row.risk_score} / {row.risk_level}
                          </span>
                        </td>
                        <td>{Number(row.ear ?? 0).toFixed(3)}</td>
                        <td>{Number(row.mar ?? 0).toFixed(3)}</td>
                        <td>{Number(row.pitch ?? 0).toFixed(1)}°</td>
                        <td>{Number(row.yaw ?? 0).toFixed(1)}°</td>
                        <td>{row.phone_detected ? "Yes" : "No"}</td>
                        <td>{row.seatbelt_detected ? "Yes" : "No"}</td>
                      </tr>
                    ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default History;
