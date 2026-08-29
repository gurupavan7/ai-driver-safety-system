from ultralytics import YOLO


# Load lightweight YOLO model
model = YOLO("yolov8n.pt")

PHONE_CLASS_ID = 67


def detect_phone(frame, confidence_threshold=0.45):
    results = model(
        frame,
        verbose=False
    )

    phone_detected = False
    detections = []

    for result in results:

        if result.boxes is None:
            continue

        for box in result.boxes:

            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            if (
                class_id == PHONE_CLASS_ID
                and confidence >= confidence_threshold
            ):
                phone_detected = True

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0]
                )

                detections.append(
                    {
                        "confidence": confidence,
                        "box": (x1, y1, x2, y2),
                    }
                )

    return phone_detected, detections
    