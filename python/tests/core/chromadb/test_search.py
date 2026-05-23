import re
from collections.abc import Iterable

import pytest

from mirage.cache.index.ram import RAMIndexCacheStore
from mirage.resource.chromadb.config import ChromaDBConfig
from mirage.types import PathSpec


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
            "kind": "get",
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
            result["metadatas"] = [record.get("metadata", {}) for record in page]
        if include is None or "documents" in include:
            result["documents"] = [record.get("document") for record in page]
        return result

    def query(
        self,
        query_texts: list[str],
        n_results: int,
        where: dict | None = None,
        include: list[str] | None = None,
    ) -> dict:
        query = query_texts[0].lower()
        self.calls.append({
            "kind": "query",
            "query_texts": query_texts,
            "n_results": n_results,
            "where": where,
            "include": include,
        })
        records = self._filter_records(where, None)
        scored = sorted(records,
                        key=lambda record:
                        (0 if query in str(record.get("document", "")).lower()
                         else 1, str(record.get("document", ""))))
        page = scored[:n_results]
        documents = [record.get("document") for record in page]
        distances = [
            0.0 if query in str(record.get("document", "")).lower() else 1.0
            for record in page
        ]
        return {"documents": [documents], "distances": [distances]}

    def _filter_records(
        self,
        where: dict | None,
        where_document: dict | None,
    ) -> list[dict]:
        records = self.records
        if where_document is not None:
            records = [
                record for record in records
                if _document_matches(record.get("document"), where_document)
            ]
        if where is None:
            return records
        value = where["page_slug"]
        if isinstance(value, dict):
            allowed = set(value["$in"])
            return [
                record for record in records
                if record["metadata"]["page_slug"] in allowed
            ]
        return [
            record for record in records
            if record["metadata"]["page_slug"] == value
        ]


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


def _document_matches(document: object, where_document: dict) -> bool:
    text = "" if document is None else str(document)
    if "$contains" in where_document:
        return str(where_document["$contains"]) in text
    if "$regex" in where_document:
        return re.search(str(where_document["$regex"]), text) is not None
    return True


@pytest.mark.asyncio
async def test_search_segments_scopes_keyword_search_to_directory() -> None:
    from mirage.core.chromadb.search import search_segments

    accessor = FakeAccessor([
        _record("guides/quickstart.md", 0, "setup line1"),
        _record("guides/quickstart.md", 1, "setup line2"),
        _record("readme.md", 0, "setup readme"),
    ])

    result = await search_segments(
        accessor,
        "setup",
        [PathSpec(original="/docs/guides",
                  directory="/docs/guides",
                  prefix="/docs")],
        RAMIndexCacheStore(),
        method="keyword",
    )

    assert result == b"setup line1\nsetup line2"
    keyword_call = [
        call for call in accessor.collection.calls if call["kind"] == "get"
    ][-1]
    assert keyword_call["where"] == {"page_slug": "guides/quickstart.md"}


@pytest.mark.asyncio
async def test_search_segments_uses_query_for_semantic_search() -> None:
    from mirage.core.chromadb.search import search_segments

    accessor = FakeAccessor([
        _record("guides/quickstart.md", 0, "oauth token"),
        _record("readme.md", 0, "readme"),
    ])

    result = await search_segments(accessor, "oauth", [], RAMIndexCacheStore(),
                                   method="semantic", top_k=2)

    assert result == b"oauth token\nreadme"
    query_call = [call for call in accessor.collection.calls
                  if call["kind"] == "query"][-1]
    assert query_call["query_texts"] == ["oauth"]
    assert query_call["n_results"] == 2


@pytest.mark.asyncio
async def test_search_segments_hybrid_merges_unique_matches() -> None:
    from mirage.core.chromadb.search import search_segments

    accessor = FakeAccessor([
        _record("guides/quickstart.md", 0, "oauth token"),
        _record("guides/advanced.md", 0, "oauth flows"),
    ])

    result = await search_segments(accessor, "oauth", [], RAMIndexCacheStore(),
                                   method="hybrid", top_k=3)

    assert result == b"oauth flows\noauth token"


@pytest.mark.asyncio
async def test_search_segments_validates_arguments() -> None:
    from mirage.core.chromadb.search import search_segments

    accessor = FakeAccessor([])
    index = RAMIndexCacheStore()

    with pytest.raises(ValueError, match="search: query is required"):
        await search_segments(accessor, "", [], index)
    with pytest.raises(ValueError, match="search: top-k must be positive"):
        await search_segments(accessor, "x", [], index, top_k=0)
    with pytest.raises(ValueError, match="search: threshold must be"):
        await search_segments(accessor, "x", [], index, threshold=-1)
    with pytest.raises(ValueError, match="search: method must be one of"):
        await search_segments(accessor, "x", [], index, method="bad")
