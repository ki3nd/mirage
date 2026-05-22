import fnmatch

from mirage.cache.index import IndexCacheStore
from mirage.core.dify.readdir import readdir
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
                child for child in await walk(accessor, path.dir, index)
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


async def walk(accessor, path: PathSpec, index: IndexCacheStore) -> list[str]:
    results: list[str] = []
    try:
        children = await readdir(accessor, path, index)
    except (FileNotFoundError, NotADirectoryError):
        return results
    for child in children:
        results.append(child)
        child_path = PathSpec(original=child,
                              directory=child,
                              resolved=False,
                              prefix=path.prefix)
        results.extend(await walk(accessor, child_path, index))
    return results


async def is_file(index: IndexCacheStore, path: str) -> bool:
    lookup = await index.get(path)
    return (lookup.entry is not None and lookup.entry.resource_type == "file")
