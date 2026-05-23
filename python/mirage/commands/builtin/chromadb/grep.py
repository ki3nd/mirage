from collections.abc import AsyncIterator

from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.grep_context import grep_context_lines
from mirage.commands.builtin.grep_helper import compile_pattern, grep_lines
from mirage.commands.builtin.utils.lines import split_lines
from mirage.commands.builtin.utils.stream import _read_stdin_async
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.grep import candidate_pages, grep_paths
from mirage.core.chromadb.read import read_bytes
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
    if paths and not A and not B and not C:
        result = await grep_paths(
            accessor,
            paths,
            pattern,
            index,
            recursive=recursive,
            ignore_case=i,
            invert=v,
            line_numbers=n,
            count_only=c,
            files_only=args_l,
            whole_word=w,
            fixed_string=F,
            only_matching=o,
            max_count=max_count,
        )
        return _build_result(result.lines,
                             q=q,
                             reads=result.reads,
                             cache=result.cache)
    if paths:
        return await _grep_with_context(accessor,
                                        paths,
                                        pattern,
                                        index,
                                        recursive=recursive,
                                        ignore_case=i,
                                        invert=v,
                                        line_numbers=n,
                                        count_only=c,
                                        files_only=args_l,
                                        whole_word=w,
                                        fixed_string=F,
                                        only_matching=o,
                                        max_count=max_count,
                                        q=q,
                                        after_context=int(A) if A is not None
                                        else (int(C) if C is not None else 0),
                                        before_context=int(B) if B is not None
                                        else (int(C) if C is not None else 0))
    return await _grep_stdin(stdin,
                             pattern,
                             ignore_case=i,
                             invert=v,
                             line_numbers=n,
                             count_only=c,
                             files_only=args_l,
                             whole_word=w,
                             fixed_string=F,
                             only_matching=o,
                             max_count=max_count,
                             q=q,
                             after_context=int(A) if A is not None else
                             (int(C) if C is not None else 0),
                             before_context=int(B) if B is not None else
                             (int(C) if C is not None else 0))


def _pattern(texts: tuple[str, ...], e: str | None) -> str:
    if e is not None:
        return e
    if texts:
        return texts[0]
    raise ValueError("grep: usage: grep [flags] pattern [path]")


def _build_result(lines: list[str], *,
                  q: bool,
                  reads: dict[str, bytes],
                  cache: list[str]) -> tuple[ByteSource | None, IOResult]:
    exit_code = 0 if lines else 1
    if q:
        return b"", IOResult(exit_code=exit_code, reads=reads, cache=cache)
    stdout = b"" if not lines else "\n".join(lines).encode()
    return stdout, IOResult(exit_code=exit_code, reads=reads, cache=cache)


async def _grep_stdin(
    stdin: AsyncIterator[bytes] | bytes | None,
    pattern: str,
    *,
    ignore_case: bool,
    invert: bool,
    line_numbers: bool,
    count_only: bool,
    files_only: bool,
    whole_word: bool,
    fixed_string: bool,
    only_matching: bool,
    max_count: int | None,
    q: bool,
    after_context: int,
    before_context: int,
) -> tuple[ByteSource | None, IOResult]:
    raw = await _read_stdin_async(stdin)
    if raw is None:
        raise ValueError("grep: missing operand")
    lines = _grep_data("",
                       raw,
                       pattern,
                       ignore_case=ignore_case,
                       invert=invert,
                       line_numbers=line_numbers,
                       count_only=count_only,
                       files_only=files_only,
                       whole_word=whole_word,
                       fixed_string=fixed_string,
                       only_matching=only_matching,
                       max_count=max_count,
                       prefix_path=False,
                       after_context=after_context,
                       before_context=before_context)
    return _build_result(lines, q=q, reads={}, cache=[])


async def _grep_with_context(
    accessor,
    paths: list[PathSpec],
    pattern: str,
    index: IndexCacheStore,
    *,
    recursive: bool,
    ignore_case: bool,
    invert: bool,
    line_numbers: bool,
    count_only: bool,
    files_only: bool,
    whole_word: bool,
    fixed_string: bool,
    only_matching: bool,
    max_count: int | None,
    q: bool,
    after_context: int,
    before_context: int,
) -> tuple[ByteSource | None, IOResult]:
    resolved_paths = await resolve_glob(accessor, paths, index)
    candidates = await candidate_pages(accessor, resolved_paths, index,
                                       recursive)
    reads: dict[str, bytes] = {}
    cache: list[str] = []
    lines: list[str] = []
    prefix_path = len(candidates) > 1 or recursive
    for candidate in candidates:
        data = await read_bytes(accessor, candidate.path, index)
        cache_key = candidate.path.strip_prefix
        reads[cache_key] = data
        cache.append(cache_key)
        lines.extend(_grep_data(candidate.path.original,
                                data,
                                pattern,
                                ignore_case=ignore_case,
                                invert=invert,
                                line_numbers=line_numbers,
                                count_only=count_only,
                                files_only=files_only,
                                whole_word=whole_word,
                                fixed_string=fixed_string,
                                only_matching=only_matching,
                                max_count=max_count,
                                prefix_path=prefix_path,
                                after_context=after_context,
                                before_context=before_context))
    return _build_result(lines, q=q, reads=reads, cache=cache)


def _grep_data(
    path: str,
    data: bytes,
    pattern: str,
    *,
    ignore_case: bool,
    invert: bool,
    line_numbers: bool,
    count_only: bool,
    files_only: bool,
    whole_word: bool,
    fixed_string: bool,
    only_matching: bool,
    max_count: int | None,
    prefix_path: bool,
    after_context: int,
    before_context: int,
) -> list[str]:
    compiled = compile_pattern(pattern, ignore_case, fixed_string, whole_word)
    text_lines = split_lines(data.decode(errors="replace"))
    if after_context > 0 or before_context > 0:
        raw_lines = grep_context_lines(text_lines, compiled, invert,
                                       line_numbers, max_count, after_context,
                                       before_context)
        context_lines = [
            line.decode(errors="replace").rstrip("\n") for line in raw_lines
        ]
        if prefix_path:
            return [line if line == "--" else f"{path}:{line}"
                    for line in context_lines]
        return context_lines
    hits = grep_lines(path, text_lines, compiled, invert, line_numbers,
                      count_only, files_only, only_matching, max_count)
    if count_only:
        return [f"{path}:{hits[0]}"] if prefix_path and hits else hits
    if files_only:
        return hits
    if prefix_path:
        return [f"{path}:{line}" for line in hits]
    return hits
