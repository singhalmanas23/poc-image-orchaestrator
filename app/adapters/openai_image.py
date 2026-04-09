"""
GPT Image 1 (OpenAI) adapter — strong photorealism, native alpha channel support.
gpt-image-1 always returns base64 PNG; we persist it to local storage and serve via /generated.
"""

import base64
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx

from app.adapters.base import BaseAdapter, AdapterResult
from app.config import get_settings


class OpenAIImageAdapter(BaseAdapter):
    BASE_URL = "https://api.openai.com/v1"

    def _get_headers(self) -> dict:
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

    def _save_b64_png(self, b64: str) -> str:
        """Decode base64 PNG and persist to image_storage_dir, return public URL."""
        settings = get_settings()
        out_dir = Path(settings.image_storage_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"img_{uuid.uuid4().hex[:12]}.png"
        path = out_dir / filename
        path.write_bytes(base64.b64decode(b64))

        # Served by FastAPI static mount in app/main.py
        return f"{settings.api_base_url.rstrip('/')}/generated/{filename}"

    async def generate(self, prompt: str, **kwargs) -> AdapterResult:
        start = time.time()

        quality = kwargs.get("quality", "medium")
        size = kwargs.get("size", "1024x1024")
        transparent = bool(kwargs.get("transparent_background", False))

        body: dict = {
            "model": "gpt-image-1",
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality,
        }
        if transparent:
            body["background"] = "transparent"
            body["output_format"] = "png"

        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.BASE_URL}/images/generations",
                headers=self._get_headers(),
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        # gpt-image-1 always returns b64_json
        b64 = data["data"][0]["b64_json"]
        image_url = self._save_b64_png(b64)

        latency_ms = int((time.time() - start) * 1000)
        cost_map = {"low": 0.011, "medium": 0.042, "high": 0.167}

        return AdapterResult(
            image_url=image_url,
            cost=cost_map.get(quality, 0.042),
            latency_ms=latency_ms,
            model_id="gpt-image-1.5",
            provider="openai",
            metadata={"transparent_background": transparent},
        )

    async def edit(
        self,
        image_url: str,
        instruction: str,
        mask_url: Optional[str] = None,
        **kwargs,
    ) -> AdapterResult:
        # gpt-image-1 editing tends to regenerate the whole image — router prefers FLUX Kontext.
        # Kept for completeness; not currently routed.
        raise NotImplementedError(
            "gpt-image-1 editing is not wired — router prefers FLUX Kontext for instruction edits"
        )
