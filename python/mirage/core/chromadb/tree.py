import asyncio
from collections import defaultdict

from mirage.cache.index import IndexCacheStore, IndexEntry


async def ensure_tree(accessor,
                      index: IndexCacheStore,
                      mount_prefix: str = "") -> None:
    root_key = _mount_root(mount_prefix)
    listing = await index.list_dir(root_key)
    if listing.entries is not None:
        return

    raw_by_path = await _scan_slugs(accessor)
    _raise_on_collisions(raw_by_path)
    dir_entries = _build_dir_entries(raw_by_path, mount_prefix)
    for directory in sorted(dir_entries):
        await index.set_dir(
            directory, sorted(dir_entries[directory],
                              key=lambda item: item[0]))


async def _scan_slugs(accessor) -> dict[str, list[str]]:
    raw_by_path: dict[str, list[str]] = defaultdict(list)
    offset = 0
    while True:
        result = await asyncio.to_thread(
            accessor.collection.get,
            include=["metadatas"],
            limit=accessor.config.metadata_batch_size,
            offset=offset,
        )
        metadatas = result.get("metadatas") or []
        if not metadatas:
            break
        for metadata in metadatas:
            if not isinstance(metadata, dict):
                continue
            raw_slug = metadata.get(accessor.config.slug_field)
            path = normalize_slug(raw_slug)
            if path is None:
                continue
            raw_value = str(raw_slug)
            if raw_value not in raw_by_path[path]:
                raw_by_path[path].append(raw_value)
        offset += len(metadatas)
    return dict(raw_by_path)


def normalize_slug(value: object) -> str | None:
    if value is None:
        return None
    parts = [
        part for part in str(value).strip("/").split("/")
        if part and part not in {".", ".."}
    ]
    if not parts:
        return None
    return "/" + "/".join(parts)


def _raise_on_collisions(raw_by_path: dict[str, list[str]]) -> None:
    paths = set(raw_by_path)
    for path in sorted(paths):
        parts = path.strip("/").split("/")
        for index in range(1, len(parts)):
            ancestor = "/" + "/".join(parts[:index])
            if ancestor in paths:
                raise ValueError(
                    "Path collision: slug "
                    f"'{ancestor.strip('/')}' is both a file and a "
                    f"directory prefix for slug '{path.strip('/')}'.")


def _build_dir_entries(
    raw_by_path: dict[str, list[str]],
    mount_prefix: str,
) -> dict[str, list[tuple[str, IndexEntry]]]:
    dirs = _collect_directories(raw_by_path)
    dir_entries: dict[str, list[tuple[str, IndexEntry]]] = {
        _virtual_path(directory, mount_prefix): []
        for directory in dirs
    }
    for directory in sorted(dirs):
        if directory == "/":
            continue
        parent = _parent(directory)
        entry = IndexEntry(id=directory,
                           name=_basename(directory),
                           resource_type="folder")
        dir_entries[_virtual_path(parent, mount_prefix)].append(
            (entry.name, entry))
    for path, raw_slugs in sorted(raw_by_path.items()):
        parent = _parent(path)
        entry = IndexEntry(
            id=path,
            name=_basename(path),
            resource_type="file",
            size=None,
            extra={
                "raw_slugs": raw_slugs,
                "path": path,
            },
        )
        dir_entries[_virtual_path(parent, mount_prefix)].append(
            (entry.name, entry))
    return dir_entries


def _collect_directories(raw_by_path: dict[str, list[str]]) -> set[str]:
    dirs = {"/"}
    for path in raw_by_path:
        parts = path.strip("/").split("/")
        for index in range(1, len(parts)):
            dirs.add("/" + "/".join(parts[:index]))
    return dirs


def _mount_root(mount_prefix: str) -> str:
    return mount_prefix.rstrip("/") or "/"


def _virtual_path(path: str, mount_prefix: str) -> str:
    root = _mount_root(mount_prefix)
    if path == "/":
        return root
    if root == "/":
        return path
    return root + path


def _parent(path: str) -> str:
    parent = path.rsplit("/", 1)[0]
    return parent or "/"


def _basename(path: str) -> str:
    return path.rstrip("/").rsplit("/", 1)[-1] or "/"
