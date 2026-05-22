from dataclasses import dataclass

from mirage.cache.index import IndexCacheStore, IndexEntry
from mirage.core.chromadb.tree import ensure_tree
from mirage.types import PathSpec


@dataclass(frozen=True)
class ResolvedChromaPath:
    virtual_key: str
    mount_prefix: str
    is_dir: bool
    entry: IndexEntry | None = None


async def resolve_path(accessor, path: PathSpec,
                       index: IndexCacheStore) -> ResolvedChromaPath:
    if isinstance(path, str):
        path = PathSpec(original=path, directory=path)
    mount_prefix = path.prefix or ""
    await ensure_tree(accessor, index, mount_prefix)
    virtual_key = virtual_key_for(path)
    result = await index.get(virtual_key)
    if result.entry is not None:
        if result.entry.resource_type == "folder":
            return ResolvedChromaPath(virtual_key, mount_prefix, True,
                                      result.entry)
        return ResolvedChromaPath(virtual_key, mount_prefix, False,
                                  result.entry)
    listing = await index.list_dir(virtual_key)
    if listing.entries is not None:
        return ResolvedChromaPath(virtual_key, mount_prefix, True)
    raise FileNotFoundError(path.original)


def virtual_key_for(path: PathSpec) -> str:
    raw = path.directory if path.pattern else path.original
    prefix = path.prefix or ""
    if prefix:
        root = prefix.rstrip("/") or "/"
        if raw == root or raw.startswith(root + "/"):
            return raw.rstrip("/") or root
        rest = raw.strip("/")
        if not rest:
            return root
        return root + "/" + rest
    return "/" + raw.strip("/") if raw.strip("/") else "/"
