from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.utils.formatting import _human_size
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.path import is_dir as _is_dir
from mirage.core.chromadb.readdir import readdir
from mirage.core.chromadb.stat import stat
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("ls", resource="chromadb", spec=SPECS["ls"])
async def ls(
    accessor,
    paths: list[PathSpec],
    *texts: str,
    stdin: bytes | None = None,
    args_l: bool = False,
    args_1: bool = False,
    a: bool = False,
    A: bool = False,
    h: bool = False,
    t: bool = False,
    S: bool = False,
    r: bool = False,
    R: bool = False,
    d: bool = False,
    F: bool = False,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    index = _extra.get("index")
    if not paths:
        cwd = _extra.get("cwd", "/")
        if isinstance(cwd, PathSpec):
            paths = [cwd]
        else:
            paths = [PathSpec(original=cwd, directory=cwd)]
    paths = await resolve_glob(accessor, paths, index)
    warnings: list[str] = []
    output: list[str] = []
    for path in paths:
        try:
            entries = [path.original] if d else await readdir(
                accessor, path, index)
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            warnings.append(f"ls: cannot access '{path.original}': {exc}")
            continue
        if not a and not A:
            entries = [
                entry for entry in entries
                if not entry.rstrip("/").rsplit("/", 1)[-1].startswith(".")
            ]
        if args_l and not args_1:
            output.extend(await _long_lines(accessor, entries, path.prefix,
                                            index, h))
            continue
        names = []
        for entry in entries:
            name = entry.rstrip("/").rsplit("/", 1)[-1] or "/"
            if F and await _is_dir(entry, path.prefix, index):
                name += "/"
            names.append(name)
        output.extend(sorted(names, reverse=r))
    stderr = "\n".join(warnings).encode() if warnings else None
    exit_code = 1 if warnings and not output else 0
    return "\n".join(output).encode(), IOResult(stderr=stderr,
                                                exit_code=exit_code)


async def _long_lines(accessor, entries: list[str], prefix: str,
                      index: IndexCacheStore, human: bool) -> list[str]:
    stats = []
    for entry in entries:
        spec = PathSpec(original=entry, directory=entry, prefix=prefix)
        stats.append(await stat(accessor, spec, index))
    lines = []
    for item in sorted(stats, key=lambda stat: stat.name):
        size = _human_size(item.size or 0) if human else str(item.size or 0)
        kind = item.type.value if item.type is not None else "-"
        lines.append(f"{kind}\t{size}\t{item.modified or ''}\t{item.name}")
    return lines
