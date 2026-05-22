import re

from mirage.cache.index import IndexCacheStore
from mirage.core.dify.read import read_bytes
from mirage.types import PathSpec


async def grep_bytes(
        accessor,
        paths: list[PathSpec],
        pattern: str,
        index: IndexCacheStore,
        ignore_case: bool = False) -> tuple[bytes, dict[str, bytes]]:
    flags = re.IGNORECASE if ignore_case else 0
    regex = re.compile(pattern, flags)
    lines: list[str] = []
    reads: dict[str, bytes] = {}
    for path in paths:
        data = await read_bytes(accessor, path, index)
        reads[path.original] = data
        for line_number, line in enumerate(
                data.decode(errors="replace").splitlines(), 1):
            if regex.search(line):
                lines.append(f"{path.original}:{line_number}:{line}")
    return "\n".join(lines).encode(), reads
