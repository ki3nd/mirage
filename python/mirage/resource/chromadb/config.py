from pydantic import BaseModel, Field, field_validator


class ChromaDBConfig(BaseModel):
    host: str
    port: int = Field(default=8000, ge=1, le=65535)
    prefix: str = ""
    ssl: bool = False
    api_key: str | None = None
    collection_name: str

    slug_field: str = "page_slug"
    chunk_index_field: str = "chunk_index"
    metadata_batch_size: int = Field(default=1000, ge=1)
    chunk_batch_size: int = Field(default=1000, ge=1)

    @field_validator("host", "collection_name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("prefix")
    @classmethod
    def _normalize_prefix(cls, value: str) -> str:
        parts = [part for part in value.strip("/").split("/") if part]
        if not parts:
            return ""
        return "/" + "/".join(parts)
