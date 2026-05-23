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
    from mirage.core.dify import read, stat, tree

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

    async def get_detail(config, document_id):
        if document_id == "doc-1":
            return {
                "id": document_id,
                "updated_at": 1716285600,
                "data_source_info": {
                    "upload_file": {
                        "size": 17
                    }
                },
                "tokens": 4,
                "indexing_status": "completed",
            }
        return {
            "id": document_id,
            "updated_at": 1716285601,
            "data_source_info": {
                "upload_file": {
                    "size": 6
                }
            },
            "tokens": 4,
            "indexing_status": "completed",
        }

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    monkeypatch.setattr(read, "get_document_segments", get_segments)
    monkeypatch.setattr(read, "iter_segment_pages", iter_pages)
    monkeypatch.setattr(stat, "get_document_detail", get_detail)
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
    assert await materialize(grep_stdout) == b"gamma\n"
    assert grep_io.exit_code == 0

    find_stdout, _ = await find(acc, [root], "quick*.md", index=index)
    assert await materialize(find_stdout) == b"/knowledge/guides/quickstart.md"

    head_stdout, _ = await head(acc, [guide], index=index, n=2)
    assert await materialize(head_stdout) == b"alpha\nbeta\n"

    tail_stdout, _ = await tail(acc, [guide], index=index, n=1)
    assert await materialize(tail_stdout) == b"gamma"

    wc_stdout, wc_io = await wc(acc, [guide], index=index)
    assert await materialize(wc_stdout
                             ) == b"3\t3\t17\t/knowledge/guides/quickstart.md"
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
    assert await materialize(grep_stdout) == b"gamma\n"
    assert guide.original not in grep_io.reads


@pytest.mark.asyncio
async def test_head_tail_support_byte_counts(monkeypatch):
    from mirage.commands.builtin.dify.head import head
    from mirage.commands.builtin.dify.tail import tail
    from mirage.core.dify import read, tree

    async def list_documents(config):
        return [document("doc-1", "Guide", "guides/quickstart.md")]

    async def iter_pages(config, document_id):
        yield [{"content": "abcdef"}]

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    monkeypatch.setattr(read, "iter_segment_pages", iter_pages)
    index = RAMIndexCacheStore()
    acc = accessor()
    guide = PathSpec(
        original="/knowledge/guides/quickstart.md",
        directory="/knowledge/guides/quickstart.md",
        prefix="/knowledge/",
    )

    head_stdout, _ = await head(acc, [guide], c="3", index=index)
    assert await materialize(head_stdout) == b"abc"

    tail_stdout, _ = await tail(acc, [guide], c="2", index=index)
    assert await materialize(tail_stdout) == b"ef"


@pytest.mark.asyncio
async def test_ls_uses_cwd_and_supports_list_dir(monkeypatch):
    from mirage.commands.builtin.dify.ls import ls
    from mirage.core.dify import stat, tree

    async def list_documents(config):
        return [
            document("doc-1", "Guide", "guides/quickstart.md"),
            document("doc-2", "Readme", "README.md"),
        ]

    async def get_detail(config, document_id):
        return {
            "id": document_id,
            "updated_at": 1716285600,
            "data_source_info": {
                "upload_file": {
                    "size": 12
                }
            },
            "tokens": 4,
            "indexing_status": "completed",
        }

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    monkeypatch.setattr(stat, "get_document_detail", get_detail)
    index = RAMIndexCacheStore()
    acc = accessor()
    guides = PathSpec(
        original="/knowledge/guides",
        directory="/knowledge/guides",
        prefix="/knowledge/",
    )

    cwd_stdout, cwd_io = await ls(acc, [], index=index, cwd=guides)
    assert await materialize(cwd_stdout) == b"quickstart.md"
    assert cwd_io.exit_code == 0

    dir_stdout, dir_io = await ls(acc, [guides], d=True, index=index)
    assert await materialize(dir_stdout) == b"guides"
    assert dir_io.exit_code == 0


