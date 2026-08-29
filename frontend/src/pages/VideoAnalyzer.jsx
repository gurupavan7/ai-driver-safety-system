import { useMemo, useRef, useState } from "react";
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

import { analyzeVideo } from "../services/api";

const ACCEPTED = ".mp4,.mov,.avi,.mkv,.m4v";

function secondsToClock(value) {
  const total = Math.max(0, Math.floor(Number(value) || 0));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function SummaryCard({ label, value, tone = "neutral" }) {
  return (
    <div className="card video-summary-card">
      <div className="card-label">{label}</div>
      <div className={`video-summary-value tone-${tone}`}>{value}</div>
    </div>
  );
}

function VideoAnalyzer() {
  const inputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [dragging, setDragging] = useState(false);

  const [uploadProgress, setUploadProgress] = useState(0);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const summary = result?.summary || {};
  const timeline = result?.timeline || [];
  const events = result?.events || [];

  const riskTone = useMemo(() => {
    const score = Number(summary.max_risk || 0);
    if (score >= 70) return "danger";
    if (score >= 35) return "warning";
    return "safe";
  }, [summary.max_risk]);

  const chooseFile = (selected) => {
    if (!selected) return;

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setFile(selected);
    setPreviewUrl(URL.createObjectURL(selected));
    setResult(null);
    setError("");
    setUploadProgress(0);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);

    const dropped = event.dataTransfer.files?.[0];
    chooseFile(dropped);
  };

  const runAnalysis = async () => {
    if (!file) {
      setError("Select a driving video first.");
      return;
    }

    setAnalyzing(true);
    setError("");
    setResult(null);
    setUploadProgress(0);

    try {
      const response = await analyzeVideo(file, (progressEvent) => {
        if (!progressEvent.total) return;

        const percentage = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );

        setUploadProgress(percentage);
      });

      setResult(response.data);
    } catch (requestError) {
      console.error(requestError);

      setError(
        requestError.response?.data?.detail ||
          "Video analysis failed. Check FastAPI and the terminal for details."
      );
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div>
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">RECORDED VIDEO AI</p>
          <h1>Video Analyzer</h1>
          <p>
            Upload recorded driving footage and run the full driver-safety
            detection pipeline.
          </p>
        </div>

        {result && (
          <span className={`video-risk-badge tone-${riskTone}`}>
            {summary.overall_risk_level} RISK
          </span>
        )}
      </header>

      <section className="video-top-grid">
        <div className="card upload-panel">
          <div
            className={`drop-zone ${dragging ? "dragging" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <div className="upload-icon">↑</div>
            <h3>{file ? file.name : "Drop a driving video here"}</h3>
            <p>MP4, MOV, AVI, MKV or M4V</p>
            <button type="button" className="secondary-button">
              Select Video
            </button>

            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED}
              hidden
              onChange={(event) => chooseFile(event.target.files?.[0])}
            />
          </div>

          {file && (
            <div className="selected-file-row">
              <div>
                <strong>{file.name}</strong>
                <span>{(file.size / (1024 * 1024)).toFixed(2)} MB</span>
              </div>

              <button
                className="primary-button"
                onClick={runAnalysis}
                disabled={analyzing}
              >
                {analyzing ? "Analyzing..." : "Analyze Video"}
              </button>
            </div>
          )}

          {analyzing && (
            <div className="analysis-progress">
              <div className="progress-copy">
                <span>
                  {uploadProgress < 100
                    ? "Uploading video"
                    : "Running MediaPipe + YOLO analysis"}
                </span>
                <strong>{uploadProgress}% uploaded</strong>
              </div>

              <div className="progress-track">
                <div
                  className="progress-bar"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>

              <p>
                After upload reaches 100%, the backend may continue processing
                for some time depending on the video length and your Mac.
              </p>
            </div>
          )}

          {error && <div className="video-error">{error}</div>}
        </div>

        <div className="card video-preview-card">
          <div className="card-label">VIDEO PREVIEW</div>

          {previewUrl ? (
            <video src={previewUrl} controls className="video-preview" />
          ) : (
            <div className="video-empty-preview">
              Select a video to preview it here.
            </div>
          )}
        </div>
      </section>

      {result && (
        <>
          <section className="video-summary-grid">
            <SummaryCard
              label="Peak Risk"
              value={`${summary.max_risk ?? 0}/100`}
              tone={riskTone}
            />
            <SummaryCard
              label="Average Risk"
              value={`${summary.average_risk ?? 0}/100`}
              tone="neutral"
            />
            <SummaryCard
              label="Drowsiness"
              value={summary.drowsiness_events ?? 0}
              tone="danger"
            />
            <SummaryCard
              label="Yawning"
              value={summary.yawn_events ?? 0}
              tone="warning"
            />
            <SummaryCard
              label="Distraction"
              value={summary.distraction_events ?? 0}
              tone="warning"
            />
            <SummaryCard
              label="Phone"
              value={summary.phone_events ?? 0}
              tone="danger"
            />
            <SummaryCard
              label="Seatbelt"
              value={summary.seatbelt_violations ?? 0}
              tone="danger"
            />
          </section>

          <section className="video-results-grid">
            <div className="card chart-card">
              <div className="section-heading">
                <div>
                  <div className="card-label">RISK ANALYSIS</div>
                  <h3>Video Risk Timeline</h3>
                </div>
              </div>

              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={timeline}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#263247" />
                    <XAxis
                      dataKey="time_seconds"
                      tickFormatter={secondsToClock}
                      tick={{ fill: "#8491a8", fontSize: 10 }}
                      minTickGap={25}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fill: "#8491a8", fontSize: 10 }}
                    />
                    <Tooltip
                      labelFormatter={(value) => secondsToClock(value)}
                      contentStyle={{
                        background: "#121b2b",
                        border: "1px solid #2a374d",
                        borderRadius: "10px",
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="risk_score"
                      name="Risk Score"
                      stroke="#5b8cff"
                      strokeWidth={3}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="card video-events-card">
              <div className="section-heading">
                <div>
                  <div className="card-label">DETECTED EVENTS</div>
                  <h3>Event Timeline</h3>
                </div>
                <span className="count-badge">{events.length}</span>
              </div>

              <div className="video-event-list">
                {events.length === 0 ? (
                  <div className="empty-state">
                    No safety events detected.
                  </div>
                ) : (
                  events.map((event, index) => (
                    <div
                      className="video-event-row"
                      key={`${event.event_type}-${event.time_seconds}-${index}`}
                    >
                      <span className="video-event-time">
                        {secondsToClock(event.time_seconds)}
                      </span>

                      <div>
                        <strong>{event.event_type}</strong>
                        <span>{event.risk_level} risk</span>
                      </div>

                      <b>{event.risk_score}/100</b>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>

          <section className="card chart-card video-fatigue-card">
            <div className="section-heading">
              <div>
                <div className="card-label">FATIGUE + HEAD POSE</div>
                <h3>EAR / MAR / Pitch / Yaw</h3>
              </div>
            </div>

            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#263247" />
                  <XAxis
                    dataKey="time_seconds"
                    tickFormatter={secondsToClock}
                    tick={{ fill: "#8491a8", fontSize: 10 }}
                    minTickGap={25}
                  />
                  <YAxis
                    yAxisId="ratio"
                    tick={{ fill: "#8491a8", fontSize: 10 }}
                  />
                  <YAxis
                    yAxisId="angle"
                    orientation="right"
                    tick={{ fill: "#8491a8", fontSize: 10 }}
                  />
                  <Tooltip
                    labelFormatter={(value) => secondsToClock(value)}
                    contentStyle={{
                      background: "#121b2b",
                      border: "1px solid #2a374d",
                      borderRadius: "10px",
                    }}
                  />
                  <Legend />

                  <Line
                    yAxisId="ratio"
                    type="monotone"
                    dataKey="ear"
                    name="EAR"
                    stroke="#55d6be"
                    dot={false}
                    isAnimationActive={false}
                  />

                  <Line
                    yAxisId="ratio"
                    type="monotone"
                    dataKey="mar"
                    name="MAR"
                    stroke="#f5b971"
                    dot={false}
                    isAnimationActive={false}
                  />

                  <Line
                    yAxisId="angle"
                    type="monotone"
                    dataKey="pitch"
                    name="Pitch"
                    stroke="#9b8cff"
                    dot={false}
                    isAnimationActive={false}
                  />

                  <Line
                    yAxisId="angle"
                    type="monotone"
                    dataKey="yaw"
                    name="Yaw"
                    stroke="#5b8cff"
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="card video-metadata-card">
            <div className="card-label">VIDEO METADATA</div>

            <div className="video-metadata-grid">
              <div>
                <span>File</span>
                <strong>
                  {result.video?.original_file_name ||
                    result.video?.file_name ||
                    "--"}
                </strong>
              </div>
              <div>
                <span>Resolution</span>
                <strong>
                  {result.video?.width} × {result.video?.height}
                </strong>
              </div>
              <div>
                <span>FPS</span>
                <strong>{result.video?.fps}</strong>
              </div>
              <div>
                <span>Duration</span>
                <strong>
                  {secondsToClock(result.video?.duration_seconds)}
                </strong>
              </div>
              <div>
                <span>Frames</span>
                <strong>{result.processed_frames}</strong>
              </div>
              <div>
                <span>Total Events</span>
                <strong>{summary.total_events ?? 0}</strong>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default VideoAnalyzer;
