from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.generate import router as generate_router
from app.api.edit import router as edit_router
from app.api.history import router as history_router
from app.config import get_settings

app = FastAPI(
    title="AI Image Orchestrator",
    description="Intelligent orchestration layer that analyzes your prompt and routes to the best AI image model",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve locally-saved images (e.g. gpt-image-1 PNGs with alpha) at /generated/<file>
_settings = get_settings()
_image_dir = Path(_settings.image_storage_dir)
_image_dir.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(_image_dir)), name="generated")

app.include_router(generate_router, prefix="/api", tags=["Generation"])
app.include_router(edit_router, prefix="/api", tags=["Editing"])
app.include_router(history_router, prefix="/api", tags=["History"])


@app.get("/")
async def root():
    return {
        "name": "AI Image Orchestrator",
        "version": "0.1.0",
        "endpoints": {
            "generate": "POST /api/generate",
            "edit": "POST /api/edit",
            "history": "GET /api/history",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
