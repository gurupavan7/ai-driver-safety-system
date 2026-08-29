from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "face_landmarker.task"
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}

# Eye / mouth landmarks
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [78, 13, 14, 308]

# Head pose landmarks
NOSE_TIP = 1
CHIN = 152
LEFT_EYE_CORNER = 33
RIGHT_EYE_CORNER = 263
LEFT_MOUTH_CORNER = 61
RIGHT_MOUTH_CORNER = 291

# Detection thresholds
EYE_THRESHOLD = 0.20
DROWSINESS_TIME = 2.0

YAWN_THRESHOLD = 0.30
YAWN_TIME = 1.5

YAW_THRESHOLD = 15.0
PITCH_THRESHOLD = 12.0
DISTRACTION_TIME = 2.0

PHONE_CLASS_ID = 67
PHONE_CONFIDENCE = 0.45
PHONE_DETECT_EVERY_N_FRAMES = 3

# Risk weights
RISK_DROWSY = 45
RISK_YAWN = 20
RISK_DISTRACTED = 25
RISK_PHONE = 35
RISK_NO_SEATBELT = 20


def validate_video(video_path: str | Path) -> Path:
    path = Path(video_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"Video not found: {path}")

    if not path.is_file():
        raise ValueError(f"Video path is not a file: {path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"Unsupported video format {path.suffix}. Supported: {allowed}"
        )

    return path


def get_video_metadata(video_path: str | Path) -> dict[str, Any]:
    path = validate_video(video_path)
    capture = cv2.VideoCapture(str(path))

    if not capture.isOpened():
        raise RuntimeError(f"OpenCV could not open: {path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    capture.release()

    duration_seconds = total_frames / fps if fps > 0 else 0

    return {
        "file_name": path.name,
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "width": width,
        "height": height,
        "duration_seconds": round(duration_seconds, 2),
    }


def _point(landmarks, index: int, width: int, height: int) -> np.ndarray:
    lm = landmarks[index]
    return np.array([lm.x * width, lm.y * height], dtype=np.float64)


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def calculate_ear(landmarks, indices, width: int, height: int) -> float:
    p1, p2, p3, p4, p5, p6 = [
        _point(landmarks, idx, width, height) for idx in indices
    ]

    horizontal = _distance(p1, p4)
    if horizontal <= 1e-8:
        return 0.0

    vertical_1 = _distance(p2, p6)
    vertical_2 = _distance(p3, p5)
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def calculate_mar(landmarks, width: int, height: int) -> float:
    left = _point(landmarks, MOUTH[0], width, height)
    top = _point(landmarks, MOUTH[1], width, height)
    bottom = _point(landmarks, MOUTH[2], width, height)
    right = _point(landmarks, MOUTH[3], width, height)

    horizontal = _distance(left, right)
    if horizontal <= 1e-8:
        return 0.0

    return _distance(top, bottom) / horizontal


def estimate_head_pose(
    landmarks,
    width: int,
    height: int,
) -> tuple[float, float, str]:
    image_points = np.array(
        [
            _point(landmarks, NOSE_TIP, width, height),
            _point(landmarks, CHIN, width, height),
            _point(landmarks, LEFT_EYE_CORNER, width, height),
            _point(landmarks, RIGHT_EYE_CORNER, width, height),
            _point(landmarks, LEFT_MOUTH_CORNER, width, height),
            _point(landmarks, RIGHT_MOUTH_CORNER, width, height),
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
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1],
        ],
        dtype=np.float64,
    )

    distortion = np.zeros((4, 1), dtype=np.float64)

    success, rotation_vector, _ = cv2.solvePnP(
        model_points,
        image_points,
        camera_matrix,
        distortion,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )

    if not success:
        return 0.0, 0.0, "CENTER"

    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    angles = cv2.RQDecomp3x3(rotation_matrix)[0]

    pitch = float(angles[0])
    yaw = float(angles[1])

    if yaw > YAW_THRESHOLD:
        direction = "RIGHT"
    elif yaw < -YAW_THRESHOLD:
        direction = "LEFT"
    elif pitch > PITCH_THRESHOLD:
        direction = "DOWN"
    elif pitch < -PITCH_THRESHOLD:
        direction = "UP"
    else:
        direction = "CENTER"

    return pitch, yaw, direction


