from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, HOST, PORT, OUTPUT_DIR, MOCK_MODE, BFL_API_KEY, VIDEO_API_KEY
from .models import CampaignRequest, VideoRequest, ImageRequest
from .gemini_service import generate_content
from .gemini_video_service import generate_video
from .bfl_image_service import generate_bfl_image
from .mock_service import mock_content


app = FastAPI(title=APP_NAME, version="1.0.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

app.mount(
    "/outputs",
    StaticFiles(directory=OUTPUT_DIR),
    name="outputs"
)


@app.get("/")
def root():
    return {
        "service": APP_NAME,
        "status": "running",
        "bfl_image_generation": bool(BFL_API_KEY),
        "video_generation": bool(VIDEO_API_KEY),
        "docs": "/docs"
    }


@app.get("/health")
def health():
    from .config import GEMINI_API_KEY, BFL_API_KEY, VIDEO_API_KEY

    return {
        "status": "ok",
        "gemini_configured": bool(GEMINI_API_KEY),
        "bfl_image_key_configured": bool(BFL_API_KEY),
        "bfl_key": BFL_API_KEY[:8] + "..." if BFL_API_KEY else "none",
        "video_key_configured": bool(VIDEO_API_KEY),
        "video_key": VIDEO_API_KEY[:8] + "..." if VIDEO_API_KEY else "none",
        "video_provider": "Wan-AI / Fal.ai / Video Engine",
        "mock_mode": MOCK_MODE,
    }


@app.post("/api/content/generate")
@app.post("/content/generate")
def create_content(request: CampaignRequest):

    payload = request.model_dump()

    try:
        if MOCK_MODE:
            result = mock_content(payload)
        else:
            try:
                result = generate_content(payload)
            except Exception as e:
                print(f"[WARN] Gemini API call failed: {e}. Using dynamic content fallback.")
                result = mock_content(payload)
                result["_fallback_reason"] = str(e)

        return {
            "success": True,
            "agent": "content",
            "data": result
        }

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Content generation failed: {exc}"
        ) from exc


@app.post("/api/content/generate-image")
@app.post("/content/generate-image")
def create_image(request: ImageRequest):
    try:
        res = generate_bfl_image(
            prompt=request.prompt,
            width=request.width,
            height=request.height,
            model=request.model or "flux-pro-1.1"
        )
        return {
            "success": True,
            "agent": "content",
            "provider": res.get("provider", "BFL FLUX"),
            "image_url": res.get("image_url"),
            "filename": res.get("filename"),
            "prompt": request.prompt
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"BFL image generation failed: {exc}"
        ) from exc


@app.post("/api/content/generate-video")
@app.post("/content/generate-video")
def create_video(request: VideoRequest):

    try:

        filename = generate_video(
            prompt=request.prompt
        )

        return {
            "success": True,
            "agent": "content",
            "provider": "Wan-AI / Video Engine",
            "video_url": f"/outputs/{filename}",
            "filename": filename
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=f"Video generation failed: {exc}"
        ) from exc



if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True
    )