import fnmatch

from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.generic.find import parse_find_args
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.path import virtual_key_for
from mirage.core.chromadb.readdir import readdir
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


async def _walk(accessor,
                path: PathSpec,
                index: IndexCacheStore,
                maxdepth: int | None,
                depth: int = 0) -> list[str]:
    if maxdepth is not None and depth > maxdepth:
        return []
    try:
        children = await readdir(accessor, path, index)
    except (FileNotFoundError, NotADirectoryError):
        return []
    results: list[str] = []
    for child in children:
        results.append(child)
        if await _is_dir(child, path.prefix, index):
            child_spec = PathSpec(original=child,
                                  directory=child,
                                  resolved=False,
                                  prefix=path.prefix)
            results.extend(await _walk(accessor, child_spec, index, maxdepth,
                                       depth + 1))
    return results


async def _is_dir(path: str, prefix: str, index: IndexCacheStore) -> bool:
    spec = PathSpec(original=path, directory=path, prefix=prefix)
    result = await index.get(virtual_key_for(spec))
    if result.entry is not None:
        return result.entry.resource_type == "folder"
    listing = await index.list_dir(virtual_key_for(spec))
    return listing.entries is not None


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
                           maxdepth=maxdepth,
                           iname=iname,
                           path=path,
                           mindepth=mindepth)
    all_paths = await _walk(accessor, search, index, args.maxdepth)
    base_depth = search.original.strip("/").count(
        "/") if search.original.strip("/") else -1
    matches = []
    for item in sorted(all_paths):
        item_name = item.rsplit("/", 1)[-1]
        depth = item.strip("/").count("/") - (base_depth + 1)
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
        matches.append(item)
    return "\n".join(matches).encode(), IOResult()
