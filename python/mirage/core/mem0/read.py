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

import json
from collections.abc import AsyncIterator

from mirage.accessor.mem0 import Mem0Accessor
from mirage.cache.index import IndexCacheStore
from mirage.core.mem0._client import get_memory
from mirage.core.mem0.scope import detect
from mirage.types import PathSpec
from mirage.utils.errors import enoent


def _json_bytes(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode()


async def _resolve_memory(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore | None,
) -> dict:
    if isinstance(path, str):
        path = PathSpec(original=path, directory=path)
    scope = detect(path)
    if scope.level != "memory":
        raise enoent(path.original)
    if index is not None:
        lookup = await index.get(path.original)
        if lookup.entry is not None and lookup.entry.extra.get("memory"):
            return lookup.entry.extra["memory"]
    return await get_memory(accessor.client, scope.memory_id)


async def read(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore = None,
) -> bytes:
    """Read a memory as full JSON bytes.

    Args:
        accessor (Mem0Accessor): mem0 accessor.
        path (PathSpec): the memory file path.
        index (IndexCacheStore | None): index cache.
    """
    memory = await _resolve_memory(accessor, path, index)
    return _json_bytes(memory)


async def read_stream(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore = None,
) -> AsyncIterator[bytes]:
    """Stream a memory as full JSON bytes (used by jq).

    Args:
        accessor (Mem0Accessor): mem0 accessor.
        path (PathSpec): the memory file path.
        index (IndexCacheStore | None): index cache.
    """
    memory = await _resolve_memory(accessor, path, index)
    yield _json_bytes(memory)


async def read_content(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore = None,
) -> bytes:
    """Read only the memory text (used by grep/rg).

    Args:
        accessor (Mem0Accessor): mem0 accessor.
        path (PathSpec): the memory file path.
        index (IndexCacheStore | None): index cache.
    """
    memory = await _resolve_memory(accessor, path, index)
    text = memory.get("memory", "")
    return (text + "\n").encode()


async def read_content_stream(
    accessor: Mem0Accessor,
    path: PathSpec,
    index: IndexCacheStore = None,
) -> AsyncIterator[bytes]:
    """Stream the memory text (used by grep/rg single-file path).

    Args:
        accessor (Mem0Accessor): mem0 accessor.
        path (PathSpec): the memory file path.
        index (IndexCacheStore | None): index cache.
    """
    yield await read_content(accessor, path, index)
