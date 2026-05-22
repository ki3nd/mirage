import builtins

import pytest

from mirage.accessor.chromadb import ChromaDBAccessor
from mirage.resource.chromadb import ChromaDBConfig, ChromaDBResource
from mirage.resource.registry import REGISTRY, build_resource

ORIGINAL_IMPORT = builtins.__import__


def fake_import(name, *args, **kwargs):
    if name == "chromadb":
        raise ImportError("missing chromadb")
    return ORIGINAL_IMPORT(name, *args, **kwargs)


def test_resource_name_and_remote_flag() -> None:
    res = ChromaDBResource(
        ChromaDBConfig(host="localhost", collection_name="docs"))

    assert res.name == "chromadb"
    assert res.is_remote is True


def test_resource_registers_ops_and_commands() -> None:
    res = ChromaDBResource(
        ChromaDBConfig(host="localhost", collection_name="docs"))

    assert {"read", "readdir", "stat",
            "grep"} <= {ro.name
                        for ro in res.ops_list()}
    assert {"cat", "find", "grep", "head", "ls", "tail",
            "tree"} <= {rc.name
                        for rc in res.commands()}


def test_resource_in_registry() -> None:
    assert "chromadb" in REGISTRY
    res = build_resource("chromadb",
                         config={
                             "host": "localhost",
                             "collection_name": "docs",
                         })
    assert res.name == "chromadb"


def test_resource_get_state_redacts_api_key() -> None:
    res = ChromaDBResource(
        ChromaDBConfig(host="localhost",
                       collection_name="docs",
                       api_key="secret"))

    state = res.get_state()

    assert state["type"] == "chromadb"
    assert state["needs_override"] is True
    assert state["config"]["api_key"] == "<REDACTED>"
    assert "api_key" in state["redacted_fields"]


def test_resource_load_state_noop() -> None:
    res = ChromaDBResource(
        ChromaDBConfig(host="localhost", collection_name="docs"))

    res.load_state({"type": "chromadb"})


def test_missing_chromadb_dependency_raises_clear_import_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builtins, "__import__", fake_import)
    accessor = ChromaDBAccessor(
        ChromaDBConfig(host="localhost", collection_name="docs"))

    with pytest.raises(ImportError, match="mirage-ai\\[chromadb\\]"):
        _ = accessor.client
