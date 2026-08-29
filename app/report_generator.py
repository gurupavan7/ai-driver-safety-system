from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.analytics import get_dashboard_payload, get_recent_events
from app.paths import REPORTS_DIR


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = PROJECT_ROOT / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_timestamp(value: Any) -> str:
    if not value:
        return "--"

    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %I:%M:%S %p")
    except Exception:
        return str(value)


def _risk_level(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def _styles():
    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        "TitleDG",
        parent=styles["Title"],
        fontSize=21,
        leading=26,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#172554"),
        spaceAfter=8,
    )

    subtitle = ParagraphStyle(
        "SubtitleDG",
        parent=styles["Normal"],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=16,
    )

    heading = ParagraphStyle(
        "HeadingDG",
        parent=styles["Heading2"],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=10,
        spaceAfter=8,
    )

    body = ParagraphStyle(
        "BodyDG",
        parent=styles["BodyText"],
        fontSize=9.2,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
    )

    return title, subtitle, heading, body


def _make_table(data, widths, header_color="#1E3A8A", font_size=8.5):
    table = Table(data, colWidths=widths, repeatRows=1)

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return table


def _plot_risk_timeline(rows: list[dict[str, Any]], output: Path) -> bool:
    if not rows:
        return False

    x = []
    y = []

    for index, row in enumerate(rows):
        x.append(_safe_float(row.get("time_seconds", index), index))
        y.append(_safe_float(row.get("risk_score", 0), 0))

    plt.figure(figsize=(8, 3.2))
    plt.plot(x, y, linewidth=2)
    plt.ylim(0, 100)
    plt.xlabel("Time / Sample")
    plt.ylabel("Risk Score")
    plt.title("Driver Risk Timeline")
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight")
    plt.close()

    return True


def _plot_fatigue_timeline(rows: list[dict[str, Any]], output: Path) -> bool:
    if not rows:
        return False

    x = []
    ear = []
    mar = []

    for index, row in enumerate(rows):
        x.append(_safe_float(row.get("time_seconds", index), index))
        ear.append(_safe_float(row.get("ear", 0), 0))
        mar.append(_safe_float(row.get("mar", 0), 0))

    plt.figure(figsize=(8, 3.2))
    plt.plot(x, ear, label="EAR", linewidth=2)
    plt.plot(x, mar, label="MAR", linewidth=2)
    plt.xlabel("Time / Sample")
    plt.ylabel("Ratio")
    plt.title("Fatigue Indicators")
    plt.grid(alpha=0.2)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight")
    plt.close()

    return True


def generate_session_report(output_name: str | None = None) -> Path:
    dashboard = get_dashboard_payload(limit=500)
    recent_events = get_recent_events(limit=100)
    generated_at = datetime.now()

    if output_name is None:
        output_name = f"driver_safety_session_{generated_at:%Y%m%d_%H%M%S}.pdf"

    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"

    output_path = REPORT_DIR / output_name

    risk_summary = dashboard.get("risk_summary", {}) or {}
    session_summary = dashboard.get("session_summary", {}) or {}
    event_counts = dashboard.get("event_counts", {}) or {}
    charts = dashboard.get("charts", {}) or {}
    risk_rows = charts.get("risk", []) or []

    avg_risk = _safe_float(risk_summary.get("average_risk", 0))
    max_risk = _safe_float(risk_summary.get("max_risk", 0))

    risk_chart = REPORT_DIR / "_session_risk.png"
    has_risk_chart = _plot_risk_timeline(risk_rows, risk_chart)

    title_style, subtitle_style, heading_style, body_style = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="AI Driver Safety Session Report",
        author="DriverGuard AI",
    )

    story = [
        Paragraph("AI Driver Safety & Accident Prevention System", title_style),
        Paragraph(
            f"Live Monitoring Session Report<br/>Generated: {generated_at:%d %b %Y, %I:%M:%S %p}",
            subtitle_style,
        ),
        Paragraph("Executive Summary", heading_style),
        Paragraph(
            "This report summarizes a DriverGuard AI monitoring session. "
            "It combines risk telemetry and detected safety events such as "
            "fatigue, distraction, phone usage and seatbelt violations.",
            body_style,
        ),
        Spacer(1, 8),
    ]

    story.append(
        _make_table(
            [
                ["Metric", "Result"],
                ["Average Risk", f"{avg_risk:.1f} / 100"],
                ["Peak Risk", f"{max_risk:.0f} / 100"],
                ["Overall Risk", _risk_level(max_risk)],
                ["Telemetry Samples", str(risk_summary.get("samples", 0))],
                ["Session Start", _format_timestamp(session_summary.get("start_time"))],
                ["Latest Sample", _format_timestamp(session_summary.get("end_time"))],
            ],
            [70 * mm, 90 * mm],
        )
    )

    story += [Paragraph("Detected Safety Events", heading_style)]

    story.append(
        _make_table(
            [
                ["Event", "Count"],
                ["Drowsiness", event_counts.get("DROWSINESS", 0)],
                ["Yawning", event_counts.get("YAWN", 0)],
                ["Distraction", event_counts.get("DISTRACTION", 0)],
                ["Phone Usage", event_counts.get("PHONE", 0)],
                ["Seatbelt Violations", event_counts.get("NO_SEATBELT", 0)],
            ],
            [100 * mm, 60 * mm],
            header_color="#0F766E",
        )
    )

    story += [Paragraph("Risk Timeline", heading_style)]

    if has_risk_chart:
        story.append(Image(str(risk_chart), width=165 * mm, height=66 * mm))
    else:
        story.append(Paragraph("No risk telemetry available.", body_style))

    story += [Paragraph("Recent Safety Events", heading_style)]

    event_rows = [["Time", "Event", "Risk"]]

    for event in recent_events[:20]:
        event_rows.append(
            [
                _format_timestamp(event.get("timestamp")),
                str(event.get("event_type", "--")),
                f"{event.get('risk_score', 0)} / 100",
            ]
        )

    if len(event_rows) == 1:
        event_rows.append(["--", "No events recorded", "--"])

    story.append(
        _make_table(
            event_rows,
            [65 * mm, 60 * mm, 35 * mm],
            header_color="#334155",
            font_size=8,
        )
    )

    story += [
        Spacer(1, 12),
        Paragraph(
            "<b>Important:</b> This report is generated by a prototype AI driver-safety "
            "system and should not be used as the sole basis for real-world driving, "
            "medical, legal or emergency decisions.",
            body_style,
        ),
    ]

    doc.build(story)

    risk_chart.unlink(missing_ok=True)
    return output_path


