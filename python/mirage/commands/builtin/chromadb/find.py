import fnmatch

from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.generic.find import parse_find_args
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.path import is_dir as _is_dir
from mirage.core.chromadb.path import resolve_path
from mirage.core.chromadb.readdir import readdir
from mirage.core.chromadb.stat import stat
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


async def _walk(accessor,
                path: PathSpec,
                index: IndexCacheStore,
                maxdepth: int | None,
                depth: int = 0) -> list[str]:
    resolved = await resolve_path(accessor, path, index)
    results: list[str] = []
    results.append(path.original)
    if not resolved.is_dir or (maxdepth is not None and depth >= maxdepth):
        return results
    children = await readdir(accessor, path, index)
    for child in children:
        if await _is_dir(child, path.prefix, index):
            child_spec = PathSpec(original=child,
                                  directory=child,
                                  resolved=False,
                                  prefix=path.prefix)
            results.extend(await _walk(accessor, child_spec, index, maxdepth,
                                       depth + 1))
            continue
        results.append(child)
    return results


@command("find", resource="chromadb", spec=SPECS["find"])
async def find(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    stdin: bytes | None = None,
    name: str | None = None,
    type: str | None = None,
    maxdepth: str | None = None,
    size: str | None = None,
    mtime: str | None = None,
    iname: str | None = None,
    path: str | None = None,
    mindepth: str | None = None,
    index: IndexCacheStore = None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    paths = await resolve_glob(accessor, paths, index)
    search = paths[0] if paths else PathSpec(original="/", directory="/")
    args = parse_find_args(texts,
                           name=name,
                           type=type,
                           size=size,
                           maxdepth=maxdepth,
                           iname=iname,
                           path=path,
                           mindepth=mindepth)
    try:
        all_paths = await _walk(accessor, search, index, args.maxdepth)
    except FileNotFoundError as exc:
        stderr = f"find: '{search.original}': {exc}".encode()
        return b"", IOResult(stderr=stderr, exit_code=1)
    matches = []
    for item in sorted(all_paths):
        item_name = item.rsplit("/", 1)[-1]
        depth = _relative_depth(item, search.original)
        if args.mindepth is not None and depth < args.mindepth:
            continue
        if args.name and not fnmatch.fnmatch(item_name, args.name):
            continue
        if args.iname and not fnmatch.fnmatch(item_name.lower(),
                                              args.iname.lower()):
            continue
        if args.name_exclude and fnmatch.fnmatch(item_name, args.name_exclude):
            continue
        if args.path_pattern and not fnmatch.fnmatch(item, args.path_pattern):
            continue
        if args.or_names and not any(
                fnmatch.fnmatch(item_name, pattern)
                for pattern in args.or_names):
            continue
        if args.type == "f" and await _is_dir(item, search.prefix, index):
            continue
        if args.type == "d" and not await _is_dir(item, search.prefix, index):
            continue
        if not await _matches_stat_filters(accessor, item, search.prefix,
                                           index, args):
            continue
        matches.append(item)
    return "\n".join(matches).encode(), IOResult()


def _relative_depth(item: str, root: str) -> int:
    root_norm = root.rstrip("/") or "/"
    item_norm = item.rstrip("/") or "/"
    if item_norm == root_norm:
        return 0
    if root_norm == "/":
        relative = item_norm.strip("/")
    else:
        relative = item_norm.removeprefix(root_norm).lstrip("/")
    if not relative:
        return 0
    return relative.count("/") + 1


async def _matches_stat_filters(accessor, path: str, prefix: str,
                                index: IndexCacheStore, args) -> bool:
    if args.min_size is None and args.max_size is None:
        return True
    spec = PathSpec(original=path, directory=path, prefix=prefix)
    item_stat = await stat(accessor, spec, index)
    if item_stat.size is None:
        return False
    if args.min_size is not None and item_stat.size < args.min_size:
        return False
    if args.max_size is not None and item_stat.size > args.max_size:
        return False
    return True
