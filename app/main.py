import cv2
import mediapipe as mp
import time
import math
import json
import csv
import sqlite3
import subprocess
import threading
import queue
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

import numpy as np
from ultralytics import YOLO
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from app.telemetry import init_telemetry_table, log_telemetry


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "face_landmarker.task"
YOLO_MODEL_PATH = PROJECT_ROOT / "models" / "yolov8n.pt"
LOG_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"

LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

EVENT_CSV = LOG_DIR / "driver_events.csv"
EVENT_DB = DATA_DIR / "driver_safety.db"


# ============================================================
# CONFIGURATION
# ============================================================

# Eye landmarks
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# Mouth landmarks
MOUTH = [78, 13, 14, 308]

# Head-pose landmarks
NOSE_TIP = 1
CHIN = 152
LEFT_EYE_CORNER = 33
RIGHT_EYE_CORNER = 263
LEFT_MOUTH_CORNER = 61
RIGHT_MOUTH_CORNER = 291

# Eye / drowsiness settings
EYE_THRESHOLD = 0.20
DROWSINESS_TIME = 2.0

# Yawn settings
YAWN_THRESHOLD = 0.30
YAWN_TIME = 1.5

# Head-pose / distraction settings
YAW_THRESHOLD = 15.0
PITCH_THRESHOLD = 12.0
DISTRACTION_TIME = 2.0

# Phone detection
PHONE_CLASS_ID = 67
PHONE_CONFIDENCE = 0.45
PHONE_DETECT_EVERY_N_FRAMES = 3
PHONE_ALERT_TIME = 1.0

# Seatbelt heuristic settings
SEATBELT_CHECK_EVERY_N_FRAMES = 5
SEATBELT_EDGE_THRESHOLD = 60
SEATBELT_MIN_LINE_LENGTH = 70
SEATBELT_ALERT_TIME = 3.0

# Risk score weights
RISK_DROWSY = 45
RISK_YAWN = 20
RISK_DISTRACTED = 25
RISK_PHONE = 35
RISK_NO_SEATBELT = 20

# Event cooldown
EVENT_COOLDOWN = 5.0

# Continuous analytics telemetry
TELEMETRY_INTERVAL = 1.0  # seconds between database samples
CLOUD_TELEMETRY_URL = (
    "https://ai-driver-safety-system-production.up.railway.app/telemetry/live"
)

CLOUD_TIMEOUT = 3

# Sound alert settings (macOS)
SOUND_ALERTS_ENABLED = True
VOICE_ALERTS_ENABLED = True
SOUND_ALERT_COOLDOWN = 4.0
SOUND_QUEUE_MAXSIZE = 5

SYSTEM_SOUNDS = {
    "DROWSINESS": "/System/Library/Sounds/Basso.aiff",
    "YAWN": "/System/Library/Sounds/Pop.aiff",
    "DISTRACTION": "/System/Library/Sounds/Funk.aiff",
    "PHONE": "/System/Library/Sounds/Sosumi.aiff",
    "NO_SEATBELT": "/System/Library/Sounds/Ping.aiff",
    "HIGH_RISK": "/System/Library/Sounds/Hero.aiff",
}


# ============================================================
# MODEL SETUP
# ============================================================

base_options = python.BaseOptions(
    model_asset_path=str(MODEL_PATH),
    delegate=python.BaseOptions.Delegate.CPU,
)

options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_faces=1,
)

landmarker = vision.FaceLandmarker.create_from_options(options)

# Use a local models/ path if it exists; otherwise let Ultralytics download.
if YOLO_MODEL_PATH.exists():
    phone_model = YOLO(str(YOLO_MODEL_PATH))
else:
    phone_model = YOLO("yolov8n.pt")


# ============================================================
# SOUND / VOICE ALERT MANAGER
# ============================================================

