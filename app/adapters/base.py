from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AdapterResult:
    image_url: str
    cost: float
    latency_ms: int
    model_id: str
    provider: str
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseAdapter(ABC):
    """Base class for all image model adapters."""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> AdapterResult:
        """Generate an image from a text prompt."""
        ...

    @abstractmethod
    async def edit(
        self,
        image_url: str,
        instruction: str,
        mask_url: Optional[str] = None,
        **kwargs,
    ) -> AdapterResult:
        """Edit an existing image."""
        ...
