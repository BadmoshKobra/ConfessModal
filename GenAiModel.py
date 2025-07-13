from fastapi import FastAPI, Header, HTTPException, Query, Depends
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
import os
import threading
import time
import requests
import hashlib
import google.generativeai as genai
import os
import time
import psutil
import socket

app = FastAPI()

#* Health datas
serverId = socket.gethostname()
process = psutil.Process(os.getpid())
startTime = time.time()

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
    You are a content moderation assistant for a social media app used by Indian users in English and Hinglish.

    Classify the following post into ONLY ONE of these categories:
    [safe, religious_hate, sexual_threat, national_offense]

    Classify strictly based on the intention and context of the message, not just words used.

    Moderation Rules:

    - Vulgar words, slang, personal insults, and anger/rage are acceptable if they are expressions of frustration or aggression (not actual threats) → classify as **safe**
    - Posts targeting or promoting hate against any religion → classify as **religious_hate**
    - Posts promoting anti-national sentiment, terrorism, or insulting a country → classify as **national_offense**
    - Posts involving **serious or intentional** sexual harassment, threats, blackmail, or predatory behavior → classify as **sexual_threat**

    The following post is written in Hinglish or informal tone:

    Post: "{data.post}"

    Now return the category label only (no explanation):
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

async def cors_health_preflight(
    request: Request,
    origin: str = Header(default="*"),
    access_control_request_method: str = Header(default=""),
    access_control_request_headers: str = Header(default="*"),
):
    if request.method == "OPTIONS":
        return JSONResponse(
            status_code=200,
            content={},
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": access_control_request_headers,
                "Access-Control-Max-Age": "86400"
            }
        )

def collect_health_data():
    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0.0, 0.0, 0.0)
    uptime = round(time.time() - startTime, 2)
    threads = process.num_threads()
    process_memory = round(process.memory_info().rss / (1024 ** 2), 2)

    return {
        "serverId": serverId,
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "uptime": uptime,
        "loadAvg": {
            "1m": round(load_avg[0], 2),
            "5m": round(load_avg[1], 2),
            "15m": round(load_avg[2], 2)
        },
        "threads": threads,
        "processMemoryMB": process_memory,
        "active": True
    }

@app.api_route("/health", methods=["GET", "OPTIONS"])
async def get_health_route(
    request: Request,
    cors_response=Depends(cors_health_preflight)
):
    # Handle preflight CORS
    if request.method == "OPTIONS":
        return cors_response

    # Validate API key
    api_key = request.headers.get("x-api-key")
    if not validate.validate(api_key):
        return JSONResponse(
            status_code=401,
            content={"message": False, "error": "Invalid API key"}
        )

    # Collect and return health stats
    health_data = await run_in_threadpool(collect_health_data)

    return JSONResponse(
        status_code=200,
        content=health_data,
        headers={
            "X-Server-ID": serverId,
            "X-Response-Time": str(round(time.time(), 2)),
            "Access-Control-Allow-Origin": "*",  # for GET response
        }
    )
