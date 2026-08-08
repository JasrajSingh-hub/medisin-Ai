from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import string

router = APIRouter(prefix="/api/v1/avatar", tags=["avatar"])

class TextPayLoad(BaseModel):
    text: str

@router.post("/parse")
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
