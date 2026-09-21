# CORTEX Content Agent Backend

> AI-powered campaign intelligence and platform-native content generation for the CORTEX multi-agent marketing system.

The **CORTEX Content Agent** transforms research insights and campaign requirements into structured, ready-to-review marketing content using **Google Gemini**.

It sits between the **Research Agent** and downstream **Compliance / Human Approval** workflows, converting research into campaign strategy, platform-specific content, A/B variants, and visual concepts.

---

## 🚀 Overview

```text
Research Insight
       ↓
Campaign Intelligence
       ↓
Platform-Native Content
       ↓
A/B Variants
       ↓
Visual / Reel Brief
       ↓
Compliance Agent
       ↓
Human Approval
```

The Content Agent is designed to produce content that is:

- Research-driven
- Platform-aware
- Structured
- Reviewable
- Adaptable
- Ready for downstream compliance processing

---

# ✨ Features

### 🧠 AI Campaign Intelligence

Uses Google Gemini to transform research findings into:

- Campaign titles
- Campaign objectives
- Target audience messaging
- Core campaign messages
- Campaign angles
- Hooks

### 📱 Platform-Native Content

Generates content specifically for:

- LinkedIn
- Instagram
- X

### 🔀 A/B Content Variants

Generates multiple messaging approaches containing:

- Angle
- Hook
- Message

### 🎨 Visual Concepts

Generates a visual direction containing:

- Concept
- Composition
- Mood
- Headline

### 🎬 Optional Local MP4 Generation

The project includes a **₹0 local MP4 generator** using:

```text
Python + Pillow + MoviePy + FFmpeg
```

It does **not** use Hugging Face, Veo, or a paid video-generation API.

> The local video generator is a supporting demo feature. It is not an AI text-to-video model.

---

# 🏗️ Architecture

```text
                    CORTEX
                       │
                       ▼
              ┌─────────────────┐
              │  Research Agent │
              └────────┬────────┘
                       │
                       │ Research Insight
                       ▼
              ┌─────────────────┐
              │  Content Agent  │
              │     FastAPI     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Google Gemini  │
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
     Campaign      Platform       A/B
    Intelligence    Content     Variants
          │            │            │
          └────────────┼────────────┘
                       │
                       ▼
                Visual Concept
                       │
                       ▼
              Compliance Agent
                       │
                       ▼
                Human Approval
```

---

# 🔄 Content Agent Workflow

```text
1. Research Agent produces research insight
                    ↓
2. Content Agent receives structured input
                    ↓
3. Gemini analyzes the research
                    ↓
4. Campaign strategy is generated
                    ↓
5. Core messaging is generated
                    ↓
6. Platform-specific content is generated
                    ↓
7. A/B variants are generated
                    ↓
8. Visual concept is generated
                    ↓
9. Structured JSON is returned
                    ↓
10. Output can be passed to Compliance Agent
```

---

# 🧩 Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| API Framework | FastAPI |
| Server | Uvicorn |
| AI | Google Gemini |
| Gemini SDK | `google-genai` |
| Data Validation | Pydantic |
| Video Processing | MoviePy |
| Image Processing | Pillow |
| Video Encoding | FFmpeg / imageio-ffmpeg |
| API Documentation | Swagger / OpenAPI |
| Configuration | `.env` |
| CORS | FastAPI CORS Middleware |

---

# 📁 Project Structure

```text
cortex_content_agent_backend/
│
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── gemini_service.py
│   ├── gemini_video_service.py
│   ├── main.py
│   ├── mock_service.py
│   └── models.py
│
├── outputs/
│   └── generated MP4 files
│
├── prompts/
│   └── content_prompt.txt
│
├── .env
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── test_payload.json
```

---

# ⚙️ Requirements

- Windows / macOS / Linux
- Python 3.11+
- Google Gemini API key
- Internet connection for Gemini API requests

For local video generation:

- Pillow
- MoviePy
- imageio-ffmpeg

No Hugging Face token or paid video API is required by the current implementation.

---

# 🛠️ Installation

## 1. Navigate to the project

```powershell
cd D:\cortex_content_agent_backend
```

## 2. Create a virtual environment

```powershell
python -m venv .venv
```

## 3. Activate it

```powershell
.\.venv\Scripts\Activate.ps1
```

## 4. Install dependencies

```powershell
pip install -r requirements.txt
```

---

# 🔐 Environment Configuration

Create `.env` from the example:

```powershell
copy .env.example .env
```

Open it:

```powershell
code .env
```

Use:

```env
APP_NAME=CORTEX Content Agent
APP_ENV=development
HOST=0.0.0.0
PORT=8001

GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-3.6-flash

MOCK_MODE=false

OUTPUT_DIR=outputs
```

Replace `YOUR_GEMINI_API_KEY` with your Gemini API key.

### Security