@pytest.mark.asyncio
async def test_wc_supports_chars_and_max_line_length(monkeypatch):
    from mirage.commands.builtin.dify.wc import wc
    from mirage.core.dify import read, tree

    async def list_documents(config):
        return [document("doc-1", "Guide", "guides/quickstart.md")]

    async def get_segments(config, document_id):
        return [{"content": "xin\nchaoo\nbanh mi"}]

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    monkeypatch.setattr(read, "get_document_segments", get_segments)
    index = RAMIndexCacheStore()
    acc = accessor()
    guide = PathSpec(
        original="/knowledge/guides/quickstart.md",
        directory="/knowledge/guides/quickstart.md",
        prefix="/knowledge/",
    )

    chars_stdout, _ = await wc(acc, [guide], m=True, index=index)
    assert await materialize(chars_stdout) == b"17\t/knowledge/guides/quickstart.md"

    max_line_stdout, _ = await wc(acc, [guide], L=True, index=index)
    assert await materialize(max_line_stdout) == b"7\t/knowledge/guides/quickstart.md"


@pytest.mark.asyncio
async def test_grep_supports_standard_flags(monkeypatch):
    from mirage.commands.builtin.dify.grep import grep
    from mirage.core.dify import read, tree

    async def list_documents(config):
        return [document("doc-1", "Guide", "guides/quickstart.md")]

    async def iter_pages(config, document_id):
        yield [{"content": "alpha beta"}]
        yield [{"content": "gamma alpha"}]

    async def get_segments(config, document_id):
        return [{"content": "alpha beta"}, {"content": "gamma alpha"}]

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    monkeypatch.setattr(read, "iter_segment_pages", iter_pages)
    monkeypatch.setattr(read, "get_document_segments", get_segments)
    index = RAMIndexCacheStore()
    acc = accessor()
    guide = PathSpec(
        original="/knowledge/guides/quickstart.md",
        directory="/knowledge/guides/quickstart.md",
        prefix="/knowledge/",
    )

    plain_stdout, plain_io = await grep(acc, [guide], "alpha", index=index)
    assert await materialize(plain_stdout) == b"alpha beta\ngamma alpha\n"
    assert plain_io.exit_code == 0

    numbered_stdout, _ = await grep(acc, [guide], "alpha", n=True, index=index)
    assert await materialize(numbered_stdout) == b"1:alpha beta\n3:gamma alpha\n"

    count_stdout, _ = await grep(acc, [guide], "alpha", c=True, index=index)
    assert await materialize(count_stdout) == b"2\n"

    files_stdout, _ = await grep(acc, [guide], "alpha", args_l=True, index=index)
    assert await materialize(files_stdout) == b"/knowledge/guides/quickstart.md"

    fixed_stdout, _ = await grep(acc, [guide], "alpha beta", F=True, index=index)
    assert await materialize(fixed_stdout) == b"alpha beta\n"

    word_stdout, _ = await grep(acc, [guide], "alph", w=True, index=index)
    assert await materialize(word_stdout) == b""

    quiet_stdout, quiet_io = await grep(acc, [guide], "alpha", q=True, index=index)
    assert quiet_stdout is not None
    assert await materialize(quiet_stdout) == b""
    assert quiet_io.exit_code == 0


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


@pytest.mark.asyncio
async def test_find_uses_cwd_when_path_missing(monkeypatch):
    from mirage.commands.builtin.dify.find import find
    from mirage.core.dify import tree

    async def list_documents(config):
        return [
            document("doc-1", "Guide", "guides/quickstart.md"),
            document("doc-2", "Guide 2", "guides/deep/note.md"),
            document("doc-3", "Readme", "README.md"),
        ]

    monkeypatch.setattr(tree, "list_all_documents", list_documents)
    index = RAMIndexCacheStore()
    acc = accessor()
    guides = PathSpec(
        original="/knowledge/guides",
        directory="/knowledge/guides",
        prefix="/knowledge/",
    )

    stdout, io = await find(acc, [], "quick*.md", cwd=guides, index=index)

    assert await materialize(stdout) == b"/knowledge/guides/quickstart.md"
    assert io.exit_code == 0
