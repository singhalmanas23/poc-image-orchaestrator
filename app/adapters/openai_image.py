"""
GPT Image 1.5 (OpenAI) adapter — strong photorealism, good for generation.
Avoid for local edits (tends to regenerate whole image).
"""

import time
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

    async def generate(self, prompt: str, **kwargs) -> AdapterResult:
        start = time.time()

        quality = kwargs.get("quality", "medium")
        size = kwargs.get("size", "1024x1024")

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.BASE_URL}/images/generations",
                headers=self._get_headers(),
                json={
                    "model": "gpt-image-1",
                    "prompt": prompt,
                    "n": 1,
                    "size": size,
                    "quality": quality,
                },
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = int((time.time() - start) * 1000)
        image_url = data["data"][0]["url"]

        cost_map = {"low": 0.009, "medium": 0.034, "high": 0.167}

        return AdapterResult(
            image_url=image_url,
            cost=cost_map.get(quality, 0.034),
            latency_ms=latency_ms,
            model_id="gpt-image-1.5",
            provider="openai",
        )

    async def edit(
        self,
        image_url: str,
        instruction: str,
        mask_url: Optional[str] = None,
        **kwargs,
    ) -> AdapterResult:
        # GPT Image editing is unreliable for local edits — tends to regenerate whole image.
        # Included for completeness but router should prefer FLUX Kontext.
        start = time.time()

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.BASE_URL}/images/edits",
                headers=self._get_headers(),
                json={
                    "model": "gpt-image-1",
                    "image": image_url,
                    "prompt": instruction,
                },
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = int((time.time() - start) * 1000)

        return AdapterResult(
            image_url=data["data"][0]["url"],
            cost=0.034,
            latency_ms=latency_ms,
            model_id="gpt-image-1.5",
            provider="openai",
        )
