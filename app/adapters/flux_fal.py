"""
FLUX models via fal.ai — handles generation (FLUX.2 Pro), editing (Kontext Pro), inpainting (Fill Pro).
fal.ai is 30-50% cheaper than calling BFL directly.
"""

import os
import time
from typing import Optional

import fal_client

from app.adapters.base import BaseAdapter, AdapterResult
from app.config import get_settings


class FluxFalAdapter(BaseAdapter):
    """Adapter for FLUX models hosted on fal.ai."""

    def __init__(self):
        # fal-client reads FAL_KEY from env — ensure it's set from our config
        settings = get_settings()
        if settings.fal_key:
            os.environ["FAL_KEY"] = settings.fal_key

    # fal.ai model endpoints
    MODEL_MAP = {
        "flux-2-pro": "fal-ai/flux-pro/v1.1",
        "flux-kontext-pro": "fal-ai/flux-pro/kontext",
        "flux-fill-pro": "fal-ai/flux-pro/v1/fill",
    }

    COST_MAP = {
        "flux-2-pro": 0.055,
        "flux-kontext-pro": 0.10,
        "flux-fill-pro": 0.05,
    }

    async def generate(self, prompt: str, model_id: str = "flux-2-pro", **kwargs) -> AdapterResult:
        endpoint = self.MODEL_MAP[model_id]
        start = time.time()

        result = await fal_client.run_async(
            endpoint,
            arguments={
                "prompt": prompt,
                "image_size": kwargs.get("image_size", "landscape_16_9"),
                "num_images": 1,
                "safety_tolerance": "5",
            },
        )

        latency_ms = int((time.time() - start) * 1000)
        image_url = result["images"][0]["url"]

        return AdapterResult(
            image_url=image_url,
            cost=self.COST_MAP[model_id],
            latency_ms=latency_ms,
            model_id=model_id,
            provider="fal",
        )

    async def edit(
        self,
        image_url: str,
        instruction: str,
        mask_url: Optional[str] = None,
        model_id: str = "flux-kontext-pro",
        **kwargs,
    ) -> AdapterResult:
        start = time.time()

        if model_id == "flux-fill-pro" and mask_url:
            # Mask-based inpainting
            endpoint = self.MODEL_MAP["flux-fill-pro"]
            result = await fal_client.run_async(
                endpoint,
                arguments={
                    "image_url": image_url,
                    "mask_url": mask_url,
                    "prompt": instruction,
                },
            )
        else:
            # Instruction-based editing (Kontext)
            endpoint = self.MODEL_MAP["flux-kontext-pro"]
            result = await fal_client.run_async(
                endpoint,
                arguments={
                    "prompt": instruction,
                    "image_url": image_url,
                },
            )

        latency_ms = int((time.time() - start) * 1000)
        image_url = result["images"][0]["url"]

        return AdapterResult(
            image_url=image_url,
            cost=self.COST_MAP[model_id],
            latency_ms=latency_ms,
            model_id=model_id,
            provider="fal",
        )
