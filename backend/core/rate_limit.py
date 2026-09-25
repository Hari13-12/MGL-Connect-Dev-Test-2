from collections import defaultdict
from time import monotonic


class MemoryRateLimiter:
    def __init__(self):
        self.values = defaultdict(list)

    async def allow(self, key: str, limit: int, window: int) -> bool:
        now = monotonic()
        self.values[key] = [v for v in self.values[key] if now - v < window]
        if len(self.values[key]) >= limit:
            return False
        self.values[key].append(now)
        return True
