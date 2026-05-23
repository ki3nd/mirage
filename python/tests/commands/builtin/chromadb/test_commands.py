import re
from collections.abc import Iterable

import pytest

from mirage.cache.index.ram import RAMIndexCacheStore
from mirage.commands.builtin.chromadb.cat import cat
from mirage.commands.builtin.chromadb.find import find
from mirage.commands.builtin.chromadb.grep import grep
from mirage.commands.builtin.chromadb.head import head
from mirage.commands.builtin.chromadb.ls import ls
from mirage.commands.builtin.chromadb.tail import tail
from mirage.commands.builtin.chromadb.tree import tree
from mirage.io.types import materialize
from mirage.ops.chromadb.grep import grep as grep_op
from mirage.resource.chromadb.config import ChromaDBConfig
from mirage.types import PathSpec


class FakeCollection:

    def __init__(self, records: Iterable[dict]) -> None:
        self.records = list(records)

    def get(
        self,
        include: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        where: dict | None = None,
        where_document: dict | None = None,
    ) -> dict:
        records = self._filter_records(where, where_document)
        page = records[offset:offset + limit if limit is not None else None]
        result: dict[str, list] = {}
        if include is None or "metadatas" in include:
            result["metadatas"] = [r["metadata"] for r in page]
        if include is None or "documents" in include:
            result["documents"] = [r["document"] for r in page]
        return result

    def _filter_records(
        self,
        where: dict | None,
        where_document: dict | None,
    ) -> list[dict]:
        records = self.records
        if where_document is not None:
            records = [
                r for r in records
                if _document_matches(r["document"], where_document)
            ]
        if where is None:
            return records
        value = where["page_slug"]
        if isinstance(value, dict):
            allowed = set(value["$in"])
            return [
                r for r in records if r["metadata"]["page_slug"] in allowed
            ]
        return [r for r in records if r["metadata"]["page_slug"] == value]


class FakeAccessor:

    def __init__(self, records: Iterable[dict]) -> None:
        self.config = ChromaDBConfig(host="localhost",
                                     collection_name="docs",
                                     metadata_batch_size=100,
                                     chunk_batch_size=100)
        self._collection = FakeCollection(records)

    @property
    def collection(self) -> FakeCollection:
        return self._collection


def _record(slug: str, chunk_index: int, document: str) -> dict:
    return {
        "metadata": {
            "page_slug": slug,
            "chunk_index": chunk_index,
        },
        "document": document,
    }


def _document_matches(document: str, where_document: dict) -> bool:
    if "$contains" in where_document:
        return str(where_document["$contains"]) in document
    if "$regex" in where_document:
        return re.search(str(where_document["$regex"]), document) is not None
    return True


async def _bytes(source) -> bytes:
    return await materialize(source)


@pytest.fixture
def index() -> RAMIndexCacheStore:
    return RAMIndexCacheStore()


@pytest.fixture
def accessor() -> FakeAccessor:
    return FakeAccessor([
        _record("guides/quickstart.md", 1, "line2"),
        _record("guides/quickstart.md", 0, "line1"),
        _record("readme.md", 0, "readme"),
    ])


