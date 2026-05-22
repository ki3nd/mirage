import re
from collections.abc import Iterable

import pytest

from mirage.resource.chromadb import ChromaDBConfig, ChromaDBResource
from mirage.types import MountMode
from mirage.workspace import Workspace


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


@pytest.fixture
def chromadb_workspace() -> Workspace:
    resource = ChromaDBResource(
        ChromaDBConfig(host="localhost", collection_name="docs"))
    resource.accessor = FakeAccessor([
        _record("guides/quickstart.md", 1, "line2"),
        _record("guides/quickstart.md", 0, "line1"),
        _record("readme.md", 0, "readme"),
    ])
    return Workspace(resources={"/docs": (resource, MountMode.READ)},
                     history=None)


async def _stdout(io) -> bytes:
    return await io.materialize_stdout()


@pytest.mark.asyncio
async def test_chromadb_workspace_ls(chromadb_workspace: Workspace) -> None:
    io = await chromadb_workspace.execute("ls -F /docs")

    assert io.exit_code == 0
    assert await _stdout(io) == b"guides/\nreadme.md"


@pytest.mark.asyncio
async def test_chromadb_workspace_cat_head_tail(
        chromadb_workspace: Workspace) -> None:
    cat = await chromadb_workspace.execute("cat /docs/guides/quickstart.md")
    head = await chromadb_workspace.execute(
        "head -n 1 /docs/guides/quickstart.md")
    tail = await chromadb_workspace.execute(
        "tail -n 1 /docs/guides/quickstart.md")

    assert cat.exit_code == 0
    assert await _stdout(cat) == b"line1\nline2"
    assert (await _stdout(head)).splitlines() == [b"line1"]
    assert (await _stdout(tail)).splitlines() == [b"line2"]


@pytest.mark.asyncio
async def test_chromadb_workspace_find(chromadb_workspace: Workspace) -> None:
    io = await chromadb_workspace.execute("find /docs -name '*.md' -type f")

    assert io.exit_code == 0
    assert await _stdout(io) == b"/docs/guides/quickstart.md\n/docs/readme.md"


@pytest.mark.asyncio
async def test_chromadb_workspace_tree(chromadb_workspace: Workspace) -> None:
    io = await chromadb_workspace.execute("tree /docs")

    output = (await _stdout(io)).decode()
    assert io.exit_code == 0
    assert "guides" in output
    assert "quickstart.md" in output
    assert "readme.md" in output


@pytest.mark.asyncio
async def test_chromadb_workspace_grep_recursive(
        chromadb_workspace: Workspace) -> None:
    io = await chromadb_workspace.execute("grep -r line1 /docs")

    assert io.exit_code == 0
    assert await _stdout(io) == b"/docs/guides/quickstart.md:line1"
