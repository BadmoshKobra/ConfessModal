from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import os
import requests

app = FastAPI()

# Use Gemini or any hosted API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Add this in your .env or Render env vars

class ModerateInput(BaseModel):
    post: str

@app.get("/")
def root():
    return {"status": "moderation server running"}

@app.post("/moderate")
def moderate(data: ModerateInput):
    prompt = f"""
You are a moderation assistant for a social media app used by Indian users in English and Hinglish.

Classify the following post into ONLY ONE of these categories:

[safe, religious_hate, sexual_threat, national_offense]

Guidelines:
- Abuse, slang, and emotional expressions like depression, anxiety, or self-hate are allowed → classify as safe
- Religious hate or targeting of any religion is not allowed → classify as religious_hate
- National hate, anti-country sentiment, terrorism, or attack on any nation's dignity is not allowed → classify as national_offense
- Any sexual threat, abuse, harassment, or assault-related content is not allowed → classify as sexual_threat

Example Post: "{data.post}"
Label:
    """

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]}
        )
        res = response.json()
        label = res["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
        return {"label": label}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
