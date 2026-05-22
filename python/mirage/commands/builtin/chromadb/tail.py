from collections.abc import AsyncIterator

from mirage.commands.builtin.utils.stream import _read_stdin_async
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.read import read_bytes
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


async def _tail_bytes(data: bytes, lines: int,
                      bytes_mode: int | None) -> AsyncIterator[bytes]:
    if bytes_mode is not None:
        yield data[-bytes_mode:] if bytes_mode else b""
        return
    trailing_newline = data.endswith(b"\n")
    parts = data.split(b"\n")
    if trailing_newline and parts and parts[-1] == b"":
        parts = parts[:-1]
    result = b"\n".join(parts[-lines:])
    if trailing_newline:
        result += b"\n"
    yield result


@command("tail", resource="chromadb", spec=SPECS["tail"])
async def tail(
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
        data = await read_bytes(accessor, paths[0], index)
        return _tail_bytes(data, lines, bytes_mode), IOResult()
    raw = await _read_stdin_async(stdin)
    if raw is None:
        raise ValueError("tail: missing operand")
    return _tail_bytes(raw, lines, bytes_mode), IOResult()
