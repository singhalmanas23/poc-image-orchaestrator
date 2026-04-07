"""
Ideogram 3.0 adapter — best for text rendering on images (90-95% accuracy).
"""

import time
from typing import Optional

import httpx

from app.adapters.base import BaseAdapter, AdapterResult
from app.config import get_settings


class IdeogramAdapter(BaseAdapter):
    BASE_URL = "https://api.ideogram.ai"

    def _get_headers(self) -> dict:
        settings = get_settings()
        return {
            "Api-Key": settings.ideogram_api_key,
            "Content-Type": "application/json",
        }

    async def generate(self, prompt: str, **kwargs) -> AdapterResult:
        start = time.time()

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.BASE_URL}/generate",
                headers=self._get_headers(),
                json={
                    "image_request": {
                        "prompt": prompt,
                        "model": "V_3",
                        "magic_prompt_option": "AUTO",
                        "aspect_ratio": kwargs.get("aspect_ratio", "ASPECT_1_1"),
                    }
                },
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = int((time.time() - start) * 1000)
        image_url = data["data"][0]["url"]

        return AdapterResult(
            image_url=image_url,
            cost=0.06,
            latency_ms=latency_ms,
            model_id="ideogram-3",
            provider="ideogram",
        )

    async def edit(
        self,
        image_url: str,
        instruction: str,
        mask_url: Optional[str] = None,
        **kwargs,
    ) -> AdapterResult:
        start = time.time()

        async with httpx.AsyncClient(timeout=60) as client:
            payload = {
                "image_request": {
                    "prompt": instruction,
                    "model": "V_3",
                    "image_url": image_url,
                }
            }
            if mask_url:
                payload["image_request"]["mask_url"] = mask_url

            response = await client.post(
                f"{self.BASE_URL}/edit",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = int((time.time() - start) * 1000)
        image_url = data["data"][0]["url"]

        return AdapterResult(
            image_url=image_url,
            cost=0.05,
            latency_ms=latency_ms,
            model_id="ideogram-3-edit",
            provider="ideogram",
        )
