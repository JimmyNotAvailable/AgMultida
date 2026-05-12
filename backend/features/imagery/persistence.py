from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PreviewPersistence:
    bucket_name: str = 'imagery-previews'
    _memory: dict[str, str] = field(default_factory=dict)

    async def get_preview_url(self, scene_id: str, mode: str) -> str | None:
        return self._memory.get(self._key(scene_id, mode))

    async def render_and_store(self, scene_id: str, mode: str) -> str:
        url = f'/v1/imagery/preview/{scene_id}?mode={mode}'
        self._memory[self._key(scene_id, mode)] = url
        return url

    async def placeholder(self, zone_id: str, mode: str) -> str:
        return f'/v1/imagery/placeholder/{zone_id}?mode={mode}'

    def _key(self, scene_id: str, mode: str) -> str:
        return f'{self.bucket_name}:{scene_id}:{mode}'
