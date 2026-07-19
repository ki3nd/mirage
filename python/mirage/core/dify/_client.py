import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from mirage.accessor.dify import DifyAccessor

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4
MAX_RETRY_DELAY = 30.0


async def dify_request(accessor: DifyAccessor, method: str, endpoint: str,
                       **request_kwargs: Any) -> dict[str, Any]:
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = await accessor.request(method, endpoint,
                                              **request_kwargs)
        except httpx.TransportError:
            if attempt + 1 >= MAX_ATTEMPTS:
                raise
            logger.warning("Dify transport error requesting %s", endpoint)
            await asyncio.sleep(2**attempt)
            continue
        retryable = (response.status_code == 429
                     or 500 <= response.status_code < 600)
        if retryable and attempt + 1 < MAX_ATTEMPTS:
            logger.warning("Dify request to %s returned HTTP %s", endpoint,
                           response.status_code)
            await asyncio.sleep(retry_delay(response, attempt))
            continue
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Dify response must be a JSON object")
        return payload
    raise RuntimeError(f"Dify request failed: {endpoint}")


def retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return min(MAX_RETRY_DELAY, max(0.0, float(retry_after)))
        except ValueError:
            logger.debug("Ignoring invalid Dify Retry-After value %r",
                         retry_after)
    return min(MAX_RETRY_DELAY, float(2**attempt))


async def dify_get(accessor: DifyAccessor,
                   endpoint: str,
                   params: dict[str, Any] | None = None) -> dict[str, Any]:
    return await dify_request(accessor, "GET", endpoint, params=params)


async def dify_post(accessor: DifyAccessor, endpoint: str,
                    body: dict[str, Any]) -> dict[str, Any]:
    return await dify_request(accessor, "POST", endpoint, json=body)


async def list_all_documents(accessor: DifyAccessor) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = await dify_get(
            accessor,
            f"/datasets/{accessor.config.dataset_id}/documents",
            {
                "page": page,
                "limit": 100
            },
        )
        for document in payload.get("data") or []:
            if is_visible_document(document):
                documents.append(document)
        if not payload.get("has_more"):
            return documents
        page += 1


async def get_document_detail(accessor: DifyAccessor,
                              document_id: str) -> dict[str, Any]:
    return await dify_get(
        accessor,
        f"/datasets/{accessor.config.dataset_id}/documents/{document_id}")


async def get_document_segments(accessor: DifyAccessor,
                                document_id: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    async for page in iter_segment_pages(accessor, document_id):
        segments.extend(page)
    return segments


async def iter_segment_pages(
    accessor: DifyAccessor,
    document_id: str,
) -> AsyncIterator[list[dict[str, Any]]]:
    page = 1
    while True:
        payload = await dify_get(
            accessor,
            (f"/datasets/{accessor.config.dataset_id}/documents/"
             f"{document_id}/segments"),
            {
                "page": page,
                "limit": 100,
                "status": "completed",
                "enabled": "true",
            },
        )
        yield payload.get("data") or []
        if not payload.get("has_more"):
            return
        page += 1


def is_visible_document(document: dict[str, Any]) -> bool:
    return (document.get("enabled") is True
            and document.get("indexing_status") == "completed"
            and document.get("archived") is False)
