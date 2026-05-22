from collections.abc import AsyncIterator

from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.generic.grep import grep as generic_grep
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.grep import grep_paths
from mirage.core.chromadb.read import read_bytes
from mirage.core.chromadb.readdir import readdir
from mirage.core.chromadb.stat import stat
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("grep", resource="chromadb", spec=SPECS["grep"])
async def grep(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    stdin: AsyncIterator[bytes] | bytes | None = None,
    r: bool = False,
    R: bool = False,
    i: bool = False,
    I: bool = False,
    v: bool = False,
    n: bool = False,
    c: bool = False,
    args_l: bool = False,
    w: bool = False,
    F: bool = False,
    E: bool = False,
    o: bool = False,
    m: str | None = None,
    q: bool = False,
    H: bool = False,
    args_h: bool = False,
    A: str | None = None,
    B: str | None = None,
    C: str | None = None,
    e: str | None = None,
    prefix: str = "",
    index: IndexCacheStore = None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    pattern = _pattern(texts, e)
    max_count = int(m) if m is not None else None
    recursive = r or R
    if paths and recursive and not v and not A and not B and not C:
        result = await grep_paths(
            accessor,
            paths,
            pattern,
            index,
            recursive=True,
            ignore_case=i,
            line_numbers=n,
            count_only=c,
            files_only=args_l,
            whole_word=w,
            fixed_string=F,
            only_matching=o,
            max_count=max_count,
        )
        exit_code = 0 if result.lines else 1
        stdout = b"" if q or not result.lines else "\n".join(
            result.lines).encode()
        if q:
            return b"", IOResult(exit_code=exit_code,
                                  reads=result.reads,
                                  cache=result.cache)
        return stdout, IOResult(exit_code=exit_code,
                                reads=result.reads,
                                cache=result.cache)

    after_ctx = int(A) if A is not None else (int(C) if C is not None else 0)
    before_ctx = int(B) if B is not None else (int(C) if C is not None else 0)
    return await generic_grep(
        paths,
        pattern=pattern,
        readdir=readdir,
        stat=stat,
        read_bytes=read_bytes,
        read_stream=None,
        accessor=accessor,
        stdin=stdin,
        ignore_case=i,
        invert=v,
        line_numbers=n,
        count_only=c,
        files_only=args_l,
        whole_word=w,
        fixed_string=F,
        only_matching=o,
        quiet=q,
        recursive=recursive,
        max_count=max_count,
        after_context=after_ctx,
        before_context=before_ctx,
        index=index,
    )


def _pattern(texts: tuple[str, ...], e: str | None) -> str:
    if e is not None:
        return e
    if texts:
        return texts[0]
    raise ValueError("grep: usage: grep [flags] pattern [path]")
