import re
from collections.abc import Iterable

import pytest

from mirage.cache.index.ram import RAMIndexCacheStore
from mirage.core.chromadb.glob import resolve_glob
from mirage.core.chromadb.grep import grep_paths
from mirage.core.chromadb.read import read_bytes, read_stream
from mirage.core.chromadb.readdir import readdir
from mirage.core.chromadb.stat import stat
from mirage.core.chromadb.tree import ensure_tree
from mirage.resource.chromadb.config import ChromaDBConfig
from mirage.types import FileType, PathSpec


class FakeCollection:

    def __init__(self, records: Iterable[dict]) -> None:
        self.records = list(records)
        self.calls: list[dict] = []

    def get(
        self,
        include: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        where: dict | None = None,
        where_document: dict | None = None,
    ) -> dict:
        self.calls.append({
            "include": include,
            "limit": limit,
            "offset": offset,
            "where": where,
            "where_document": where_document,
        })
        records = self._filter_records(where, where_document)
        page = records[offset:offset + limit if limit is not None else None]
        result: dict[str, list] = {}
        if include is None or "metadatas" in include:
            result["metadatas"] = [r.get("metadata", {}) for r in page]
        if include is None or "documents" in include:
            result["documents"] = [r.get("document") for r in page]
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
                if _document_matches(r.get("document"), where_document)
            ]
        if where is None:
            return records
        if "page_slug" not in where:
            return records
        value = where["page_slug"]
        if isinstance(value, dict) and "$in" in value:
            allowed = set(value["$in"])
            return [
                r for r in records
                if r.get("metadata", {}).get("page_slug") in allowed
            ]
        return [
            r for r in records
            if r.get("metadata", {}).get("page_slug") == value
        ]


class FakeAccessor:

    def __init__(self, records: Iterable[dict]) -> None:
        self.config = ChromaDBConfig(host="localhost",
                                     collection_name="docs",
                                     metadata_batch_size=2,
                                     chunk_batch_size=2)
        self._collection = FakeCollection(records)

    @property
    def collection(self) -> FakeCollection:
        return self._collection


def _record(slug: object,
            chunk_index: object,
            document: object = "doc") -> dict:
    return {
        "metadata": {
            "page_slug": slug,
            "chunk_index": chunk_index,
        },
        "document": document,
    }


def _document_matches(document: object, where_document: dict) -> bool:
    text = "" if document is None else str(document)
    if "$contains" in where_document:
        return str(where_document["$contains"]) in text
    if "$regex" in where_document:
        return re.search(str(where_document["$regex"]), text) is not None
    return True


@pytest.fixture
def index() -> RAMIndexCacheStore:
    return RAMIndexCacheStore()


