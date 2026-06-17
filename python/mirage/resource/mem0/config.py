# ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========

from pydantic import BaseModel, SecretStr, model_validator


class Mem0Config(BaseModel):
    api_key: SecretStr
    host: str = "https://api.mem0.ai"
    user_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    default_page_size: int = 100
    default_search_limit: int = 10

    @model_validator(mode="after")
    def _exactly_one_entity(self) -> "Mem0Config":
        present = [
            k for k in ("user_id", "agent_id", "run_id")
            if getattr(self, k) is not None
        ]
        if len(present) != 1:
            raise ValueError(
                "Mem0Config requires exactly one of "
                f"user_id, agent_id, run_id; got {present or 'none'}")
        return self

    @property
    def scope_kind(self) -> str:
        for kind in ("user", "agent", "run"):
            if getattr(self, f"{kind}_id") is not None:
                return kind
        raise ValueError("no scope set")

    @property
    def scope_filter(self) -> dict[str, str]:
        key = f"{self.scope_kind}_id"
        return {key: getattr(self, key)}
