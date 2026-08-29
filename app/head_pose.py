import cv2
import numpy as np


# MediaPipe Face Landmarker indices used for head pose
NOSE_TIP = 1
CHIN = 152
LEFT_EYE_CORNER = 33
RIGHT_EYE_CORNER = 263
LEFT_MOUTH_CORNER = 61
RIGHT_MOUTH_CORNER = 291


def detect_head_pose(frame, landmarks):
    height, width, _ = frame.shape

    # 2D landmark points from the camera image
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
        dtype="double",
    )

    # Approximate 3D face model
    model_points = np.array(
        [
            (0.0, 0.0, 0.0),          # Nose tip
            (0.0, -330.0, -65.0),     # Chin
            (-225.0, 170.0, -135.0),  # Left eye
            (225.0, 170.0, -135.0),   # Right eye
            (-150.0, -150.0, -125.0), # Left mouth
            (150.0, -150.0, -125.0),  # Right mouth
        ],
        dtype="double",
    )

    # Camera approximation
    focal_length = width

    center = (
        width / 2,
        height / 2,
    )

    camera_matrix = np.array(
        [
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1],
        ],
        dtype="double",
    )

    distortion_coefficients = np.zeros(
        (4, 1)
    )

    success, rotation_vector, translation_vector = cv2.solvePnP(
        model_points,
        image_points,
        camera_matrix,
        distortion_coefficients,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )

    if not success:
        return "UNKNOWN", 0.0, 0.0

    rotation_matrix, _ = cv2.Rodrigues(
        rotation_vector
    )

    angles, _, _, _, _, _ = cv2.RQDecomp3x3(
        rotation_matrix
    )

    pitch = angles[0]
    yaw = angles[1]

    # Head direction thresholds
    if yaw < -15:
        direction = "LOOKING LEFT"

    elif yaw > 15:
        direction = "LOOKING RIGHT"

    elif pitch < -12:
        direction = "LOOKING DOWN"

    elif pitch > 12:
        direction = "LOOKING UP"

    else:
        direction = "LOOKING FORWARD"

    return direction, pitch, yaw