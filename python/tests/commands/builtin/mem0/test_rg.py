import pytest
from pydantic import SecretStr

from mirage.commands.builtin.mem0.rg import rg
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
async def test_rg_recursive_by_default_matches_content():
    res = _res()
    p = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    source, _io = await rg.__wrapped__(res.accessor, [p],
                                       "bananas",
                                       index=res._index)
    out = b"".join([c async for c in source]) if hasattr(
        source, "__aiter__") else source
    assert b"bananas" in out
    assert b"sci-fi" not in out