Never commit `.env` to Git and never expose the API key in frontend code, screenshots, public documents, or repositories.

---

# ▶️ Running the Backend

```powershell
uvicorn app.main:app --reload --port 8001
```

Expected startup:

```text
Uvicorn running on http://127.0.0.1:8001
Application startup complete.
```

---

# 🌐 API Access

### Base URL

```text
http://127.0.0.1:8001
```

### Swagger UI

```text
http://127.0.0.1:8001/docs
```

### Health Check

```text
http://127.0.0.1:8001/health
```

---

# 📡 API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Service status |
| GET | `/health` | Health/configuration check |
| POST | `/api/content/generate` | Generate campaign content |
| POST | `/api/content/generate-video` | Generate local MP4 |
| GET | `/outputs/{filename}` | Serve generated files |

---

# 🏠 GET /

Example response:

```json
{
  "service": "CORTEX Content Agent",
  "status": "running",
  "docs": "/docs"
}
```

---

# ❤️ GET /health

Example response:

```json
{
  "status": "ok",
  "gemini_configured": true,
  "video_provider": "Local MP4 Generator",
  "mock_mode": false
}
```

---

# 🧠 POST /api/content/generate

This is the **main Content Agent endpoint**.

It accepts research insight and campaign requirements and sends them to Gemini.

## Request

```json
{
  "research_insight": {
    "topic": "Insurance awareness among young professionals",
    "key_finding": "Young professionals often delay insurance decisions.",
    "opportunity": "Create an educational campaign around early financial planning.",
    "source": "Research Agent"
  },
  "product": "Term Insurance",
  "target_audience": "Young Professionals",
  "campaign_goal": "Lead Generation",
  "platforms": [
    "LinkedIn",
    "Instagram",
    "X"
  ],
  "language": "English",
  "tone": "Professional but human",
  "content_format": "Campaign"
}
```

## Output

The generated response can contain:

```text
Campaign
├── Title
├── Objective
└── Audience

Messaging
├── Core Message
├── Angle
└── Hook

Platform Content
├── LinkedIn
├── Instagram
└── X

A/B Variants
├── Variant A
├── Variant B
└── Variant C

Visual Concept
├── Concept
├── Composition
├── Mood
└── Headline
```

### Example Response

```json
{
  "success": true,
  "agent": "content",
  "data": {
    "campaign": {
      "title": "Campaign Title",
      "objective": "Campaign objective",
      "audience": "Young Professionals"
    },
    "messaging": {
      "core_message": "Core campaign message",
      "angle": "Campaign angle",
      "hook": "Campaign hook"
    },
    "linkedin": {},
    "instagram": {},
    "x": {},
    "ab_variants": [],
    "visual": {}
  }
}
```

---

# 🎬 POST /api/content/generate-video

This endpoint provides an optional local MP4 capability for the hackathon demo.

It does not call Hugging Face, Veo, or another paid video-generation API.

## Request

```json
{
  "prompt": "A cinematic vertical social media advertisement about financial protection for young professionals.",
  "negative_prompt": "",
  "model": "",
  "provider": "",
  "seed": 42,
  "num_frames": 81,
  "num_inference_steps": 20
}
```

The API accepts these compatibility fields so existing frontend payloads can continue to work, but the local generator currently only needs the prompt.

## Pipeline

```text
Video Prompt
     ↓
Local Scene Generation
     ↓
Pillow
     ↓
Scene Images
     ↓
MoviePy
     ↓
FFmpeg
     ↓
Vertical MP4
```

Generated files are stored in:

```text
outputs/
```

Example:

```text
outputs/cortex_generated_video.mp4
```

The video is served through:

```text
http://127.0.0.1:8001/outputs/cortex_generated_video.mp4
```

Current format:

```text
Resolution: 720 × 1280
Aspect Ratio: 9:16
Format: MP4
Codec: H.264
Frame Rate: 24 FPS
```

> The local video generator is a programmatic scene-card/video assembly system, not an AI text-to-video model.

---

# 🔌 Frontend Integration

The backend is framework-independent and can be connected to React, Next.js, HTML/JavaScript, Flutter, Vue, or any REST client.

### Generate content

```javascript
const response = await fetch(
  "http://localhost:8001/api/content/generate",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  }
);

const result = await response.json();
```

### Generate local video

```javascript
const response = await fetch(
  "http://localhost:8001/api/content/generate-video",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(videoPayload)
  }
);

const result = await response.json();
```

Example video response:

```json
{
  "success": true,
  "agent": "content",
  "provider": "Local MP4 Generator",
  "video_url": "/outputs/cortex_generated_video.mp4",
  "filename": "cortex_generated_video.mp4"
}
```

---

# 🤝 CORTEX Agent Integration

## Research → Content

```text
Research Agent
      ↓
Research Insight
      ↓
POST /api/content/generate
```

