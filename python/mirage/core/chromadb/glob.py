import fnmatch
import logging

from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.constants import SCOPE_ERROR
from mirage.core.chromadb.readdir import readdir
from mirage.types import PathSpec

logger = logging.getLogger(__name__)


async def resolve_glob(
    accessor,
    paths: list[PathSpec],
    index: IndexCacheStore,
) -> list[PathSpec]:
    result: list[PathSpec] = []
    for path in paths:
        if isinstance(path, str):
            result.append(PathSpec(original=path, directory=path))
            continue
        if path.resolved:
            result.append(path)
            continue
        if not path.pattern:
            result.append(path)
            continue
        entries = await readdir(accessor, path.dir, index)
        matched = [
            PathSpec(original=entry,
                     directory=path.directory,
                     prefix=path.prefix) for entry in entries
            if fnmatch.fnmatch(entry.rsplit("/", 1)[-1], path.pattern)
        ]
        if len(matched) > SCOPE_ERROR:
            logger.warning("%s: %d matches exceeds limit (%d), truncating",
                           path.directory, len(matched), SCOPE_ERROR)
            matched = matched[:SCOPE_ERROR]
        result.extend(matched)
    return result
