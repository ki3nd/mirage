import asyncio
from typing import Any

import httpx

from mirage.accessor.base import Accessor
from mirage.resource.dify.config import DifyConfig

MAX_CONCURRENT_REQUESTS = 10
POOL_MAX_CONNECTIONS = 20
POOL_MAX_KEEPALIVE = 10
POOL_KEEPALIVE_EXPIRY = 30.0
REQUEST_TIMEOUT = 30.0


class DifyAccessor(Accessor):

    def __init__(self, config: DifyConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._request_limit = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                timeout=REQUEST_TIMEOUT,
                limits=httpx.Limits(
                    max_connections=POOL_MAX_CONNECTIONS,
                    max_keepalive_connections=POOL_MAX_KEEPALIVE,
                    keepalive_expiry=POOL_KEEPALIVE_EXPIRY,
                ),
            )
        return self._client

    async def request(self, method: str, endpoint: str,
                      **kwargs: Any) -> httpx.Response:
        async with self._request_limit:
            return await self.get_client().request(method, endpoint, **kwargs)

    async def close(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None
