from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from services import emergency_service

router = APIRouter(prefix="/api/v1/emergency", tags=["emergency"])

class ImagePayload(BaseModel):
    image: Optional[str] = None

@router.post("/predict")
async def emergency_predict(
    file: Optional[UploadFile] = File(None),
    image: Optional[str] = Form(None)
):
    try:
        if file:
            file_bytes = await file.read()
            return emergency_service.predict(file_bytes=file_bytes)
        elif image:
            return emergency_service.predict(image_base64=image)
        else:
            raise HTTPException(status_code=400, detail="No image file or base64 data provided")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/status")
def emergency_status():
    return emergency_service.status()

@router.get("/health")
def emergency_health():
    return emergency_service.health()

@router.get("/nearby-hospitals")
def get_nearby_hospitals(lat: float, lng: float):
    # Mock nearby hospitals based on given coordinates
    return [
        {
            "name": "City General Hospital",
            "lat": lat + 0.005,
            "lng": lng + 0.005,
            "distance_m": 850.0
        },
        {
            "name": "St. Jude Emergency Center",
            "lat": lat - 0.003,
            "lng": lng + 0.002,
            "distance_m": 420.0
        },
        {
            "name": "Metro Care Clinic",
            "lat": lat + 0.001,
            "lng": lng - 0.006,
            "distance_m": 1200.0
        }
    ]
