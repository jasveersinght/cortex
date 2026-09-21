import json
import re
from pathlib import Path
from google import genai
from google.genai import types
from .config import GEMINI_API_KEY, GEMINI_MODEL

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "content_prompt.txt"


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def generate_content(payload: dict) -> dict:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=GEMINI_API_KEY)
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    user_prompt = json.dumps(payload, ensure_ascii=False, indent=2)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"{system_prompt}\n\nCAMPAIGN INPUT:\n{user_prompt}",
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=5000,
            response_mime_type="application/json",
        ),
    )
    return _extract_json(response.text)
