from collections.abc import Iterable

import pytest

from mirage.cache.index.ram import RAMIndexCacheStore
from mirage.resource.chromadb.config import ChromaDBConfig
from mirage.types import PathSpec


class FakeCollection:

    def __init__(self, records: Iterable[dict]) -> None:
        self.records = list(records)

    def query(
        self,
        query_texts: list[str],
        n_results: int,
        where: dict | None = None,
        include: list[str] | None = None,
    ) -> dict:
        documents = [record["document"] for record in self.records][:n_results]
        return {"documents": [documents], "distances": [[0.0] * len(documents)]}

    def get(
        self,
        include: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        where: dict | None = None,
        where_document: dict | None = None,
    ) -> dict:
        page = self.records[offset:offset + limit if limit is not None else None]
        result: dict[str, list] = {}
        if include is None or "metadatas" in include:
            result["metadatas"] = [record["metadata"] for record in page]
        if include is None or "documents" in include:
            result["documents"] = [record["document"] for record in page]
        return result


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


@pytest.mark.asyncio
async def test_search_op_delegates_to_core() -> None:
    from mirage.ops.chromadb.search import search as search_op

    accessor = FakeAccessor([_record("guides/a.md", 0, "result")])
    result = await search_op(accessor,
                             [PathSpec(original="/docs", directory="/docs",
                                       prefix="/docs")],
                             "query",
                             index=RAMIndexCacheStore(),
                             method="semantic")

    assert result == b"result"
