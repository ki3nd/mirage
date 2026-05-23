import fnmatch

from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.generic.find import parse_find_args
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.dify.path import resolve_path
from mirage.core.dify.readdir import readdir
from mirage.core.dify.stat import stat
from mirage.io.types import ByteSource, IOResult
from mirage.types import FindType, PathSpec


async def _walk(accessor,
                path: PathSpec,
                index: IndexCacheStore,
                maxdepth: int | None,
                depth: int = 0) -> list[str]:
    resolved = await resolve_path(accessor, path, index)
    results = [path.original]
    if not resolved.is_dir or (maxdepth is not None and depth >= maxdepth):
        return results
    children = await readdir(accessor, path, index)
    for child in children:
        child_spec = PathSpec(original=child,
                              directory=child,
                              resolved=False,
                              prefix=path.prefix)
        results.extend(await _walk(accessor, child_spec, index, maxdepth,
                                   depth + 1))
    return results


@command("find", resource="dify", spec=SPECS["find"])
async def find(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    name: str | None = None,
    type: str | None = None,
    size: str | None = None,
    maxdepth: str | None = None,
    iname: str | None = None,
    path: str | None = None,
    mindepth: str | None = None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    index = _extra.get("index")
    if not paths:
        paths = [PathSpec(original="/", directory="/")]
    name_pattern = name or (texts[0] if texts and not texts[0].startswith("-")
                            else None)
    args = parse_find_args(texts,
                           name=name_pattern,
                           type=type,
                           size=size,
                           maxdepth=maxdepth,
                           iname=iname,
                           path=path,
                           mindepth=mindepth)
    results: list[str] = []
    for path in paths:
        try:
            children = await _walk(accessor, path, index, args.maxdepth)
        except FileNotFoundError as exc:
            stderr = f"find: '{path.original}': {exc}".encode()
            return b"", IOResult(stderr=stderr, exit_code=1)
        for child in children:
            if await _matches(accessor, child, path.prefix, index, args,
                              path.original):
                results.append(child)
    return "\n".join(sorted(results)).encode(), IOResult()


async def _matches(accessor, item: str, prefix: str, index: IndexCacheStore,
                   args, root: str) -> bool:
    item_name = item.rstrip("/").rsplit("/", 1)[-1]
    if args.mindepth is not None and _relative_depth(item,
                                                     root) < args.mindepth:
        return False
    if args.name and not fnmatch.fnmatch(item_name, args.name):
        return False
    if args.iname and not fnmatch.fnmatch(item_name.lower(),
                                          args.iname.lower()):
        return False
    if args.path_pattern and not fnmatch.fnmatch(item, args.path_pattern):
        return False
    if args.name_exclude and fnmatch.fnmatch(item_name, args.name_exclude):
        return False
    if args.or_names and not any(
            fnmatch.fnmatch(item_name, pattern) for pattern in args.or_names):
        return False
    spec = PathSpec(original=item, directory=item, prefix=prefix)
    if args.type is not None:
        resolved = await resolve_path(accessor, spec, index)
        if args.type == FindType.FILE and resolved.is_dir:
            return False
        if args.type == FindType.DIRECTORY and not resolved.is_dir:
            return False
    if args.min_size is not None or args.max_size is not None:
        item_stat = await stat(accessor, spec, index)
        if item_stat.size is None:
            return False
        if args.min_size is not None and item_stat.size < args.min_size:
            return False
        if args.max_size is not None and item_stat.size > args.max_size:
            return False
    return True


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