def detect_seatbelt(frame: np.ndarray) -> bool:
    """
    Prototype heuristic only.
    It searches the central torso region for a strong diagonal line.
    This is not equivalent to a dedicated trained seatbelt detector.
    """
    height, width = frame.shape[:2]

    x1 = int(width * 0.25)
    x2 = int(width * 0.75)
    y1 = int(height * 0.35)
    y2 = int(height * 0.95)

    roi = frame[y1:y2, x1:x2]

    if roi.size == 0:
        return False

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    min_length = max(40, int(min(roi.shape[:2]) * 0.22))

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=45,
        minLineLength=min_length,
        maxLineGap=20,
    )

    if lines is None:
        return False

    for line in lines:
        coords = np.asarray(line).reshape(-1)
        if coords.size != 4:
            continue

        lx1, ly1, lx2, ly2 = map(int, coords)

        dx = lx2 - lx1
        dy = ly2 - ly1
        length = math.hypot(dx, dy)

        if length < min_length:
            continue

        angle = abs(math.degrees(math.atan2(dy, dx)))
        angle = angle if angle <= 90 else 180 - angle

        if 25 <= angle <= 70:
            return True

    return False


def calculate_risk(
    drowsy: bool,
    yawning: bool,
    distracted: bool,
    phone_detected: bool,
    seatbelt_detected: bool,
) -> tuple[int, str]:
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

    score = min(100, score)

    if score >= 70:
        level = "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    else:
        level = "LOW"

    return score, level


def _event_name(flags: dict[str, bool]) -> list[str]:
    names = []
    if flags["drowsy"]:
        names.append("DROWSINESS")
    if flags["yawning"]:
        names.append("YAWN")
    if flags["distracted"]:
        names.append("DISTRACTION")
    if flags["phone"]:
        names.append("PHONE")
    if flags["no_seatbelt"]:
        names.append("NO_SEATBELT")
    return names


