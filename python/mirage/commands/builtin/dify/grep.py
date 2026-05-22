from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.dify.glob import resolve_glob
from mirage.core.dify.grep import grep_bytes
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("grep", resource="dify", spec=SPECS["grep"])
async def grep(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    i: bool = False,
    args_i: bool = False,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    if not texts:
        raise ValueError("grep: missing pattern")
    index = _extra.get("index")
    paths = await resolve_glob(accessor, paths, index)
    output, reads = await grep_bytes(accessor,
                                     paths,
                                     texts[0],
                                     index,
                                     ignore_case=i or args_i)
    return output, IOResult(reads=reads,
                            cache=list(reads),
                            exit_code=0 if output else 1)