@pytest.mark.asyncio
async def test_ensure_tree_builds_cached_slug_tree(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([
        _record("auth/oauth", 0),
        _record("/auth/oauth/", 1),
        _record("foo//bar", 0),
        _record("./foo/../bar", 0),
        _record("", 0),
        _record(None, 0),
        _record("/", 0),
    ])

    await ensure_tree(accessor, index, "/docs")

    assert await readdir(
        accessor, PathSpec(original="/docs", directory="/docs",
                           prefix="/docs"),
        index) == ["/docs/auth", "/docs/foo"]
    oauth = await index.get("/docs/auth/oauth")
    assert oauth.entry is not None
    assert oauth.entry.extra == {
        "raw_slugs": ["auth/oauth", "/auth/oauth/"],
        "path": "/auth/oauth",
    }
    foo = await index.get("/docs/foo/bar")
    assert foo.entry is not None
    assert foo.entry.extra["raw_slugs"] == ["foo//bar", "./foo/../bar"]

    call_count = len(accessor.collection.calls)
    await ensure_tree(accessor, index, "/docs")
    assert len(accessor.collection.calls) == call_count


@pytest.mark.asyncio
async def test_ensure_tree_raises_for_collision(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([_record("foo", 0), _record("foo/bar", 0)])

    with pytest.raises(ValueError,
                       match="slug 'foo' is both a file and a directory"):
        await ensure_tree(accessor, index, "/docs")


@pytest.mark.asyncio
async def test_empty_collection_builds_empty_root(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([])

    await ensure_tree(accessor, index, "/docs")

    assert await readdir(
        accessor, PathSpec(original="/docs", directory="/docs",
                           prefix="/docs"), index) == []


@pytest.mark.asyncio
async def test_readdir_handles_file_dir_and_missing(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([_record("guides/quickstart.md", 0)])

    assert await readdir(
        accessor,
        PathSpec(original="/docs/guides",
                 directory="/docs/guides",
                 prefix="/docs"), index) == ["/docs/guides/quickstart.md"]
    with pytest.raises(NotADirectoryError):
        await readdir(
            accessor,
            PathSpec(original="/docs/guides/quickstart.md",
                     directory="/docs/guides/quickstart.md",
                     prefix="/docs"), index)
    with pytest.raises(FileNotFoundError):
        await readdir(
            accessor,
            PathSpec(original="/docs/missing",
                     directory="/docs/missing",
                     prefix="/docs"), index)


@pytest.mark.asyncio
async def test_read_bytes_and_stream_sort_chunks(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([
        _record("guides/quickstart.md", 2, "third"),
        _record("guides/quickstart.md", 0, "first"),
        _record("guides/quickstart.md", 1, "second"),
    ])
    path = PathSpec(original="/docs/guides/quickstart.md",
                    directory="/docs/guides/quickstart.md",
                    prefix="/docs")

    assert await read_bytes(accessor, path, index) == b"first\nsecond\nthird"
    stream_data = b"".join(
        [chunk async for chunk in read_stream(accessor, path, index)])
    assert stream_data == b"first\nsecond\nthird"


@pytest.mark.asyncio
async def test_read_bytes_fetches_all_raw_slugs(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([
        _record("guide", 1, "raw-a"),
        _record("/guide/", 0, "raw-b"),
    ])

    data = await read_bytes(
        accessor,
        PathSpec(original="/docs/guide",
                 directory="/docs/guide",
                 prefix="/docs"),
        index,
    )

    assert data == b"raw-b\nraw-a"
    where_calls = [
        c["where"] for c in accessor.collection.calls if c["where"] is not None
    ]
    assert {"page_slug": {"$in": ["guide", "/guide/"]}} in where_calls


@pytest.mark.asyncio
async def test_read_bytes_returns_empty_existing_file(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([_record("empty.md", 0, "ignored")])
    path = PathSpec(original="/docs/empty.md",
                    directory="/docs/empty.md",
                    prefix="/docs")
    await ensure_tree(accessor, index, "/docs")
    accessor.collection.records.clear()

    assert await read_bytes(accessor, path, index) == b""
    assert [chunk async for chunk in read_stream(accessor, path, index)] == []


@pytest.mark.asyncio
async def test_stat_file_computes_metadata(index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([
        _record("guides/quickstart.md", 1, "world"),
        _record("guides/quickstart.md", 0, "hello"),
    ])

    result = await stat(
        accessor,
        PathSpec(original="/docs/guides/quickstart.md",
                 directory="/docs/guides/quickstart.md",
                 prefix="/docs"),
        index,
    )

    assert result.name == "quickstart.md"
    assert result.type == FileType.TEXT
    assert result.size == len(b"hello\nworld")
    assert result.fingerprint is None
    assert result.revision is None
    assert result.extra["path"] == "/guides/quickstart.md"
    assert result.extra["raw_slugs"] == ["guides/quickstart.md"]
    assert result.extra["chunk_count"] == 2


@pytest.mark.asyncio
async def test_stat_directory_does_not_fetch_chunks(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([_record("guides/quickstart.md", 0, "hello")])

    result = await stat(
        accessor,
        PathSpec(original="/docs/guides",
                 directory="/docs/guides",
                 prefix="/docs"),
        index,
    )

    assert result.name == "guides"
    assert result.type == FileType.DIRECTORY
    assert result.size is None
    assert all(call["where"] is None for call in accessor.collection.calls)


@pytest.mark.asyncio
async def test_resolve_glob_expands_basename_patterns(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([
        _record("guides/quickstart.md", 0),
        _record("guides/install.txt", 0),
    ])

    result = await resolve_glob(
        accessor,
        [
            PathSpec(original="/docs/guides/*.md",
                     directory="/docs/guides",
                     pattern="*.md",
                     resolved=False,
                     prefix="/docs")
        ],
        index,
    )

    assert result == [
        PathSpec(original="/docs/guides/quickstart.md",
                 directory="/docs/guides/",
                 prefix="/docs")
    ]


@pytest.mark.asyncio
async def test_grep_paths_coarse_then_fine(index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([
        _record("guides/auth.md", 1, "full page details"),
        _record("guides/auth.md", 0, "access token overview"),
        _record("guides/billing.md", 0, "invoice setup"),
    ])

    result = await grep_paths(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        pattern="token",
        index=index,
        recursive=True,
    )

    assert result.lines == ["/docs/guides/auth.md:access token overview"]
    assert result.cache == ["/guides/auth.md"]
    assert result.reads == {
        "/guides/auth.md": b"access token overview\nfull page details"
    }
    coarse_calls = [
        call for call in accessor.collection.calls
        if call["include"] == ["metadatas"]
        and call["where_document"] == {"$contains": "token"}
    ]
    assert coarse_calls[0]["limit"] == 2
    assert coarse_calls[0]["offset"] == 0
    assert set(coarse_calls[0]["where"]["page_slug"]["$in"]) == {
        "guides/auth.md",
        "guides/billing.md",
    }
    fetch_calls = [
        call for call in accessor.collection.calls
        if call["include"] == ["documents", "metadatas"]
    ]
    assert fetch_calls[0]["where"] == {"page_slug": "guides/auth.md"}
    assert all(call["where"] == {"page_slug": "guides/auth.md"}
               for call in fetch_calls)


@pytest.mark.asyncio
async def test_grep_paths_reads_all_raw_slugs(
        index: RAMIndexCacheStore) -> None:
    accessor = FakeAccessor([
        _record("guide", 0, "token in raw guide"),
        _record("/guide/", 1, "token in slash guide"),
    ])

    result = await grep_paths(
        accessor,
        [PathSpec(original="/docs", directory="/docs", prefix="/docs")],
        pattern="token",
        index=index,
        recursive=True,
    )

    assert result.lines == [
        "/docs/guide:token in raw guide",
        "/docs/guide:token in slash guide",
    ]
    assert result.cache == ["/guide"]
    assert result.reads == {
        "/guide": b"token in raw guide\ntoken in slash guide"
    }
    assert {
        "page_slug": {
            "$in": ["guide", "/guide/"]
        }
    } in [
        call["where"] for call in accessor.collection.calls
        if call["include"] == ["documents", "metadatas"]
    ]
