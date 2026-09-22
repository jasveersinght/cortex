from typing import List
from pydantic import BaseModel, Field

class ResearchInsight(BaseModel):
    topic: str
    key_finding: str
    opportunity: str = ""
    source: str = "Research Agent"

class CampaignRequest(BaseModel):
    research_insight: ResearchInsight
    product: str = "Term Insurance"
    target_audience: str = "Young Professionals"
    campaign_goal: str = "Lead Generation"
    platforms: List[str] = Field(default_factory=lambda: ["LinkedIn", "Instagram", "X"])
    language: str = "English"
    tone: str = "Professional but human"
    content_format: str = "Campaign"

class VideoRequest(BaseModel):
    prompt: str
    negative_prompt: str = "text artifacts, distorted faces, blurry, low quality, watermark, logo errors"
    model: str | None = None
    provider: str | None = None
    seed: int | None = None
    num_frames: int | None = None
    num_inference_steps: int | None = None

class ImageRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    model: str = "flux-pro-1.1"

