from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import os
import requests
import threading
import time

app = FastAPI()

# Your Gemini API key from Render environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Make sure to set this in Render

# Input model
class ModerateInput(BaseModel):
    post: str

# Root endpoint
@app.get("/")
def root():
    return {"status": "moderation server running"}

# Moderation endpoint
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

# 🔁 Self-ping thread to keep Render app awake
def self_ping():
    app_url = os.getenv("RENDER_EXTERNAL_URL")
    if not app_url:
        print("Self-ping skipped: not running on Render")
        return

    while True:
        try:
            requests.get(f"{app_url}/")
            print("🔁 Self-ping successful")
        except Exception as e:
            print("❌ Self-ping failed:", e)
        time.sleep(600)  # Every 10 minutes

# ✅ Start the background ping thread if running on Render
if os.getenv("RENDER_EXTERNAL_URL"):
    threading.Thread(target=self_ping, daemon=True).start()
