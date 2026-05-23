from types import SimpleNamespace

import pytest

from mirage.cache.index import RAMIndexCacheStore
from mirage.types import FileType, PathSpec


def document(
    document_id: str,
    name: str,
    *,
    slug: object | None = None,
    enabled: bool = True,
    indexing_status: str = "completed",
    archived: bool = False,
    size: int | None = 123,
) -> dict:
    doc_metadata = []
    if slug is not None:
        doc_metadata = [{"name": "slug", "value": slug}]
    data_source_detail_dict = {}
    if size is not None:
        data_source_detail_dict = {"upload_file": {"size": size}}
    return {
        "id": document_id,
        "name": name,
        "doc_metadata": doc_metadata,
        "enabled": enabled,
        "indexing_status": indexing_status,
        "archived": archived,
        "tokens": 9,
        "data_source_type": "upload_file",
        "data_source_detail_dict": data_source_detail_dict,
        "created_at": 1716282000,
    }


def accessor() -> SimpleNamespace:
    return SimpleNamespace(config=SimpleNamespace())


@pytest.mark.asyncio
async def test_tree_builds_prefixed_entries_and_uses_api_size(monkeypatch, ):
    from mirage.core.dify import tree
    from mirage.core.dify.readdir import readdir

    calls = {"documents": 0}

    async def list_documents(config):
        calls["documents"] += 1
        return [
            document("doc-1", "Quickstart", slug="guides/quickstart",
                     size=333),
            document("doc-2", "API", slug="api", size=444, archived=True),
            document("doc-3",
                     "Draft",
                     slug="draft",
                     indexing_status="indexing"),
            document("doc-4", "Disabled", slug="disabled", enabled=False),
            document("doc-5", "Archived", slug="archived", archived=True),
            document("doc-6", "README.md", size=None),
        ]

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    index = RAMIndexCacheStore()

    await tree.ensure_tree(accessor(), index, "/knowledge/")

    root = await index.list_dir("/knowledge")
    guides = await index.list_dir("/knowledge/guides")
    quickstart = await index.get("/knowledge/guides/quickstart")
    readme = await index.get("/knowledge/README.md")

    assert root.entries == ["/knowledge/README.md", "/knowledge/guides"]
    assert guides.entries == ["/knowledge/guides/quickstart"]
    assert quickstart.entry.id == "doc-1"
    assert quickstart.entry.size == 333
    assert quickstart.entry.extra["slug"] == "guides/quickstart"
    assert quickstart.entry.extra["raw_slug"] == "guides/quickstart"
    assert quickstart.entry.extra["has_slug"] is True
    assert readme.entry.id == "doc-6"
    assert readme.entry.size is None
    assert readme.entry.extra["raw_slug"] == "README.md"
    assert readme.entry.extra["has_slug"] is False

    children = await readdir(
        accessor(),
        PathSpec(original="/knowledge",
                 directory="/knowledge",
                 prefix="/knowledge/"),
        index,
    )
    assert children == ["/knowledge/README.md", "/knowledge/guides"]

    await tree.ensure_tree(accessor(), index, "/knowledge/")
    assert calls["documents"] == 1


@pytest.mark.asyncio
async def test_ensure_tree_rejects_duplicate_and_path_collision(monkeypatch):
    from mirage.core.dify import tree

    async def duplicates(config):
        return [
            document("doc-1", "one", slug="same"),
            document("doc-2", "two", slug="same"),
        ]

    monkeypatch.setattr(tree, "list_all_documents", duplicates)
    with pytest.raises(ValueError, match="Duplicate slug 'same'"):
        await tree.ensure_tree(accessor(), RAMIndexCacheStore(), "")

    async def collisions(config):
        return [
            document("doc-1", "foo", slug="foo"),
            document("doc-2", "bar", slug="foo/bar"),
        ]

    monkeypatch.setattr(tree, "list_all_documents", collisions)
    with pytest.raises(ValueError, match="Path collision"):
        await tree.ensure_tree(accessor(), RAMIndexCacheStore(), "")


@pytest.mark.asyncio
async def test_read_and_stat_use_segments_and_document_api_size(monkeypatch, ):
    from mirage.core.dify import read, stat, tree

    segment_calls = {"count": 0}

    async def list_documents(config):
        return [
            document("doc-1", "Quickstart", slug="guides/quickstart", size=111)
        ]

    async def get_segments(config, document_id):
        segment_calls["count"] += 1
        return [{"content": "first"}, {"content": "second"}]

    async def get_detail(config, document_id):
        return {
            "id": document_id,
            "name": "Quickstart",
            "updated_at": 1716285600,
            "data_source_info": {
                "upload_file": {
                    "size": 999
                }
            },
            "tokens": 7,
            "indexing_status": "completed",
        }

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    monkeypatch.setattr(read, "get_document_segments", get_segments)
    monkeypatch.setattr(stat, "get_document_detail", get_detail)

    index = RAMIndexCacheStore()
    path = PathSpec(
        original="/knowledge/guides/quickstart",
        directory="/knowledge/guides/quickstart",
        prefix="/knowledge/",
    )

    data = await read.read_bytes(accessor(), path, index)
    assert data == b"first\nsecond"
    assert segment_calls["count"] == 1

    item = await stat.stat(accessor(), path, index)
    assert item.name == "quickstart"
    assert item.type == FileType.TEXT
    assert item.size == 999
    assert item.modified == "2024-05-21T10:00:00Z"
    assert item.extra["document_id"] == "doc-1"
    assert segment_calls["count"] == 1
