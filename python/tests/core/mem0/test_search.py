import pytest
from pydantic import SecretStr

from mirage.accessor.mem0 import Mem0Accessor
from mirage.core.mem0.search import search_memories_rendered
from mirage.resource.mem0.config import Mem0Config


class FakeClient:

    def __init__(self):
        self.calls = []

    async def search(self, query, options=None):
        self.calls.append((query, options.model_dump(exclude_unset=True)))
        return {
            "results": [
                {
                    "id": "aaa",
                    "memory": "eats banana",
                    "score": 0.91
                },
                {
                    "id": "bbb",
                    "memory": "likes sci-fi",
                    "score": 0.70
                },
            ]
        }


def _accessor():
    cfg = Mem0Config(api_key=SecretStr("k"), agent_id="routine_agent")
    acc = Mem0Accessor(cfg)
    acc._client = FakeClient()
    return acc


@pytest.mark.asyncio
async def test_search_renders_ranked():
    acc = _accessor()
    out = await search_memories_rendered(acc,
                                         "morning",
                                         prefix="/mem",
                                         top_k=5,
                                         threshold=0.0)
    text = out.decode()
    assert "/mem/aaa.json:0.91" in text
    assert "eats banana" in text
    assert acc._client.calls[0][1]["filters"] == {"agent_id": "routine_agent"}
    assert acc._client.calls[0][1]["top_k"] == 5


@pytest.mark.asyncio
async def test_search_empty():
    acc = _accessor()

    async def _empty(query, options=None):
        return {"results": []}

    acc._client.search = _empty
    out = await search_memories_rendered(acc,
                                         "nope",
                                         prefix="/mem",
                                         top_k=5,
                                         threshold=0.0)
    assert out == b""
