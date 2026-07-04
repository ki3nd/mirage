import json

import pytest
from pydantic import SecretStr

from mirage.commands.builtin.mem0.cat import cat
from mirage.resource.mem0 import Mem0Config
from mirage.resource.mem0.mem0 import Mem0Resource
from mirage.types import PathSpec


class FakeClient:

    async def get_all(self, options=None):
        return {
            "count": 1,
            "next": None,
            "results": [{
                "id": "aaa",
                "memory": "loves bananas"
            }]
        }

    async def get(self, memory_id):
        return {"id": memory_id, "memory": "loves bananas"}


def _res():
    res = Mem0Resource(Mem0Config(api_key=SecretStr("k"), user_id="alex"))
    res.accessor._client = FakeClient()
    return res


@pytest.mark.asyncio
async def test_cat_returns_full_json():
    res = _res()
    p = PathSpec(virtual="/mem/aaa.json",
                 directory="/mem",
                 resource_path="aaa.json",
                 resolved=True)
    out, _io = await cat.__wrapped__(res.accessor, [p], index=res._index)
    data = json.loads(out)
    assert data["memory"] == "loves bananas"
