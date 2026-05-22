from mirage.core.chromadb.read import read_bytes
from mirage.ops.registry import op
from mirage.types import PathSpec


@op("read", resource="chromadb")
async def read(accessor, path: PathSpec, *, index, **kwargs) -> bytes:
    return await read_bytes(accessor, path, index)