def generate_video_report(
    analysis: dict[str, Any],
    output_name: str | None = None,
) -> Path:
    generated_at = datetime.now()

    if output_name is None:
        output_name = f"driver_safety_video_{generated_at:%Y%m%d_%H%M%S}.pdf"

    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"

    output_path = REPORT_DIR / output_name

    video = analysis.get("video", {}) or {}
    summary = analysis.get("summary", {}) or {}
    events = analysis.get("events", []) or []
    timeline = analysis.get("timeline", []) or []

    risk_chart = REPORT_DIR / "_video_risk.png"
    fatigue_chart = REPORT_DIR / "_video_fatigue.png"

    has_risk_chart = _plot_risk_timeline(timeline, risk_chart)
    has_fatigue_chart = _plot_fatigue_timeline(timeline, fatigue_chart)

    title_style, subtitle_style, heading_style, body_style = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="AI Driver Safety Video Analysis Report",
        author="DriverGuard AI",
    )

    story = [
        Paragraph("AI Driver Safety & Accident Prevention System", title_style),
        Paragraph(
            f"Recorded Video Analysis Report<br/>Generated: {generated_at:%d %b %Y, %I:%M:%S %p}",
            subtitle_style,
        ),
        Paragraph("Video Information", heading_style),
    ]

    story.append(
        _make_table(
            [
                ["Field", "Value"],
                ["File", video.get("original_file_name") or video.get("file_name", "--")],
                ["Resolution", f"{video.get('width', '--')} × {video.get('height', '--')}"],
                ["FPS", video.get("fps", "--")],
                ["Frames", video.get("total_frames", analysis.get("processed_frames", "--"))],
                ["Duration", f"{video.get('duration_seconds', '--')} seconds"],
            ],
            [65 * mm, 95 * mm],
        )
    )

    story += [Paragraph("Safety Summary", heading_style)]

    peak_risk = _safe_float(summary.get("max_risk", 0))
    avg_risk = _safe_float(summary.get("average_risk", 0))

    story.append(
        _make_table(
            [
                ["Metric", "Result"],
                ["Average Risk", f"{avg_risk:.1f} / 100"],
                ["Peak Risk", f"{peak_risk:.0f} / 100"],
                ["Overall Risk", summary.get("overall_risk_level", _risk_level(peak_risk))],
                ["Drowsiness Events", summary.get("drowsiness_events", 0)],
                ["Yawning Events", summary.get("yawn_events", 0)],
                ["Distraction Events", summary.get("distraction_events", 0)],
                ["Phone Events", summary.get("phone_events", 0)],
                ["Seatbelt Violations", summary.get("seatbelt_violations", 0)],
                ["Total Events", summary.get("total_events", len(events))],
            ],
            [90 * mm, 70 * mm],
            header_color="#0F766E",
        )
    )

    story += [Paragraph("Risk Timeline", heading_style)]

    if has_risk_chart:
        story.append(Image(str(risk_chart), width=165 * mm, height=66 * mm))
    else:
        story.append(Paragraph("No video risk timeline available.", body_style))

    story += [Paragraph("Fatigue Timeline", heading_style)]

    if has_fatigue_chart:
        story.append(Image(str(fatigue_chart), width=165 * mm, height=66 * mm))
    else:
        story.append(Paragraph("No EAR/MAR timeline available.", body_style))

    story += [Paragraph("Detected Video Events", heading_style)]

    rows = [["Time", "Event", "Risk", "Level"]]

    for event in events[:50]:
        rows.append(
            [
                f"{event.get('time_seconds', 0)}s",
                str(event.get("event_type", "--")),
                str(event.get("risk_score", 0)),
                str(event.get("risk_level", "--")),
            ]
        )

    if len(rows) == 1:
        rows.append(["--", "No events detected", "--", "--"])

    story.append(
        _make_table(
            rows,
            [35 * mm, 60 * mm, 30 * mm, 35 * mm],
            header_color="#334155",
            font_size=7.8,
        )
    )

    story += [
        Spacer(1, 12),
        Paragraph(
            "<b>Model note:</b> Seatbelt detection in this project is a prototype "
            "computer-vision heuristic rather than a dedicated production-trained model.",
            body_style,
        ),
        Spacer(1, 5),
        Paragraph(
            "<b>Important:</b> This report is for prototype and portfolio demonstration "
            "purposes and is not a substitute for certified automotive safety systems.",
            body_style,
        ),
    ]

    doc.build(story)

    risk_chart.unlink(missing_ok=True)
    fatigue_chart.unlink(missing_ok=True)

    return output_path


if __name__ == "__main__":
    path = generate_session_report()
    print("\nReport generated successfully:")
    print(path)
