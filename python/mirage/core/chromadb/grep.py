import asyncio
import re
from dataclasses import dataclass

from mirage.cache.index import IndexCacheStore, IndexEntry
from mirage.commands.builtin.grep_helper import compile_pattern, grep_lines
from mirage.commands.builtin.utils.lines import split_lines
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.path import resolve_path
from mirage.core.chromadb.read import read_bytes
from mirage.types import PathSpec


@dataclass(frozen=True)
class ChromaGrepResult:
    lines: list[str]
    reads: dict[str, bytes]
    cache: list[str]


@dataclass(frozen=True)
class CandidatePage:
    path: PathSpec
    entry: IndexEntry


async def grep_paths(
    accessor,
    paths: list[PathSpec],
    pattern: str,
    index: IndexCacheStore,
    *,
    recursive: bool = False,
    ignore_case: bool = False,
    invert: bool = False,
    line_numbers: bool = False,
    count_only: bool = False,
    files_only: bool = False,
    whole_word: bool = False,
    fixed_string: bool = False,
    only_matching: bool = False,
    max_count: int | None = None,
) -> ChromaGrepResult:
    resolved_paths = await resolve_glob(accessor, paths, index)
    candidates = await candidate_pages(accessor, resolved_paths, index,
                                       recursive)
    raw_hits = _candidate_raw_slugs(candidates)
    if not invert and not count_only:
        raw_hits = await coarse_matching_raw_slugs(
            accessor,
            pattern,
            ignore_case=ignore_case,
            fixed_string=fixed_string,
            whole_word=whole_word,
        )
    compiled = compile_pattern(pattern, ignore_case, fixed_string, whole_word)
    lines: list[str] = []
    reads: dict[str, bytes] = {}
    cache: list[str] = []
    for candidate in candidates:
        raw_slugs = candidate.entry.extra.get("raw_slugs", [])
        if raw_hits.isdisjoint(raw_slugs):
            continue
        data = await read_bytes(accessor, candidate.path, index)
        cache_key = candidate.path.strip_prefix
        reads[cache_key] = data
        cache.append(cache_key)
        file_hits = grep_lines(
            candidate.path.original,
            split_lines(data.decode(errors="replace")),
            compiled,
            invert,
            line_numbers,
            count_only,
            files_only,
            only_matching,
            max_count,
        )
        lines.extend(_format_file_hits(candidate.path.original, file_hits,
                                      count_only, files_only,
                                      len(candidates) > 1 or recursive))
    return ChromaGrepResult(lines, reads, cache)


async def candidate_pages(
    accessor,
    paths: list[PathSpec],
    index: IndexCacheStore,
    recursive: bool,
) -> list[CandidatePage]:
    candidates: list[CandidatePage] = []
    for path in paths:
        resolved = await resolve_path(accessor, path, index)
        if resolved.is_dir:
            if not recursive:
                raise IsADirectoryError(path.original)
            candidates.extend(
                await _walk_candidate_pages(accessor, resolved.virtual_key,
                                            resolved.mount_prefix, index))
            continue
        if resolved.entry is not None:
            candidates.append(CandidatePage(path, resolved.entry))
    return sorted(candidates, key=lambda candidate: candidate.path.original)


async def coarse_matching_raw_slugs(
    accessor,
    pattern: str,
    *,
    ignore_case: bool = False,
    fixed_string: bool = False,
    whole_word: bool = False,
) -> set[str]:
    raw_slugs: set[str] = set()
    offset = 0
    where_document = _where_document(pattern, ignore_case, fixed_string,
                                     whole_word)
    while True:
        result = await asyncio.to_thread(
            accessor.collection.get,
            include=["metadatas"],
            where_document=where_document,
            limit=accessor.config.metadata_batch_size,
            offset=offset,
        )
        metadatas = result.get("metadatas") or []
        if not metadatas:
            break
        for metadata in metadatas:
            if not isinstance(metadata, dict):
                continue
            raw_slug = metadata.get(accessor.config.slug_field)
            if raw_slug is not None and str(raw_slug):
                raw_slugs.add(str(raw_slug))
        offset += len(metadatas)
    return raw_slugs


async def _walk_candidate_pages(
    accessor,
    virtual_key: str,
    mount_prefix: str,
    index: IndexCacheStore,
) -> list[CandidatePage]:
    listing = await index.list_dir(virtual_key)
    if listing.entries is None:
        return []
    candidates: list[CandidatePage] = []
    for child in listing.entries:
        child_spec = PathSpec(original=child,
                              directory=_parent(child),
                              prefix=mount_prefix)
        resolved = await resolve_path(accessor, child_spec, index)
        if resolved.is_dir:
            candidates.extend(
                await _walk_candidate_pages(accessor, resolved.virtual_key,
                                            mount_prefix, index))
        elif resolved.entry is not None:
            candidates.append(CandidatePage(child_spec, resolved.entry))
    return candidates


def _candidate_raw_slugs(candidates: list[CandidatePage]) -> set[str]:
    raw_slugs: set[str] = set()
    for candidate in candidates:
        raw_slugs.update(candidate.entry.extra.get("raw_slugs", []))
    return raw_slugs


def _format_file_hits(
    path: str,
    hits: list[str],
    count_only: bool,
    files_only: bool,
    prefix_path: bool,
) -> list[str]:
    if count_only:
        return [f"{path}:{hits[0]}"] if prefix_path and hits else hits
    if files_only:
        return hits
    if prefix_path:
        return [f"{path}:{hit}" for hit in hits]
    return hits


def _where_document(
    pattern: str,
    ignore_case: bool,
    fixed_string: bool,
    whole_word: bool,
) -> dict[str, str]:
    if (fixed_string or _is_plain_pattern(pattern)) and not ignore_case and not whole_word:
        return {"$contains": pattern}
    expr = re.escape(pattern) if fixed_string else pattern
    if whole_word:
        expr = r"\b" + expr + r"\b"
    if ignore_case:
        expr = "(?i)" + expr
    return {"$regex": expr}


def _is_plain_pattern(pattern: str) -> bool:
    return re.fullmatch(r"[\w\s\-_.]+", pattern) is not None


def _parent(path: str) -> str:
    parent = path.rstrip("/").rsplit("/", 1)[0]
    return parent or "/"
