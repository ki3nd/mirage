import fnmatch

from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.dify.glob import walk
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("find", resource="dify", spec=SPECS["find"])
async def find(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    name: str | None = None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    index = _extra.get("index")
    pattern = name or (texts[0] if texts else "*")
    if not paths:
        paths = [PathSpec(original="/", directory="/")]
    results: list[str] = []
    for path in paths:
        for child in await walk(accessor, path, index):
            child_name = child.rstrip("/").rsplit("/", 1)[-1]
            if fnmatch.fnmatch(child_name, pattern):
                results.append(child)
    return "\n".join(sorted(results)).encode(), IOResult()
