from mirage.core.chromadb.stat import stat as core_stat
from mirage.ops.registry import op
from mirage.types import FileStat, PathSpec


@op("stat", resource="chromadb")
async def stat(accessor, path: PathSpec, *, index, **kwargs) -> FileStat:
    return await core_stat(accessor, path, index)