class VideoSafetyAnalyzer:
    def __init__(self) -> None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Missing MediaPipe model: {MODEL_PATH}. "
                "Expected models/face_landmarker.task"
            )

        base_options = python.BaseOptions(
            model_asset_path=str(MODEL_PATH),
            delegate=python.BaseOptions.Delegate.CPU,
        )

        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
        )

        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        self.phone_model = YOLO("yolov8n.pt")

    def close(self) -> None:
        self.landmarker.close()

    def analyze(self, video_path: str | Path) -> dict[str, Any]:
        path = validate_video(video_path)
        metadata = get_video_metadata(path)

        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise RuntimeError(f"Unable to open video: {path}")

        fps = float(metadata["fps"] or 0)
        if fps <= 0:
            fps = 30.0

        total_frames = int(metadata["total_frames"])

        eye_closed_start: float | None = None
        yawn_start: float | None = None
        distraction_start: float | None = None

        processed_frames = 0

        phone_detected = False
        seatbelt_detected = False

        last_flags = {
            "drowsy": False,
            "yawning": False,
            "distracted": False,
            "phone": False,
            "no_seatbelt": False,
        }

        event_counts = {
            "drowsiness_events": 0,
            "yawn_events": 0,
            "distraction_events": 0,
            "phone_events": 0,
            "seatbelt_violations": 0,
        }

        timeline: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        risk_scores: list[int] = []

        last_sample_second = -1

        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break

                processed_frames += 1
                height, width = frame.shape[:2]
                video_time = processed_frames / fps
                timestamp_ms = int(video_time * 1000)

                # Defaults when no face is detected.
                ear = 0.0
                mar = 0.0
                pitch = 0.0
                yaw = 0.0
                head_direction = "NO_FACE"

                drowsy = False
                yawning = False
                distracted = False

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb_frame,
                )

                face_result = self.landmarker.detect_for_video(
                    mp_image,
                    timestamp_ms,
                )

                if face_result.face_landmarks:
                    landmarks = face_result.face_landmarks[0]

                    left_ear = calculate_ear(
                        landmarks,
                        LEFT_EYE,
                        width,
                        height,
                    )
                    right_ear = calculate_ear(
                        landmarks,
                        RIGHT_EYE,
                        width,
                        height,
                    )
                    ear = (left_ear + right_ear) / 2.0

                    mar = calculate_mar(landmarks, width, height)

                    pitch, yaw, head_direction = estimate_head_pose(
                        landmarks,
                        width,
                        height,
                    )

                    if ear < EYE_THRESHOLD:
                        if eye_closed_start is None:
                            eye_closed_start = video_time
                        drowsy = (
                            video_time - eye_closed_start
                        ) >= DROWSINESS_TIME
                    else:
                        eye_closed_start = None

                    if mar > YAWN_THRESHOLD:
                        if yawn_start is None:
                            yawn_start = video_time
                        yawning = (
                            video_time - yawn_start
                        ) >= YAWN_TIME
                    else:
                        yawn_start = None

                    looking_away = (
                        abs(yaw) > YAW_THRESHOLD
                        or abs(pitch) > PITCH_THRESHOLD
                    )

                    if looking_away:
                        if distraction_start is None:
                            distraction_start = video_time
                        distracted = (
                            video_time - distraction_start
                        ) >= DISTRACTION_TIME
                    else:
                        distraction_start = None

                else:
                    eye_closed_start = None
                    yawn_start = None

                    if distraction_start is None:
                        distraction_start = video_time

                    distracted = (
                        video_time - distraction_start
                    ) >= DISTRACTION_TIME

                # YOLO phone detection every N frames.
                if processed_frames % PHONE_DETECT_EVERY_N_FRAMES == 0:
                    phone_detected = False
                    results = self.phone_model.predict(
                        frame,
                        verbose=False,
                        conf=PHONE_CONFIDENCE,
                    )

                    for result in results:
                        if result.boxes is None:
                            continue

                        for cls in result.boxes.cls.tolist():
                            if int(cls) == PHONE_CLASS_ID:
                                phone_detected = True
                                break

                        if phone_detected:
                            break

                # Seatbelt heuristic at a lower frequency for speed.
                if processed_frames % 5 == 0:
                    seatbelt_detected = detect_seatbelt(frame)

                risk_score, risk_level = calculate_risk(
                    drowsy=drowsy,
                    yawning=yawning,
                    distracted=distracted,
                    phone_detected=phone_detected,
                    seatbelt_detected=seatbelt_detected,
                )

                risk_scores.append(risk_score)

                flags = {
                    "drowsy": drowsy,
                    "yawning": yawning,
                    "distracted": distracted,
                    "phone": phone_detected,
                    "no_seatbelt": not seatbelt_detected,
                }

                # Count only rising edges so one long condition = one event.
                counter_map = {
                    "drowsy": "drowsiness_events",
                    "yawning": "yawn_events",
                    "distracted": "distraction_events",
                    "phone": "phone_events",
                    "no_seatbelt": "seatbelt_violations",
                }

                for key, active in flags.items():
                    if active and not last_flags[key]:
                        event_counts[counter_map[key]] += 1

                        events.append(
                            {
                                "time_seconds": round(video_time, 2),
                                "event_type": {
                                    "drowsy": "DROWSINESS",
                                    "yawning": "YAWN",
                                    "distracted": "DISTRACTION",
                                    "phone": "PHONE",
                                    "no_seatbelt": "NO_SEATBELT",
                                }[key],
                                "risk_score": risk_score,
                                "risk_level": risk_level,
                            }
                        )

                last_flags = flags.copy()

                # One chart sample per second.
                current_second = int(video_time)
                if current_second != last_sample_second:
                    timeline.append(
                        {
                            "time_seconds": round(video_time, 2),
                            "ear": round(float(ear), 4),
                            "mar": round(float(mar), 4),
                            "pitch": round(float(pitch), 2),
                            "yaw": round(float(yaw), 2),
                            "head_direction": head_direction,
                            "phone_detected": bool(phone_detected),
                            "seatbelt_detected": bool(seatbelt_detected),
                            "drowsy": bool(drowsy),
                            "yawning": bool(yawning),
                            "distracted": bool(distracted),
                            "risk_score": int(risk_score),
                            "risk_level": risk_level,
                            "active_events": _event_name(flags),
                        }
                    )
                    last_sample_second = current_second

        finally:
            capture.release()

        average_risk = (
            round(sum(risk_scores) / len(risk_scores), 2)
            if risk_scores
            else 0.0
        )
        max_risk = max(risk_scores) if risk_scores else 0

        if max_risk >= 70:
            overall_level = "HIGH"
        elif max_risk >= 35:
            overall_level = "MEDIUM"
        else:
            overall_level = "LOW"

        summary = {
            **event_counts,
            "average_risk": average_risk,
            "max_risk": int(max_risk),
            "overall_risk_level": overall_level,
            "total_events": len(events),
        }

        return {
            "status": "completed",
            "video": metadata,
            "processed_frames": processed_frames,
            "summary": summary,
            "events": events,
            "timeline": timeline,
        }


def analyze_video(video_path: str | Path) -> dict[str, Any]:
    analyzer = VideoSafetyAnalyzer()
    try:
        return analyzer.analyze(video_path)
    finally:
        analyzer.close()


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Path to MP4/MOV/AVI/MKV/M4V video")
    args = parser.parse_args()

    result = analyze_video(args.video)
    print(json.dumps(result, indent=2))
