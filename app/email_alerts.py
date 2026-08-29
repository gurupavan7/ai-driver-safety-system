import os
import smtplib
import threading
import time
from email.message import EmailMessage


ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "").strip()
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "").strip()
ALERT_EMAIL_APP_PASSWORD = (
    os.getenv("ALERT_EMAIL_APP_PASSWORD", "")
    .replace(" ", "")
    .strip()
)

HIGH_RISK_THRESHOLD = 70
EMAIL_COOLDOWN_SECONDS = 300  # 5 minutes

_last_alert_time = 0.0
_alert_lock = threading.Lock()


def email_alerts_configured():
    return bool(
        ALERT_EMAIL_FROM
        and ALERT_EMAIL_TO
        and ALERT_EMAIL_APP_PASSWORD
    )


def _detected_reasons(payload):
    reasons = []

    if payload.get("drowsy"):
        reasons.append("Drowsiness detected")

    if payload.get("yawning"):
        reasons.append("Yawning detected")

    if payload.get("distracted"):
        reasons.append("Driver distraction detected")

    if payload.get("phone_detected"):
        reasons.append("Phone usage detected")

    if not payload.get("seatbelt_detected", True):
        reasons.append("Seatbelt not detected")

    if not reasons:
        reasons.append("High overall driver risk")

    return reasons


def _send_email(payload):
    reasons = _detected_reasons(payload)

    message = EmailMessage()

    message["From"] = ALERT_EMAIL_FROM
    message["To"] = ALERT_EMAIL_TO
    message["Subject"] = (
        f"🚨 Driver Safety HIGH Risk Alert "
        f"({payload.get('risk_score', 0)}/100)"
    )

    reason_text = "\n".join(
        f"- {reason}" for reason in reasons
    )

    message.set_content(
        f"""
AI DRIVER SAFETY SYSTEM

HIGH-RISK DRIVER CONDITION DETECTED

Risk Score: {payload.get('risk_score', 0)}/100
Risk Level: {payload.get('risk_level', 'HIGH')}

Detected conditions:
{reason_text}

Driver status:
EAR: {payload.get('ear', 0)}
MAR: {payload.get('mar', 0)}
Head Direction: {payload.get('head_direction', 'UNKNOWN')}
Pitch: {payload.get('pitch', 0)}
Yaw: {payload.get('yaw', 0)}

Immediate attention is recommended.

AI Driver Safety & Accident Prevention System
""".strip()
    )

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465,
        timeout=10,
    ) as smtp:
        smtp.login(
            ALERT_EMAIL_FROM,
            ALERT_EMAIL_APP_PASSWORD,
        )

        smtp.send_message(message)

    print(
        "[EMAIL] HIGH-risk alert sent successfully "
        f"to {ALERT_EMAIL_TO}"
    )


def send_high_risk_email(payload):
    global _last_alert_time

    risk_score = int(payload.get("risk_score", 0))

    if risk_score < HIGH_RISK_THRESHOLD:
        return {
            "status": "not_high_risk",
        }

    if not email_alerts_configured():
        print("[EMAIL] Alert credentials are not configured.")

        return {
            "status": "not_configured",
        }

    now = time.monotonic()

    with _alert_lock:
        remaining = EMAIL_COOLDOWN_SECONDS - (
            now - _last_alert_time
        )

        if remaining > 0:
            return {
                "status": "cooldown",
                "remaining_seconds": int(remaining),
            }

        # Reserve the cooldown immediately so multiple
        # telemetry requests cannot send duplicate emails.
        _last_alert_time = now

    def worker():
        try:
            _send_email(payload)

        except Exception as exc:
            print(
                f"[EMAIL] Failed to send HIGH-risk alert: {exc}"
            )

    threading.Thread(
        target=worker,
        daemon=True,
    ).start()

    return {
        "status": "queued",
    }
