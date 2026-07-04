import pytest
from pydantic import SecretStr

from mirage.commands.builtin.mem0.grep import grep
from mirage.resource.mem0 import Mem0Config
from mirage.resource.mem0.mem0 import Mem0Resource
from mirage.types import PathSpec


class FakeClient:

    async def get_all(self, options=None):
        return {
            "count":
            2,
            "next":
            None,
            "results": [
                {
                    "id": "aaa",
                    "memory": "loves bananas",
                    "categories": ["food"]
                },
                {
                    "id": "bbb",
                    "memory": "likes sci-fi",
                    "categories": ["movies"]
                },
            ]
        }


def _res():
    res = Mem0Resource(Mem0Config(api_key=SecretStr("k"), user_id="alex"))
    res.accessor._client = FakeClient()
    return res


@pytest.mark.asyncio
async def test_grep_recursive_matches_content():
    res = _res()
    p = PathSpec(virtual="/mem", directory="/mem", resource_path="")
    source, _io = await grep.__wrapped__(res.accessor, [p],
                                         "bananas",
                                         r=True,
                                         index=res._index)
    out = b"".join([c async for c in source]) if hasattr(
        source, "__aiter__") else source
    assert b"bananas" in out


@pytest.mark.asyncio
async def test_grep_ignores_metadata():
    res = _res()
    p = PathSpec(virtual="/mem", directory="/mem", resource_path="")
    source, _io = await grep.__wrapped__(res.accessor, [p],
                                         "food",
                                         r=True,
                                         index=res._index)
    out = b"".join([c async for c in source]) if hasattr(
        source, "__aiter__") else source
    assert out in (b"", None) or b"food" not in out


@pytest.mark.asyncio
async def test_grep_bare_directory_is_a_directory():
    res = _res()
    p = PathSpec(virtual="/mem", directory="/mem", resource_path="")
    source, io = await grep.__wrapped__(res.accessor, [p],
                                        "bananas",
                                        index=res._index)
    assert io.exit_code == 1
    assert b"Is a directory" in (io.stderr or b"")
