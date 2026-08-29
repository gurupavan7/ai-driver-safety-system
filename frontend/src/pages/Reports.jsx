import { useEffect, useState } from "react";

import {
  downloadSessionReport,
  getAnalytics,
  getEvents,
  saveBlobAsFile,
} from "../services/api";

function Reports() {
  const [analytics, setAnalytics] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const [analyticsResponse, eventsResponse] = await Promise.all([
          getAnalytics(300),
          getEvents(10),
        ]);

        if (!mounted) return;

        setAnalytics(analyticsResponse.data);
        setEvents(eventsResponse.data?.events || []);
        setError("");
      } catch (requestError) {
        if (!mounted) return;

        console.error(requestError);
        setError("Could not load report preview data.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();

    return () => {
      mounted = false;
    };
  }, []);

  const downloadReport = async () => {
    setDownloading(true);
    setError("");

    try {
      const response = await downloadSessionReport();

      const date = new Date()
        .toISOString()
        .slice(0, 19)
        .replaceAll(":", "-");

      saveBlobAsFile(
        response.data,
        `driver_safety_session_${date}.pdf`
      );
    } catch (requestError) {
      console.error(requestError);
      setError("PDF generation failed. Check the FastAPI terminal.");
    } finally {
      setDownloading(false);
    }
  };

  const risk = analytics?.risk_summary || {};
  const counts = analytics?.event_counts || {};
  const session = analytics?.session_summary || {};

  return (
    <div>
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">SESSION DOCUMENTATION</p>
          <h1>Safety Reports</h1>
          <p>
            Generate a professional PDF from live driver telemetry and recorded
            safety events.
          </p>
        </div>

        <button
          className="primary-button report-download-button"
          onClick={downloadReport}
          disabled={downloading}
        >
          {downloading ? "Generating PDF..." : "Download Safety Report"}
        </button>
      </header>

      {error && <div className="video-error report-error">{error}</div>}

      <section className="report-hero-grid">
        <div className="card report-preview-card">
          <div className="report-document-preview">
            <div className="report-paper-header">
              <div className="report-logo">DG</div>

              <div>
                <h2>DriverGuard AI</h2>
                <p>Driver Safety Session Report</p>
              </div>
            </div>

            <div className="report-rule" />

            <h3>Executive Summary</h3>

            <p className="report-copy">
              DriverGuard AI analyzes fatigue, distraction, phone usage,
              seatbelt behavior and overall driver risk.
            </p>

            <div className="report-preview-metrics">
              <div>
                <span>Average Risk</span>
                <strong>{risk.average_risk ?? 0}/100</strong>
              </div>

              <div>
                <span>Peak Risk</span>
                <strong>{risk.max_risk ?? 0}/100</strong>
              </div>

              <div>
                <span>Samples</span>
                <strong>{risk.samples ?? 0}</strong>
              </div>
            </div>

            <h3>Detected Events</h3>

            <div className="report-event-grid">
              <span>Drowsiness</span>
              <b>{counts.DROWSINESS ?? 0}</b>

              <span>Yawning</span>
              <b>{counts.YAWN ?? 0}</b>

              <span>Distraction</span>
              <b>{counts.DISTRACTION ?? 0}</b>

              <span>Phone</span>
              <b>{counts.PHONE ?? 0}</b>

              <span>Seatbelt</span>
              <b>{counts.NO_SEATBELT ?? 0}</b>
            </div>
          </div>
        </div>

        <div className="report-side-column">
          <div className="card report-info-card">
            <div className="card-label">REPORT CONTENT</div>

            <div className="report-check-list">
              <span>✓ Executive safety summary</span>
              <span>✓ Average and peak risk</span>
              <span>✓ Safety event statistics</span>
              <span>✓ Risk timeline chart</span>
              <span>✓ Recent event table</span>
              <span>✓ Session timestamps</span>
            </div>
          </div>

          <div className="card report-info-card">
            <div className="card-label">SESSION</div>

            <div className="report-kv">
              <span>Start</span>
              <strong>{session.start_time || "--"}</strong>
            </div>

            <div className="report-kv">
              <span>Latest</span>
              <strong>{session.end_time || "--"}</strong>
            </div>

            <div className="report-kv">
              <span>Recent events</span>
              <strong>{events.length}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="card report-events-panel">
        <div className="section-heading">
          <div>
            <div className="card-label">REPORT PREVIEW</div>
            <h3>Recent Events Included</h3>
          </div>
        </div>

        {loading ? (
          <div className="empty-state">Loading report data...</div>
        ) : events.length === 0 ? (
          <div className="empty-state">No events available.</div>
        ) : (
          <div className="report-event-table">
            <div className="report-event-table-head">
              <span>Timestamp</span>
              <span>Event</span>
              <span>Risk</span>
            </div>

            {events.map((event, index) => (
              <div
                className="report-event-table-row"
                key={`${event.timestamp}-${event.event_type}-${index}`}
              >
                <span>{event.timestamp || "--"}</span>
                <strong>{event.event_type || "--"}</strong>
                <b>{event.risk_score ?? 0}/100</b>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default Reports;
