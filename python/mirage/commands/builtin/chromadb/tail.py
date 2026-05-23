from collections.abc import AsyncIterator

from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.generic.tail import tail as generic_tail
from mirage.commands.builtin.utils.stream import _resolve_source
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.read import read_stream
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("tail", resource="chromadb", spec=SPECS["tail"])
async def tail(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    stdin: AsyncIterator[bytes] | bytes | None = None,
    n: int | str = 10,
    args_n: int | str | None = None,
    c: str | None = None,
    index: IndexCacheStore = None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    limit = int(args_n if args_n is not None else n)
    bytes_limit = int(c) if c is not None else None
    if paths:
        paths = await resolve_glob(accessor, paths, index)
        source: AsyncIterator[bytes] | bytes = read_stream(accessor, paths[0],
                                                           index)
    else:
        source = _resolve_source(stdin, "tail: missing operand")
    return generic_tail(source, n=limit, c=bytes_limit), IOResult()
