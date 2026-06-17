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

from mirage.accessor.mem0 import Mem0Accessor
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.mem0.search import search_memories_rendered
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec


@command("search", resource="mem0", spec=SPECS["search"])
async def search(
    accessor: Mem0Accessor,
    paths: list[PathSpec],
    *texts: str,
    top_k: str | int | None = None,
    threshold: str | float = 0.0,
    index=None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    if not texts:
        raise ValueError("search: query is required")
    query = texts[0]
    limit = (int(top_k)
             if top_k is not None else accessor.config.default_search_limit)
    prefix = ""
    if paths:
        p0 = paths[0]
        prefix = p0.prefix if isinstance(p0, PathSpec) else ""
    output = await search_memories_rendered(
        accessor,
        query,
        prefix=prefix,
        top_k=limit,
        threshold=float(threshold),
    )
    return output, IOResult()
