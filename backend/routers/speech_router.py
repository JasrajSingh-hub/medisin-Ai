from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/speech", tags=["speech"])

class TextPayload(BaseModel):
    text: str

@router.post("/tts")
def text_to_speech(payload: TextPayload):
    return {"status": "success", "message": "TTS simulated successfully"}

@router.post("/stt")
def speech_to_text():
    return {"status": "success", "text": "Simulated speech transcription"}
