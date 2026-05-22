from mirage.commands.builtin.utils.formatting import _human_size
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.dify.readdir import readdir
from mirage.core.dify.stat import stat
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("ls", resource="dify", spec=SPECS["ls"])
async def ls(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    args_l: bool = False,
    h: bool = False,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    index = _extra.get("index")
    if not paths:
        paths = [PathSpec(original="/", directory="/")]
    output: list[str] = []
    warnings: list[str] = []
    for path in paths:
        try:
            entries = await readdir(accessor, path, index)
        except Exception as exc:
            warnings.append(f"ls: cannot access '{path.original}': {exc}")
            continue
        if args_l:
            for entry in entries:
                item = await stat(
                    accessor,
                    PathSpec(original=entry,
                             directory=entry,
                             prefix=path.prefix), index)
                size = _human_size(item.size or 0) if h else str(item.size
                                                                 or 0)
                kind = item.type.value if item.type else "-"
                output.append(
                    f"{kind}\t{size}\t{item.modified or ''}\t{item.name}")
        else:
            output.extend(
                entry.rstrip("/").rsplit("/", 1)[-1] or "/"
                for entry in entries)
    stderr = "\n".join(warnings).encode() if warnings else None
    return "\n".join(output).encode(), IOResult(stderr=stderr,
                                                exit_code=1 if warnings else 0)
