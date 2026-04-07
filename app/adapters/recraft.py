"""
Recraft V4 adapter — best for vector/SVG output, logos, design assets.
Only model that generates real SVG vector graphics.
"""

import time
from typing import Optional

import httpx

from app.adapters.base import BaseAdapter, AdapterResult
from app.config import get_settings


class RecraftAdapter(BaseAdapter):
    BASE_URL = "https://external.api.recraft.ai/v1"

    def _get_headers(self) -> dict:
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.recraft_api_key}",
            "Content-Type": "application/json",
        }

    async def generate(self, prompt: str, **kwargs) -> AdapterResult:
        start = time.time()

        # Determine if SVG or raster
        response_format = kwargs.get("response_format", "url")
        style = kwargs.get("style", "realistic_image")

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.BASE_URL}/images/generations",
                headers=self._get_headers(),
                json={
                    "prompt": prompt,
                    "style": style,
                    "size": kwargs.get("size", "1024x1024"),
                    "response_format": response_format,
                },
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = int((time.time() - start) * 1000)
        image_url = data["data"][0]["url"]

        return AdapterResult(
            image_url=image_url,
            cost=0.04 if style != "vector_illustration" else 0.08,
            latency_ms=latency_ms,
            model_id="recraft-v4",
            provider="recraft",
        )

    async def edit(
        self,
        image_url: str,
        instruction: str,
        mask_url: Optional[str] = None,
        **kwargs,
    ) -> AdapterResult:
        raise NotImplementedError("Recraft V4 does not support image editing")
