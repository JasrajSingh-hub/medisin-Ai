from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.sign_service import predict_sign, predict_sign_landmarks

router = APIRouter(tags=["sign"])


class ImagePayLoad(BaseModel):
    image: str


class LandmarkPayLoad(BaseModel):
    landmarks: list[float]


@router.post("/predict")
async def sign_predict(payload: ImagePayLoad):
    try:
        return predict_sign(payload.image)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/predict_landmarks")
async def sign_predict_landmarks(payload: LandmarkPayLoad):
    try:
        return predict_sign_landmarks(payload.landmarks)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
