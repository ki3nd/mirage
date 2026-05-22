from pydantic import BaseModel, ConfigDict, field_validator


class DifyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key: str
    base_url: str
    dataset_id: str

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        return value.rstrip("/")
