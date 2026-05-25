import asyncio
import errno
from collections.abc import AsyncIterator
from dataclasses import dataclass

from mirage.cache.index import IndexCacheStore
from mirage.core.chromadb.path import resolve_path
from mirage.types import PathSpec


@dataclass(frozen=True)
class ChromaChunk:
    order: int
    document: object


async def read_bytes(accessor, path: PathSpec,
                     index: IndexCacheStore) -> bytes:
    resolved = await resolve_path(accessor, path, index)
    if resolved.is_dir:
        raise IsADirectoryError(errno.EISDIR, "Is a directory", path.original)
    chunks = await fetch_chunks(accessor, resolved.entry.extra["raw_slugs"])
    return chunks_to_bytes(chunks)


async def read_stream(accessor, path: PathSpec,
                      index: IndexCacheStore) -> AsyncIterator[bytes]:
    resolved = await resolve_path(accessor, path, index)
    if resolved.is_dir:
        raise IsADirectoryError(errno.EISDIR, "Is a directory", path.original)
    chunks = await fetch_chunks(accessor, resolved.entry.extra["raw_slugs"])
    for i, chunk in enumerate(chunks):
        if i:
            yield b"\n"
        yield document_to_text(chunk.document).encode()


async def fetch_chunks(accessor, raw_slugs: list[str]) -> list[ChromaChunk]:
    chunks: list[ChromaChunk] = []
    offset = 0
    while True:
        result = await asyncio.to_thread(
            accessor.collection.get,
            include=["documents", "metadatas"],
            where=_where(accessor.config.slug_field, raw_slugs),
            limit=accessor.config.chunk_batch_size,
            offset=offset,
        )
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        count = max(len(documents), len(metadatas))
        if count == 0:
            break
        for item_index in range(count):
            document = documents[item_index] if item_index < len(
                documents) else ""
            metadata = metadatas[item_index] if item_index < len(
                metadatas) else {}
            chunks.append(
                ChromaChunk(_chunk_order(accessor, metadata, item_index),
                            document))
        offset += count
    return sorted(chunks, key=lambda chunk: chunk.order)


def chunks_to_bytes(chunks: list[ChromaChunk]) -> bytes:
    return "\n".join(document_to_text(chunk.document)
                     for chunk in chunks).encode()


def document_to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _where(slug_field: str, raw_slugs: list[str]) -> dict:
    if not raw_slugs:
        raise ValueError("raw_slugs must not be empty")
    if len(raw_slugs) == 1:
        return {slug_field: raw_slugs[0]}
    return {slug_field: {"$in": raw_slugs}}


def _chunk_order(accessor, metadata: object, fallback: int) -> int:
    if not isinstance(metadata, dict):
        return fallback
    value = metadata.get(accessor.config.chunk_index_field)
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
