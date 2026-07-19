import asyncio
import re
from collections.abc import AsyncIterator

from mirage.accessor.dify import DifyAccessor
from mirage.cache.index import NULL_INDEX, IndexCacheStore
from mirage.core.dify.read import read_stream
from mirage.io.async_line_iterator import AsyncLineIterator
from mirage.types import PathSpec

MAX_WORKERS = 10
GrepResult = tuple[list[str], str, bytes]


async def grep_bytes(
        accessor: DifyAccessor,
        paths: list[PathSpec],
        pattern: str,
        index: IndexCacheStore = NULL_INDEX,
        ignore_case: bool = False) -> tuple[bytes, dict[str, bytes]]:
    flags = re.IGNORECASE if ignore_case else 0
    regex = re.compile(pattern, flags)
    lines: list[str] = []
    reads: dict[str, bytes] = {}
    if not paths:
        return b"", reads
    queue: asyncio.Queue[tuple[int, PathSpec] | None] = asyncio.Queue()
    results: list[GrepResult | None] = [None] * len(paths)
    for position, path in enumerate(paths):
        queue.put_nowait((position, path))
    worker_count = min(MAX_WORKERS, len(paths))
    for _ in range(worker_count):
        queue.put_nowait(None)
    async with asyncio.TaskGroup() as group:
        for _ in range(worker_count):
            group.create_task(
                _grep_worker(accessor, regex, index, queue, results))
    for result in results:
        if result is None:
            raise RuntimeError("Dify grep worker did not return a result")
        path_lines, virtual, data = result
        lines.extend(path_lines)
        reads[virtual] = data
    return "\n".join(lines).encode(), reads


async def _grep_worker(
    accessor: DifyAccessor,
    regex: re.Pattern[str],
    index: IndexCacheStore,
    queue: asyncio.Queue[tuple[int, PathSpec] | None],
    results: list[GrepResult | None],
) -> None:
    while True:
        item = await queue.get()
        try:
            if item is None:
                return
            position, path = item
            results[position] = await _grep_path(accessor, path, regex, index)
        finally:
            queue.task_done()


async def _grep_path(accessor: DifyAccessor, path: PathSpec,
                     regex: re.Pattern[str],
                     index: IndexCacheStore) -> GrepResult:
    lines: list[str] = []
    chunks: list[bytes] = []
    stream = _record_chunks(read_stream(accessor, path, index), chunks)
    async for line_number, raw_line in _enumerate_lines(stream):
        line = raw_line.decode(errors="replace")
        if regex.search(line):
            lines.append(f"{path.virtual}:{line_number}:{line}")
    return lines, path.virtual, b"".join(chunks)


async def _record_chunks(source: AsyncIterator[bytes],
                         chunks: list[bytes]) -> AsyncIterator[bytes]:
    async for chunk in source:
        chunks.append(chunk)
        yield chunk


async def _enumerate_lines(
        source: AsyncIterator[bytes]) -> AsyncIterator[tuple[int, bytes]]:
    line_number = 0
    async for raw_line in AsyncLineIterator(source):
        line_number += 1
        yield line_number, raw_line
