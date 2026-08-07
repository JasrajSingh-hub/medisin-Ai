import base64

import cv2
import numpy as np
from services.isl_sign_model import get_model

try:
    import mediapipe as mp

    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(static_image_mode=True, max_num_hands=2)
except Exception:
    mp = None
    mp_hands = None
    hands = None
recent_predictions = []
CONFIRM_THRESHOLD = 15
current_word = ""
last_confirmed_letter = None


def decode_image_data(image_data: str) -> bytes:
    if not image_data:
        raise ValueError("image is required")

    encoded_image = image_data.split(",", 1)[1] if "," in image_data else image_data
    try:
        return base64.b64decode(encoded_image, validate=True)
    except Exception as exc:
        raise ValueError(f"invalid image payload: {exc}") from exc


def extract_hand(landmarks):
    wrist_x, wrist_y, wrist_z = landmarks[0].x, landmarks[0].y, landmarks[0].z
    row = []
    for point in landmarks:
        row.extend([point.x - wrist_x, point.y - wrist_y, point.z - wrist_z])
    return row


def normalize(landmarks_relative):
    if not landmarks_relative:
        return landmarks_relative

    wrist = np.asarray(landmarks_relative[:3], dtype=np.float32)
    centered = np.asarray(landmarks_relative, dtype=np.float32).reshape(-1, 3) - wrist
    max_dist = max(float(np.linalg.norm(point)) for point in centered) or 1.0
    return (centered / max_dist).flatten().tolist()


def landmarks_to_points(landmarks):
    return [{"x": float(point.x), "y": float(point.y), "z": float(point.z)} for point in landmarks]


def predict_sign(image_data: str) -> dict:
    if hands is None:
        return {"letter": "Unavailable", "confidence": "0%", "landmarks": []}

    model = get_model()
    decoded_bytes = decode_image_data(image_data)
    frame = cv2.imdecode(np.frombuffer(decoded_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("could not decode image bytes")
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    if not result.multi_hand_landmarks:
        return {"letter": "No hand", "confidence": "0%", "landmarks": []}

    data_row = []
    num_hands = len(result.multi_hand_landmarks)
    if num_hands == 2:
        hands_data = list(zip(result.multi_hand_landmarks, result.multi_handedness))
        hands_data.sort(key=lambda x: x[1].classification[0].label)
        for hand, _ in hands_data:
            data_row.extend(extract_hand(hand.landmark))
    elif num_hands == 1:
        hand = result.multi_hand_landmarks[0]
        handedness = result.multi_handedness[0].classification[0].label
        hand_data = extract_hand(hand.landmark)
        data_row = hand_data + [0] * 63 if handedness == "Left" else [0] * 63 + hand_data

    if len(data_row) != 126:
        return {"letter": "Error", "confidence": "0%", "landmarks": []}

    data_row = normalize(data_row)
    prediction_result = model.predict_one(data_row)
    prediction = prediction_result["letter"]
    confidence = prediction_result["confidence"]

    global recent_predictions, current_word, last_confirmed_letter
    recent_predictions.append(str(prediction))
    if len(recent_predictions) > CONFIRM_THRESHOLD:
        recent_predictions.pop(0)

    letter_confirmed = False
    if len(recent_predictions) == CONFIRM_THRESHOLD and len(set(recent_predictions)) == 1:
        steady_letter = recent_predictions[0]
        if steady_letter != last_confirmed_letter:
            current_word += steady_letter
            last_confirmed_letter = steady_letter
            letter_confirmed = True

    hand_landmarks = []
    if num_hands == 2:
        hands_data = list(zip(result.multi_hand_landmarks, result.multi_handedness))
        hands_data.sort(key=lambda x: x[1].classification[0].label)
        hand_landmarks = [landmarks_to_points(hand.landmark) for hand, _ in hands_data]
    elif num_hands == 1:
        hand_landmarks = [landmarks_to_points(result.multi_hand_landmarks[0].landmark)]

    return {
        "letter": str(prediction),
        "confidence": f"{confidence:.1f}%",
        "letter_confirmed": letter_confirmed,
        "current_word": current_word,
        "landmarks": hand_landmarks,
    }


def predict_sign_landmarks(vector: list[float]) -> dict:
    model = get_model()
    if len(vector) != 126:
        raise ValueError("landmarks must contain exactly 126 floats")

    prediction_result = model.predict_one(vector)
    return {
        "letter": str(prediction_result["letter"]),
        "confidence": f"{prediction_result['confidence']:.1f}%",
    }
