import pytest
from pydantic import SecretStr

from mirage.resource.mem0 import Mem0Config
from mirage.resource.mem0.mem0 import Mem0Resource
from mirage.types import ResourceName


def test_resource_basic():
    cfg = Mem0Config(api_key=SecretStr("secret"), user_id="alex")
    res = Mem0Resource(cfg)
    assert res.name == ResourceName.MEM0
    assert res.caches_reads is True
    assert res.SUPPORTS_SNAPSHOT is False


def test_get_state_redacts_api_key():
    cfg = Mem0Config(api_key=SecretStr("secret"), user_id="alex")
    res = Mem0Resource(cfg)
    state = res.get_state()
    assert state["type"] == ResourceName.MEM0
    assert "secret" not in str(state)


@pytest.mark.asyncio
async def test_fingerprint_none():
    cfg = Mem0Config(api_key=SecretStr("secret"), user_id="alex")
    res = Mem0Resource(cfg)
    assert await res.fingerprint("/mem/aaa.json") is None
