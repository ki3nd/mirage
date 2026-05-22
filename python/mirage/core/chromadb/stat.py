from mirage.cache.index import IndexCacheStore
from mirage.core.chromadb.path import resolve_path
from mirage.core.chromadb.read import document_to_text, fetch_chunks
from mirage.types import FileStat, FileType, PathSpec
from mirage.utils.filetype import guess_type


async def stat(accessor, path: PathSpec, index: IndexCacheStore) -> FileStat:
    resolved = await resolve_path(accessor, path, index)
    if resolved.is_dir:
        return FileStat(
            name=_stat_name(resolved.virtual_key, resolved.mount_prefix),
            type=FileType.DIRECTORY,
        )
    chunks = await fetch_chunks(accessor, resolved.entry.extra["raw_slugs"])
    size = sum(
        len(document_to_text(c.document).encode()) for c in chunks
    ) + max(0, len(chunks) - 1)
    extra = dict(resolved.entry.extra)
    extra["chunk_count"] = len(chunks)
    return FileStat(
        name=resolved.entry.name,
        type=guess_type(resolved.entry.extra["path"]),
        size=size,
        modified=None,
        fingerprint=None,
        revision=None,
        extra=extra,
    )


def _stat_name(virtual_key: str, mount_prefix: str) -> str:
    root = mount_prefix.rstrip("/") or "/"
    if virtual_key == root:
        return "/"
    return virtual_key.rstrip("/").rsplit("/", 1)[-1]
