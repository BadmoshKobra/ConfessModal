from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import os
import threading
import time
import requests
import hashlib
import google.generativeai as genai

app = FastAPI()

# 🔐 Load Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

# 🔐 API auth setup
API_SECRET_SALT = os.getenv("SERVER_SALT")
API_HASHED_KEYS = os.getenv("SERVER_KEY", "").split(",")

# 📥 Input schema
class ModerateInput(BaseModel):
    post: str

# 🔐 Debug-enhanced API key validator
def verify_hashed_api_key(client_key: str = Header(None)):
    if not client_key:
        print("❌ No client-api-key received in headers.")
        raise HTTPException(status_code=401, detail="Missing API key")

    if not API_SECRET_SALT:
        print("❌ API_SECRET_SALT is missing")
        raise HTTPException(status_code=500, detail="Server misconfigured: missing salt")

    # Compute hash
    combined = client_key + API_SECRET_SALT
    hashed = hashlib.sha256(combined.encode()).hexdigest()

    if hashed not in API_HASHED_KEYS:
        print("❌ API key hash mismatch. Unauthorized access.")
        raise HTTPException(status_code=401, detail="Invalid API key")
    else:
        print("✅ API key validated successfully.")

# 🌐 Root check
@app.get("/")
def root():
    return {"status": "moderation server running"}

# 🧠 Main moderation route
@app.post("/moderate")
def moderate(data: ModerateInput, client_api_key: str = Header(None)):
    verify_hashed_api_key(client_api_key)

    if not model:
        return JSONResponse(status_code=500, content={"error": "Gemini not configured"})

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
        response = model.generate_content(prompt)
        label = response.text.strip().lower()
        return JSONResponse(
            status_code=200,
            content={"label": label}
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# 🔁 Keep-alive thread for Render
def self_ping():
    app_url = os.getenv("RENDER_EXTERNAL_URL")
    if not app_url:
        print("⚠️ Self-ping disabled (RENDER_EXTERNAL_URL not set)")
        return

    while True:
        try:
            requests.get(f"{app_url}/")
            print("🔁 Self-ping successful")
        except Exception as e:
            print("❌ Self-ping failed:", e)
        time.sleep(600)

# 🧵 Start self-ping thread only on Render
if os.getenv("RENDER_EXTERNAL_URL"):
    threading.Thread(target=self_ping, daemon=True).start()
