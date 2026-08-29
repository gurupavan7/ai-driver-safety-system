import { useEffect, useState } from "react";
import { getHealth } from "../services/api";

function Settings() {
  const [health, setHealth] = useState("Checking...");
  const [refreshRate, setRefreshRate] = useState(
    localStorage.getItem("driverguard_refresh_rate") || "1000"
  );
  const [eventLimit, setEventLimit] = useState(
    localStorage.getItem("driverguard_event_limit") || "8"
  );
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getHealth()
      .then(() => setHealth("Connected"))
      .catch(() => setHealth("Disconnected"));
  }, []);

  const saveSettings = () => {
    localStorage.setItem("driverguard_refresh_rate", refreshRate);
    localStorage.setItem("driverguard_event_limit", eventLimit);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
  };

  return (
    <div>
      <header className="page-header">
        <p className="eyebrow">CONFIGURATION</p>
        <h1>Settings</h1>
        <p>Local dashboard preferences and backend status.</p>
      </header>

      <section className="settings-grid">
        <div className="card settings-card">
          <div className="card-label">BACKEND</div>
          <h3>API Configuration</h3>

          <label>
            API URL
            <input
              type="text"
              value={
                import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
              }
              readOnly
            />
          </label>

          <div className="setting-status-row">
            <span>Health</span>
            <strong
              className={health === "Connected" ? "tone-safe" : "tone-danger"}
            >
              {health}
            </strong>
          </div>

          <p className="settings-note">
            For deployment, set <code>VITE_API_URL</code> in the frontend
            environment.
          </p>
        </div>

        <div className="card settings-card">
          <div className="card-label">DASHBOARD</div>
          <h3>Display Preferences</h3>

          <label>
            Preferred refresh interval
            <select
              value={refreshRate}
              onChange={(event) => setRefreshRate(event.target.value)}
            >
              <option value="500">0.5 seconds</option>
              <option value="1000">1 second</option>
              <option value="2000">2 seconds</option>
              <option value="5000">5 seconds</option>
            </select>
          </label>

          <label>
            Recent alert limit
            <select
              value={eventLimit}
              onChange={(event) => setEventLimit(event.target.value)}
            >
              <option value="5">5 alerts</option>
              <option value="8">8 alerts</option>
              <option value="10">10 alerts</option>
              <option value="20">20 alerts</option>
            </select>
          </label>

          <button className="primary-button" onClick={saveSettings}>
            Save Preferences
          </button>

          {saved && <div className="saved-message">Preferences saved.</div>}
        </div>

        <div className="card settings-card">
          <div className="card-label">MODEL STATUS</div>
          <h3>Detection Pipeline</h3>

          <div className="settings-list">
            <div><span>Face landmarks</span><strong>Enabled</strong></div>
            <div><span>Drowsiness detection</span><strong>Enabled</strong></div>
            <div><span>Yawning detection</span><strong>Enabled</strong></div>
            <div><span>Head pose</span><strong>Enabled</strong></div>
            <div><span>Phone detection</span><strong>Enabled</strong></div>
            <div><span>Seatbelt heuristic</span><strong>Prototype</strong></div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Settings;
