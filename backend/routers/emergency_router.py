from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services import emergency_service

router = APIRouter(prefix="/emergency", tags=["emergency"])

class ImagePayload(BaseModel):
    image: Optional[str] = None

@router.post("/predict")
async def emergency_predict(payload: ImagePayload):
    try:
        return emergency_service.predict(image_base64=payload.image)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/status")
def emergency_status():
    return emergency_service.status()
