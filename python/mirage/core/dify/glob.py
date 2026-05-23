import fnmatch

from mirage.cache.index import IndexCacheStore
from mirage.core.dify.readdir import readdir
from mirage.core.dify.walk import walk
from mirage.types import PathSpec


async def resolve_glob(accessor, paths: list,
                       index: IndexCacheStore) -> list[PathSpec]:
    if not paths:
        return []
    resolved: list[PathSpec] = []
    for path in paths:
        if isinstance(path, str):
            path = PathSpec.from_str_path(path)
        if path.resolved and not path.pattern:
            resolved.append(path)
            continue
        if path.pattern == "**":
            children = [
                child for child in await walk(accessor,
                                             path.dir,
                                             index,
                                             ignore_missing=True)
                if await is_file(index, child)
            ]
        else:
            children = await readdir(accessor, path.dir, index)
        for child in children:
            name = child.rstrip("/").rsplit("/", 1)[-1]
            if path.pattern in {None, "**"} or fnmatch.fnmatch(
                    name, path.pattern):
                resolved.append(
                    PathSpec(original=child,
                             directory=child,
                             resolved=True,
                             prefix=path.prefix))
    return resolved


async def is_file(index: IndexCacheStore, path: str) -> bool:
    lookup = await index.get(path)
    return (lookup.entry is not None and lookup.entry.resource_type == "file")
