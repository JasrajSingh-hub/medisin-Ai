import base64
import string
import traceback

import cv2
import mediapipe as mp
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.isl_sign_model import get_model
from routers.vital_guard_router import router as vital_guard_router


class ImagePayLoad(BaseModel):
    image: str


class LandmarkPayLoad(BaseModel):
    landmarks: list[float]


class TextPayLoad(BaseModel):
    text: str


mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=True, max_num_hands=2)
model = get_model()
print("[OK] ISL JSON model loaded!")
print(f"[OK] Model class: {type(model).__name__}")

app = FastAPI()
app.include_router(vital_guard_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

recent_predictions = []
CONFIRM_THRESHOLD = 15
current_word = ""
last_confirmed_letter = None


def extract_hand(landmarks):
    wx, wy, wz = landmarks[0].x, landmarks[0].y, landmarks[0].z
    row = []
    for point in landmarks:
        row.extend([point.x - wx, point.y - wy, point.z - wz])
    return row


def normalize(landmarks_relative):
    if not landmarks_relative:
        return landmarks_relative

    wrist = np.asarray(landmarks_relative[:3], dtype=np.float32)
    centered = np.asarray(landmarks_relative, dtype=np.float32).reshape(-1, 3) - wrist
    max_dist = max(float(np.linalg.norm(point)) for point in centered) or 1.0
    return (centered / max_dist).flatten().tolist()


def decode_image_data(image_data: str) -> bytes:
    if not image_data:
        raise ValueError("Missing image payload")

    encoded_image = image_data.split(",", 1)[1] if "," in image_data else image_data
    encoded_image = "".join(encoded_image.split())
    try:
        return base64.b64decode(encoded_image + "==")
    except Exception as exc:
        raise ValueError(f"Invalid image payload: {exc}") from exc


def predict_from_landmarks_vector(vector: list[float]) -> dict:
    if len(vector) != 126:
        raise ValueError("landmarks must contain exactly 126 floats")

    prediction_result = model.predict_one(vector)
    prediction = prediction_result["letter"]
    confidence = prediction_result["confidence"]
    return {
        "letter": str(prediction),
        "confidence": f"{confidence:.1f}%",
    }


@app.post("/predict")
async def predict(payload: ImagePayLoad):
    try:
        decoded_bytes = decode_image_data(payload.image)
        frame = cv2.imdecode(np.frombuffer(decoded_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Unable to decode image bytes")
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("Decoded image is not a valid color frame")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        if not result.multi_hand_landmarks:
            return {"letter": "No hand", "confidence": "0%"}

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
            return {"letter": "Error", "confidence": "0%"}

        data_row = normalize(data_row)
        result = predict_from_landmarks_vector(data_row)
        return result
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"sign prediction failed: {exc}")


@app.post("/predict_landmarks")
async def predict_landmarks(payload: LandmarkPayLoad):
    try:
        result = predict_from_landmarks_vector(payload.landmarks)
        return result
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/avatar/parse")
async def parse_text_to_tokens(payload: TextPayLoad):
    raw_text = payload.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="No text content provided")
    clean_text = raw_text.lower().translate(str.maketrans("", "", string.punctuation))
    words = clean_text.split()
    final_token_sequence = []
    for word in words:
        for letter in word:
            if letter.isalpha():
                final_token_sequence.append(letter.upper())
        final_token_sequence.append("SPACE")
    if final_token_sequence and final_token_sequence[-1] == "SPACE":
        final_token_sequence.pop()
    return {"status": "success", "original_text": raw_text, "tokens": final_token_sequence}


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)

