import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "CORTEX Content Agent")
APP_ENV = os.getenv("APP_ENV", "development")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_PROVIDER = os.getenv("HF_PROVIDER", "fal-ai")
HF_VIDEO_MODEL = os.getenv("HF_VIDEO_MODEL", "Wan-AI/Wan2.1-T2V-1.3B")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"
