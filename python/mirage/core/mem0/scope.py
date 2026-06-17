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

from dataclasses import dataclass

from mirage.types import PathSpec


@dataclass
class Mem0Scope:
    level: str
    memory_id: str | None = None


def _backend_key(path: PathSpec) -> str:
    raw = path.original
    prefix = path.prefix
    if prefix and raw.startswith(prefix):
        rest = raw[len(prefix):]
        if prefix.endswith("/") or rest == "" or rest.startswith("/"):
            raw = rest or "/"
    return raw.strip("/")


def detect(path: PathSpec) -> Mem0Scope:
    """Classify a mem0 virtual path.

    Args:
        path (PathSpec): the virtual path to classify.
    """
    key = _backend_key(path)
    if not key:
        return Mem0Scope(level="root")
    parts = key.split("/")
    if any(p.startswith(".") for p in parts):
        return Mem0Scope(level="invalid")
    if len(parts) == 1 and parts[0].endswith(".json"):
        return Mem0Scope(level="memory", memory_id=parts[0][:-len(".json")])
    return Mem0Scope(level="invalid")
