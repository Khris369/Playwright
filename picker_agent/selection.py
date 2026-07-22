from __future__ import annotations

import asyncio


class SelectionCoordinator:
    """One inspector attachment at a time across picker and preview modes."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.owner: str | None = None

    async def acquire(self, owner: str) -> bool:
        if self._lock.locked():
            return False
        await self._lock.acquire()
        self.owner = owner
        return True

    def release(self, owner: str) -> None:
        if self.owner == owner and self._lock.locked():
            self.owner = None
            self._lock.release()
