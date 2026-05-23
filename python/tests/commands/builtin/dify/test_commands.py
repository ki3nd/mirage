from types import SimpleNamespace

import pytest

from mirage.cache.index import RAMIndexCacheStore
from mirage.io.types import materialize
from mirage.types import PathSpec


def document(document_id: str, name: str, slug: str, size: int = 12) -> dict:
    return {
        "id": document_id,
        "name": name,
        "doc_metadata": [{
            "name": "slug",
            "value": slug
        }],
        "enabled": True,
        "indexing_status": "completed",
        "archived": False,
        "tokens": 4,
        "data_source_type": "upload_file",
        "data_source_detail_dict": {
            "upload_file": {
                "size": size
            }
        },
        "created_at": 1716282000,
    }


def accessor() -> SimpleNamespace:
    return SimpleNamespace(config=SimpleNamespace())


@pytest.mark.asyncio
async def test_ls_cat_grep_find_head_tail_wc_commands(monkeypatch):
    from mirage.commands.builtin.dify.cat import cat
    from mirage.commands.builtin.dify.find import find
    from mirage.commands.builtin.dify.grep import grep
    from mirage.commands.builtin.dify.head import head
    from mirage.commands.builtin.dify.ls import ls
    from mirage.commands.builtin.dify.tail import tail
    from mirage.commands.builtin.dify.wc import wc
    from mirage.core.dify import read, tree

    async def list_documents(config):
        return [
            document("doc-1", "Guide", "guides/quickstart.md"),
            document("doc-2", "Readme", "README.md"),
        ]

    async def get_segments(config, document_id):
        if document_id == "doc-1":
            return [{"content": "alpha\nbeta"}, {"content": "gamma"}]
        return [{"content": "readme"}]

    async def iter_pages(config, document_id):
        if document_id == "doc-1":
            yield [{"content": "alpha\nbeta"}, {"content": "gamma"}]
        else:
            yield [{"content": "readme"}]

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    monkeypatch.setattr(read, "get_document_segments", get_segments)
    monkeypatch.setattr(read, "iter_segment_pages", iter_pages)
    index = RAMIndexCacheStore()
    acc = accessor()

    root = PathSpec(original="/knowledge",
                    directory="/knowledge",
                    prefix="/knowledge/")
    guide = PathSpec(
        original="/knowledge/guides/quickstart.md",
        directory="/knowledge/guides/quickstart.md",
        prefix="/knowledge/",
    )

    ls_stdout, _ = await ls(acc, [root], index=index)
    assert await materialize(ls_stdout) == b"README.md\nguides"

    cat_stdout, cat_io = await cat(acc, [guide], index=index)
    assert await materialize(cat_stdout) == b"alpha\nbeta\n\ngamma"
    assert guide.original in cat_io.reads
    assert cat_io.cache == [guide.original]

    grep_stdout, grep_io = await grep(acc, [guide], "gamma", index=index)
    assert await materialize(grep_stdout
                             ) == b"/knowledge/guides/quickstart.md:4:gamma"
    assert grep_io.exit_code == 0

    find_stdout, _ = await find(acc, [root], "quick*.md", index=index)
    assert await materialize(find_stdout) == b"/knowledge/guides/quickstart.md"

    head_stdout, _ = await head(acc, [guide], index=index, n=2)
    assert await materialize(head_stdout) == b"alpha\nbeta\n"

    tail_stdout, _ = await tail(acc, [guide], index=index, n=1)
    assert await materialize(tail_stdout) == b"gamma"

    wc_stdout, wc_io = await wc(acc, [guide], index=index)
    assert await materialize(wc_stdout
                             ) == b"4 3 17 /knowledge/guides/quickstart.md"
    assert wc_io.cache == [guide.original]


@pytest.mark.asyncio
async def test_head_tail_grep_use_read_stream(monkeypatch):
    from mirage.commands.builtin.dify.grep import grep
    from mirage.commands.builtin.dify.head import head
    from mirage.commands.builtin.dify.tail import tail
    from mirage.core.dify import read, tree

    async def list_documents(config):
        return [document("doc-1", "Guide", "guides/quickstart.md")]

    async def get_segments(config, document_id):
        raise AssertionError("read_bytes should not be used")

    async def iter_pages(config, document_id):
        yield [{"content": "alpha\nbeta"}]
        yield [{"content": "gamma"}]

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    monkeypatch.setattr(read, "get_document_segments", get_segments)
    monkeypatch.setattr(read, "iter_segment_pages", iter_pages)
    index = RAMIndexCacheStore()
    acc = accessor()
    guide = PathSpec(
        original="/knowledge/guides/quickstart.md",
        directory="/knowledge/guides/quickstart.md",
        prefix="/knowledge/",
    )

    head_stdout, _ = await head(acc, [guide], index=index, n=2)
    assert await materialize(head_stdout) == b"alpha\nbeta\n"

    tail_stdout, _ = await tail(acc, [guide], index=index, n=2)
    assert await materialize(tail_stdout) == b"\ngamma"

    grep_stdout, grep_io = await grep(acc, [guide], "gamma", index=index)
    assert await materialize(grep_stdout
                             ) == b"/knowledge/guides/quickstart.md:4:gamma"
    assert grep_io.reads[guide.original] == b"alpha\nbeta\n\ngamma"


@pytest.mark.asyncio
async def test_find_handles_file_missing_and_maxdepth(monkeypatch):
    from mirage.commands.builtin.dify.find import find
    from mirage.core.dify import tree

    async def list_documents(config):
        return [
            document("doc-1", "Guide", "guides/quickstart.md"),
            document("doc-2", "Readme", "README.md"),
        ]

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    index = RAMIndexCacheStore()
    acc = accessor()
    root = PathSpec(original="/knowledge",
                    directory="/knowledge",
                    prefix="/knowledge/")
    guide = PathSpec(
        original="/knowledge/guides/quickstart.md",
        directory="/knowledge/guides/quickstart.md",
        prefix="/knowledge/",
    )

    file_stdout, file_io = await find(acc, [guide], index=index)
    assert await materialize(file_stdout) == b"/knowledge/guides/quickstart.md"
    assert file_io.exit_code == 0

    maxdepth_stdout, maxdepth_io = await find(acc, [root],
                                              maxdepth="0",
                                              index=index)
    assert await materialize(maxdepth_stdout) == b"/knowledge"
    assert maxdepth_io.exit_code == 0

    missing = PathSpec(
        original="/knowledge/missing.md",
        directory="/knowledge/missing.md",
        prefix="/knowledge/",
    )
    missing_stdout, missing_io = await find(acc, [missing], index=index)
    assert await materialize(missing_stdout) == b""
    assert missing_io.stderr is not None
    assert b"/knowledge/missing.md" in missing_io.stderr
    assert missing_io.exit_code == 1
