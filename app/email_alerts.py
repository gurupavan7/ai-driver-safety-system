import json
import os
import threading
import time
import urllib.error
import urllib.request


RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "").strip()

RESEND_FROM = os.getenv(
    "RESEND_FROM",
    "AI Driver Safety <onboarding@resend.dev>",
).strip()

HIGH_RISK_THRESHOLD = 70
EMAIL_COOLDOWN_SECONDS = 300  # 5 minutes

_last_alert_time = 0.0
_alert_lock = threading.Lock()


def email_alerts_configured():
    return bool(
        RESEND_API_KEY
        and ALERT_EMAIL_TO
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

    reason_text = "\n".join(
        f"- {reason}" for reason in reasons
    )

    email_body = f"""
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

    resend_payload = {
        "from": RESEND_FROM,
        "to": [ALERT_EMAIL_TO],
        "subject": (
            f"Driver Safety HIGH Risk Alert "
            f"({payload.get('risk_score', 0)}/100)"
        ),
        "text": email_body,
    }

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(resend_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "ai-driver-safety-system/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=10,
        ) as response:
            response_body = response.read().decode("utf-8")

            print(
                "[EMAIL] HIGH-risk Resend alert sent "
                f"to {ALERT_EMAIL_TO}"
            )
            print(f"[EMAIL] Resend response: {response_body}")

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Resend HTTP {exc.code}: {error_body}"
        ) from exc


def send_high_risk_email(payload):
    global _last_alert_time

    risk_score = int(
        payload.get("risk_score", 0)
    )

    if risk_score < HIGH_RISK_THRESHOLD:
        return {
            "status": "not_high_risk",
        }

    if not email_alerts_configured():
        print(
            "[EMAIL] Resend credentials are not configured."
        )

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

        _last_alert_time = now

    def worker():
        try:
            _send_email(payload)

        except Exception as exc:
            print(
                f"[EMAIL] Failed to send Resend alert: {exc}"
            )

    threading.Thread(
        target=worker,
        daemon=True,
    ).start()

    return {
        "status": "queued",
    }
