from collections.abc import AsyncIterator

from mirage.commands.builtin.utils.stream import _read_stdin_async
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.read import read_stream
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


async def _head_bytes(data: bytes, lines: int,
                      bytes_mode: int | None) -> AsyncIterator[bytes]:
    if bytes_mode is not None:
        yield data[:bytes_mode]
        return
    parts = data.split(b"\n", lines)
    yield b"\n".join(parts[:lines])


async def _read_stream_bytes(source: AsyncIterator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in source])


@command("head", resource="chromadb", spec=SPECS["head"])
async def head(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    stdin: AsyncIterator[bytes] | bytes | None = None,
    n: str | None = None,
    c: str | None = None,
    index=None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    lines = int(n) if n is not None else 10
    bytes_mode = int(c) if c is not None else None
    if paths:
        paths = await resolve_glob(accessor, paths, index)
        data = await _read_stream_bytes(read_stream(accessor, paths[0], index))
        return _head_bytes(data, lines, bytes_mode), IOResult()
    raw = await _read_stdin_async(stdin)
    if raw is None:
        raise ValueError("head: missing operand")
    return _head_bytes(raw, lines, bytes_mode), IOResult()
