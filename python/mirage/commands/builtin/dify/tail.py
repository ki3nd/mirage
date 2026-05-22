from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.dify.glob import resolve_glob
from mirage.core.dify.read import read_bytes
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("tail", resource="dify", spec=SPECS["tail"])
async def tail(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    n: int | str = 10,
    args_n: int | str | None = None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    index = _extra.get("index")
    limit = int(args_n if args_n is not None else n)
    paths = await resolve_glob(accessor, paths, index)
    data = await read_bytes(accessor, paths[0], index)
    return "\n".join(data.decode(
        errors="replace").splitlines()[-limit:]).encode(), IOResult()
