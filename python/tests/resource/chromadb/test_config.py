import pytest
from pydantic import ValidationError

from mirage.resource.chromadb.config import ChromaDBConfig


def test_config_defaults_and_prefix_normalization() -> None:
    cfg = ChromaDBConfig(host="localhost",
                         port=9000,
                         prefix="api/v1/",
                         collection_name="docs")

    assert cfg.host == "localhost"
    assert cfg.port == 9000
    assert cfg.prefix == "/api/v1"
    assert cfg.ssl is False
    assert cfg.api_key is None
    assert cfg.collection_name == "docs"
    assert cfg.slug_field == "page_slug"
    assert cfg.chunk_index_field == "chunk_index"
    assert cfg.metadata_batch_size == 1000
    assert cfg.chunk_batch_size == 1000


def test_config_rejects_blank_required_fields() -> None:
    with pytest.raises(ValidationError):
        ChromaDBConfig(host="", collection_name="docs")
    with pytest.raises(ValidationError):
        ChromaDBConfig(host="localhost", collection_name="")


def test_config_accepts_empty_prefix() -> None:
    cfg = ChromaDBConfig(host="localhost", prefix="/", collection_name="docs")
    assert cfg.prefix == ""