class AlertManager:
    """
    Non-blocking macOS sound + voice alert manager.

    Alerts are placed into a small queue and processed by one background
    thread so OpenCV/MediaPipe/YOLO inference is not blocked by audio.
    """

    def __init__(self):
        self.enabled = SOUND_ALERTS_ENABLED
        self.voice_enabled = VOICE_ALERTS_ENABLED
        self.cooldown = SOUND_ALERT_COOLDOWN
        self.last_alert_times = {}
        self.alert_queue = queue.Queue(maxsize=SOUND_QUEUE_MAXSIZE)
        self.stop_event = threading.Event()

        self.worker = threading.Thread(
            target=self._worker_loop,
            daemon=True,
        )
        self.worker.start()

    def _worker_loop(self):
        while not self.stop_event.is_set():
            try:
                event_name, message = self.alert_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                sound_path = SYSTEM_SOUNDS.get(event_name)

                if self.enabled and sound_path and Path(sound_path).exists():
                    subprocess.run(
                        ["afplay", sound_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                elif self.enabled:
                    # Fallback terminal bell if the macOS sound file is unavailable.
                    print("\a", end="", flush=True)

                if self.voice_enabled and message:
                    subprocess.run(
                        ["say", message],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )

            finally:
                self.alert_queue.task_done()

    def alert(self, event_name, message):
        if not self.enabled and not self.voice_enabled:
            return False

        now = time.monotonic()
        last_time = self.last_alert_times.get(event_name, 0.0)

        if now - last_time < self.cooldown:
            return False

        self.last_alert_times[event_name] = now

        try:
            self.alert_queue.put_nowait((event_name, message))
            return True
        except queue.Full:
            return False

    def close(self):
        self.stop_event.set()


# ============================================================
# DATABASE / LOGGING
# ============================================================

def init_storage():
    conn = sqlite3.connect(EVENT_DB)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            details TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    if not EVENT_CSV.exists():
        with EVENT_CSV.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                ["timestamp", "event_type", "risk_score", "details"]
            )


def log_event(event_type, risk_score, details):
    timestamp = datetime.now().isoformat(timespec="seconds")
    details_text = json.dumps(details, ensure_ascii=False)

    with EVENT_CSV.open("a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [timestamp, event_type, risk_score, details_text]
        )

    conn = sqlite3.connect(EVENT_DB)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO events (timestamp, event_type, risk_score, details)
        VALUES (?, ?, ?, ?)
        """,
        (timestamp, event_type, risk_score, details_text),
    )
    conn.commit()
    conn.close()

def send_cloud_telemetry(payload):
    """
    Send live driver telemetry to the Railway backend.

    Runs in a background thread so network problems
    never freeze the camera/detection loop.
    """

    def _send():
        try:
            data = json.dumps(payload).encode("utf-8")

            request = urllib.request.Request(
                CLOUD_TELEMETRY_URL,
                data=data,
                headers={
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(
                request,
                timeout=CLOUD_TIMEOUT,
            ) as response:
                if response.status == 200:
                    print(
                        f"[CLOUD] Telemetry sent | "
                        f"Risk: {payload['risk_score']} "
                        f"({payload['risk_level']})"
                    )

        except Exception as exc:
            print(f"[CLOUD] Telemetry unavailable: {exc}")

    threading.Thread(
        target=_send,
        daemon=True,
    ).start()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def distance(point1, point2):
    return math.sqrt(
        (point1.x - point2.x) ** 2
        + (point1.y - point2.y) ** 2
    )


def calculate_ear(landmarks, eye_indices):
    p1 = landmarks[eye_indices[0]]
    p2 = landmarks[eye_indices[1]]
    p3 = landmarks[eye_indices[2]]
    p4 = landmarks[eye_indices[3]]
    p5 = landmarks[eye_indices[4]]
    p6 = landmarks[eye_indices[5]]

    vertical_1 = distance(p2, p6)
    vertical_2 = distance(p3, p5)
    horizontal = distance(p1, p4)

    if horizontal == 0:
        return 0.0

    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def calculate_mar(landmarks):
    left_corner = landmarks[MOUTH[0]]
    upper_lip = landmarks[MOUTH[1]]
    lower_lip = landmarks[MOUTH[2]]
    right_corner = landmarks[MOUTH[3]]

    vertical = distance(upper_lip, lower_lip)
    horizontal = distance(left_corner, right_corner)

    if horizontal == 0:
        return 0.0

    return vertical / horizontal


def draw_landmarks(frame, landmarks, indices, radius=3):
    height, width, _ = frame.shape

    for index in indices:
        landmark = landmarks[index]
        x = int(landmark.x * width)
        y = int(landmark.y * height)

        cv2.circle(
            frame,
            (x, y),
            radius,
            (0, 255, 255),
            -1,
        )


def detect_head_pose(frame, landmarks):
    height, width, _ = frame.shape

    image_points = np.array(
        [
            (
                landmarks[NOSE_TIP].x * width,
                landmarks[NOSE_TIP].y * height,
            ),
            (
                landmarks[CHIN].x * width,
                landmarks[CHIN].y * height,
            ),
            (
                landmarks[LEFT_EYE_CORNER].x * width,
                landmarks[LEFT_EYE_CORNER].y * height,
            ),
            (
                landmarks[RIGHT_EYE_CORNER].x * width,
                landmarks[RIGHT_EYE_CORNER].y * height,
            ),
            (
                landmarks[LEFT_MOUTH_CORNER].x * width,
                landmarks[LEFT_MOUTH_CORNER].y * height,
            ),
            (
                landmarks[RIGHT_MOUTH_CORNER].x * width,
                landmarks[RIGHT_MOUTH_CORNER].y * height,
            ),
        ],
        dtype=np.float64,
    )

    model_points = np.array(
        [
            (0.0, 0.0, 0.0),
            (0.0, -330.0, -65.0),
            (-225.0, 170.0, -135.0),
            (225.0, 170.0, -135.0),
            (-150.0, -150.0, -125.0),
            (150.0, -150.0, -125.0),
        ],
        dtype=np.float64,
    )

    focal_length = float(width)
    center = (width / 2.0, height / 2.0)

    camera_matrix = np.array(
        [
            [focal_length, 0.0, center[0]],
            [0.0, focal_length, center[1]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )

    distortion_coefficients = np.zeros((4, 1), dtype=np.float64)

    success, rotation_vector, _ = cv2.solvePnP(
        model_points,
        image_points,
        camera_matrix,
        distortion_coefficients,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )

    if not success:
        return "UNKNOWN", 0.0, 0.0

    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_matrix)

    pitch = float(angles[0])
    yaw = float(angles[1])

    if yaw < -YAW_THRESHOLD:
        direction = "LOOKING LEFT"
    elif yaw > YAW_THRESHOLD:
        direction = "LOOKING RIGHT"
    elif pitch < -PITCH_THRESHOLD:
        direction = "LOOKING DOWN"
    elif pitch > PITCH_THRESHOLD:
        direction = "LOOKING UP"
    else:
        direction = "LOOKING FORWARD"

    return direction, pitch, yaw


def detect_phone(frame):
    results = phone_model(
        frame,
        verbose=False,
        conf=PHONE_CONFIDENCE,
        classes=[PHONE_CLASS_ID],
    )

    detections = []

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            confidence = float(box.conf[0])

            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0].tolist(),
            )

            detections.append(
                {
                    "confidence": confidence,
                    "box": (x1, y1, x2, y2),
                }
            )

    return len(detections) > 0, detections


def estimate_seatbelt(frame):
    """
    Heuristic seatbelt detector.

    It looks for a strong diagonal line across the torso region.
    This is useful as a prototype but is NOT a trained seatbelt model.
    """
    height, width, _ = frame.shape

    x1 = int(width * 0.20)
    x2 = int(width * 0.80)
    y1 = int(height * 0.40)
    y2 = int(height * 0.95)

    roi = frame[y1:y2, x1:x2]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, SEATBELT_EDGE_THRESHOLD, 180)

    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=50,
        minLineLength=SEATBELT_MIN_LINE_LENGTH,
        maxLineGap=20,
    )

    seatbelt_detected = False
    best_line = None

    if lines is not None:
        for line in lines:
            coords = np.asarray(line).reshape(-1)

            if coords.size != 4:
                continue

            lx1, ly1, lx2, ly2 = map(int, coords)

            dx = lx2 - lx1
            dy = ly2 - ly1

            if dx == 0:
                continue

            angle = abs(math.degrees(math.atan2(dy, dx)))
            length = math.sqrt(dx * dx + dy * dy)

            if 25 <= angle <= 70 and length >= SEATBELT_MIN_LINE_LENGTH:
                seatbelt_detected = True
                best_line = (
                    lx1 + x1,
                    ly1 + y1,
                    lx2 + x1,
                    ly2 + y1,
                )
                break

    return seatbelt_detected, best_line, (x1, y1, x2, y2)


def calculate_risk(
    drowsy,
    yawning,
    distracted,
    phone_detected,
    seatbelt_detected,
):
    score = 0

    if drowsy:
        score += RISK_DROWSY

    if yawning:
        score += RISK_YAWN

    if distracted:
        score += RISK_DISTRACTED

    if phone_detected:
        score += RISK_PHONE

    if not seatbelt_detected:
        score += RISK_NO_SEATBELT

    score = min(score, 100)

    if score >= 70:
        level = "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    else:
        level = "LOW"

    return score, level


def should_log(last_event_times, event_name):
    now = time.monotonic()
    last_time = last_event_times.get(event_name, 0.0)

    if now - last_time >= EVENT_COOLDOWN:
        last_event_times[event_name] = now
        return True

    return False


# ============================================================
# MAIN
# ============================================================

def main():
    init_storage()
    init_telemetry_table()
    alert_manager = AlertManager()

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("❌ Error: Could not open camera.")
        alert_manager.close()
        return

    print("✅ AI Driver Safety System started.")
    print("Press Q to quit.")

    start_time = time.monotonic()
    last_timestamp_ms = 0

    eye_closed_start = None
    yawn_start = None
    distraction_start = None
    phone_start = None
    no_seatbelt_start = None

    frame_counter = 0

    phone_detected = False
    phone_detections = []

    seatbelt_detected = False
    seatbelt_line = None
    seatbelt_roi = None

    last_event_times = {}
    last_telemetry_time = 0.0

    try:
        while True:
            success, frame = camera.read()

            if not success:
                print("❌ Failed to capture frame.")
                break

            frame = cv2.flip(frame, 1)
            frame_counter += 1

            # =================================================
            # YOLO PHONE DETECTION
            # =================================================

            if frame_counter % PHONE_DETECT_EVERY_N_FRAMES == 0:
                phone_detected, phone_detections = detect_phone(frame)

            # =================================================
            # SEATBELT HEURISTIC
            # =================================================

            if frame_counter % SEATBELT_CHECK_EVERY_N_FRAMES == 0:
                (
                    seatbelt_detected,
                    seatbelt_line,
                    seatbelt_roi,
                ) = estimate_seatbelt(frame)

            # =================================================
            # MEDIAPIPE FACE DETECTION
            # =================================================

            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame,
            )

            timestamp_ms = int(
                (time.monotonic() - start_time) * 1000
            )

            if timestamp_ms <= last_timestamp_ms:
                timestamp_ms = last_timestamp_ms + 1

            last_timestamp_ms = timestamp_ms

            result = landmarker.detect_for_video(
                mp_image,
                timestamp_ms,
            )

            drowsy = False
            yawning = False
            distracted = False
            average_ear = 0.0
            mar = 0.0
            pitch = 0.0
            yaw = 0.0
            head_direction = "NO FACE"

            if result.face_landmarks:
                landmarks = result.face_landmarks[0]

                left_ear = calculate_ear(
                    landmarks,
                    LEFT_EYE,
                )

                right_ear = calculate_ear(
                    landmarks,
                    RIGHT_EYE,
                )

                average_ear = (
                    left_ear + right_ear
                ) / 2.0

                mar = calculate_mar(landmarks)

                head_direction, pitch, yaw = detect_head_pose(
                    frame,
                    landmarks,
                )

                # ---------------- DROWSINESS ----------------
                if average_ear < EYE_THRESHOLD:
                    if eye_closed_start is None:
                        eye_closed_start = time.monotonic()

                    closed_duration = (
                        time.monotonic() - eye_closed_start
                    )

                    drowsy = closed_duration >= DROWSINESS_TIME
                else:
                    eye_closed_start = None
                    closed_duration = 0.0

                # ---------------- YAWN ----------------
                if mar > YAWN_THRESHOLD:
                    if yawn_start is None:
                        yawn_start = time.monotonic()

                    yawn_duration = (
                        time.monotonic() - yawn_start
                    )

                    yawning = yawn_duration >= YAWN_TIME
                else:
                    yawn_start = None
                    yawn_duration = 0.0

                # ---------------- DISTRACTION ----------------
                if head_direction != "LOOKING FORWARD":
                    if distraction_start is None:
                        distraction_start = time.monotonic()

                    distraction_duration = (
                        time.monotonic() - distraction_start
                    )

                    distracted = (
                        distraction_duration >= DISTRACTION_TIME
                    )
                else:
                    distraction_start = None
                    distraction_duration = 0.0

                draw_landmarks(
                    frame,
                    landmarks,
                    LEFT_EYE + RIGHT_EYE + MOUTH,
                )

            else:
                eye_closed_start = None
                yawn_start = None
                distraction_start = None

            # =================================================
            # PHONE ALERT TIMER
            # =================================================

            if phone_detected:
                if phone_start is None:
                    phone_start = time.monotonic()

                phone_duration = (
                    time.monotonic() - phone_start
                )
            else:
                phone_start = None
                phone_duration = 0.0

            phone_alert = phone_duration >= PHONE_ALERT_TIME

            # =================================================
            # SEATBELT ALERT TIMER
            # =================================================

            if not seatbelt_detected:
                if no_seatbelt_start is None:
                    no_seatbelt_start = time.monotonic()

                no_seatbelt_duration = (
                    time.monotonic() - no_seatbelt_start
                )
            else:
                no_seatbelt_start = None
                no_seatbelt_duration = 0.0

            no_seatbelt_alert = (
                no_seatbelt_duration >= SEATBELT_ALERT_TIME
            )

            # =================================================
            # RISK ENGINE
            # =================================================

            risk_score, risk_level = calculate_risk(
                drowsy=drowsy,
                yawning=yawning,
                distracted=distracted,
                phone_detected=phone_alert,
                seatbelt_detected=seatbelt_detected,
            )

            # =================================================
            # CONTINUOUS TELEMETRY LOGGING
            # =================================================

            now = time.monotonic()

            if now - last_telemetry_time >= TELEMETRY_INTERVAL:
                log_telemetry(
                    ear=average_ear,
                    mar=mar,
                    pitch=pitch,
                    yaw=yaw,
                    head_direction=head_direction,
                    phone_detected=phone_alert,
                    seatbelt_detected=seatbelt_detected,
                    drowsy=drowsy,
                    yawning=yawning,
                    distracted=distracted,
                    risk_score=risk_score,
                    risk_level=risk_level,
                )

                last_telemetry_time = now

            # =================================================
            # EVENT LOGGING
            # =================================================

            event_details = {
                "ear": round(average_ear, 3),
                "mar": round(mar, 3),
                "head_direction": head_direction,
                "pitch": round(pitch, 1),
                "yaw": round(yaw, 1),
                "phone": phone_alert,
                "seatbelt": seatbelt_detected,
            }

            if drowsy and should_log(
                last_event_times,
                "DROWSINESS",
            ):
                log_event(
                    "DROWSINESS",
                    risk_score,
                    event_details,
                )

            if yawning and should_log(
                last_event_times,
                "YAWN",
            ):
                log_event(
                    "YAWN",
                    risk_score,
                    event_details,
                )

            if distracted and should_log(
                last_event_times,
                "DISTRACTION",
            ):
                log_event(
                    "DISTRACTION",
                    risk_score,
                    event_details,
                )

            if phone_alert and should_log(
                last_event_times,
                "PHONE",
            ):
                log_event(
                    "PHONE",
                    risk_score,
                    event_details,
                )

            if no_seatbelt_alert and should_log(
                last_event_times,
                "NO_SEATBELT",
            ):
                log_event(
                    "NO_SEATBELT",
                    risk_score,
                    event_details,
                )

            # =================================================
            # SOUND / VOICE ALERTS
            # =================================================

            # High-risk alert gets the strongest warning.
            if risk_level == "HIGH":
                alert_manager.alert(
                    "HIGH_RISK",
                    "Warning. High driver risk detected.",
                )

            if drowsy:
                alert_manager.alert(
                    "DROWSINESS",
                    "Drowsiness detected. Please stay alert.",
                )

            if yawning:
                alert_manager.alert(
                    "YAWN",
                    "Frequent yawning detected. Consider taking a break.",
                )

            if distracted:
                alert_manager.alert(
                    "DISTRACTION",
                    "Driver distraction detected. Please look at the road.",
                )

            if phone_alert:
                alert_manager.alert(
                    "PHONE",
                    "Phone use detected. Please put the phone away.",
                )

            if no_seatbelt_alert:
                alert_manager.alert(
                    "NO_SEATBELT",
                    "Seatbelt not detected. Please wear your seatbelt.",
                )

            # =================================================
            # UI OVERLAY
            # =================================================

            y = 30

            def put_status(text, color=(255, 255, 255), size=0.65):
                nonlocal y

                cv2.putText(
                    frame,
                    text,
                    (20, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    size,
                    color,
                    2,
                )

                y += 32

            if result.face_landmarks:
                put_status(
                    "DRIVER DETECTED",
                    (0, 255, 0),
                )
            else:
                put_status(
                    "NO DRIVER DETECTED",
                    (0, 0, 255),
                )

            put_status(
                f"EAR: {average_ear:.3f}",
                (255, 255, 0),
            )

            put_status(
                f"MAR: {mar:.3f}",
                (255, 255, 0),
            )

            put_status(
                f"HEAD: {head_direction}",
            )

            put_status(
                f"Pitch: {pitch:.1f}  Yaw: {yaw:.1f}",
            )

            if drowsy:
                put_status(
                    "DROWSINESS ALERT!",
                    (0, 0, 255),
                    0.8,
                )

            if yawning:
                put_status(
                    "YAWN DETECTED!",
                    (0, 0, 255),
                    0.8,
                )

            if distracted:
                put_status(
                    "DISTRACTION ALERT!",
                    (0, 0, 255),
                    0.8,
                )

            if phone_alert:
                put_status(
                    "PHONE ALERT!",
                    (0, 0, 255),
                    0.8,
                )

            if no_seatbelt_alert:
                put_status(
                    "SEATBELT NOT DETECTED",
                    (0, 165, 255),
                    0.75,
                )
            else:
                put_status(
                    "SEATBELT DETECTED",
                    (0, 255, 0),
                )

            if risk_level == "HIGH":
                risk_color = (0, 0, 255)
            elif risk_level == "MEDIUM":
                risk_color = (0, 165, 255)
            else:
                risk_color = (0, 255, 0)

            put_status(
                f"RISK: {risk_score}/100 ({risk_level})",
                risk_color,
                0.8,
            )

            # =================================================
            # DRAW PHONE BOXES
            # =================================================

            for detection in phone_detections:
                x1, y1, x2, y2 = detection["box"]
                confidence = detection["confidence"]

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 0, 255),
                    2,
                )

                cv2.putText(
                    frame,
                    f"PHONE {confidence:.2f}",
                    (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )

            # =================================================
            # DRAW SEATBELT REGION
            # =================================================

            if seatbelt_roi is not None:
                sx1, sy1, sx2, sy2 = seatbelt_roi

                cv2.rectangle(
                    frame,
                    (sx1, sy1),
                    (sx2, sy2),
                    (255, 255, 255),
                    1,
                )

            if seatbelt_line is not None:
                lx1, ly1, lx2, ly2 = seatbelt_line

                cv2.line(
                    frame,
                    (lx1, ly1),
                    (lx2, ly2),
                    (0, 255, 0),
                    3,
                )

            cv2.imshow(
                "AI Driver Safety System",
                frame,
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n⚠️ Monitoring stopped by user.")

    finally:
        camera.release()
        cv2.destroyAllWindows()
        landmarker.close()
        alert_manager.close()

        print("✅ AI Driver Safety System stopped.")
        print(f"📄 CSV events: {EVENT_CSV}")
        print(f"🗄️ SQLite database: {EVENT_DB}")


if __name__ == "__main__":
    main()
