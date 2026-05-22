from mirage.core.chromadb.grep import grep_paths
from mirage.ops.registry import op
from mirage.types import PathSpec


@op("grep", resource="chromadb")
async def grep(
    accessor,
    path: PathSpec,
    pattern: str,
    *,
    index,
    recursive: bool = True,
    ignore_case: bool = False,
    invert: bool = False,
    line_numbers: bool = False,
    count_only: bool = False,
    files_only: bool = False,
    whole_word: bool = False,
    fixed_string: bool = False,
    only_matching: bool = False,
    max_count: int | None = None,
    **kwargs,
) -> list[str]:
    result = await grep_paths(
        accessor,
        [path],
        pattern,
        index,
        recursive=recursive,
        ignore_case=ignore_case,
        invert=invert,
        line_numbers=line_numbers,
        count_only=count_only,
        files_only=files_only,
        whole_word=whole_word,
        fixed_string=fixed_string,
        only_matching=only_matching,
        max_count=max_count,
    )
    return result.lines