@pytest.mark.asyncio
async def test_ls_lists_directories_without_fetching_file_content(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await ls(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        index=index,
        F=True)

    assert await _bytes(output) == b"guides/\nreadme.md"
    assert io.exit_code == 0


@pytest.mark.asyncio
async def test_ls_long_uses_stat_sizes(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await ls(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        index=index,
        args_l=True)

    text = (await _bytes(output)).decode()
    assert "directory\t0\t\tguides" in text
    assert "text\t6\t\treadme.md" in text
    assert io.exit_code == 0


@pytest.mark.asyncio
async def test_cat_reads_sorted_chunks_and_records_cache(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    path = PathSpec(original="/docs/guides/quickstart.md",
                    directory="/docs/guides/quickstart.md",
                    prefix="/docs")

    output, io = await cat(accessor, [path], index=index)

    assert await _bytes(output) == b"line1\nline2"
    assert io.cache == ["/guides/quickstart.md"]


@pytest.mark.asyncio
async def test_head_and_tail_read_from_stream(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    path = PathSpec(original="/docs/guides/quickstart.md",
                    directory="/docs/guides/quickstart.md",
                    prefix="/docs")

    head_output, _ = await head(accessor, [path], n="1", index=index)
    tail_output, _ = await tail(accessor, [path], n="1", index=index)

    assert await _bytes(head_output) == b"line1\n"
    assert await _bytes(tail_output) == b"line2"


@pytest.mark.asyncio
async def test_head_and_tail_zero_lines_return_empty(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    path = PathSpec(original="/docs/guides/quickstart.md",
                    directory="/docs/guides/quickstart.md",
                    prefix="/docs")

    head_output, _ = await head(accessor, [path], n="0", index=index)
    tail_output, _ = await tail(accessor, [path], n="0", index=index)

    assert await _bytes(head_output) == b""
    assert await _bytes(tail_output) == b""


@pytest.mark.asyncio
async def test_find_filters_by_name_and_type(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await find(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        name="*.md",
        type="f",
        index=index)

    assert await _bytes(output
                        ) == b"/docs/guides/quickstart.md\n/docs/readme.md"
    assert io.exit_code == 0


@pytest.mark.asyncio
async def test_find_returns_file_operand(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await find(
        accessor,
        [
            PathSpec(original="/docs/readme.md",
                     directory="/docs/readme.md",
                     prefix="/docs")
        ],
        index=index)

    assert await _bytes(output) == b"/docs/readme.md"
    assert io.exit_code == 0


@pytest.mark.asyncio
async def test_find_missing_path_returns_error(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await find(
        accessor,
        [
            PathSpec(original="/docs/missing.md",
                     directory="/docs/missing.md",
                     prefix="/docs")
        ],
        index=index)

    assert await _bytes(output) == b""
    assert io.stderr is not None
    assert b"/docs/missing.md" in io.stderr
    assert io.exit_code == 1


@pytest.mark.asyncio
async def test_find_maxdepth_zero_returns_start_path(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await find(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        maxdepth="0",
        index=index)

    assert await _bytes(output) == b"/docs"
    assert io.exit_code == 0


@pytest.mark.asyncio
async def test_find_size_filters_files(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await find(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        type="f",
        size="+7",
        index=index)

    assert await _bytes(output) == b"/docs/guides/quickstart.md"
    assert io.exit_code == 0


@pytest.mark.asyncio
async def test_grep_recursive_uses_two_phase(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([
        _record("guides/auth.md", 1, "full page details"),
        _record("guides/auth.md", 0, "access token overview"),
        _record("guides/billing.md", 0, "invoice setup"),
    ])

    output, io = await grep(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        "token",
        r=True,
        index=index,
    )

    assert await _bytes(output
                        ) == b"/docs/guides/auth.md:access token overview"
    assert io.exit_code == 0
    assert io.cache == ["/guides/auth.md"]
    assert io.reads == {
        "/guides/auth.md": b"access token overview\nfull page details"
    }


@pytest.mark.asyncio
async def test_grep_recursive_returns_exit_one_without_matches(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await grep(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        "missing",
        r=True,
        index=index,
    )

    assert await _bytes(output) == b""
    assert io.exit_code == 1
    assert io.cache == []


@pytest.mark.asyncio
async def test_grep_op_returns_chromadb_matches(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    lines = await grep_op(
        accessor,
        PathSpec(original="/docs", directory="/docs", prefix="/docs"),
        "line1",
        index=index,
        recursive=True,
    )

    assert lines == ["/docs/guides/quickstart.md:line1"]


@pytest.mark.asyncio
async def test_tree_renders_directory_tree_without_file_stat_fetch(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await tree(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        index=index)

    text = (await _bytes(output)).decode()
    assert "guides" in text
    assert "quickstart.md" in text
    assert "readme.md" in text
    assert io.exit_code == 0


@pytest.mark.asyncio
async def test_tree_respects_max_depth(
    accessor: FakeAccessor,
    index: RAMIndexCacheStore,
) -> None:
    output, io = await tree(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        L="1",
        index=index)

    text = (await _bytes(output)).decode()
    assert "guides" in text
    assert "readme.md" in text
    assert "quickstart.md" not in text
    assert io.exit_code == 0
