from collections.abc import AsyncIterator

from mirage.commands.builtin.aggregators import concat_aggregate
from mirage.commands.builtin.utils.stream import _resolve_source
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.read import read_stream
from mirage.io.cachable_iterator import CachableAsyncIterator
from mirage.io.types import ByteSource, IOResult, materialize
from mirage.types import PathSpec


async def _number_lines(source: ByteSource) -> AsyncIterator[bytes]:
    data = await materialize(source)
    lines = data.decode(errors="replace").splitlines()
    for index, line in enumerate(lines, 1):
        yield f"     {index}\t{line}\n".encode()


async def _chain_streams(
        streams: list[AsyncIterator[bytes]]) -> AsyncIterator[bytes]:
    for stream in streams:
        async for chunk in stream:
            yield chunk


@command("cat",
         resource="chromadb",
         spec=SPECS["cat"],
         aggregate=concat_aggregate)
async def cat(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    stdin: AsyncIterator[bytes] | bytes | None = None,
    n: bool = False,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    if not paths:
        source = _resolve_source(stdin, "cat: missing operand")
        if n:
            return _number_lines(source), IOResult()
        return source, IOResult()

    paths = await resolve_glob(accessor, paths, _extra.get("index"))
    streams: list[CachableAsyncIterator] = []
    reads = {}
    cache = []
    for path in paths:
        stream = CachableAsyncIterator(
            read_stream(accessor, path, _extra.get("index")))
        streams.append(stream)
        reads[path.strip_prefix] = stream
        cache.append(path.strip_prefix)
    source: ByteSource = streams[0] if len(streams) == 1 else _chain_streams(
        streams)
    if n:
        return _number_lines(source), IOResult(reads=reads, cache=cache)
    return source, IOResult(reads=reads, cache=cache)
