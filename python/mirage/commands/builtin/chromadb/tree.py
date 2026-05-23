import fnmatch

from mirage.cache.index import IndexCacheStore
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.path import is_dir as _is_dir
from mirage.core.chromadb.readdir import readdir
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


async def _tree_lines(
    accessor,
    path: PathSpec,
    index: IndexCacheStore,
    prefix: str = "",
    max_depth: int | None = None,
    show_hidden: bool = False,
    ignore_pattern: str | None = None,
    dirs_only: bool = False,
    match_pattern: str | None = None,
    depth: int = 0,
) -> list[str]:
    try:
        entries = await readdir(accessor, path, index)
    except (FileNotFoundError, NotADirectoryError):
        return []
    filtered = []
    for entry in entries:
        name = entry.rsplit("/", 1)[-1]
        is_dir = await _is_dir(entry, path.prefix, index)
        if not show_hidden and name.startswith("."):
            continue
        if ignore_pattern and fnmatch.fnmatch(name, ignore_pattern):
            continue
        if dirs_only and not is_dir:
            continue
        if match_pattern and not is_dir and not fnmatch.fnmatch(
                name, match_pattern):
            continue
        filtered.append((entry, name, is_dir))
    lines: list[str] = []
    for item_index, (entry, name, is_dir) in enumerate(filtered):
        is_last = item_index == len(filtered) - 1
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        lines.append(prefix + connector + name)
        if is_dir and (max_depth is None or depth + 1 < max_depth):
            child = PathSpec(original=entry,
                             directory=entry,
                             resolved=False,
                             prefix=path.prefix)
            extension = "    " if is_last else "\u2502   "
            lines.extend(await
                         _tree_lines(accessor, child, index,
                                     prefix + extension, max_depth,
                                     show_hidden, ignore_pattern, dirs_only,
                                     match_pattern, depth + 1))
    return lines


@command("tree", resource="chromadb", spec=SPECS["tree"])
async def tree(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    stdin: bytes | None = None,
    L: str | None = None,
    a: bool = False,
    args_I: str | None = None,
    d: bool = False,
    P: str | None = None,
    index: IndexCacheStore = None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    paths = await resolve_glob(accessor, paths, index)
    path = paths[0] if paths else PathSpec(original="/", directory="/")
    max_depth = int(L) if L is not None else None
    lines = await _tree_lines(accessor,
                              path,
                              index,
                              max_depth=max_depth,
                              show_hidden=a,
                              ignore_pattern=args_I,
                              dirs_only=d,
                              match_pattern=P)
    return "\n".join(lines).encode(), IOResult()
