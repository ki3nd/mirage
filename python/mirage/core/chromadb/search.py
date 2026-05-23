import asyncio

from mirage.cache.index import IndexCacheStore
from mirage.core.chromadb.path import resolve_path
from mirage.core.chromadb.read import _where, document_to_text
from mirage.core.chromadb.walk import walk
from mirage.types import PathSpec

METHODS = {"semantic", "keyword", "hybrid"}


async def search_segments(
    accessor,
    query: str,
    paths: list[PathSpec],
    index: IndexCacheStore,
    method: str = "semantic",
    top_k: int = 10,
    threshold: float = 0.0,
) -> bytes:
    search_method = validate_args(query, method, top_k, threshold)
    raw_slugs = await target_raw_slugs(accessor, paths, index)
    if paths and not raw_slugs:
        return b""
    if search_method == "semantic":
        return records_to_bytes(await semantic_search(accessor, query, raw_slugs,
                                                     top_k, threshold))
    if search_method == "keyword":
        return records_to_bytes(await keyword_search(accessor, query, raw_slugs,
                                                    top_k))
    semantic = await semantic_search(accessor, query, raw_slugs, top_k,
                                     threshold)
    keyword = await keyword_search(accessor, query, raw_slugs, top_k)
    return records_to_bytes(merge_results(semantic, keyword, top_k))


def validate_args(query: str, method: str, top_k: int,
                  threshold: float) -> str:
    if not query:
        raise ValueError("search: query is required")
    if len(query) > 250:
        raise ValueError("search: query cannot exceed 250 characters")
    if top_k <= 0:
        raise ValueError("search: top-k must be positive")
    if threshold < 0:
        raise ValueError("search: threshold must be non-negative")
    if method not in METHODS:
        raise ValueError(
            "search: method must be one of semantic, keyword, hybrid")
    return method


async def target_raw_slugs(
    accessor,
    paths: list[PathSpec],
    index: IndexCacheStore,
) -> list[str]:
    raw_slugs: list[str] = []
    seen: set[str] = set()
    for path in paths:
        resolved = await resolve_path(accessor, path, index)
        if resolved.entry is not None and not resolved.is_dir:
            _extend_raw_slugs(raw_slugs, seen,
                              resolved.entry.extra.get("raw_slugs", []))
            continue
        if resolved.is_dir:
            children = await walk(accessor,
                                  path,
                                  index,
                                  include_root=False,
                                  strip_prefix=False)
            for child in children:
                child_spec = PathSpec(original=child,
                                      directory=child,
                                      prefix=path.prefix)
                child_resolved = await resolve_path(accessor, child_spec, index)
                if (child_resolved.entry is not None
                        and not child_resolved.is_dir):
                    _extend_raw_slugs(raw_slugs, seen,
                                      child_resolved.entry.extra.get(
                                          "raw_slugs", []))
    return raw_slugs


def _extend_raw_slugs(target: list[str], seen: set[str],
                      values: list[str]) -> None:
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        target.append(value)


async def semantic_search(
    accessor,
    query: str,
    raw_slugs: list[str],
    top_k: int,
    threshold: float,
) -> list[str]:
    kwargs = {
        "query_texts": [query],
        "n_results": min(top_k, 100),
        "include": ["documents", "distances"],
    }
    if raw_slugs:
        kwargs["where"] = _where(accessor.config.slug_field, raw_slugs)
    result = await asyncio.to_thread(accessor.collection.query, **kwargs)
    documents = _first_query_list(result.get("documents"))
    distances = _first_query_list(result.get("distances"))
    matches: list[str] = []
    for index, document in enumerate(documents):
        distance = None
        if index < len(distances):
            distance = distances[index]
        if threshold > 0 and distance is not None:
            try:
                if float(distance) > threshold:
                    continue
            except (TypeError, ValueError):
                continue
        matches.append(document_to_text(document))
    return matches


async def keyword_search(
    accessor,
    query: str,
    raw_slugs: list[str],
    top_k: int,
) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()
    offset = 0
    where = _where(accessor.config.slug_field, raw_slugs) if raw_slugs else None
    while len(matches) < top_k:
        result = await asyncio.to_thread(
            accessor.collection.get,
            include=["documents", "metadatas"],
            where=where,
            where_document={"$contains": query},
            limit=min(accessor.config.chunk_batch_size, top_k),
            offset=offset,
        )
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        count = max(len(documents), len(metadatas))
        if count == 0:
            break
        rows = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            rows.append((metadata, document))
        rows.sort(key=lambda row: _metadata_sort_key(accessor, row[0]))
        for _metadata, document in rows:
            text = document_to_text(document)
            if text in seen:
                continue
            seen.add(text)
            matches.append(text)
            if len(matches) >= top_k:
                break
        offset += count
    return matches


def merge_results(primary: list[str], secondary: list[str],
                  top_k: int) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for text in primary + secondary:
        if text in seen:
            continue
        seen.add(text)
        merged.append(text)
        if len(merged) >= top_k:
            break
    return merged


def _first_query_list(value: object) -> list:
    if not isinstance(value, list) or not value:
        return []
    first = value[0]
    if isinstance(first, list):
        return first
    return value


def _metadata_sort_key(accessor, metadata: object) -> tuple[str, int]:
    if not isinstance(metadata, dict):
        return ("", 0)
    slug = str(metadata.get(accessor.config.slug_field) or "")
    chunk_index = metadata.get(accessor.config.chunk_index_field)
    try:
        order = int(chunk_index)
    except (TypeError, ValueError):
        order = 0
    return (slug, order)


def records_to_bytes(records: list[str]) -> bytes:
    return "\n".join(records).encode()