## Content → Compliance

```text
Content Agent
      ↓
Generated Campaign
      ↓
Compliance Agent
```

## Compliance → Human Approval

```text
Compliance Agent
      ↓
Compliance Result
      ↓
Human Approval Dashboard
```

---

# 🧪 Mock Mode

For frontend development without Gemini:

```env
MOCK_MODE=true
```

For real Gemini generation:

```env
MOCK_MODE=false
```

---

# 🧪 Recommended Testing Order

Open Swagger:

```text
http://127.0.0.1:8001/docs
```

Then test:

```text
1. GET /
       ↓
2. GET /health
       ↓
3. POST /api/content/generate
       ↓
4. POST /api/content/generate-video
```

---

# 🐛 Troubleshooting

## Gemini API Error

Check that `.env` contains a valid key:

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Restart the server after changing `.env`.

## Server Does Not Start

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then:

```powershell
uvicorn app.main:app --reload --port 8001
```

## Port 8001 Already in Use

Use another port:

```powershell
uvicorn app.main:app --reload --port 8002
```

## Video Generation Error

Install the local video dependencies:

```powershell
pip install moviepy pillow imageio-ffmpeg
```

---

# 🔒 Security Checklist

Before pushing to GitHub:

```text
[ ] .env is in .gitignore
[ ] Gemini API key is not in source code
[ ] Gemini API key is not in README
[ ] API key is not in frontend code
[ ] API key is not visible in screenshots
[ ] Generated secrets are not committed
```

---

# 📊 Current Implementation Status

| Component | Status |
|---|---|
| FastAPI Backend | ✅ Implemented |
| Gemini API Integration | ✅ Implemented |
| Campaign Intelligence | ✅ Implemented |
| Platform Content | ✅ Implemented |
| LinkedIn Content | ✅ Implemented |
| Instagram Content | ✅ Implemented |
| X Content | ✅ Implemented |
| A/B Variants | ✅ Implemented |
| Visual Concept | ✅ Implemented |
| Research Insight Input | ✅ Implemented |
| Mock Mode | ✅ Available |
| Swagger Documentation | ✅ Implemented |
| CORS | ✅ Implemented |
| Static MP4 Serving | ✅ Implemented |
| Local MP4 Generator | ✅ Implemented |
| Hugging Face | ❌ Removed |
| Hugging Face Token | ❌ Not Required |
| Gemini Veo | ❌ Not Required |
| Paid Video API | ❌ Not Required |
| Compliance Agent | 🔗 Downstream Integration |
| Human Approval | 🔗 Downstream Integration |

---

# 🎯 Content Agent Responsibility

The primary responsibility of this project is:

> **Transform research-driven insights and campaign requirements into structured, platform-native marketing content using Google Gemini.**

### Input

```text
Research Insight
Product
Target Audience
Campaign Goal
Platforms
Language
Tone
Content Format
```

### Processing

```text
Research Analysis
       ↓
Campaign Strategy
       ↓
Messaging
       ↓
Platform Adaptation
       ↓
A/B Variants
       ↓
Visual Direction
```

### Output

```text
Campaign Strategy
Platform Content
A/B Variants
Visual Concept
```

---

# 🚀 Future Enhancements

Potential future improvements include:

- AI-generated image assets
- Advanced AI video generation
- Dynamic Reel storyboards
- Platform-specific character limits
- Brand voice memory
- Brand guideline enforcement
- Automated compliance pre-checks
- Content performance feedback loops
- Campaign analytics
- Content version history
- Human feedback learning
- Multi-campaign management
- Scheduled content generation
- Database-backed campaign storage

---

# 📌 Important Notes

### Gemini

Google Gemini powers the primary AI content-generation workflow.

### Video

The current video implementation is local and does not require Hugging Face or Veo.

### Content Agent

The Content Agent is the main component of this repository. The local video generator is an optional supporting capability for the hackathon demonstration.

### API

The backend exposes REST endpoints so other CORTEX agents and frontend applications can communicate with the Content Agent independently.

---

# 🏁 Quick Start

```powershell
cd D:\cortex_content_agent_backend

python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

copy .env.example .env

code .env
```

Add your key:

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Run:

```powershell
uvicorn app.main:app --reload --port 8001
```

Open:

```text
http://127.0.0.1:8001/docs
```

---

# 👨‍💻 Project Role

**CORTEX Content Agent**

The Content Agent is responsible for:

```text
Research
   ↓
Campaign Intelligence
   ↓
Content Generation
   ↓
A/B Variants
   ↓
Visual Direction
```

and provides structured outputs for downstream **Compliance** and **Human Approval** workflows.

---

# 📄 License

This project is developed as part of the **CORTEX Hackathon Project**.

---

# CORTEX

> **Research-driven. AI-powered. Platform-native. Human-approved.**
