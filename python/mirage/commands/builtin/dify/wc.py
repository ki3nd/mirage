from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.dify.glob import resolve_glob
from mirage.core.dify.read import read_bytes
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("wc", resource="dify", spec=SPECS["wc"])
async def wc(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    args_l: bool = False,
    w: bool = False,
    c: bool = False,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    index = _extra.get("index")
    paths = await resolve_glob(accessor, paths, index)
    reads: dict[str, bytes] = {}
    output: list[str] = []
    for path in paths:
        data = await read_bytes(accessor, path, index)
        reads[path.original] = data
        text = data.decode(errors="replace")
        values = [
            str(line_count(text)),
            str(len(text.split())),
            str(len(data))
        ]
        if args_l:
            values = [values[0]]
        elif w:
            values = [values[1]]
        elif c:
            values = [values[2]]
        output.append(" ".join([*values, path.original]))
    return "\n".join(output).encode(), IOResult(reads=reads, cache=list(reads))


def line_count(text: str) -> int:
    return text.count("\n") + (1 if text else 0)
