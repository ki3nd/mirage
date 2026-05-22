from mirage.core.chromadb.readdir import readdir as core_readdir
from mirage.ops.registry import op
from mirage.types import PathSpec


@op("readdir", resource="chromadb")
async def readdir(accessor, path: PathSpec, *, index, **kwargs) -> list[str]:
    return await core_readdir(accessor, path, index)
