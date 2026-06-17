import pytest
from pydantic import SecretStr

from mirage.commands.builtin.mem0.ls import ls
from mirage.resource.mem0 import Mem0Config
from mirage.resource.mem0.mem0 import Mem0Resource
from mirage.types import PathSpec


class FakeClient:

    async def get_all(self, options=None):
        return {
            "count": 2,
            "next": None,
            "results": [{
                "id": "aaa",
                "memory": "x"
            }, {
                "id": "bbb",
                "memory": "y"
            }]
        }


def _res():
    res = Mem0Resource(Mem0Config(api_key=SecretStr("k"), user_id="alex"))
    res.accessor._client = FakeClient()
    return res


@pytest.mark.asyncio
async def test_ls_lists_memories():
    res = _res()
    p = PathSpec(original="/mem", directory="/mem", prefix="/mem")
    source, _io = await ls.__wrapped__(res.accessor, [p],
                                       index=res._index,
                                       cwd=p)
    out = b"".join([chunk async for chunk in source]) if hasattr(
        source, "__aiter__") else source
    text = out.decode()
    assert "aaa.json" in text and "bbb.json" in text
